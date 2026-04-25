from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import uvicorn
import sqlite3
import pandas as pd
import numpy as np
import os

from data_process.load_data import CryptoDataFeed
from services.chat_services import convert_df_to_chart_data

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_folder = os.path.join(base_dir, "backend", "market_data")
db_path = os.path.join(db_folder, "crypto_dashboard.db")

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

# [2] 백그라운드 작업: 과거 데이터 대량 백필 (바이낸스 기준)
def backfill_historical_data(symbol: str, timeframe: str, start_days: int):
    print(f"\n[BACKGROUND] 데이터 전체 동기화 시작: 과거 {start_days}일치\n")
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    feed.initialize_data(start_days=start_days)
    print(f"\n[BACKGROUND] {symbol} ({timeframe}) 데이터 구축 및 지표 계산 완료\n")

# [3] API: 과거 히스토리 조회 및 차트 데이터 반환
@app.get("/api/history")
async def get_history(
    background_tasks: BackgroundTasks,
    symbol: str = Query("BTCUSDT"),  # 바이낸스 심볼 규격으로 변경
    timeframe: str = Query("15m"),   # 15분봉 기본값
    days: int = Query(365)            # 기본 요청 일수
):
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    
    # 1. DB에서 데이터 로드 (넉넉히 로드)
    feed.load_latest_from_db(limit=5000)
    
    if feed.df.empty:
        # 데이터가 아예 없으면 즉시 초기 구축 (이때는 기다려야 함)
        print(f"[{symbol}] DB가 비어있어 초기 구축을 시작합니다. (약 10~20초 소요)")
        feed.initialize_data(start_days=days)
    else:
        # 🎯 데이터는 있는데 지표(RSI 등)가 NULL인 경우 감지
        if 'rsi' not in feed.df.columns or feed.df['rsi'].isnull().all():
            print(f"[{timeframe}] 지표 누락 감지! 전체 재계산(refresh_indicators)을 시작합니다...")
            feed.refresh_indicators()
            feed.load_latest_from_db(limit=5000) # 재계산 후 다시 로드
            
        # 모자란 데이터가 있다면 백그라운드에서 조용히 수집 (UX 방해 X)
        # 예: 현재 5일치만 있는데 30일치를 원할 경우
        # (바이낸스는 빠르기 때문에 그냥 background task로 넘겨버립니다)
        background_tasks.add_task(backfill_historical_data, symbol, timeframe, days)

    # 2. [핵심] 차트 렌더링용으로 데이터 정제 (시간 10자리 변환 및 최신 N개 슬라이싱)
    # CryptoDataFeed에 추가하신 get_chart_df 메서드를 사용합니다.
    chart_df = feed.get_chart_df()
    
    # 3. 전송용 JSON 데이터 변환
    # 만약 convert_df_to_chart_data 함수가 내부적으로 포맷팅을 해준다면 그대로 사용합니다.
    chart_json = convert_df_to_chart_data(chart_df)
    
    return chart_json

# [4] WebSocket: 실시간 데이터 동기화
@app.websocket("/ws/chart")
async def websocket_endpoint(
    websocket: WebSocket,
    symbol: str = "BTCUSDT",
    timeframe: str = "15m"
):
    await websocket.accept()
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    
    print(f"[WS 🟢] 실시간 스트리밍 시작: {symbol} ({timeframe})")
    
    try:
        while True:
            # 1. 바이낸스에서 최신 가격 업데이트 및 지표 재계산
            feed.update_data()
            
            # 2. 프론트엔드 포맷(10자리 시간)으로 최신 2~3개 캔들만 추출
            latest_chart_df = feed.get_chart_df(limit=2)
            
            # 3. JSON 변환 및 전송
            latest_data = convert_df_to_chart_data(latest_chart_df)
            await websocket.send_json(latest_data)
            
            # 5초마다 갱신 (바이낸스 웹소켓을 직접 쓰지 않는 경우 폴링 방식 유지)
            await asyncio.sleep(5)
            
    except WebSocketDisconnect:
        print(f"[WS ⚪] 연결 종료: {symbol}")
    except Exception as e:
        print(f"[WS 🔴] 에러 발생: {e}")

# [5] API: DB 상태 점검 (디버깅용)
@app.get("/api/db-status")
async def get_db_status(symbol: str = "BTCUSDT", timeframe: str = "15m"):
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(f'SELECT COUNT(*) as count, MIN(time) as min_t, MAX(time) as max_t FROM "{symbol}" WHERE timeframe = ?', (timeframe,))
            stats = cursor.fetchone()
            
            # 테이블이 비어있는 경우 방어 로직
            if stats['count'] == 0:
                return {"status": "Empty", "message": "데이터가 없습니다."}
                
            cursor.execute(f'SELECT * FROM "{symbol}" WHERE timeframe = ? ORDER BY time DESC LIMIT 5', (timeframe,))
            samples = [dict(row) for row in cursor.fetchall()]
            
            # 13자리 ms를 가독성 좋은 날짜로 변환
            for s in samples:
                if s['time']:
                    s['datetime_readable'] = str(pd.to_datetime(s['time'], unit='ms'))

            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "total_rows": stats['count'],
                "oldest_data": str(pd.to_datetime(stats['min_t'], unit='ms')),
                "newest_data": str(pd.to_datetime(stats['max_t'], unit='ms')),
                "latest_samples": samples,
                "status": "Healthy"
            }
    except Exception as e:
        return {"error": str(e), "message": "데이터베이스 조회 중 오류 발생"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)