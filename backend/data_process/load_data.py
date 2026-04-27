import requests
import pandas as pd
import numpy as np
import sqlite3
import os
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
        """테이블과 모든 지표 및 ML/전략 최적화 데이터셋 컬럼을 생성합니다. (표준 적용)"""
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
            
            # pine_data.py에서 생성되는 모든 컬럼 리스트 정의 (변수명 통일 규칙 적용)
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
                ('bbUpper', 'REAL'), ('bbMid', 'REAL'), ('bbLower', 'REAL'),
                # [추가] SMC 가격 레벨 (시뮬레이션 SL 및 50% 익절 기준선)
                ('swingHighLevel', 'REAL'), ('swingLowLevel', 'REAL'), ('equilibrium', 'REAL'),
                # 매매 조건 및 확정 시그널
                ('longCondition', 'INTEGER'), ('shortCondition', 'INTEGER'),
                ('longSig', 'INTEGER'), ('shortSig', 'INTEGER'),
                # 역추세 세부 신호 및 최종 마커
                ('bearishDiv', 'INTEGER'), ('bullishDiv', 'INTEGER'),
                ('extremeTop', 'INTEGER'), ('extremeBottom', 'INTEGER'),
                ('TOP', 'INTEGER'), ('BOTTOM', 'INTEGER'),
                # SMC 구조 분석 지표 (선택적 시각화용)
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
                -- 1. AI 학습용 상세 데이터셋 테이블
                CREATE TABLE IF NOT EXISTS ml_trading_dataset (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_time TIMESTAMP,           
                    symbol TEXT,                     
                    timeframe TEXT,                  
                    signal_type TEXT,                
                    
                    -- X 데이터
                    entry_open REAL, entry_high REAL, entry_low REAL, entry_close REAL, entry_volume REAL,
                    entry_tenkan REAL, entry_kijun REAL, entry_cloudTop REAL, entry_cloudBottom REAL,
                    entry_rsi REAL, entry_macdLine REAL, entry_signalLine REAL, entry_mfi REAL,
                    entry_sma224 REAL, entry_vwma224 REAL, bb_width REAL,
                    entry_equilibrium REAL, entry_smc_sl REAL,
                    
                    -- 시뮬레이션 설정
                    position_mode TEXT,              
                    leverage INTEGER,                
                    margin_ratio REAL,   -- 0.33, 0.5 등             
                    applied_sl_ratio REAL, -- 동적으로 계산된 손절 %
                    sl_tag TEXT,           -- RULE_1_ROE or RULE_2_SMC
                    
                    -- Y 라벨
                    result_status TEXT,              
                    realized_pnl REAL,               
                    duration_candles INTEGER,        
                    pyramid_count INTEGER DEFAULT 0, 
                    mdd_rate REAL DEFAULT 0,         
                    
                    -- UNIQUE 제약조건 수정
                    UNIQUE(signal_time, symbol, timeframe, position_mode, leverage, margin_ratio) ON CONFLICT REPLACE
            ''')

            # 3. 전략 최적화 최종 통계 테이블 생성 (백테스트 결과 요약)
            cursor.execute('''
                -- 2. 전략 랭킹용 요약 데이터 테이블
                CREATE TABLE IF NOT EXISTS strategy_optimization (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    position_mode TEXT,
                    leverage INTEGER,
                    margin_ratio REAL,
                    
                    total_trades INTEGER,
                    win_trades INTEGER,
                    loss_trades INTEGER,
                    win_rate REAL,
                    total_pnl REAL,
                    avg_pnl REAL,
                    max_drawdown REAL,
                    avg_duration REAL,
                    avg_pyramid_count REAL,
                    tested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- UNIQUE 제약조건 수정
                    UNIQUE(position_mode, leverage, margin_ratio) ON CONFLICT REPLACE
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
    def _fetch_binance_klines(self, start_time=None, end_time=None, limit=1500):
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