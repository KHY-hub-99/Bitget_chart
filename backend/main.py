from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import uvicorn
import sqlite3

from data_process.load_data import CryptoDataFeed
from services.chat_services import convert_df_to_chart_data

# 최신 Lifespan 방식: 서버 시작/종료 로직 관리
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "="*50)
    print("Crypto Trading Dashboard 서버 가동 중...")
    print("SQLite DB 경로 확인: market_data/crypto_dashboard.db")
    print("="*50 + "\n")
    yield
    print("서버를 종료합니다.")

app = FastAPI(title="Crypto Trading Dashboard API", lifespan=lifespan)

# CORS 설정 (프론트엔드 통신 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://127.0.0.1:5173"
    ], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def backfill_historical_data(symbol: str, timeframe: str, start_days: int, end_days: int):
    print(f"\n[BACKGROUND] 과거 데이터 채우기 시작 ({start_days}일 전 ~ {end_days}일 전)")
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    
    # 수정됨: initialize_data 내부에 이미 수집+지표계산+DB저장 로직이 모두 포함됨
    feed.initialize_data(start_days=start_days, end_days=end_days)
    print(f"\n[BACKGROUND] 과거 데이터 백필 및 지표 최적화 완료")

@app.get("/api/history")
async def get_history(
    background_tasks: BackgroundTasks,
    symbol: str = Query("BTC/USDT:USDT"), 
    timeframe: str = Query("5m"), 
    days: int = Query(90) 
):
    """사용자 선택값에 따른 차트 데이터 반환 (자동화된 데이터 구축 포함)"""
    tf_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
    minutes = tf_map.get(timeframe, 5)
    
    required_quick_days = max(round((5000 * minutes) / 1440), 1)
    quick_load_days = min(days, required_quick_days)

    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    
    # 1. DB에 데이터가 있는지 확인
    current_df = feed.load_latest_from_db(limit=1)
    
    # 2. 데이터가 아예 없다면 초기 구축 (수집+계산+저장 자동 실행)
    if current_df.empty:
        feed.initialize_data(start_days=quick_load_days, end_days=0)
    else:
        # 데이터가 있다면 차트에 보여줄 만큼만 로드
        feed.load_latest_from_db(limit=5000)
    
    # 3. 프론트엔드로 전송
    chart_json = convert_df_to_chart_data(feed.df)
    
    # 4. 백그라운드 작업: 사용자가 더 긴 기간을 원했다면 빈 구간 채우기
    if days > quick_load_days:
        background_tasks.add_task(backfill_historical_data, symbol, timeframe, days, quick_load_days)
    
    return chart_json

@app.websocket("/ws/chart")
async def websocket_endpoint(
    websocket: WebSocket,
    symbol: str = "BTC/USDT:USDT",
    timeframe: str = "5m"
):
    """실시간 데이터 스트리밍 (지능형 업데이트)"""
    await websocket.accept()
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    
    print(f"[WS] 실시간 지표 계산 모드 가동: {symbol} ({timeframe})")
    
    try:
        while True:
            # [최신 5개 수집 -> 과거 300개 로드 -> 지표 계산 -> DB 저장]을 전부 알아서 처리함
            updated_df = feed.update_data()
            
            # 최신 2개 캔들만 추출하여 프론트로 실시간 전송
            latest_data = convert_df_to_chart_data(updated_df.tail(2))
            await websocket.send_json(latest_data)
            
            # 업데이트 간격 5초
            await asyncio.sleep(5)
            
    except WebSocketDisconnect:
        print(f"[WS] 연결 종료: {symbol}")
    except Exception as e:
        print(f"[WS] 에러 발생: {e}")
        
@app.get("/api/db-status")
async def get_db_status(symbol: str = "BTC/USDT:USDT"):
    """데이터베이스에 저장된 데이터 개수를 확인합니다."""
    db_path = "market_data/crypto_dashboard.db"
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f'SELECT COUNT(*) FROM "{symbol}"')
            count = cursor.fetchone()[0]
            
            cursor.execute(f'SELECT MIN(time), MAX(time) FROM "{symbol}"')
            min_time, max_time = cursor.fetchone()
            
            import pandas as pd
            return {
                "symbol": symbol,
                "total_rows": count,
                "oldest_data": str(pd.to_datetime(min_time, unit='ms')) if min_time else None,
                "newest_data": str(pd.to_datetime(max_time, unit='ms')) if max_time else None
            }
    except Exception as e:
        return {"error": str(e), "message": "테이블이 없거나 조회할 수 없습니다."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)