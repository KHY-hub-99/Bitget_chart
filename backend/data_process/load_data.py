import requests
import pandas as pd
import numpy as np
import sqlite3
import os
import time
from datetime import datetime, timezone, timedelta
from data_process.pine_data import apply_master_strategy
pd.set_option('future.no_silent_downcasting', True)

class CryptoDataFeed:
    def __init__(self, symbol="BTCUSDT", timeframe="15m"):
        self.symbol = symbol  
        self.timeframe = timeframe
        self.base_url = "https://fapi.binance.com"
        self.df = pd.DataFrame()
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_folder = os.path.join(base_dir, "market_data")
        os.makedirs(db_folder, exist_ok=True)
        self.db_path = os.path.join(db_folder, "crypto_dashboard.db")
        
        self._init_db()
        
    def _init_db(self):
        """테이블과 모든 지표 및 ML/전략 최적화 데이터셋 컬럼을 생성합니다. (표준 CamelCase 적용)"""
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
            
            # 제공해주신 표준 CamelCase 리스트로 컬럼 정의
            indicator_columns = [
                # 일목균형표 및 구름대
                ('tenkan', 'REAL'), ('kijun', 'REAL'), 
                ('senkouA', 'REAL'), ('senkouB', 'REAL'),
                ('cloudTop', 'REAL'), ('cloudBottom', 'REAL'),
                # Whale 세력선 및 거래량
                ('sma224', 'REAL'), ('vwma224', 'REAL'), ('volConfirm', 'INTEGER'),
                # 기술적 지표
                ('rsi', 'REAL'), ('mfi', 'REAL'),
                ('macdLine', 'REAL'), ('signalLine', 'REAL'),
                ('bbLower', 'REAL'), ('bbMid', 'REAL'), ('bbUpper', 'REAL'),
                # SMC 구조 및 가격 레벨
                ('swingHighLevel', 'REAL'), ('swingLowLevel', 'REAL'), ('equilibrium', 'REAL'),
                # 매매 조건 및 확정 시그널
                ('longCondition', 'INTEGER'), ('shortCondition', 'INTEGER'),
                ('longSig', 'INTEGER'), ('shortSig', 'INTEGER'),
                # 하이브리드 전략 세부 진입 규칙 (Rule 1 & Rule 2)
                ('entryVwmaLong', 'INTEGER'), ('entrySmcLong', 'INTEGER'),
                ('entryVwmaShort', 'INTEGER'), ('entrySmcShort', 'INTEGER'),
                # 역추세 세부 신호 및 최종 마커
                ('bearishDiv', 'INTEGER'), ('bullishDiv', 'INTEGER'),
                ('extremeTop', 'INTEGER'), ('extremeBottom', 'INTEGER'),
                ('TOP', 'INTEGER'), ('BOTTOM', 'INTEGER'),
                # SMC 구조 분석 지표 (추가 시각화용)
                ('fvgBullish', 'INTEGER'), ('fvgBearish', 'INTEGER'),
                ('swingBOS', 'INTEGER'), ('swingCHOCH', 'INTEGER'),
                ('internalBOS', 'INTEGER'), ('internalCHOCH', 'INTEGER')
            ]
            
            cursor.execute(f'PRAGMA table_info("{self.symbol}")')
            existing_cols = [row[1] for row in cursor.fetchall()]
            
            for col_name, col_type in indicator_columns:
                if col_name not in existing_cols:
                    try:
                        cursor.execute(f'ALTER TABLE "{self.symbol}" ADD COLUMN "{col_name}" {col_type}')
                    except Exception as e:
                        print(f"[DEBUG] 컬럼 추가 중 오류 ({col_name}): {e}")
            
            # 2. ML 데이터셋 테이블 생성 (학습용 상세 데이터)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ml_trading_dataset (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signalTime TIMESTAMP, symbol TEXT, timeframe TEXT, signalType TEXT,
                    
                    -- X 데이터 (진입 시점의 지표 피처)
                    entryOpen REAL, entryHigh REAL, entryLow REAL, entryClose REAL, entryVolume REAL,
                    entryTenkan REAL, entryKijun REAL, entrySenkouA REAL, entrySenkouB REAL,
                    entryCloudTop REAL, entryCloudBottom REAL,
                    entryRsi REAL, entryMfi REAL, entryMacdLine REAL, entrySignalLine REAL,
                    entryBbUpper REAL, entryBbMid REAL, entryBbLower REAL,
                    entrySma224 REAL, entryVwma224 REAL, 
                    entrySwingHighLevel REAL, entrySwingLowLevel REAL, entryEquilibrium REAL,

                    -- 진입 근거 및 규칙 (Rule 1 & Rule 2)
                    entryVwmaLong INTEGER, entrySmcLong INTEGER, 
                    entryVwmaShort INTEGER, entrySmcShort INTEGER,
                    
                    -- 시뮬레이션 설정 파라미터
                    positionMode TEXT, leverage INTEGER, marginRatio REAL,
                    appliedSlRatio REAL, slTag TEXT, 
                    
                    -- Y 라벨 (매매 결과)
                    resultStatus TEXT, realizedPnl REAL, durationCandles INTEGER,
                    pyramidCount INTEGER DEFAULT 0, mddRate REAL DEFAULT 0,
                    
                    UNIQUE(signalTime, symbol, timeframe, positionMode, leverage, marginRatio) ON CONFLICT REPLACE
                )
            ''')

            # 3. 전략 최적화 최종 통계 테이블 생성 (백테스트 결과 요약)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS strategy_optimization (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    positionMode TEXT, leverage INTEGER, marginRatio REAL,
                    
                    totalTrades INTEGER, winTrades INTEGER, lossTrades INTEGER,
                    winRate REAL, totalPnl REAL, avgPnl REAL,
                    maxDrawdown REAL, avgDuration REAL, avgPyramidCount REAL,
                    testedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    UNIQUE(positionMode, leverage, marginRatio) ON CONFLICT REPLACE
                )
            ''')
            conn.commit()

    def save_enriched_df(self, df_calc):
        """지표가 계산된 데이터프레임을 DB에 저장합니다. (모든 표준 컬럼 반영)"""
        if df_calc.empty: return
        try:
            temp_df = df_calc.reset_index().copy()
            # 컬럼명을 문자열로 유지 (강제 소문자 변환 제거)
            temp_df.columns = [str(c) for c in temp_df.columns]
            
            if 'time' in temp_df.columns:
                temp_df['time'] = temp_df['time'].apply(lambda x: int(x.timestamp() * 1000) if isinstance(x, pd.Timestamp) else int(x))
                
            temp_df['timeframe'] = self.timeframe
            
            # 정수형/불리언 컬럼 리스트 (pine_data.py 기준)
            int_cols = [
                'volConfirm', 'longCondition', 'shortCondition', 'longSig', 'shortSig',
                'bearishDiv', 'bullishDiv', 'extremeTop', 'extremeBottom', 'TOP', 'BOTTOM',
                'fvgBullish', 'fvgBearish', 'swingBOS', 'swingCHOCH', 'internalBOS', 'internalCHOCH'
            ]
            for col in int_cols:
                if col in temp_df.columns:
                    temp_df[col] = pd.to_numeric(temp_df[col], errors='coerce').fillna(0).astype(int)
            
            temp_df = temp_df.replace([np.inf, -np.inf], np.nan)
            
            # 저장할 전체 컬럼 리스트 (SMC Level 포함)
            db_cols = [
                'time', 'timeframe', 'open', 'high', 'low', 'close', 'volume',
                'tenkan', 'kijun', 'senkouA', 'senkouB', 'cloudTop', 'cloudBottom',
                'sma224', 'vwma224', 'volConfirm', 'rsi', 'mfi', 'macdLine', 'signalLine',
                'bbUpper', 'bbMid', 'bbLower', 'swingHighLevel', 'swingLowLevel', 'equilibrium',
                'longCondition', 'shortCondition', 'longSig', 'shortSig',
                'bearishDiv', 'bullishDiv', 'extremeTop', 'extremeBottom', 'TOP', 'BOTTOM',
                'fvgBullish', 'fvgBearish', 'swingBOS', 'swingCHOCH', 'internalBOS', 'internalCHOCH'
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

    # --- 머신러닝 및 시뮬레이션 결과 저장 메서드 (UPSERT 적용) ---
    def save_ml_result(self, ml_data: dict):
        """
        [AI 학습용 상세 데이터]
        신호 시간, 심볼, 타임프레임, 모드, 레버리지, 진입비중을 기준으로 
        중복 데이터가 들어오면 최신 결과(PNL, MDD 등)로 업데이트합니다.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                keys = list(ml_data.keys())
                placeholders = ", ".join(["?"] * len(keys))
                cols_str = ", ".join([f'"{k}"' for k in keys])
                
                # [기획 반영] UNIQUE 제약 조건 키 리스트 (고정 파라미터들)
                conflict_keys = [
                    'signal_time', 'symbol', 'timeframe', 
                    'position_mode', 'leverage', 'margin_ratio'
                ]
                
                # 업데이트할 컬럼 (데이터 및 결과값들 - 제약 조건 키 제외)
                update_cols = [k for k in keys if k not in conflict_keys]
                update_str = ", ".join([f'"{k}"=excluded."{k}"' for k in update_cols])
                
                # ON CONFLICT 구문 수정
                sql = f'''
                    INSERT INTO ml_trading_dataset ({cols_str}) VALUES ({placeholders})
                    ON CONFLICT({", ".join(conflict_keys)}) 
                    DO UPDATE SET {update_str}
                '''
                cursor.execute(sql, list(ml_data.values()))
                conn.commit()
        except Exception as e:
            print(f"ML 데이터 저장/업데이트 에러: {e}")

    def save_opt_result(self, opt_data: dict):
        """
        [전략 랭킹용 요약 데이터]
        동일한 모드/레버리지/진입비중 설정의 최적화 결과가 들어오면 
        최신 성적(승률, 전체 PNL 등)으로 업데이트합니다.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                keys = list(opt_data.keys())
                placeholders = ", ".join(["?"] * len(keys))
                cols_str = ", ".join([f'"{k}"' for k in keys])
                
                # [기획 반영] 요약 테이블의 UNIQUE 제약 조건 키
                conflict_keys = ['position_mode', 'leverage', 'margin_ratio']
                
                # 업데이트할 컬럼 (결과 지표들)
                update_cols = [k for k in keys if k not in conflict_keys]
                update_str = ", ".join([f'"{k}"=excluded."{k}"' for k in update_cols])
                
                sql = f'''
                    INSERT INTO strategy_optimization ({cols_str}) VALUES ({placeholders})
                    ON CONFLICT({", ".join(conflict_keys)}) 
                    DO UPDATE SET {update_str}, tested_at=CURRENT_TIMESTAMP
                '''
                cursor.execute(sql, list(opt_data.values()))
                conn.commit()
        except Exception as e:
            print(f"최적화 결과 저장/업데이트 에러: {e}")

    # --- 기존의 보조 메서드들 ---
    def sync_recent_data(self, required_limit=5000):
        """
        [UX 최적화] 최근 5,000개 데이터를 체크하여 부족할 때만 API를 호출합니다.
        """
        print(f"\n[CHECK] {self.symbol} ({self.timeframe}) 최근 데이터 상태 확인 중...")
        
        # 1. DB에 저장된 데이터 개수 확인
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f'SELECT COUNT(*) FROM "{self.symbol}" WHERE timeframe = ?', (self.timeframe,))
                count = cursor.fetchone()[0]
        except Exception:
            count = 0

        # 2. 이미 데이터가 충분하다면 API 호출 생략 (SKIP)
        if count >= required_limit:
            print(f"  >>> [SKIP] {self.symbol} 이미 {count}건의 데이터가 DB에 존재합니다. API 호출을 생략합니다.")
            return

        # 3. 부족할 경우만 API 호출 (API CALL)
        print(f"  >>> [API CALL] {self.symbol} DB 데이터({count}건)가 부족하여 최신 {required_limit}개를 수집합니다.")
        
        current_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        total_fetched = 0

        while total_fetched < required_limit:
            params = {
                "symbol": self.symbol,
                "interval": self.timeframe,
                "endTime": current_ts,
                "limit": 1000
            }
            try:
                response = requests.get(f"{self.base_url}/fapi/v1/klines", params=params, timeout=10)
                klines = response.json()
                if not klines: break

                self._save_raw_ohlcv(klines) # UPSERT 로직으로 중복 자동 방지
                total_fetched += len(klines)
                current_ts = klines[0][0] - 1 
                
                print(f"    > [API] {total_fetched}/{required_limit} 수집 중... ({pd.to_datetime(current_ts, unit='ms')})")
                time.sleep(0.1) 
            except Exception as e:
                print(f"    >>> [API ERROR] {e}")
                break

        print(f"  >>> [SUCCESS] {self.symbol} 우선순위 데이터 확보 완료.")
        self.refresh_indicators()

    def sync_historical_data(self, start_days=730):
        """
        [스마트 백필] DB의 가장 오래된 시간을 체크하여 설정일(730일)까지의 빈틈만 API로 채웁니다.
        """
        print(f"\n[CHECK] {self.symbol} ({self.timeframe}) 과거 {start_days}일치 백필 상태 확인 중...")
        
        target_ts = int((datetime.now(timezone.utc) - timedelta(days=start_days)).timestamp() * 1000)

        # 1. DB에서 가장 오래된 데이터 시간 확인
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f'SELECT MIN(time) FROM "{self.symbol}" WHERE timeframe = ?', (self.timeframe,))
                db_min = cursor.fetchone()[0]
        except Exception:
            db_min = None

        # 2. 이미 목표 시간보다 더 과거 데이터가 있다면 (SKIP)
        if db_min and db_min <= target_ts:
            print(f"  >>> [SKIP] {self.symbol} 이미 목표 시점({pd.to_datetime(target_ts, unit='ms')}) 이전 데이터가 확보되어 있습니다.")
            return

        # 3. 데이터가 아예 없거나 부족하면 그 지점부터 백필 (API CALL)
        current_ts = db_min - 1 if db_min else int(datetime.now(timezone.utc).timestamp() * 1000)
        print(f"  >>> [API CALL] {self.symbol} 부족한 과거 구간 백필 시작 (목표: {pd.to_datetime(target_ts, unit='ms')})")
        
        total_count = 0
        while current_ts > target_ts:
            params = {
                "symbol": self.symbol,
                "interval": self.timeframe,
                "endTime": current_ts,
                "limit": 1000
            }
            try:
                response = requests.get(f"{self.base_url}/fapi/v1/klines", params=params, timeout=10)
                data = response.json()
                if not data or len(data) <= 1: break
                
                self._save_raw_ohlcv(data)
                first_ts = data[0][0]
                current_ts = first_ts - 1
                total_count += len(data)
                
                print(f"    > [API] {total_count}개 과거 데이터 수집 중... ({pd.to_datetime(first_ts, unit='ms')})")
                time.sleep(0.1) 
            except Exception as e:
                print(f"    >>> [API ERROR] {e}")
                break

        print(f"  >>> [SUCCESS] {self.symbol} 총 {total_count}개 과거 데이터 동기화 완료.")
        self.refresh_indicators()
    
    def _fetch_binance_klines(self, start_time=None, end_time=None, limit=1000):
        endpoint = "/fapi/v1/klines"
        params = {"symbol": self.symbol, "interval": self.timeframe, "limit": limit}
        if start_time: params["startTime"] = start_time
        if end_time: params["endTime"] = end_time
        try:
            response = requests.get(self.base_url + endpoint, params=params)
            return response.json() if response.status_code == 200 else []
        except: return []

    def _save_raw_ohlcv(self, klines):
        if not klines: return
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            data = [(int(item[0]), self.timeframe, float(item[1]), float(item[2]), float(item[3]), float(item[4]), float(item[5])) for item in klines]
            sql = f'INSERT INTO "{self.symbol}" (time, timeframe, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(time, timeframe) DO UPDATE SET open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close, volume=excluded.volume'
            cursor.executemany(sql, data)
            conn.commit()

    def load_latest_from_db(self, limit=5000):
        """DB에서 데이터를 가져올 때 로그를 남깁니다."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = f'SELECT * FROM "{self.symbol}" WHERE timeframe = ? ORDER BY time DESC LIMIT ?'
                df = pd.read_sql_query(query, conn, params=(self.timeframe, limit))
                
            if not df.empty:
                # [디버깅 로그] DB에서 몇 건을 가져왔는지 출력
                print(f"  >>> [DATABASE] {self.symbol} DB에서 {len(df)}건 로드 완료.")
                df['time'] = pd.to_datetime(df['time'], unit='ms')
                df.set_index('time', inplace=True)
                df = df.sort_index()
                self.df = df
                return df
            else:
                print(f"  >>> [DATABASE] {self.symbol} DB가 비어있습니다. API 호출이 필요합니다.")
                return None
        except Exception as e:
            print(f"  >>> [DATABASE ERROR] {e}")
            return None

    def refresh_indicators(self):
        with sqlite3.connect(self.db_path) as conn:
            query = f'SELECT * FROM "{self.symbol}" WHERE timeframe = "{self.timeframe}" ORDER BY time ASC'
            full_df = pd.read_sql(query, conn)
        if full_df.empty or len(full_df) < 224: return  # Whale 지표(224) 계산을 위한 최소치 수정
        full_df['time'] = pd.to_datetime(full_df['time'], unit='ms')
        full_df.set_index('time', inplace=True)
        self.df = apply_master_strategy(full_df)
        self.save_enriched_df(self.df)

    def update_data(self):
        klines = self._fetch_binance_klines(limit=20)
        self._save_raw_ohlcv(klines)
        # Whale 지표(sma224/vwma224) 계산을 위해 최소 224개 이상의 캔들 필요. 여유있게 300~500개 권장
        self.load_latest_from_db(limit=500) 
        if len(self.df) >= 224: 
            self.df = apply_master_strategy(self.df)
            self.save_enriched_df(self.df)
        return self.df

    def get_chart_df(self, limit=5000):
        if self.df.empty: return pd.DataFrame()
        df_chart = self.df.tail(limit).reset_index()
        df_chart.columns = [str(c) for c in df_chart.columns]
        if 'time' in df_chart.columns:
            df_chart['time'] = df_chart['time'].apply(lambda x: int(x.timestamp()) if isinstance(x, pd.Timestamp) else int(x // 1000))
        return df_chart