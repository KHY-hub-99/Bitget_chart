from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import uvicorn

from data_process.load_data import CryptoDataFeed
from data_process.pine_data import apply_master_strategy
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
    ], # 프론트엔드 주소를 명시적으로 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/history")
async def get_history(
    symbol: str = Query("BTC/USDT:USDT"), 
    timeframe: str = Query("5m"), 
    days: int = Query(90)
):
    """사용자 선택값에 따른 과거 차트 데이터 및 지표 반환"""
    print(f"\n[GET] 요청 수신: {symbol} | {timeframe} | {days}일치")
    
    # 1. 해당 조건으로 데이터 피드 생성
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    
    # 2. 데이터 초기화 (DB 로드 또는 수집)
    feed.initialize_data(days=days)
    
    # 3. 전략 계산 (메모리 상에서 수행)
    processed_df = apply_master_strategy(feed.df)
    
    # 4. 🎯 중요: 계산된 지표를 DB에 업데이트 (나중에 시뮬레이션에서 바로 꺼내쓰기 위함)
    feed.save_enriched_df(processed_df)
    
    # 5. 프론트엔드 전송용 JSON 변환 (최적화된 5000개 슬라이싱 포함)
    chart_json = convert_df_to_chart_data(processed_df)
    
    print(f"[SUCCESS] {symbol} 데이터 전송 준비 완료 ({len(chart_json['candles'])} candles)")
    return chart_json

@app.websocket("/ws/chart")
async def websocket_endpoint(
    websocket: WebSocket,
    symbol: str = "BTC/USDT:USDT",
    timeframe: str = "5m"
):
    """실시간 데이터 스트리밍 (특정 종목/분봉 전용)"""
    await websocket.accept()
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    
    print(f"[WS] 연결 성공: {symbol} ({timeframe})")
    
    try:
        while True:
            # 1. 최신 캔들 수집 및 DB 저장
            updated_df = feed.update_data()
            
            # 2. 실시간 전략 재계산
            processed_df = apply_master_strategy(updated_df)
            
            # 3. 실시간 지표 DB 업데이트
            feed.save_enriched_df(processed_df)
            
            # 4. 최신 캔들 정보(미완성 캔들 포함)만 전송
            # convert_df_to_chart_data 내부에서 tail(5000)을 하지만, 
            # 웹소켓에서는 최신 2개만 콤팩트하게 보냅니다.
            latest_data = convert_df_to_chart_data(processed_df.tail(2))
            await websocket.send_json(latest_data)
            
            # 업데이트 간격 조정 (5분봉의 경우 5~10초 간격이 적당)
            await asyncio.sleep(5)
            
    except WebSocketDisconnect:
        print(f"[WS] 연결 종료: {symbol}")
    except Exception as e:
        print(f"[WS] 에러 발생: {e}")

if __name__ == "__main__":
    # reload=True는 개발 환경에서 코드 수정 시 서버 자동 재시작
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)