from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import uvicorn
import sqlite3
import pandas as pd
import numpy as nps
import os

from data_process.load_data import CryptoDataFeed
from data_process.pine_data import apply_master_strategy
from services.chat_services import convert_df_to_chart_data

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_folder = os.path.join(base_dir, "backend", "market_data")
db_path = os.path.join(db_folder, "crypto_dashboard.db")
print(db_path)

# [1] Lifespan: 서버 가동 시 상태 메시지 출력
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "="*60)
    print("Crypto Trading Dashboard API 서버 가동")
    print("데이터베이스: market_data/crypto_dashboard.db")
    print("="*60 + "\n")
    yield
    print("\n서버를 안전하게 종료합니다.")

app = FastAPI(title="Crypto Trading Dashboard API", lifespan=lifespan)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# [2] 백그라운드 작업: 과거 데이터 백필
def backfill_historical_data(symbol: str, timeframe: str, start_days: int, end_days: int):
    print(f"\n[BACKGROUND 🛠️] 데이터 동기화: {start_days}일 전 ~ {end_days}일 전")
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    feed.initialize_data(start_days=start_days, end_days=end_days)
    print(f"[BACKGROUND ✅] {symbol} ({timeframe}) 데이터 구축 완료")

# [3] API: 과거 히스토리 조회 (지표 누락 자동 감지 및 복구 포함)
@app.get("/api/history")
async def get_history(
    background_tasks: BackgroundTasks,
    symbol: str = Query("BTC/USDT:USDT"), 
    timeframe: str = Query("5m"), 
    days: int = Query(90) 
):
    tf_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
    minutes = tf_map.get(timeframe, 5)
    required_quick_days = max(round((5000 * minutes) / 1440), 1)
    quick_load_days = min(days, required_quick_days)

    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    
    # 1. DB에서 최신 데이터 로드
    current_df = feed.load_latest_from_db(limit=5000)
    
    if current_df.empty:
        # 데이터가 아예 없으면 초기 구축
        feed.initialize_data(start_days=quick_load_days, end_days=0)
    else:
        # 🎯 [방법 2 핵심] 데이터는 있는데 지표(RSI)가 NULL인 행이 있는지 확인
        # (과거에 가격만 저장된 데이터를 찾아 복구합니다)
        if 'rsi' not in current_df.columns or current_df['rsi'].isnull().any():
            print(f"[{timeframe}] 지표 누락 감지! 자동 복구 계산을 시작합니다...")
            # 메모리 상에서 지표 재계산
            feed.df = apply_master_strategy(current_df)
            # 계산된 결과를 DB에 다시 덮어쓰기 (무손실 업데이트)
            feed.save_enriched_df(feed.df)
            print(f"[{timeframe}] 지표 복구 및 DB 저장 완료")

    # 2. 전송용 데이터 변환
    chart_json = convert_df_to_chart_data(feed.df)
    
    # 3. 부족한 기간 백그라운드 채우기
    if days > quick_load_days:
        background_tasks.add_task(backfill_historical_data, symbol, timeframe, days, quick_load_days)
    
    return chart_json

# [4] WebSocket: 실시간 데이터 동기화
@app.websocket("/ws/chart")
async def websocket_endpoint(
    websocket: WebSocket,
    symbol: str = "BTC/USDT:USDT",
    timeframe: str = "5m"
):
    await websocket.accept()
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    feed.load_latest_from_db(limit=300)
    
    print(f"[WS 🟢] 실시간 스트리밍 시작: {symbol} ({timeframe})")
    
    try:
        while True:
            updated_df = feed.update_data()
            latest_data = convert_df_to_chart_data(updated_df.tail(2))
            await websocket.send_json(latest_data)
            await asyncio.sleep(5)
            
    except WebSocketDisconnect:
        print(f"[WS ⚪] 연결 종료: {symbol}")
    except Exception as e:
        print(f"[WS 🔴] 에러 발생: {e}")

# [5] API: DB 상태 점검 (JSON 데이터 샘플 포함)
@app.get("/api/db-status")
async def get_db_status(symbol: str = "BTC/USDT:USDT", timeframe: str = "15m"):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_folder = os.path.join(base_dir, "backend", "market_data")
    db_path = os.path.join(db_folder, "crypto_dashboard.db")
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row # 결과를 딕셔너리 형태로 받기 위해 설정
            cursor = conn.cursor()
            
            # 1. 전체 통계
            cursor.execute(f'SELECT COUNT(*) as count, MIN(time) as min_t, MAX(time) as max_t FROM "{symbol}" WHERE timeframe = ?', (timeframe,))
            stats = cursor.fetchone()
            
            # 2. 실제 데이터 샘플 (최신 5행)
            cursor.execute(f'SELECT * FROM "{symbol}" WHERE timeframe = ? ORDER BY time DESC LIMIT 5', (timeframe,))
            samples = [dict(row) for row in cursor.fetchall()]
            
            # 읽기 쉬운 시간 형식 추가
            for s in samples:
                s['datetime_readable'] = str(pd.to_datetime(s['time'], unit='ms'))

            return {
                "db_path": db_path,
                "symbol": symbol,
                "timeframe": timeframe,
                "total_rows": stats['count'],
                "oldest_data": str(pd.to_datetime(stats['min_t'], unit='ms')) if stats['min_t'] else None,
                "newest_data": str(pd.to_datetime(stats['max_t'], unit='ms')) if stats['max_t'] else None,
                "latest_samples": samples, # 실제 저장된 값들을 JSON으로 확인 가능
                "status": "Healthy"
            }
    except Exception as e:
        return {"error": str(e), "message": "데이터베이스 조회 중 오류 발생"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)