import ccxt
import pandas as pd
import time
import sqlite3
import os
from datetime import datetime, timedelta, timezone

class CryptoDataFeed:
    def __init__(self, method="swap", symbol="BTC/USDT:USDT", timeframe="5m"):
        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange = ccxt.bitget({
            'options': {'defaultType': method},
            'enableRateLimit': True
        })
        self.df = pd.DataFrame()
        
        os.makedirs("market_data", exist_ok=True)
        self.db_path = "market_data/crypto_dashboard.db"
        self._init_db()
        
    def _init_db(self):
        """데이터베이스 테이블 생성 및 구조 보정"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # 1. 기본 테이블 생성 (이미 있으면 통과)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS "{self.symbol}" (
                    time INTEGER,
                    timeframe TEXT,
                    open REAL, high REAL, low REAL, close REAL, volume REAL,
                    PRIMARY KEY (time, timeframe)
                )
            """)
            
            # 2. bb_middle 등 부족한 지표 컬럼들이 있는지 확인하고 자동 추가
            required_columns = [
                ('kijun', 'REAL'), ('senkou_a', 'REAL'), ('senkou_b', 'REAL'),
                ('rsi', 'REAL'), ('macd_line', 'REAL'), ('macd_sig', 'REAL'),
                ('bb_upper', 'REAL'), ('bb_middle', 'REAL'), ('bb_lower', 'REAL'),
                ('master_long', 'INTEGER'), ('master_short', 'INTEGER'),
                ('top_detected', 'INTEGER'), ('bottom_detected', 'INTEGER')
            ]
            
            # 현재 테이블의 컬럼 정보 가져오기
            cursor.execute(f'PRAGMA table_info("{self.symbol}")')
            existing_cols = [row[1] for row in cursor.fetchall()]
            
            for col_name, col_type in required_columns:
                if col_name not in existing_cols:
                    try:
                        cursor.execute(f'ALTER TABLE "{self.symbol}" ADD COLUMN {col_name} {col_type}')
                        print(f"[DB INFO] 새 컬럼 추가됨: {col_name}")
                    except Exception as e:
                        print(f"[DB ERROR] 컬럼 추가 실패 ({col_name}): {e}")
            
            conn.commit()
            
    def _save_raw_ohlcv(self, ohlcv_list):
        """거래소에서 가져온 순수 OHLCV 리스트를 DB에 저장합니다 (지표는 NULL)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            data_to_insert = [
                (item[0], self.timeframe, item[1], item[2], item[3], item[4], item[5]) 
                for item in ohlcv_list
            ]
            # 명시적으로 순수 가격 데이터 컬럼만 지정하여 INSERT OR REPLACE 합니다.
            cursor.executemany(
                f'INSERT OR REPLACE INTO "{self.symbol}" (time, timeframe, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                data_to_insert
            )
            conn.commit()
    
    def save_enriched_df(self, df_with_indicators):
        """전략 지표가 계산된 DataFrame을 DB에 전체 덮어쓰기(UPSERT) 합니다."""
        temp_df = df_with_indicators.reset_index().copy()
        
        # 시간 포맷 변환 (ms)
        if 'time' in temp_df.columns and pd.api.types.is_datetime64_any_dtype(temp_df['time']):
            temp_df['time'] = (temp_df['time'].astype('int64') // 10**6)
            
        temp_df['timeframe'] = self.timeframe
        
        # 1. 불리언 신호를 정수(0, 1)로 변환
        bool_cols = [c for c in temp_df.columns if 'LONG' in c or 'SHORT' in c or 'DETECTED' in c]
        for col in bool_cols:
            temp_df[col] = temp_df[col].fillna(False).astype(int)

        # 2. pine_data.py 컬럼명을 DB 스키마 컬럼명으로 매핑
        rename_map = {
            'RSI_14': 'rsi', 'MACD_line': 'macd_line', 'MACD_signal': 'macd_sig',
            'BB_upper': 'bb_upper', 'BB_middle': 'bb_middle', 'BB_lower': 'bb_lower',
            'MASTER_LONG': 'master_long', 'MASTER_SHORT': 'master_short',
            'TOP_DETECTED': 'top_detected', 'BOTTOM_DETECTED': 'bottom_detected'
        }
        temp_df = temp_df.rename(columns=rename_map)

        # 3. DB에 존재하는 컬럼만 추출 (안전장치)
        db_cols = [
            'time', 'timeframe', 'open', 'high', 'low', 'close', 'volume',
            'kijun', 'senkou_a', 'senkou_b', 'rsi', 'macd_line', 'macd_sig',
            'bb_upper', 'bb_middle', 'bb_lower', 'master_long', 'master_short',
            'top_detected', 'bottom_detected'
        ]
        temp_df = temp_df[[c for c in temp_df.columns if c in db_cols]]

        # 4. DB 덮어쓰기 실행
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            columns = ", ".join([f'"{c}"' for c in temp_df.columns])
            placeholders = ", ".join(["?"] * len(temp_df.columns))
            sql = f'INSERT OR REPLACE INTO "{self.symbol}" ({columns}) VALUES ({placeholders})'
            
            cursor.executemany(sql, temp_df.values.tolist())
            conn.commit()
            print(f"[{self.symbol}] {len(temp_df)}행 지표 DB 업데이트 완료.")
            
    def initialize_data(self, days=90):
        """과거 데이터를 수집하고 DB에 저장합니다."""
        print(f"[{self.symbol}] 과거 {days}일치 데이터 수집 및 DB 저장 시작...")
        now_utc = datetime.now(timezone.utc)
        since = int((now_utc - timedelta(days=days)).timestamp() * 1000)
        
        while True:
            try:
                ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, since=since, limit=1000)
                if not ohlcv: break
                
                # 순수 가격 데이터 DB 저장
                self._save_raw_ohlcv(ohlcv)
                
                since = ohlcv[-1][0] + 1
                print(f"DB 저장 중... 마지막 캔들 시간: {pd.to_datetime(ohlcv[-1][0], unit='ms')}", end='\r')
                
                if ohlcv[-1][0] >= int(time.time() * 1000) - 300000: break
                time.sleep(0.1)
            except Exception as e:
                print(f"\n에러 발생: {e}. 재시도 중...")
                time.sleep(5)

        self.load_latest_from_db()
            
    def load_latest_from_db(self, limit=5000):
        """조회 시 현재 설정된 timeframe과 일치하는 데이터만 가져옵니다."""
        with sqlite3.connect(self.db_path) as conn:
            query = f"""
                SELECT * FROM "{self.symbol}" 
                WHERE timeframe = '{self.timeframe}' 
                ORDER BY time DESC LIMIT {limit}
            """
            df = pd.read_sql(query, conn)
            
            df = df.sort_values('time')
            df['time'] = pd.to_datetime(df['time'], unit='ms')
            df.set_index('time', inplace=True)
            self.df = df.drop(columns=['timeframe'], errors='ignore')
            return self.df
        
    def update_data(self):
        """실시간 가격 업데이트용"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=5)
            self._save_raw_ohlcv(ohlcv)
            self.load_latest_from_db()
            return self.df
        except Exception as e:
            print(f"실시간 업데이트 에러: {e}")
            return self.df
        
    def get_chart_df(self):
        return self.df.reset_index()