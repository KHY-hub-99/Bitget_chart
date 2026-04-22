from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from app.data_process.load_data import CryptoDataFeed
from app.data_process.pine_data import apply_master_strategy
from app.services.chat_services import convert_df_to_chart_data

# 데이터 피드 인스턴스
feed = CryptoDataFeed(method="swap", symbol="BTC/USDT:USDT", timeframe="5m")

# 🌟 최신 Lifespan 방식: 서버 시작/종료 로직 관리
@asynccontextmanager
async def lifespan(app: FastAPI):
    # [Startup] 서버 시작 시 데이터 로드
    print("서버를 시작합니다. 데이터를 초기화 중...")
    feed.initialize_data(days=90)
    yield
    # [Shutdown] 서버 종료 시 필요한 정리 작업이 있다면 여기서 수행
    print("서버를 종료합니다.")

app = FastAPI(title="Crypto Trading Dashboard API", lifespan=lifespan)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/history")
async def get_history():
    """과거 차트 데이터 및 지표 전체 반환"""
    processed_df = apply_master_strategy(feed.df)
    chart_json = convert_df_to_chart_data(processed_df)
    return chart_json

@app.websocket("/ws/chart")
async def websocket_endpoint(websocket: WebSocket):
    """실시간 데이터 스트리밍"""
    await websocket.accept()
    try:
        while True:
            updated_df = feed.update_data()
            processed_df = apply_master_strategy(updated_df)
            
            # 최신 캔들 정보만 전송 (tail(2)로 현재 미완성 캔들 포함)
            latest_data = convert_df_to_chart_data(processed_df.tail(2))
            await websocket.send_json(latest_data)
            
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        print("Client disconnected")

if __name__ == "__main__":
    import uvicorn
    # 포트 충돌 방지를 위해 포트를 지정하거나 0.0.0.0으로 열기
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)