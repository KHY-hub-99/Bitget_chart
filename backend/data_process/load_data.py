import requests
import pandas as pd
import numpy as np
import sqlite3
import os
import time
from datetime import datetime
from data_process.pine_data import apply_master_strategy

class CryptoDataFeed:
    def __init__(self, symbol="BTCUSDT", timeframe="15m"):
        # CCXT 제거 후 바이낸스 선물 직접 연결
        self.symbol = symbol  # 바이낸스는 빗금 없이 BTCUSDT 형식 사용
        self.timeframe = timeframe
        self.base_url = "https://fapi.binance.com"
        self.df = pd.DataFrame()
        
        # 1. 경로 고정
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_folder = os.path.join(base_dir, "market_data")
        os.makedirs(db_folder, exist_ok=True)
        self.db_path = os.path.join(db_folder, "crypto_dashboard.db")
        
        self._init_db()
        
    def clear_memory(self):
        """심볼 변경 시 반드시 호출하여 이전 심볼 데이터를 제거합니다."""
        self.df = pd.DataFrame()
        print(f"[{self.symbol}] 메모리 데이터가 초기화되었습니다.")

    def _init_db(self):
        """테이블과 필요한 모든 지표 컬럼을 생성합니다."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS "{self.symbol}" (
                    time INTEGER, timeframe TEXT,
                    open REAL, high REAL, low REAL, close REAL, volume REAL,
                    PRIMARY KEY (time, timeframe)
                )
            """)
            
            indicator_columns = [
                ('kijun', 'REAL'), ('senkou_a', 'REAL'), ('senkou_b', 'REAL'),
                ('rsi', 'REAL'), ('macd_line', 'REAL'), ('macd_sig', 'REAL'),
                ('bb_upper', 'REAL'), ('bb_middle', 'REAL'), ('bb_lower', 'REAL'),
                ('mfi', 'REAL'),
                ('master_long', 'INTEGER'), ('master_short', 'INTEGER'),
                ('top_detected', 'INTEGER'), ('bottom_detected', 'INTEGER')
            ]
            
            cursor.execute(f'PRAGMA table_info("{self.symbol}")')
            existing_cols = [row[1] for row in cursor.fetchall()]
            
            for col_name, col_type in indicator_columns:
                if col_name not in existing_cols:
                    try:
                        cursor.execute(f'ALTER TABLE "{self.symbol}" ADD COLUMN {col_name} {col_type}')
                    except Exception:
                        pass
                    
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS strategy_optimization (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    position_mode TEXT,
                    leverage INTEGER,
                    tp_ratio REAL,
                    sl_ratio REAL,
                    total_trades INTEGER,
                    win_rate REAL,
                    net_profit REAL,
                    tested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ml_trading_dataset (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_time TIMESTAMP,           -- 신호 발생 시간
                    symbol TEXT,                     -- 코인 심볼 (예: BTCUSDT)
                    timeframe TEXT,                  -- 타임프레임 (예: 15m)
                    signal_type TEXT,                -- 신호 종류 (MASTER_LONG/SHORT)
                    entry_open REAL,                 -- 진입 당시 시가
                    entry_high REAL,                 -- 진입 당시 고가
                    entry_low REAL,                  -- 진입 당시 저가
                    entry_close REAL,                -- 진입 당시 종가
                    entry_volume REAL,               -- 진입 당시 거래량
                    entry_rsi REAL,                  -- 보조지표: RSI
                    entry_macd REAL,                 -- 보조지표: MACD
                    entry_mfi REAL,                  -- 보조지표: MFI
                    bb_width REAL,                   -- 보조지표: 볼린저 밴드 너비
                    position_mode TEXT,              -- 포지션 모드 (ONE_WAY/HEDGE)
                    leverage INTEGER,                -- 사용 레버리지
                    tp_ratio REAL,                   -- 익절 비율 설정값
                    sl_ratio REAL,                   -- 손절 비율 설정값
                    result_status TEXT,              -- 결과 (TAKE_PROFIT, STOP_LOSS, LIQUIDATED, SWITCHED 등)
                    realized_pnl REAL,               -- 수수료 및 슬리피지가 제외된 최종 순수익
                    duration_candles INTEGER,        -- 포지션 유지 봉 개수
                    pyramid_count INTEGER DEFAULT 0, -- 불타기(추가 진입) 횟수
                    mdd_rate REAL DEFAULT 0          -- 포지션 유지 중 겪은 최대 낙폭 비율 (%)
                )
            ''')
            conn.commit()
            print("[DEBUG] DB 초기화 완료: MDD 지표가 포함된 최신 ML 데이터 테이블이 준비되었습니다.")
            
    def _fetch_binance_klines(self, start_time=None, end_time=None, limit=1500):
        """바이낸스 선물 API에서 데이터를 직접 가져옵니다."""
        endpoint = "/fapi/v1/klines"
        params = {
            "symbol": self.symbol,
            "interval": self.timeframe,
            "limit": limit
        }
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time # 🎯 역방향 수집을 위한 핵심 키

        try:
            response = requests.get(self.base_url + endpoint, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"API 에러: {response.status_code}")
                return []
        except Exception as e:
            print(f"네트워크 에러: {e}")
            return []
            
    def _save_raw_ohlcv(self, klines):
        """수집한 바이낸스 가격 데이터 6개 항목만 추출하여 DB에 UPSERT"""
        if not klines: return
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            data = [(
                int(item[0]),         # time (13자리 밀리초)
                self.timeframe,       # timeframe
                float(item[1]),       # open
                float(item[2]),       # high
                float(item[3]),       # low
                float(item[4]),       # close
                float(item[5])        # volume
            ) for item in klines]
            
            sql = f'''
                INSERT INTO "{self.symbol}" (time, timeframe, open, high, low, close, volume) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(time, timeframe) DO UPDATE SET 
                    open=excluded.open,
                    high=excluded.high,
                    low=excluded.low,
                    close=excluded.close,
                    volume=excluded.volume
            '''
            cursor.executemany(sql, data)
            conn.commit()
    
    def save_enriched_df(self, df_calc):
        """지표가 계산된 데이터프레임을 DB에 무손실 덮어쓰기 (UPSERT)"""
        if df_calc.empty: return
        try:
            temp_df = df_calc.reset_index().copy()
            temp_df.columns = [str(c).lower() for c in temp_df.columns]
            
            def enforce_13_digits(val):
                if pd.isna(val): return 0
                if isinstance(val, pd.Timestamp): return int(val.timestamp() * 1000)
                try:
                    num = float(val)
                    if num < 10000000000: return int(num * 1000)
                    elif num > 100000000000000000: return int(num // 1000000)
                    else: return int(num)
                except: return 0

            if 'time' in temp_df.columns:
                temp_df['time'] = temp_df['time'].apply(enforce_13_digits)
                
            temp_df['timeframe'] = self.timeframe
            
            bool_cols = ['master_long', 'master_short', 'top_detected', 'bottom_detected']
            for col in bool_cols:
                if col in temp_df.columns:
                    temp_df[col] = temp_df[col].fillna(False).astype(int)
            temp_df = temp_df.replace([np.inf, -np.inf], np.nan)
            
            db_cols = [
                'time', 'timeframe', 'open', 'high', 'low', 'close', 'volume',
                'kijun', 'senkou_a', 'senkou_b', 'rsi', 'macd_line', 'macd_sig',
                'bb_upper', 'bb_middle', 'bb_lower', 'mfi',
                'master_long', 'master_short', 'top_detected', 'bottom_detected'
            ]
            for col in db_cols:
                if col not in temp_df.columns:
                    temp_df[col] = None
                    
            final_df = temp_df[db_cols].where(pd.notnull(temp_df[db_cols]), None)
            data_list = final_df.values.tolist()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cols_str = ", ".join([f'"{c}"' for c in db_cols])
                placeholders = ", ".join(["?"] * len(db_cols))
                update_cols = [c for c in db_cols if c not in ['time', 'timeframe']]
                update_str = ", ".join([f'"{c}"=excluded."{c}"' for c in update_cols])
                
                sql = f'''
                    INSERT INTO "{self.symbol}" ({cols_str}) VALUES ({placeholders})
                    ON CONFLICT(time, timeframe) DO UPDATE SET {update_str}
                '''
                cursor.executemany(sql, data_list)
                conn.commit()
        except Exception as e:
            print(f"DB 저장 에러: {e}")
            
    def load_latest_from_db(self, limit=5000):
        """DB에서 데이터를 가져올 때 '현재 심볼'임을 다시 한번 보장합니다."""
        with sqlite3.connect(self.db_path) as conn:
            # f-string 테이블명뿐만 아니라 WHERE 절에도 심볼 체크를 넣는 것이 안전합니다.
            query = f'SELECT * FROM "{self.symbol}" WHERE timeframe = "{self.timeframe}" ORDER BY time DESC LIMIT {limit}'
            df = pd.read_sql(query, conn)
            
            if df.empty:
                self.df = pd.DataFrame()
                return self.df
                
            df = df.sort_values('time')
            df['time'] = pd.to_datetime(df['time'], unit='ms')
            df.set_index('time', inplace=True)
            
            # 기존 self.df와 병합하는 대신, 완전히 새로 불러온 데이터로 교체합니다.
            self.df = df.drop(columns=['timeframe'], errors='ignore')
            return self.df
        
    def refresh_indicators(self):
        """
        [백그라운드 엔진] 
        DB의 모든 데이터를 긁어와서 지표(Master Strategy)를 계산하고 다시 저장합니다.
        """
        print(f"[{self.symbol}] 전체 데이터 지표 계산 및 DB 업데이트 시작...")
        
        # 1. DB에서 전체 데이터 로드 (리미트 없음)
        with sqlite3.connect(self.db_path) as conn:
            query = f'SELECT * FROM "{self.symbol}" WHERE timeframe = "{self.timeframe}" ORDER BY time ASC'
            full_df = pd.read_sql(query, conn)
            
        if full_df.empty or len(full_df) < 60:
            print("데이터가 부족하여 지표를 계산할 수 없습니다.")
            return

        # 2. 판다스 데이터 정리
        full_df['time'] = pd.to_datetime(full_df['time'], unit='ms')
        full_df.set_index('time', inplace=True)
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        full_df[numeric_cols] = full_df[numeric_cols].apply(pd.to_numeric, errors='coerce')

        # 3. 핵심: 마스터 전략 적용 (지표 생성)
        self.df = apply_master_strategy(full_df)
        
        # 4. 결과물을 DB에 다시 저장 (UPSERT)
        self.save_enriched_df(self.df)
        print(f"[{self.symbol}] {len(self.df)}행의 지표가 DB에 성공적으로 반영되었습니다.")
            
    def sync_recent_data(self, required_limit=None, fallback_limit=5000):
        """
        [스마트 동기화] 
        DB의 마지막 저장 시점부터 현재까지의 공백을 계산하여 자동으로 수집합니다.
        required_limit을 직접 입력하면 해당 개수만큼 강제 수집합니다.
        """
        # 1. 타임프레임별 밀리초(ms) 간격 정의
        tf_ms_map = {
            "1m": 60000, "5m": 300000, "15m": 900000, "1h": 3600000, "4h": 14400000, "1d": 86400000
        }
        interval_ms = tf_ms_map.get(self.timeframe, 900000) # 기본값 15분

        # 2. 동적 리미트 계산 (공백 메우기)
        if required_limit is None:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    # DB에서 가장 최근에 저장된 캔들의 시간을 가져옴
                    cursor.execute(f'SELECT MAX(time) FROM "{self.symbol}" WHERE timeframe = ?', (self.timeframe,))
                    max_time = cursor.fetchone()[0]

                if max_time:
                    now_ms = int(time.time() * 1000)
                    gap_ms = now_ms - max_time
                    
                    # (현재 시간 - 마지막 시간) / 봉 간격 = 누락된 캔들 수
                    # 지표 계산을 위해 여유분 20개를 추가합니다.
                    calculated_limit = int(gap_ms / interval_ms) + 20
                    required_limit = max(calculated_limit, 100) # 최소 100개는 가져오도록 설정
                    print(f"[{self.symbol}] 마지막 데이터 이후 {int(gap_ms/60000)}분 경과. {required_limit}개 동기화 필요.")
                else:
                    # DB가 완전히 비어있을 때
                    required_limit = fallback_limit
            except Exception as e:
                print(f"[{self.symbol}] 공백 계산 중 오류 발생, 기본값 사용: {e}")
                required_limit = fallback_limit

        # 3. 데이터 수집 루프 (기존 로직 최적화)
        print(f"[{self.symbol}] {self.timeframe} 최신 {required_limit}개 캔들 역방향 수집 시작...")
        end_ts = int(time.time() * 1000)
        total_fetched = 0
        
        while total_fetched < required_limit:
            # 남은 개수만큼만 요청 (최대 1500개)
            fetch_now = min(1500, required_limit - total_fetched)
            klines = self._fetch_binance_klines(end_time=end_ts, limit=fetch_now)
            
            if not klines: 
                break
            
            self._save_raw_ohlcv(klines)
            total_fetched += len(klines)
            
            # 다음 호출을 위해 시간축 이동 (가장 오래된 캔들 이전으로)
            end_ts = klines[0][0] - 1
            time.sleep(0.05) # 바이낸스 API 보호를 위한 짧은 대기
            
        # 4. 수집 완료 후 지표 재계산
        self.refresh_indicators()
        
    def sync_historical_data(self, start_days=365):
        """
        [백그라운드용] 
        DB에 저장된 가장 오래된 데이터부터 더 깊은 과거로 역방향 수집합니다.
        """
        # 1. DB에서 가장 오래된 시간 찾기
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'SELECT MIN(time) FROM "{self.symbol}" WHERE timeframe = ?', (self.timeframe,))
            min_time = cursor.fetchone()[0]
            
        if not min_time:
            end_ts = int(time.time() * 1000)
        else:
            end_ts = min_time - 1 # 기존 데이터 직전부터 수집 시작
            
        target_ms = int(time.time() * 1000) - (start_days * 24 * 60 * 60 * 1000)
        total_fetched = 0
        
        print(f"[{self.symbol}] 백그라운드 과거 {start_days}일치 역방향 동기화 시작...")
        
        while end_ts > target_ms:
            klines = self._fetch_binance_klines(end_time=end_ts, limit=1500)
            if not klines: break
            
            self._save_raw_ohlcv(klines)
            total_fetched += len(klines)
            end_ts = klines[0][0] - 1
            
            print(f"과거 백필 중... {datetime.fromtimestamp(end_ts/1000)} 도달")
            time.sleep(0.05)
            
        # 과거 데이터 다 모았으면 전체 지표 한 번 쫙 맞춰주기
        if total_fetched > 0:
            self.refresh_indicators()
            
    def update_data(self):
        """[Step 4] 실시간 업데이트 로직 (루프용)"""
        try:
            # 1. 바이낸스 최신 봉 수집 (가장 최근 20개 정도면 갱신에 충분)
            klines = self._fetch_binance_klines(limit=20)
            self._save_raw_ohlcv(klines)
            
            # 2. 문맥 로드
            self.load_latest_from_db(limit=300)
            
            # 3. 전략 계산 후 최신화
            if len(self.df) > 60:
                self.df = apply_master_strategy(self.df)
                self.save_enriched_df(self.df)
                
            return self.df
        except Exception as e:
            print(f"실시간 업데이트 에러: {e}")
            return self.df
        
    def get_chart_df(self, limit=5000):
        """
        [프론트엔드 전송용] 
        메모리(self.df)에 있는 전체 데이터 중 최신 N개만 차트 규격에 맞춰 뽑아줍니다.
        """
        if self.df.empty:
            return pd.DataFrame()
            
        # 1. 최신 limit 개수만큼만 슬라이싱 (tail 사용)
        df_chart = self.df.tail(limit).reset_index()
        
        # 2. 컬럼명 소문자 통일
        df_chart.columns = [str(c).lower() for c in df_chart.columns]
        
        if self.symbol == "ETHUSDT":
            df_chart = df_chart[df_chart['close'] < 10000]
        elif self.symbol == "BTCUSDT":
            df_chart = df_chart[df_chart['close'] > 10000]
        
        # 3. 시간 변환: 13자리(ms) -> 10자리(s) 
        if 'time' in df_chart.columns:
            df_chart['time'] = df_chart['time'].apply(
                lambda x: int(x.timestamp()) if isinstance(x, pd.Timestamp) else int(x // 1000)
            )
            
        return df_chart