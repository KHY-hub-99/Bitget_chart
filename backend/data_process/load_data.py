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
        """테이블과 모든 지표 및 ML 데이터셋 컬럼을 생성합니다. (camelCase 표준 적용)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 1. 시세 및 지표 데이터 테이블 (심볼별)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS "{self.symbol}" (
                    time INTEGER, 
                    timeframe TEXT,
                    open REAL, high REAL, low REAL, close REAL, volume REAL,
                    PRIMARY KEY (time, timeframe)
                )
            """)
            
            # 지표 연산의 중간 값과 최종 시그널을 모두 저장합니다.
            indicator_columns = [
                # 일목균형표 상세
                ('tenkan', 'REAL'), ('kijun', 'REAL'), 
                ('senkouA', 'REAL'), ('senkouB', 'REAL'),
                ('cloudTop', 'REAL'), ('cloudBottom', 'REAL'),
                # Whale 세력선
                ('sma224', 'REAL'), ('vwma224', 'REAL'),
                # 기타 기술적 지표
                ('rsi', 'REAL'), ('mfi', 'REAL'),
                ('macdLine', 'REAL'), ('signalLine', 'REAL'),
                ('bbUpper', 'REAL'), ('bbMid', 'REAL'), ('bbLower', 'REAL'),
                ('volConfirm', 'INTEGER'),
                # 매매 조건 및 확정 시그널
                ('longCondition', 'INTEGER'), ('shortCondition', 'INTEGER'),
                ('longSig', 'INTEGER'), ('shortSig', 'INTEGER'),
                # 역추세 세부 신호 및 최종 마커
                ('bearishDiv', 'INTEGER'), ('bullishDiv', 'INTEGER'),
                ('extremeTop', 'INTEGER'), ('extremeBottom', 'INTEGER'),
                ('TOP', 'INTEGER'), ('BOTTOM', 'INTEGER')
            ]
            
            # 기존 테이블 컬럼 확인 후 누락된 컬럼 자동 추가 (ALTER TABLE)
            cursor.execute(f'PRAGMA table_info("{self.symbol}")')
            existing_cols = [row[1] for row in cursor.fetchall()]
            
            for col_name, col_type in indicator_columns:
                if col_name not in existing_cols:
                    try:
                        cursor.execute(f'ALTER TABLE "{self.symbol}" ADD COLUMN "{col_name}" {col_type}')
                    except Exception as e:
                        print(f"[DEBUG] 컬럼 추가 중 오류 ({col_name}): {e}")
            
            # 진입 시점의 모든 시장 상황(X)과 결과(y)를 기록합니다.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ml_trading_dataset (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_time TIMESTAMP,           -- 진입 시간
                    symbol TEXT,                     -- 코인 심볼
                    timeframe TEXT,                  -- 타임프레임
                    signal_type TEXT,                -- 신호 종류 (LONG/SHORT/TOP/BOTTOM)
                    
                    -- [학습 피처 (X)] 진입 시점의 캔들 정보
                    entry_open REAL, entry_high REAL, entry_low REAL, entry_close REAL, entry_volume REAL,
                    
                    -- [학습 피처 (X)] 진입 시점의 기술적 지표 상황
                    entry_tenkan REAL, entry_kijun REAL,
                    entry_cloudTop REAL, entry_cloudBottom REAL,
                    entry_rsi REAL, entry_macd REAL, entry_signal REAL, entry_mfi REAL,
                    entry_sma224 REAL, entry_vwma224 REAL,
                    bb_width REAL,                   -- 변동성 지표
                    
                    -- [설정 값] 시뮬레이션 환경 파라미터
                    position_mode TEXT,              -- 격리(Isolated) 모드 등
                    leverage INTEGER,                -- 레버리지 배수
                    tp_ratio REAL,                   -- 익절 설정값
                    sl_ratio REAL,                   -- 손절 설정값
                    
                    -- [결과 데이터 (y)]
                    result_status TEXT,              -- 결과 (TAKE_PROFIT, STOP_LOSS, LIQUIDATED 등)
                    realized_pnl REAL,               -- 최종 실현 수익(USDT)
                    duration_candles INTEGER,        -- 포지션 유지 봉 개수
                    pyramid_count INTEGER DEFAULT 0, -- 추세 추종 시 불타기 횟수
                    mdd_rate REAL DEFAULT 0,         -- 해당 매매 중 최대 낙폭(%)
                    
                    -- 중복 진입 데이터 방지 (동일 시간/설정 시 업데이트)
                    UNIQUE(signal_time, symbol, timeframe, position_mode, leverage, tp_ratio, sl_ratio) ON CONFLICT REPLACE
                )
            ''')
            
            conn.commit()
            print(f"[DEBUG] DB 초기화 완료: {self.symbol} 테이블 및 ML 데이터셋 구조가 최신화되었습니다.")
            
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
            params["endTime"] = end_time

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
        """지표가 계산된 데이터프레임을 DB에 저장합니다. (모든 컬럼 UPSERT)"""
        if df_calc.empty: return
        try:
            temp_df = df_calc.reset_index().copy()
            temp_df.columns = [str(c) for c in temp_df.columns]
            
            # 시간 포맷 처리 (13자리 밀리초)
            if 'time' in temp_df.columns:
                temp_df['time'] = temp_df['time'].apply(lambda x: int(x.timestamp() * 1000) if isinstance(x, pd.Timestamp) else int(x))
                
            temp_df['timeframe'] = self.timeframe
            
            # 정수형(Boolean) 컬럼 처리
            int_cols = [
                'volConfirm', 'longCondition', 'shortCondition', 'longSig', 'shortSig',
                'bearishDiv', 'bullishDiv', 'extremeTop', 'extremeBottom', 'TOP', 'BOTTOM'
            ]
            for col in int_cols:
                if col in temp_df.columns:
                    temp_df[col] = temp_df[col].fillna(0).astype(int)
            
            temp_df = temp_df.replace([np.inf, -np.inf], np.nan)
            
            # 저장할 전체 컬럼 순서 정의
            db_cols = [
                'time', 'timeframe', 'open', 'high', 'low', 'close', 'volume',
                'tenkan', 'kijun', 'senkouA', 'senkouB', 'cloudTop', 'cloudBottom',
                'sma224', 'vwma224', 'rsi', 'mfi', 'macdLine', 'signalLine',
                'bbUpper', 'bbMid', 'bbLower', 'volConfirm',
                'longCondition', 'shortCondition', 'longSig', 'shortSig',
                'bearishDiv', 'bullishDiv', 'extremeTop', 'extremeBottom', 'TOP', 'BOTTOM'
            ]
            
            # 없는 컬럼은 None으로 채우기
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
            query = f'SELECT * FROM "{self.symbol}" WHERE timeframe = "{self.timeframe}" ORDER BY time DESC LIMIT {limit}'
            df = pd.read_sql(query, conn)
            
            if df.empty:
                self.df = pd.DataFrame()
                return self.df
                
            df = df.sort_values('time')
            df['time'] = pd.to_datetime(df['time'], unit='ms')
            df.set_index('time', inplace=True)
            
            self.df = df.drop(columns=['timeframe'], errors='ignore')
            return self.df
        
    def refresh_indicators(self):
        """
        [백그라운드 엔진] 
        DB의 모든 데이터를 긁어와서 지표(Master Strategy)를 계산하고 다시 저장합니다.
        """
        print(f"[{self.symbol}] 전체 데이터 지표 계산 및 DB 업데이트 시작...")
        
        with sqlite3.connect(self.db_path) as conn:
            query = f'SELECT * FROM "{self.symbol}" WHERE timeframe = "{self.timeframe}" ORDER BY time ASC'
            full_df = pd.read_sql(query, conn)
            
        if full_df.empty or len(full_df) < 60:
            print("데이터가 부족하여 지표를 계산할 수 없습니다.")
            return

        full_df['time'] = pd.to_datetime(full_df['time'], unit='ms')
        full_df.set_index('time', inplace=True)
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        full_df[numeric_cols] = full_df[numeric_cols].apply(pd.to_numeric, errors='coerce')

        self.df = apply_master_strategy(full_df)
        self.save_enriched_df(self.df)
        print(f"[{self.symbol}] {len(self.df)}행의 지표가 DB에 성공적으로 반영되었습니다.")
            
    def sync_recent_data(self, required_limit=None, fallback_limit=5000):
        """
        [스마트 동기화] 
        DB의 마지막 저장 시점부터 현재까지의 공백을 계산하여 자동으로 수집합니다.
        """
        tf_ms_map = {
            "1m": 60000, "5m": 300000, "15m": 900000, "1h": 3600000, "4h": 14400000, "1d": 86400000
        }
        interval_ms = tf_ms_map.get(self.timeframe, 900000)

        if required_limit is None:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(f'SELECT MAX(time) FROM "{self.symbol}" WHERE timeframe = ?', (self.timeframe,))
                    max_time = cursor.fetchone()[0]

                if max_time:
                    now_ms = int(time.time() * 1000)
                    gap_ms = now_ms - max_time
                    calculated_limit = int(gap_ms / interval_ms) + 20
                    required_limit = max(calculated_limit, 100)
                    print(f"[{self.symbol}] 마지막 데이터 이후 {int(gap_ms/60000)}분 경과. {required_limit}개 동기화 필요.")
                else:
                    required_limit = fallback_limit
            except Exception as e:
                print(f"[{self.symbol}] 공백 계산 중 오류 발생, 기본값 사용: {e}")
                required_limit = fallback_limit

        print(f"[{self.symbol}] {self.timeframe} 최신 {required_limit}개 캔들 역방향 수집 시작...")
        end_ts = int(time.time() * 1000)
        total_fetched = 0
        
        while total_fetched < required_limit:
            fetch_now = min(1500, required_limit - total_fetched)
            klines = self._fetch_binance_klines(end_time=end_ts, limit=fetch_now)
            
            if not klines: 
                break
            
            self._save_raw_ohlcv(klines)
            total_fetched += len(klines)
            end_ts = klines[0][0] - 1
            time.sleep(0.05)
            
        self.refresh_indicators()
        
    def sync_historical_data(self, start_days=365):
        """
        [백그라운드용] 
        DB에 저장된 가장 오래된 데이터부터 더 깊은 과거로 역방향 수집합니다.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'SELECT MIN(time) FROM "{self.symbol}" WHERE timeframe = ?', (self.timeframe,))
            min_time = cursor.fetchone()[0]
            
        if not min_time:
            end_ts = int(time.time() * 1000)
        else:
            end_ts = min_time - 1
            
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
            
        if total_fetched > 0:
            self.refresh_indicators()
            
    def update_data(self):
        """[Step 4] 실시간 업데이트 로직 (루프용)"""
        try:
            klines = self._fetch_binance_klines(limit=20)
            self._save_raw_ohlcv(klines)
            
            self.load_latest_from_db(limit=300)
            
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
            
        df_chart = self.df.tail(limit).reset_index()
        
        # [수정] 강제 소문자 변환 제거 -> 원본 camelCase 유지
        df_chart.columns = [str(c) for c in df_chart.columns]
        
        if self.symbol == "ETHUSDT":
            df_chart = df_chart[df_chart['close'] < 10000]
        elif self.symbol == "BTCUSDT":
            df_chart = df_chart[df_chart['close'] > 10000]
        
        if 'time' in df_chart.columns:
            df_chart['time'] = df_chart['time'].apply(
                lambda x: int(x.timestamp()) if isinstance(x, pd.Timestamp) else int(x // 1000)
            )
            
        return df_chart