import ccxt
import pandas as pd
import numpy as np
import time
import sqlite3
import os
from datetime import datetime, timedelta, timezone
from data_process.pine_data import apply_master_strategy

class CryptoDataFeed:
    def __init__(self, method="swap", symbol="BTC/USDT:USDT", timeframe="5m"):
        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange = ccxt.bitget({
            'options': {'defaultType': method},
            'enableRateLimit': True
        })
        self.df = pd.DataFrame()
        
        # 🎯 [수정] 실행 위치와 상관없이 'backend/market_data' 폴더를 가리키도록 절대 경로 설정
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_folder = os.path.join(base_dir, "market_data")
        os.makedirs(db_folder, exist_ok=True)
        self.db_path = os.path.join(db_folder, "crypto_dashboard.db")
        
        print(f"DB 연결 경로: {self.db_path}") # 경로 확인용 로그
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS "{self.symbol}" (
                    time INTEGER,
                    timeframe TEXT,
                    open REAL, high REAL, low REAL, close REAL, volume REAL,
                    PRIMARY KEY (time, timeframe)
                )
            """)
            
            # 🎯 mfi 컬럼도 추가 리스트에 포함시킴
            required_columns = [
                ('kijun', 'REAL'), ('senkou_a', 'REAL'), ('senkou_b', 'REAL'),
                ('rsi', 'REAL'), ('macd_line', 'REAL'), ('macd_sig', 'REAL'),
                ('bb_upper', 'REAL'), ('bb_middle', 'REAL'), ('bb_lower', 'REAL'),
                ('mfi', 'REAL'), # 추가
                ('master_long', 'INTEGER'), ('master_short', 'INTEGER'),
                ('top_detected', 'INTEGER'), ('bottom_detected', 'INTEGER')
            ]
            
            cursor.execute(f'PRAGMA table_info("{self.symbol}")')
            existing_cols = [row[1] for row in cursor.fetchall()]
            
            for col_name, col_type in required_columns:
                if col_name not in existing_cols:
                    try:
                        cursor.execute(f'ALTER TABLE "{self.symbol}" ADD COLUMN {col_name} {col_type}')
                    except Exception as e:
                        pass
            conn.commit()
            
    def _save_raw_ohlcv(self, ohlcv_list):
        """기존 지표를 보호하기 위해 IGNORE를 사용합니다."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            data_to_insert = [(item[0], self.timeframe, item[1], item[2], item[3], item[4], item[5]) for item in ohlcv_list]
            # 🎯 REPLACE 대신 IGNORE를 사용해야 기존 지표가 NULL로 날아가지 않습니다.
            cursor.executemany(
                f'INSERT OR IGNORE INTO "{self.symbol}" (time, timeframe, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                data_to_insert
            )
            conn.commit()
    
    def save_enriched_df(self, df_with_indicators):
        """지표가 포함된 데이터를 안전하게 업데이트합니다."""
        if df_with_indicators.empty: return
        try:
            temp_df = df_with_indicators.reset_index().copy()
            temp_df.columns = [str(c).lower() for c in temp_df.columns]
            
            # 시간 포맷 변환
            if 'time' in temp_df.columns:
                print("→ time 컬럼 존재")
                # 어떤 형식이든 pd.to_datetime으로 바꾼 뒤 ms 정수로 변환
                temp_df['time'] = pd.to_datetime(temp_df['time'])
                temp_df['time'] = temp_df['time'].astype('int64') // 10**6
                
            temp_df['timeframe'] = self.timeframe
            temp_df = temp_df.replace([np.inf, -np.inf], np.nan)
            
            # 불리언 변환 및 NaN/Inf 처리
            bool_cols = ['master_long', 'master_short', 'top_detected', 'bottom_detected']
            for col in bool_cols:
                if col in temp_df.columns:
                    temp_df[col] = temp_df[col].fillna(False).astype(int)

            db_cols = [
                'time', 'timeframe', 'open', 'high', 'low', 'close', 'volume',
                'kijun', 'senkou_a', 'senkou_b', 'rsi', 'macd_line', 'macd_sig',
                'bb_upper', 'bb_middle', 'bb_lower', 'master_long', 'master_short',
                'top_detected', 'bottom_detected'
            ]
            
            # 누락된 컬럼 보정
            for col in db_cols:
                if col not in temp_df.columns:
                    temp_df[col] = None
            
            final_df = temp_df[db_cols].where(pd.notnull(temp_df[db_cols]), None)
            data_list = final_df.values.tolist()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cols_str = ", ".join([f'"{c}"' for c in db_cols])
                placeholders = ", ".join(["?"] * len(db_cols))
                
                # 업데이트할 대상 (PK 제외)
                update_cols = [c for c in db_cols if c not in ['time', 'timeframe']]
                update_str = ", ".join([f'"{c}"=excluded."{c}"' for c in update_cols])
                
                sql = f'''
                    INSERT INTO "{self.symbol}" ({cols_str})
                    VALUES ({placeholders})
                    ON CONFLICT(time, timeframe) DO UPDATE SET {update_str}
                '''
                cursor.executemany(sql, data_list)
                conn.commit()
                print(f"[{self.timeframe}] {len(data_list)}행 UPSERT 성공")
        except Exception as e:
            print(f"DB 저장 에러: {e}")
            
    def initialize_data(self, start_days=365, end_days=0):
        if start_days <= end_days: 
            return

        print(f"[{self.symbol}] 데이터 수집 시작...")
        now_utc = datetime.now(timezone.utc)
        since = int((now_utc - timedelta(days=start_days)).timestamp() * 1000)
        end_ts = int((now_utc - timedelta(days=end_days)).timestamp() * 1000)
        
        while True:
            try:
                ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, since=since, limit=1000)
                if not ohlcv: break
                
                self._save_raw_ohlcv(ohlcv)
                since = ohlcv[-1][0] + 1
                
                if ohlcv[-1][0] >= end_ts - 300000: break
                time.sleep(0.1)
            except Exception as e:
                time.sleep(3)

        self.load_latest_from_db(limit=100000)
        if not self.df.empty:
            self.df = apply_master_strategy(self.df)
            self.save_enriched_df(self.df)
            print("과거 데이터 지표 구축 완료.")
            
    def load_latest_from_db(self, limit=5000):
        with sqlite3.connect(self.db_path) as conn:
            query = f"""
                SELECT * FROM "{self.symbol}" 
                WHERE timeframe = '{self.timeframe}' 
                ORDER BY time DESC LIMIT {limit}
            """
            df = pd.read_sql(query, conn)
            
            if df.empty:
                self.df = pd.DataFrame()
                return self.df
                
            df = df.sort_values('time')
            df['time'] = pd.to_datetime(df['time'], unit='ms')
            df.set_index('time', inplace=True)
            
            # 숫자형 변환 강제 (에러 방지)
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
            
            self.df = df.drop(columns=['timeframe'], errors='ignore')
            return self.df
        
    def update_data(self):
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=20)
            self._save_raw_ohlcv(ohlcv)
            self.load_latest_from_db(limit=300)
            
            if not self.df.empty and len(self.df) > 60:
                # 🎯 전략 실행
                self.df = apply_master_strategy(self.df)
                
                # ================= [디버깅 로그 시작] =================
                print(f"\n{"-"*20} [MEMORY DEBUG] {"-"*20}")
                print(f"타임프레임: {self.timeframe} | 현재 메모리 행 수: {len(self.df)}")
                
                # 주요 지표의 최신 1행 값 출력
                last_row = self.df.iloc[-1]
                print(f"마지막 시간: {self.df.index[-1]}")
                print(f"가격: {last_row['close']:.2f}")
                print(f"RSI: {last_row.get('rsi', 'N/A')} | MACD: {last_row.get('macd_line', 'N/A')}")
                
                # NaN 개수 확인 (0이 아니면 계산 로직 문제)
                null_counts = self.df[['rsi', 'macd_line', 'kijun']].isnull().sum()
                print(f"NaN(누락) 개수: RSI({null_counts['rsi']}), MACD({null_counts['macd_line']}), KIJUN({null_counts['kijun']})")
                print(f"{"-"*56}\n")
                # ================= [디버깅 로그 끝] =================

                self.save_enriched_df(self.df)
                
            return self.df
        except Exception as e:
            import traceback
            print(f"❌ 실시간 업데이트 에러: {e}")
            traceback.print_exc()
            return self.df
        
    def get_chart_df(self):
        return self.df.reset_index()