import ccxt
import pandas as pd
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
        """거래소에서 가져온 순수 OHLCV 리스트를 DB에 저장합니다."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            data_to_insert = [
                (item[0], self.timeframe, item[1], item[2], item[3], item[4], item[5]) 
                for item in ohlcv_list
            ]
            cursor.executemany(
                f'INSERT OR REPLACE INTO "{self.symbol}" (time, timeframe, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                data_to_insert
            )
            conn.commit()
    
    def save_enriched_df(self, df_with_indicators):
        """전략 지표가 계산된 DataFrame을 DB에 전체 덮어쓰기(UPSERT) 합니다."""
        if df_with_indicators.empty:
            return
            
        temp_df = df_with_indicators.reset_index().copy()
        
        # 🎯 [핵심] 모든 컬럼명을 소문자로 강제 통일 (대소문자 충돌 원천 차단)
        temp_df.columns = [str(c).lower() for c in temp_df.columns]
        
        # 시간 포맷 변환 (ms)
        if 'time' in temp_df.columns and pd.api.types.is_datetime64_any_dtype(temp_df['time']):
            temp_df['time'] = (temp_df['time'].astype('int64') // 10**6)
            
        temp_df['timeframe'] = self.timeframe
        
        # 1. 불리언 신호를 정수(0, 1)로 변환
        bool_cols = ['master_long', 'master_short', 'top_detected', 'bottom_detected']
        for col in bool_cols:
            if col in temp_df.columns:
                temp_df[col] = temp_df[col].fillna(False).astype(int)

        # 2. SQLite가 처리할 수 없어서 None 에러를 내뿜는 NaN 값을 순수 None으로 변환
        import numpy as np
        temp_df = temp_df.replace({np.nan: None})

        # 3. DB 스키마에 존재하는 표준 컬럼만 안전하게 추출
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
            
    def initialize_data(self, start_days=90, end_days=0):
        """과거 데이터를 수집한 뒤, 지표를 즉시 계산하여 DB에 완성본을 저장합니다."""
        if start_days <= end_days: 
            return

        print(f"[{self.symbol}] 데이터 수집: {start_days}일 전 ~ {end_days}일 전...")
        now_utc = datetime.now(timezone.utc)
        since = int((now_utc - timedelta(days=start_days)).timestamp() * 1000)
        end_ts = int((now_utc - timedelta(days=end_days)).timestamp() * 1000)
        
        while True:
            try:
                ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, since=since, limit=1000)
                if not ohlcv: break
                
                # 순수 가격 데이터 DB 저장
                self._save_raw_ohlcv(ohlcv)
                
                since = ohlcv[-1][0] + 1
                print(f"DB 저장 중... 마지막 캔들: {pd.to_datetime(ohlcv[-1][0], unit='ms')}", end='\r')
                
                if ohlcv[-1][0] >= end_ts - 300000: break
                time.sleep(0.1)
            except Exception as e:
                print(f"\n에러 발생: {e}. 재시도 중...")
                time.sleep(3)

        print(f"\n[{self.symbol}] 구간 수집 완료. 지표 일괄 계산 및 저장 시작...")
        
        # 10만 개 정도 넉넉히 불러와서 누락 없이 전체 지표 맵핑
        self.load_latest_from_db(limit=100000)
        
        if not self.df.empty:
            print(f"{len(self.df)}행 전체 지표 계산 중...")
            self.df = apply_master_strategy(self.df)
            
            print("완성된 지표를 DB에 업데이트 중...")
            self.save_enriched_df(self.df)
            print("과거 데이터 구축 및 지표 저장 완벽 종료.")
            
    def load_latest_from_db(self, limit=5000):
        """조회 시 현재 설정된 timeframe과 일치하는 데이터만 가져옵니다."""
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
            self.df = df.drop(columns=['timeframe'], errors='ignore')
            return self.df
        
    def update_data(self):
        """실시간 가격 업데이트 및 자동 지표 재계산"""
        try:
            # 1. 거래소에서 최신 5개 데이터 수집 및 순수 가격 저장
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=5)
            self._save_raw_ohlcv(ohlcv)
            
            # 2. [추가된 핵심 로직] 지표 계산에 필요한 충분한 과거 데이터(Lookback Window) 로드
            # 300개 정도면 RSI(14)와 일목균형표(52)를 계산하기에 충분히 넉넉함
            self.load_latest_from_db(limit=300)
            
            if not self.df.empty:
                # 3. 전체 버퍼 데이터를 대상으로 지표 계산 (None 발생 원천 차단)
                self.df = apply_master_strategy(self.df)
                
                # 4. 새로 계산된 최신 데이터(꼬리 부분 5개)만 DB에 업데이트해서 I/O 최적화
                self.save_enriched_df(self.df.tail(5))
                
            return self.df
        except Exception as e:
            print(f"실시간 업데이트 에러: {e}")
            return self.df
        
    def get_chart_df(self):
        return self.df.reset_index()