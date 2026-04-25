from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import uvicorn
import sqlite3
import pandas as pd

from data_process.load_data import CryptoDataFeed
from services.chat_services import convert_df_to_chart_data

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
    print(f"\n[BACKGROUND] 데이터 동기화: {start_days}일 전 ~ {end_days}일 전")
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    
    # initialize_data 내부에서 [수집 -> 지표계산 -> DB저장]을 자동 처리
    feed.initialize_data(start_days=start_days, end_days=end_days)
    print(f"[BACKGROUND] {symbol} ({timeframe}) 데이터 구축 완료")

# [3] API: 과거 히스토리 조회
@app.get("/api/history")
async def get_history(
    background_tasks: BackgroundTasks,
    symbol: str = Query("BTC/USDT:USDT"), 
    timeframe: str = Query("5m"), 
    days: int = Query(90) 
):
    """지표가 포함된 완성된 차트 데이터를 반환"""
    # 쾌속 로딩 기간 계산 (차트를 즉시 띄우기 위한 최소 분량)
    tf_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
    minutes = tf_map.get(timeframe, 5)
    required_quick_days = max(round((5000 * minutes) / 1440), 1)
    quick_load_days = min(days, required_quick_days)

    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    
    # 1. DB 존재 여부 확인
    current_df = feed.load_latest_from_db(limit=1)
    
    # 2. 데이터가 없으면 즉시 초기 구축 (자동 지표 계산 포함)
    if current_df.empty:
        feed.initialize_data(start_days=quick_load_days, end_days=0)
    else:
        # 데이터가 있으면 차트용 데이터 로드 (변수명은 load_latest_from_db에서 이미 정제됨)
        feed.load_latest_from_db(limit=5000)
    
    # 3. 프론트엔드 표준 규격으로 변환하여 전송
    chart_json = convert_df_to_chart_data(feed.df)
    
    # 4. 사용자가 요청한 전체 기간(days) 중 부족한 부분은 백그라운드에서 채움
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
    """5초마다 지표를 재계산하고 DB를 갱신하며 실시간 전송"""
    await websocket.accept()
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    
    # 지표 계산용 초기 버퍼 로드
    feed.load_latest_from_db(limit=300)
    
    print(f"[WS 🟢] 실시간 스트리밍 시작: {symbol} ({timeframe})")
    
    try:
        while True:
            # 🎯 수정된 로직: update_data가 [수집 -> 계산 -> DB저장]을 원스톱으로 처리
            updated_df = feed.update_data()
            
            # 최신 2개 데이터를 표준 규격으로 변환하여 실시간 전송
            latest_data = convert_df_to_chart_data(updated_df.tail(2))
            await websocket.send_json(latest_data)
            
            await asyncio.sleep(5)
            
    except WebSocketDisconnect:
        print(f"[WS ⚪] 연결 종료: {symbol}")
    except Exception as e:
        print(f"[WS 🔴] 에러 발생: {e}")

# [5] API: DB 상태 점검
@app.get("/api/db-status")
async def get_db_status(symbol: str = "BTC/USDT:USDT"):
    db_path = "market_data/crypto_dashboard.db"
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'SELECT COUNT(*) FROM "{symbol}"')
            count = cursor.fetchone()[0]
            
            cursor.execute(f'SELECT MIN(time), MAX(time) FROM "{symbol}"')
            min_time, max_time = cursor.fetchone()
            
            return {
                "symbol": symbol,
                "total_rows": count,
                "oldest_data": str(pd.to_datetime(min_time, unit='ms')) if min_time else None,
                "newest_data": str(pd.to_datetime(max_time, unit='ms')) if max_time else None,
                "status": "Healthy"
            }
    except Exception as e:
        return {"error": str(e), "message": "데이터베이스를 조회할 수 없습니다."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)