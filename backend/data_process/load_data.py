import requests
import pandas as pd
import numpy as np
import sqlite3
import os
import time
from datetime import datetime, timezone, timedelta
from data_process.pine_data import apply_master_strategy

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
                    temp_df[col] = temp_df[col].fillna(0).astype(int)
            
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
    def sync_historical_data(self, start_days=730):
        """
        기존 _fetch_binance_klines를 활용하거나 직접 호출하여 
        지정된 날짜만큼의 과거 데이터를 루프를 돌며 채웁니다.
        """
        import time
        from datetime import datetime, timezone, timedelta

        print(f"\n[{self.symbol} | {self.timeframe}] {start_days}일치 과거 데이터 백필 시작...")
        
        # 1. 시작 시간 설정 (현재로부터 n일 전)
        end_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        start_ts = int((datetime.now(timezone.utc) - timedelta(days=start_days)).timestamp() * 1000)
        current_ts = start_ts
        total_count = 0

        while current_ts < end_ts:
            # 바이낸스 선물 API klines 호출 (최대 1000개씩)
            params = {
                "symbol": self.symbol,
                "interval": self.timeframe,
                "startTime": current_ts,
                "limit": 1000
            }
            
            try:
                response = requests.get(f"{self.base_url}/fapi/v1/klines", params=params, timeout=10)
                data = response.json()
                
                if not data or len(data) <= 1:
                    break
                
                # 원시 데이터 저장 (이미 구현된 _save_raw_ohlcv 활용)
                self._save_raw_ohlcv(data)
                
                # 다음 구간 설정을 위해 마지막 데이터 시간 업데이트
                last_ts = data[-1][0]
                current_ts = last_ts + 1
                total_count += len(data)
                
                print(f" > [{self.symbol}] {len(data)}개 추가 수집... (현재 시각: {pd.to_datetime(last_ts, unit='ms')})")
                
                # API 부하 방지 및 속도 조절
                time.sleep(0.1) 
                
                # 만약 가져온 마지막 시각이 현재 시각과 가깝다면 종료
                if last_ts >= end_ts - 60000: # 1분 이내 차이
                    break
                    
            except Exception as e:
                print(f"[ERROR] {self.symbol} 백필 중 오류 발생: {e}")
                break

        print(f"[{self.symbol}] 총 {total_count}개의 과거 캔들 동기화 완료.")
        
        # 데이터 수집이 끝났으므로 전체 지표 재계산 (CamelCase 표준 적용)
        self.refresh_indicators()

    def sync_recent_data(self, required_limit=5000):
        """
        [UX 최적화] 최근 5,000개 데이터를 빠르게 채워 차트를 즉시 활성화합니다.
        바이낸스 1회 호출 제한(1000개)을 우회하기 위해 루프를 사용합니다.
        """
        print(f"[{self.symbol}] 차트용 최신 데이터 {required_limit}개 우선 수집 시작...")
        
        current_ts = int(datetime.now(timezone.utc).timestamp() * 1000)
        total_fetched = 0

        # 5,000개를 다 채울 때까지 최대 1,000개씩 역순(Backward) 수집
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

                self._save_raw_ohlcv(klines)
                
                total_fetched += len(klines)
                # 다음 루프를 위해 가져온 데이터 중 가장 오래된 시간의 -1ms 지점으로 이동
                current_ts = klines[0][0] - 1 
                
                print(f" > [{self.symbol}] {total_fetched}/{required_limit}개 수집 중...")
                
                # 우선순위 수집은 '초고속'이 생명이므로 최소한의 대기만 함
                time.sleep(0.1) 
                
            except Exception as e:
                print(f"[ERROR] 우선순위 수집 중단: {e}")
                break

        print(f"[{self.symbol}] 우선순위 데이터 {total_fetched}개 확보 완료.")
        # 차트 전시를 위해 즉시 지표 계산 실행
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
        with sqlite3.connect(self.db_path) as conn:
            query = f'SELECT * FROM "{self.symbol}" WHERE timeframe = "{self.timeframe}" ORDER BY time DESC LIMIT {limit}'
            df = pd.read_sql(query, conn)
            if df.empty: return pd.DataFrame()
            df = df.sort_values('time')
            df['time'] = pd.to_datetime(df['time'], unit='ms')
            df.set_index('time', inplace=True)
            self.df = df.drop(columns=['timeframe'], errors='ignore')
            return self.df

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