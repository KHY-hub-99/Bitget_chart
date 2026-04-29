import requests
import pandas as pd
import numpy as np
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from pynecore.core.script_runner import ScriptRunner 
from pynecore.core.syminfo import SymInfo
from pynecore.core.ohlcv_file import OHLCV

# 판다스 설정
pd.set_option('future.no_silent_downcasting', True)

class CryptoDataFeed:
    def __init__(self, symbol="BTCUSDT", timeframe="15m"):
        self.symbol = symbol  
        self.timeframe = timeframe
        self.base_url = "https://fapi.binance.com"
        self.df = pd.DataFrame()
        
        # [경로 설정]
        self.base_dir = Path(__file__).resolve().parent.parent
        self.script_file = self.base_dir / "workdir" / "scripts" / "master_smc.py"
        
        db_folder = self.base_dir / "market_data"
        db_folder.mkdir(parents=True, exist_ok=True)
        self.db_path = db_folder / "crypto_dashboard.db"
        
        # [기준] 사용자 정의 25개 지표 컬럼 (longSig/shortSig를 Rule1/Rule2로 세분화)
        self.standard_cols = [
            "tenkan", "kijun", "senkouA", "senkouB", "cloudTop", "cloudBottom",
            "sma224", "vwma224", "rsiVal", "mfiVal", "macdLine", "signalLine",
            "bbUpper", "bbLower", "bbMid", 
            "longSig_Rule1", "shortSig_Rule1", "longSig_Rule2", "shortSig_Rule2", 
            "topDiamond", "bottomDiamond", "swingHighLevel", "trailingBottom", 
            "equilibrium", "trend"
        ]
        
        self._init_db()
        
    def _init_db(self):
        """3가지 핵심 테이블(시세/지표, ML 데이터셋, 전략 최적화) 초기화"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 1. 실시간 시세 및 지표 테이블 (PK: time, timeframe)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS "{self.symbol}" (
                    time INTEGER, timeframe TEXT,
                    open REAL, high REAL, low REAL, close REAL, volume REAL,
                    PRIMARY KEY (time, timeframe)
                )
            """)
            
            # 지표 컬럼 Migration (25개 표준 컬럼 추가)
            cursor.execute(f'PRAGMA table_info("{self.symbol}")')
            existing_cols = [row[1] for row in cursor.fetchall()]
            
            for col in self.standard_cols:
                if col not in existing_cols:
                    col_type = "INTEGER" if col in ["trend", "longSig_Rule1", "shortSig_Rule1", "longSig_Rule2", "shortSig_Rule2", "topDiamond", "bottomDiamond"] else "REAL"
                    cursor.execute(f'ALTER TABLE "{self.symbol}" ADD COLUMN "{col}" {col_type}')

            # 2. ML 학습 데이터셋 테이블 (entry_ 접두사 사용 및 메타데이터 컬럼 추가)
            ml_features = ", ".join([f'"entry_{col}" REAL' for col in self.standard_cols])
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS ml_trading_dataset (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signalTime TIMESTAMP, symbol TEXT, timeframe TEXT, 
                    positionMode TEXT, leverage INTEGER, marginRatio REAL,
                    signalType TEXT,
                    entryOpen REAL, entryHigh REAL, entryLow REAL, entryClose REAL, entryVolume REAL,
                    
                    -- 동적 지표 컬럼들 (self.standard_cols 매핑)
                    {ml_features},
                    
                    -- 하이브리드 전략 판별 및 손절 태그
                    strategyRule TEXT,
                    slTag TEXT,
                    appliedSlRatio REAL,
                    
                    -- 결과 및 통계
                    resultStatus TEXT, realizedPnl REAL, durationCandles INTEGER,
                    pyramidCount INTEGER DEFAULT 0, mddRate REAL DEFAULT 0,
                    
                    UNIQUE(signalTime, symbol, timeframe, positionMode, leverage, marginRatio) ON CONFLICT REPLACE
                )
            ''')

            # 3. 전략 최적화 요약 테이블 (불타기 평균 횟수 추가)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS strategy_optimization (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    positionMode TEXT, leverage INTEGER, marginRatio REAL,
                    totalTrades INTEGER, winTrades INTEGER, lossTrades INTEGER,
                    winRate REAL, totalPnl REAL, avgPnl REAL,
                    maxDrawdown REAL, avgDuration REAL,
                    
                    -- 불타기(피라미딩) 평균 횟수
                    avgPyramidCount REAL, 
                    
                    testedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(positionMode, leverage, marginRatio) ON CONFLICT REPLACE
                )
            ''')
            
            conn.commit()
            print(f"[DATABASE] 모든 테이블이 ({self.symbol}-{self.timeframe})에 맞춰 초기화되었습니다.")
            
    def _run_pynecore_engine(self, df):
        """PyneCore ScriptRunner를 통한 지표 연산 핵심 로직"""
        if df.empty: return pd.DataFrame()

        # SymInfo 설정 (9개 필수 인자)
        si = SymInfo(
            ticker=self.symbol, period=self.timeframe, timezone="UTC", currency="USDT",
            prefix="BINANCE", description=f"{self.symbol} Standard", type="crypto",
            mintick=0.01, pricescale=100, pointvalue=1,
            opening_hours="24x7", session_starts=[0], session_ends=[86400]
        )

        # OHLCV 변환 (Datetime index -> timestamp seconds) 방어 코드 적용
        temp_df = df.reset_index()
        ohlcv_list = []
        for _, row in temp_df.iterrows():
            t_val = row['time']
            
            # 안전한 타임스탬프 추출 로직
            if isinstance(t_val, (int, float, np.integer, np.floating)):
                ts_seconds = int(t_val / 1000) if t_val > 1e11 else int(t_val)
            elif hasattr(t_val, 'timestamp'):
                ts_seconds = int(t_val.timestamp())
            else:
                ts_seconds = int(pd.to_datetime(t_val).timestamp())

            ohlcv_list.append(
                OHLCV(
                    timestamp=ts_seconds,
                    open=float(row['open']), high=float(row['high']), 
                    low=float(row['low']), close=float(row['close']), 
                    volume=float(row['volume']), extra_fields={}
                )
            )

        runner = ScriptRunner(script_path=self.script_file, ohlcv_iter=ohlcv_list, syminfo=si)
        
        results = []
        for candle, plot_data in runner.run_iter():
            combined = {
                "time": candle.timestamp * 1000, # DB 저장을 위해 ms로 변환
                "open": candle.open, "high": candle.high, "low": candle.low, 
                "close": candle.close, "volume": candle.volume,
                **plot_data 
            }
            results.append(combined)

        return pd.DataFrame(results)

    def save_enriched_df(self, df_calc):
        """지표가 계산된 DF를 DB에 저장 (NA 객체 처리 및 Pandas 최신버전 대응)"""
        if df_calc.empty: return
        try:
            temp_df = df_calc.copy()
            temp_df['timeframe'] = self.timeframe
            
            # [1] INTEGER 컬럼들 0/1 강제 (NULL 방지)
            int_cols = ["longSig_Rule1", "shortSig_Rule1", "longSig_Rule2", "shortSig_Rule2", "topDiamond", "bottomDiamond", "trend"]
            for col in int_cols:
                if col in temp_df.columns:
                    temp_df[col] = pd.to_numeric(temp_df[col], errors='coerce').fillna(0).astype(int)

            # [2] PyneCore NA 객체를 None으로 변환하는 함수
            def clean_na_values(x):
                if pd.isna(x): return None
                # PyneCore NA 객체 체크
                if hasattr(x, '__class__') and 'NA' in x.__class__.__name__:
                    return None
                return x

            # Pandas 2.1.0+ 에서는 applymap 대신 map을 사용합니다.
            if hasattr(temp_df, 'map'):
                temp_df = temp_df.map(clean_na_values)
            else:
                temp_df = temp_df.applymap(clean_na_values)

            # [3] 최종 DB 컬럼 순서 배치 (표준 컬럼 기준)
            db_cols = ['time', 'timeframe', 'open', 'high', 'low', 'close', 'volume'] + self.standard_cols
            
            for col in db_cols:
                if col not in temp_df.columns:
                    temp_df[col] = None
            
            final_df = temp_df[db_cols].where(pd.notnull(temp_df[db_cols]), None)
            
            # [4] UPSERT 실행
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
                cursor.executemany(sql, final_df.values.tolist())
                conn.commit()
                print(f"[SUCCESS] {self.symbol} 데이터베이스 저장 완료.")
                
        except Exception as e:
            print(f"[SAVE ERROR] {e}")

    # --- 머신러닝 및 시뮬레이션 결과 저장 메서드 (UPSERT 적용) ---
    def save_ml_result(self, ml_data: dict):
        """
        [AI 학습용 상세 데이터 저장]
        - ml_data: 진입 시세, entry_지표(23개), 결과(PNL 등)가 포함된 딕셔너리
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                keys = list(ml_data.keys())
                placeholders = ", ".join(["?"] * len(keys))
                cols_str = ", ".join([f'"{k}"' for k in keys])
                
                # 제약 조건: 동일 시간/심볼/타임프레임/모드/레버리지/비중일 경우 업데이트
                conflict_keys = [
                    'signalTime', 'symbol', 'timeframe', 
                    'positionMode', 'leverage', 'marginRatio'
                ]
                
                # 업데이트할 컬럼 (제약 조건 키 제외)
                update_cols = [k for k in keys if k not in conflict_keys]
                update_str = ", ".join([f'"{k}"=excluded."{k}"' for k in update_cols])
                
                sql = f'''
                    INSERT INTO ml_trading_dataset ({cols_str}) VALUES ({placeholders})
                    ON CONFLICT({", ".join(conflict_keys)}) 
                    DO UPDATE SET {update_str}
                '''
                cursor.execute(sql, list(ml_data.values()))
                conn.commit()
                print(f"[ML SAVE] {ml_data['signalTime']} 학습 데이터 저장 완료.")
        except Exception as e:
            print(f"[ML SAVE ERROR] {e}")

    def save_opt_result(self, opt_data: dict):
        """
        [전략 랭킹용 요약 데이터 저장]
        - opt_data: 모드, 레버리지, 비중별 승률, PNL, MDD 등이 포함된 딕셔너리
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                keys = list(opt_data.keys())
                placeholders = ", ".join(["?"] * len(keys))
                cols_str = ", ".join([f'"{k}"' for k in keys])
                
                # 제약 조건: 모드/레버리지/비중 설정이 같으면 업데이트
                conflict_keys = ['positionMode', 'leverage', 'marginRatio']
                
                update_cols = [k for k in keys if k not in conflict_keys]
                update_str = ", ".join([f'"{k}"=excluded."{k}"' for k in update_cols])
                
                sql = f'''
                    INSERT INTO strategy_optimization ({cols_str}) VALUES ({placeholders})
                    ON CONFLICT({", ".join(conflict_keys)}) 
                    DO UPDATE SET {update_str}, testedAt=CURRENT_TIMESTAMP
                '''
                cursor.execute(sql, list(opt_data.values()))
                conn.commit()
                print(f"[OPT SAVE] 설정 {opt_data['positionMode']}/L{opt_data['leverage']} 성적 업데이트.")
        except Exception as e:
            print(f"[OPT SAVE ERROR] {e}")

    # --- 기존 기능 통합 및 개선 ---

    def refresh_indicators(self):
        """DB 전체 데이터를 재계산하여 업데이트"""
        with sqlite3.connect(self.db_path) as conn:
            query = f'SELECT * FROM "{self.symbol}" WHERE timeframe = ? ORDER BY time ASC'
            full_df = pd.read_sql(query, conn, params=(self.timeframe,))
        
        if full_df.empty: return
        full_df['time'] = pd.to_datetime(full_df['time'], unit='ms')
        full_df.set_index('time', inplace=True)
        
        # PyneCore 엔진 실행
        self.df = self._run_pynecore_engine(full_df)
        self.save_enriched_df(self.df)

    def update_data(self):
        """[개선됨] 빈 구간만 최신 데이터 수집 및 지표 업데이트"""
        # 1. DB의 마지막 시간을 확인하여 빠진 구간만 가져옵니다.
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f'SELECT MAX(time) FROM "{self.symbol}" WHERE timeframe = ?', (self.timeframe,))
                max_time = cursor.fetchone()[0]
        except Exception:
            max_time = None

        if max_time:
            # 마지막 데이터의 캔들 시작 시간부터 현재까지 가져옴
            klines = self._fetch_binance_klines(start_time=max_time, limit=500)
        else:
            klines = self._fetch_binance_klines(limit=500)

        # 2. Raw OHLCV 저장
        if klines:
            self._save_raw_ohlcv(klines)
        
        # 3. Whale 지표(224)를 고려하여 최근 500개 데이터로 연산 및 갱신
        latest_df = self.load_latest_from_db(limit=500)
        if latest_df is not None and len(latest_df) >= 224:
            # 엔진 연산
            calc_df = self._run_pynecore_engine(latest_df)
            self.save_enriched_df(calc_df)
            self.df = calc_df
            
        return self.df

    def sync_recent_data(self, required_limit=5000):
        """[개선됨] 최신순으로 점검하여 없는 시간대만 API 호출, 있으면 로드"""
        print(f"\n[CHECK] {self.symbol} ({self.timeframe}) 최신 데이터 상태 확인 중...")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # 최신 데이터 시간과 총 데이터 개수를 가져옴
                cursor.execute(f'SELECT MAX(time), COUNT(*) FROM "{self.symbol}" WHERE timeframe = ?', (self.timeframe,))
                row = cursor.fetchone()
                db_max_time = row[0]
                db_count = row[1]
        except Exception:
            db_max_time = None
            db_count = 0

        current_ts = int(datetime.now(timezone.utc).timestamp() * 1000)

        # 케이스 1: DB가 텅 비어있거나, 요구하는 limit보다 턱없이 부족할 때 (초기화 상태)
        if db_count < required_limit and db_max_time is None:
            print(f" >>> [API CALL] 데이터베이스가 비어있습니다. 초기 수집을 시작합니다.")
            fetch_end_time = current_ts
            total_fetched = 0
            while total_fetched < required_limit:
                klines = self._fetch_binance_klines(end_time=fetch_end_time, limit=1000)
                if not klines: break
                self._save_raw_ohlcv(klines)
                total_fetched += len(klines)
                fetch_end_time = klines[0][0] - 1
                time.sleep(0.1)

        # 케이스 2: DB에 데이터는 있지만, 최신 데이터가 밀려있을 때 (Gap 채우기)
        elif db_max_time is not None:
            tf_ms_map = {
                "1m": 60000,
                "15m": 900000,
                "30m": 1800000,
                "1h": 3600000,
                "4h": 14400000
            }
            tf_ms = tf_ms_map.get(self.timeframe, 60000)
            
            # 마지막 데이터와 현재 시간 사이에 캔들 1개 이상의 간격이 있다면 업데이트 진행
            if current_ts - db_max_time > tf_ms:
                print(f" >>> [API CALL] {self.symbol} 밀린 최신 데이터를 동기화합니다...")
                fetch_start_time = db_max_time
                while True:
                    klines = self._fetch_binance_klines(start_time=fetch_start_time, limit=1000)
                    if not klines or len(klines) <= 1: 
                        break # 업데이트 할 것이 없거나 마지막 캔들 하나만 겹칠 때
                    
                    self._save_raw_ohlcv(klines)
                    
                    # 가져온 데이터의 가장 마지막 시간을 다음 호출의 시작 시간으로 사용
                    fetch_start_time = klines[-1][0]
                    # 만약 가져온 데이터가 1000개 미만이라면 최신까지 다 가져온 것
                    if len(klines) < 1000:
                        break
                    time.sleep(0.1)
            else:
                print(f" >>> [OK] {self.symbol} 데이터가 이미 최신 상태입니다. (DB Load)")
                
        # 데이터베이스 전체 지표 갱신 (전체 계산이 너무 무거우면 이 부분을 제한하는 것도 고려해야 함)
        self.refresh_indicators()

    def sync_historical_data(self, start_days=730):
        """[유지 및 개선] 과거 데이터 방향(역방향)으로 없는 시간대만 호출"""
        target_ts = int((datetime.now(timezone.utc) - timedelta(days=start_days)).timestamp() * 1000)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # 저장된 가장 오래된 과거 시간을 확인
                cursor.execute(f'SELECT MIN(time) FROM "{self.symbol}" WHERE timeframe = ?', (self.timeframe,))
                db_min = cursor.fetchone()[0]
        except Exception: 
            db_min = None

        # 타겟 날짜보다 DB의 최소 시간이 더 최근이면(즉, 과거 데이터가 더 필요하면) 뒤로 거슬러 올라감
        if not db_min or db_min > target_ts:
            print(f" >>> [API CALL] {self.symbol} 과거 데이터 백필(Backfill)을 시작합니다. 목표일수: {start_days}일")
            current_ts = db_min - 1 if db_min else int(datetime.now(timezone.utc).timestamp() * 1000)
            
            while current_ts > target_ts:
                data = self._fetch_binance_klines(end_time=current_ts, limit=1000)
                if not data or len(data) <= 1: 
                    break
                self._save_raw_ohlcv(data)
                current_ts = data[0][0] - 1
                time.sleep(0.1)
                
            self.refresh_indicators()
        else:
            print(f" >>> [OK] {self.symbol} {start_days}일 치 과거 데이터가 이미 확보되어 있습니다.")
        
    # --- 유틸리티 메서드 ---

    def _fetch_binance_klines(self, start_time=None, end_time=None, limit=1000):
        endpoint = "/fapi/v1/klines"
        params = {"symbol": self.symbol, "interval": self.timeframe, "limit": limit}
        if start_time: params["startTime"] = start_time
        if end_time: params["endTime"] = end_time
        try:
            response = requests.get(self.base_url + endpoint, params=params, timeout=10)
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
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = f'SELECT * FROM "{self.symbol}" WHERE timeframe = ? ORDER BY time DESC LIMIT ?'
                df = pd.read_sql_query(query, conn, params=(self.timeframe, limit))
            if not df.empty:
                df['time'] = pd.to_datetime(df['time'], unit='ms')
                df.set_index('time', inplace=True)
                df = df.sort_index()
                self.df = df
                return df
        except: return None

    def get_chart_df(self, limit=5000):
        if self.df.empty: return pd.DataFrame()
        df_chart = self.df.tail(limit).reset_index()
        df_chart.columns = [str(c) for c in df_chart.columns]
        if 'time' in df_chart.columns:
            def safe_to_ms(x):
                if isinstance(x, (int, float, np.integer, np.floating)):
                    # 이미 유닉스 타임스탬프인 경우 (13자리 밀리초인지, 10자리 초 단위인지 판별)
                    return int(x) if x > 1e11 else int(x * 1000)
                elif hasattr(x, 'timestamp'):
                    return int(x.timestamp() * 1000)
                else:
                    return int(pd.to_datetime(x).timestamp() * 1000)

            df_chart['time'] = df_chart['time'].apply(safe_to_ms)
        return df_chart