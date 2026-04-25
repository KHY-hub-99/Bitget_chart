from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import uvicorn
import sqlite3
import pandas as pd
import numpy as np
import os
from datetime import datetime, timezone

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
def backfill_historical_data(symbol: str, timeframe: str, days: int):
    print(f"\n[BACKGROUND 🛠️] {days}일치 과거 데이터 백필 시작")
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    # 🎯 역사적 데이터 수집 함수 호출
    feed.sync_historical_data(start_days=days)
    print(f"[BACKGROUND] {symbol} 백필 및 지표 재계산 완료")

# [3] API: 과거 히스토리 조회 및 차트 데이터 반환
@app.get("/api/history")
async def get_history(
    background_tasks: BackgroundTasks,
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("15m"),
    days: int = Query(365)
):
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    fixed_limit = 5000 
    
    # 1. 일단 DB 로드
    feed.load_latest_from_db(limit=fixed_limit)
    
    # [동적 타임프레임 초 변환 로직]
    # '1m' -> 60, '1h' -> 3600 처럼 초 단위로 변환합니다.
    tf_map = {
        "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
        "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "8h": 28800, "12h": 43200,
        "1d": 86400, "3d": 259200, "1w": 604800
    }
    
    # 설정된 타임프레임에 맞는 초(sec)를 가져옵니다. (없으면 기본값 15분)
    interval_seconds = tf_map.get(timeframe, 900)
    
    is_outdated = False
    if not feed.df.empty:
        last_time = feed.df.index[-1]
        now = datetime.now(timezone.utc)
        
        # 🎯 [핵심] 마지막 캔들이 현재 시간보다 '1캔들' 이상 차이나면 업데이트!
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
        
        gap_seconds = (now - last_time).total_seconds()
        
        if gap_seconds > (interval_seconds + 10): 
            is_outdated = True
            print(f"[{symbol}] 시간 격차 감지: {gap_seconds}초 (기준: {interval_seconds}초)")

    # 2. 데이터 부족 또는 오래된 데이터일 경우 API 호출
    if feed.df.empty or len(feed.df) < fixed_limit or is_outdated:
        print(f"[{symbol}] 데이터 동기화 필요 (이유: {'비어있음' if feed.df.empty else '오래됨' if is_outdated else '개수부족'})")
        feed.sync_recent_data(required_limit=fixed_limit)
        feed.load_latest_from_db(limit=fixed_limit)
    else:
        # 지표 누락 시 재계산
        if 'rsi' not in feed.df.columns or feed.df['rsi'].isnull().all():
            feed.refresh_indicators()
            feed.load_latest_from_db(limit=fixed_limit)

    # 3. 과거 백필(1년치 등)은 여전히 백그라운드에서 진행
    background_tasks.add_task(backfill_historical_data, symbol, timeframe, days)

    chart_df = feed.get_chart_df(limit=fixed_limit)
    return convert_df_to_chart_data(chart_df)

# [4] WebSocket: 실시간 데이터 동기화
@app.websocket("/ws/chart")
async def websocket_endpoint(
    websocket: WebSocket,
    symbol: str = "BTCUSDT",
    timeframe: str = "15m"
):
    await websocket.accept()
    # 새로운 심볼로 피드 생성
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    
    try:
        while True:
            feed.update_data()
            latest_chart_df = feed.get_chart_df(limit=2)
            
            if not latest_chart_df.empty:
                latest_data = convert_df_to_chart_data(latest_chart_df)
                # 🎯 데이터에 현재 심볼 이름을 명시적으로 추가
                latest_data['symbol'] = symbol 
                await websocket.send_json(latest_data)
            
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