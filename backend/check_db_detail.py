import os
import sqlite3
import pandas as pd

# 설정
current_dir = os.getcwd()
db_folder = os.path.join(current_dir, "backend", "market_data")
db_path = os.path.join(db_folder, "crypto_dashboard.db")
symbol = "BTC/USDT:USDT"

def check_database_detail():
    try:
        with sqlite3.connect(db_path) as conn:
            print(f"\n{'='*60}")
            print(f"[{symbol}] 데이터베이스 정밀 점검 결과")
            print(f"{'='*60}")

            # 1. 타임프레임별 저장 개수 확인
            print("\n[1] 타임프레임별 저장 현황")
            query_count = f'SELECT timeframe, COUNT(*) as count FROM "{symbol}" GROUP BY timeframe'
            df_counts = pd.read_sql(query_count, conn)
            print(df_counts.to_string(index=False))

            # 2. 최신 데이터 3행 샘플 확인 (값이 제대로 들어갔는지 검증)
            print("\n[2] 최신 데이터 3행 샘플 (지표 포함)")
            query_sample = f'SELECT * FROM "{symbol}" ORDER BY time DESC LIMIT 3'
            df_sample = pd.read_sql(query_sample, conn)
            
            # 시간 포맷 변환 (읽기 편하게)
            df_sample['time'] = pd.to_datetime(df_sample['time'], unit='ms')
            
            # 출력할 주요 컬럼 선택 (너무 많으면 잘리므로 핵심 위주)
            cols = ['time', 'timeframe', 'open', 'close', 'rsi', 'macd_line', 'kijun', 'senkou_a']
            # 실제로 존재하는 컬럼만 필터링
            available_cols = [c for c in cols if c in df_sample.columns]
            
            print(df_sample[available_cols].to_string(index=False))

            # 3. NULL 값 존재 여부 체크
            print("\n[3] 지표 누락(NULL) 점검")
            null_check_cols = ['rsi', 'macd_line', 'kijun']
            for col in null_check_cols:
                if col in df_sample.columns:
                    cursor = conn.cursor()
                    cursor.execute(f'SELECT COUNT(*) FROM "{symbol}" WHERE "{col}" IS NULL')
                    null_count = cursor.fetchone()[0]
                    status = "정상" if null_count == 0 else f"{null_count}개 누락"
                    print(f" - {col.upper()}: {status}")

            print(f"\n{'='*60}\n")

    except Exception as e:
        print(f"점검 중 오류 발생: {e}")

if __name__ == "__main__":
    check_database_detail()