from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json

from app.data_process.load_data import CryptoDataFeed
from app.data_process.pine_data import apply_master_strategy
from app.services.chat_services import convert_df_to_chart_data

app = FastAPI(title="Crypto Trading Dashboard API")

# CORS 설정 (프론트엔드 연동용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 데이터 피드 인스턴스 (싱글턴처럼 사용)
feed = CryptoDataFeed(method="swap", symbol="BTC/USDT:USDT", timeframe="5m")

@app.on_event("startup")
async def startup_event():
    # 서버 시작 시 초기 데이터 로드 (90일치)
    feed.initialize_data(days=90)

@app.get("/api/history")
async def get_history():
    """과거 차트 데이터 및 지표 전체 반환"""
    # 최신 전략 연산 적용
    processed_df = apply_master_strategy(feed.df)
    chart_json = convert_df_to_chart_data(processed_df)
    return chart_json

@app.websocket("/ws/chart")
async def websocket_endpoint(websocket: WebSocket):
    """실시간 데이터 스트리밍"""
    await websocket.accept()
    try:
        while True:
            # 1. 데이터 업데이트
            updated_df = feed.update_data()
            # 2. 전략 재계산 (마지막 몇 개 행만 계산해도 되지만 단순화를 위해 전체 적용)
            processed_df = apply_master_strategy(updated_df)
            
            # 3. 최신 캔들 정보만 추출하여 전송
            latest_data = convert_df_to_chart_data(processed_df.tail(2)) # 마지막 2개 (현재 진행중 캔들 포함)
            
            await websocket.send_json(latest_data)
            
            # 5초 간격 업데이트 (거래소 API 제한 고려)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        print("Client disconnected")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)