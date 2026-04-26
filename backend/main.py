from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Optional
import asyncio
import time
import uvicorn
import sqlite3
import pandas as pd
import numpy as np
import os
from datetime import datetime, timezone

# [기존 데이터 피드 및 서비스]
from data_process.load_data import CryptoDataFeed
from services.chat_services import convert_df_to_chart_data

# [시뮬레이션 핵심 로직 임포트]
from simulation.models import Wallet, PositionSide, PositionMode
from simulation.engine import SimulationEngine
from simulation.strategy_optimizer import StrategyOptimizer

# --- [1. 경로 및 초기 설정] ---
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_folder = os.path.join(base_dir, "backend", "market_data")
db_path = os.path.join(db_folder, "crypto_dashboard.db")

# [시뮬레이션 전용 전역 상태 관리]
sim_wallet = Wallet(initial_balance=Decimal('10000.0'))
sim_engine = SimulationEngine()

# [로그 중계 시스템 전역 변수]
simulation_log_queue = asyncio.Queue()

# [시뮬레이션 요청 모델]
class OrderRequest(BaseModel):
    symbol: str = "BTC/USDT"
    side: PositionSide
    leverage: int
    margin: Decimal
    current_price: Decimal
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None

class TickRequest(BaseModel):
    symbol: str = "BTC/USDT"
    current_price: Decimal
    
class ModeRequest(BaseModel):
    mode: PositionMode

# --- [2. 백그라운드 데이터 작업 로직 (기존 동일)] ---
def preload_initial_market_data():
    symbols = ["BTCUSDT", "ETHUSDT"]
    timeframes = ["1m", "5m", "15m", "1h"]
    tf_map = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}
    
    print("\n[STARTUP] 스마트 동기화 시작...")
    for sym in symbols:
        for tf in timeframes:
            feed = CryptoDataFeed(symbol=sym, timeframe=tf)
            feed.load_latest_from_db(limit=100)
            
            # [/api/history]와 동일한 시간 기반 체크 로직 적용
            is_outdated = False
            if not feed.df.empty:
                last_time = feed.df.index[-1]
                now = datetime.now(timezone.utc)
                if last_time.tzinfo is None:
                    last_time = last_time.replace(tzinfo=timezone.utc)
                
                gap = (now - last_time).total_seconds()
                if gap > (tf_map.get(tf, 900) + 10):
                    is_outdated = True

            # 데이터가 아예 없거나, 오래되었으면 동기화 실행
            if feed.df.empty or is_outdated:
                print(f"[STARTUP] {sym} ({tf}) 데이터 업데이트 필요 -> 스마트 동기화 실행")
                # 매개변수를 비워두면(None), 내부에서 자동으로 공백을 계산합니다.
                feed.sync_recent_data() 
            else:
                print(f"[STARTUP] {sym} ({tf}) 최신 상태 유지 중 -> 지표만 갱신")
                feed.refresh_indicators()
            
            time.sleep(0.5) 
    print("[STARTUP] 모든 데이터가 최신 상태로 준비되었습니다.\n")
    
async def continuous_data_sync_worker():
    """
    서버 가동 내내 8가지 조합의 최신 데이터를 무한히 수집하여 DB를 최신화하는 백그라운드 엔진
    (실시간 저장 로그 추가 버전)
    """
    symbols = ["BTCUSDT", "ETHUSDT"]
    timeframes = ["1m", "5m", "15m", "1h"]
    
    # 초기 대량 적재(preload)가 끝날 시간을 충분히 벌어줍니다 (로그 겹침 방지)
    await asyncio.sleep(30) 
    print("\n" + "="*50)
    print("[BACKGROUND] 8가지 조합 무한 실시간 수집 엔진 가동!")
    print("="*50 + "\n")

    while True:
        start_time = time.time()
        
        for sym in symbols:
            for tf in timeframes:
                try:
                    feed = CryptoDataFeed(symbol=sym, timeframe=tf)
                    
                    # 1. 바이낸스에서 최신 봉을 가져와 DB에 저장
                    feed.update_data()
                    
                    # 2. [로그 찍기] 저장된 직후 최신 가격과 시간을 확인
                    if not feed.df.empty:
                        last_row = feed.df.iloc[-1]
                        last_price = last_row['close']
                        now_str = datetime.now().strftime("%H:%M:%S")
                        
                        # 터미널에 실시간 저장 상황 출력
                        print(f"[{now_str}] [백그라운드 저장 완료] {sym:8} | {tf:3} | 현재가: {last_price:,.2f}")
                    
                    # API 호출 사이 간격 (바이낸스 보호)
                    await asyncio.sleep(1) 
                    
                except Exception as e:
                    print(f"[BACKGROUND 🔴] {sym} ({tf}) 수집 중 오류: {e}")

        # 한 사이클 종료 로그
        elapsed = time.time() - start_time
        print(f"\n[INFO] 전체 8종 데이터 한 사이클 업데이트 완료 ({elapsed:.2f}초 소요). 15초 대기...")
        print("-" * 50 + "\n")

        # 15초 대기 후 다시 처음부터 수집 시작
        await asyncio.sleep(15)
        
def serialize_wallet(wallet: Wallet):
    return {
        "total_balance": float(wallet.total_balance),
        "available_balance": float(wallet.available_balance),
        "frozen_margin": float(wallet.frozen_margin),
        "position_mode": wallet.position_mode.value,
        "positions": {
            sym: {
                "side": p.side,
                "leverage": p.leverage,
                "entry_price": float(p.entry_price),
                "size": float(p.size),
                "mark_price": float(p.mark_price),
                "isolated_margin": float(p.isolated_margin),
                "liquidation_price": float(p.liquidation_price),
                "unrealized_pnl": float(p.unrealized_pnl),
                "take_profit": float(p.take_profit_price) if p.take_profit_price else None,
                "stop_loss": float(p.stop_loss_price) if p.stop_loss_price else None
            }
            for sym, p in wallet.positions.items()
        }
    }
    
# --- [시뮬레이션 백그라운드 실행 함수] ---
def run_full_optimization_task(symbol: str, timeframe: str, loop: asyncio.AbstractEventLoop):
    """
    DB에서 데이터를 로드하여 전체 시뮬레이션을 실행하고,
    발생하는 로그를 웹소켓 큐에 담습니다.
    """
    def socket_logger(msg):
        # 스레드 세이프하게 메인 루프의 비동기 큐에 메시지 삽입
        loop.call_soon_threadsafe(simulation_log_queue.put_nowait, msg)

    try:
        socket_logger(f"[{symbol} | {timeframe}] 전체 데이터 시뮬레이션 시작...")
        
        optimizer = StrategyOptimizer(db_path)
        optimizer.set_logger(socket_logger) # 로거 교체

        # 1. DB에서 데이터 로드
        feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
        df = feed.load_latest_from_db(limit=1000000) 
        
        if df is None or df.empty:
            socket_logger("데이터가 없습니다.")
            return

        optimizer.run_optimization(df, symbol, timeframe)
        socket_logger("시뮬레이션 완료")

    except Exception as e:
        socket_logger(f"오류: {str(e)}")

    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        socket_logger(f"시뮬레이션 중 치명적 오류 발생: {str(e)}")
        print(f"Detail Error: {error_msg}")

# Lifespan: 서버 가동 시 상태 메시지 출력
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "="*60)
    print("Crypto Trading Dashboard API 서버 가동")
    print("데이터베이스: market_data/crypto_dashboard.db")
    print("="*60 + "\n")
    
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, preload_initial_market_data)
    
    # 추가: 무한 실시간 수집 워커 등록 (프론트엔드 연결과 무관하게 백그라운드에서 계속 돎)
    sync_task = asyncio.create_task(continuous_data_sync_worker())
    
    yield
    print("\n서버를 안전하게 종료합니다.")
    sync_task.cancel() # 서버 종료 시 워커도 깔끔하게 종료

app = FastAPI(title="Crypto Trading Dashboard API", lifespan=lifespan)

# --- [3. FastAPI 앱 및 CORS 설정] ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- [4. 시뮬레이션 API 엔드포인트 (통합)] ---
@app.get("/api/simulation/status")
async def get_simulation_status():
    return serialize_wallet(sim_wallet)

@app.post("/api/simulation/order")
async def place_market_order(req: OrderRequest):
    if req.margin > sim_wallet.available_balance:
        raise HTTPException(status_code=400, detail="주문 가능 잔액이 부족합니다.")

    sim_engine.open_position(
        wallet=sim_wallet,
        symbol=req.symbol,
        side=req.side,
        entry_price=req.current_price,
        leverage=req.leverage,
        margin=req.margin,
        take_profit=req.take_profit,
        stop_loss=req.stop_loss
    )
    return {"message": "주문 체결 성공", "status": "success"}

@app.post("/api/simulation/close")
async def close_position(symbol: str = Query(...)):
    """특정 코인의 포지션을 현재가로 즉시 종료"""
    if symbol not in sim_wallet.positions:
        raise HTTPException(status_code=400, detail="종료할 포지션이 없습니다.")
    pos = sim_wallet.positions.pop(symbol)
    sim_wallet.total_balance += pos.unrealized_pnl
    sim_wallet.sync_balances()
    
    return {"message": f"{symbol} 포지션이 종료되었습니다."}

@app.post("/api/simulation/tick")
async def process_price_tick(req: TickRequest):
    for pos_key, pos in list(sim_wallet.positions.items()):
        if pos.symbol == req.symbol:
            pos.update_pnl(Decimal(str(req.current_price)))
            
    result = sim_engine.check_triggers(sim_wallet, req.symbol, req.current_price)
    sim_wallet.sync_balances()

    return {
        "tick_result": result,
        "wallet": serialize_wallet(sim_wallet)
    }
    
@app.post("/api/simulation/mode")
async def set_position_mode(req: ModeRequest):
    if sim_wallet.positions:
        raise HTTPException(status_code=400, detail="보유 중인 포지션이 있어 모드를 변경할 수 없습니다.")
    sim_wallet.position_mode = req.mode
    print(f"Mode changed to: {sim_wallet.position_mode}")
    return {"message": f"모드가 {req.mode}로 변경되었습니다.", "mode": req.mode}

@app.post("/api/simulation/reset")
async def reset_simulation():
    global sim_wallet
    # 지갑을 초기 상태로 덮어씌웁니다.
    sim_wallet = Wallet(
        initial_balance=Decimal('10000.0'),
        total_balance=Decimal('10000.0'),
        available_balance=Decimal('10000.0'),
        frozen_margin=Decimal('0.0'),
        positions={}
    )
    return {"message": "시뮬레이션이 초기화되었습니다."}

# --- [5. 기존 히스토리 및 웹소켓 엔드포인트] ---
def backfill_historical_data(symbol: str, timeframe: str, days: int):
    print(f"\n[BACKGROUND] {days}일치 과거 데이터 백필 시작")
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    # 역사적 데이터 수집 함수 호출
    feed.sync_historical_data(start_days=days)
    print(f"[BACKGROUND] {symbol} 백필 및 지표 재계산 완료")

@app.get("/api/history")
async def get_history(
    background_tasks: BackgroundTasks,
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("15m"),
    days: int = Query(365)
):
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    fixed_limit = 5000 
    
    # DB 로드
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
        
        # 마지막 캔들이 현재 시간보다 '1캔들' 이상 차이나면 업데이트
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
        
        gap_seconds = (now - last_time).total_seconds()
        
        if gap_seconds > (interval_seconds + 10): 
            is_outdated = True
            print(f"[{symbol}] 시간 격차 감지: {gap_seconds}초 (기준: {interval_seconds}초)")

    # 데이터 부족 또는 오래된 데이터일 경우 API 호출
    if feed.df.empty or len(feed.df) < fixed_limit or is_outdated:
        print(f"[{symbol}] 데이터 동기화 필요 (이유: {'비어있음' if feed.df.empty else '오래됨' if is_outdated else '개수부족'})")
        feed.sync_recent_data(required_limit=fixed_limit)
        feed.load_latest_from_db(limit=fixed_limit)
    else:
        # 지표 누락 시 재계산
        if 'rsi' not in feed.df.columns or feed.df['rsi'].isnull().all():
            feed.refresh_indicators()
            feed.load_latest_from_db(limit=fixed_limit)

    # 과거 백필(1년치 등)은 여전히 백그라운드에서 진행
    background_tasks.add_task(backfill_historical_data, symbol, timeframe, days)

    chart_df = feed.get_chart_df(limit=fixed_limit)
    return convert_df_to_chart_data(chart_df)

# WebSocket: 실시간 데이터 동기화
@app.websocket("/ws/chart/{symbol}/{timeframe}")
async def websocket_endpoint(
    websocket: WebSocket,
    symbol: str,
    timeframe: str
):
    await websocket.accept()
    # 새로운 심볼로 피드 생성
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    print(f"\n[WS 🟢] {symbol} ({timeframe}) 실시간 데이터 수집 및 DB 저장 스트림 시작\n")
    
    try:
        # 터미널 도배 방지를 위해 이전 가격을 기억할 변수
        prev_price = 0
        
        while True:
            # 1. 바이낸스 최신 데이터 가져와서 DB에 저장 및 지표 갱신
            feed.update_data()
            
            # 2. 프론트엔드로 보낼 차트 데이터 변환
            latest_chart_df = feed.get_chart_df(limit=2)
            
            if not latest_chart_df.empty:
                latest_data = convert_df_to_chart_data(latest_chart_df)
                latest_data['symbol'] = symbol 
                await websocket.send_json(latest_data)
                
                # [로그 출력 로직]
                last_candle = latest_chart_df.iloc[-1]
                current_price = last_candle['close']
                now_str = datetime.now().strftime("%H:%M:%S")

                # 가격이 변동되었거나 1분봉처럼 빠르게 갱신되는 걸 보고 싶을 때
                if current_price != prev_price:
                    print(f"[{now_str}] [DB 실시간 저장] {symbol} ({timeframe}) | 현재가: {current_price:,.2f} USDT")
                    prev_price = current_price
            
            # 5초 대기 후 반복
            await asyncio.sleep(5)
            
    except WebSocketDisconnect:
        print(f"[WS ⚪] 연결 종료: {symbol}")
    except Exception as e:
        print(f"[WS 🔴] 에러 발생: {e}")

# API: DB 상태 점검 (디버깅용)
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
    
# --- [6. 분석 및 최적화 데이터 API (추가)] ---

@app.get("/api/strategy-ranking")
async def get_strategy_ranking():
    """
    DB에 저장된 ml_trading_dataset 테이블을 분석하여 
    전략 조합별 수익률 및 승률 랭킹을 반환합니다.
    """
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="데이터베이스 파일을 찾을 수 없습니다.")

    try:
        query = """
        SELECT 
            position_mode, 
            leverage, 
            tp_ratio, 
            sl_ratio,
            COUNT(*) as total_trades,
            SUM(CASE WHEN result_status = 'TAKE_PROFIT' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result_status = 'STOP_LOSS' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result_status = 'TIMEOUT' THEN 1 ELSE 0 END) as timeouts,
            ROUND(SUM(realized_pnl), 2) as total_pnl,
            ROUND(AVG(realized_pnl), 2) as avg_pnl,
            SUM(pyramid_count) as total_pyramid_count
        FROM ml_trading_dataset
        GROUP BY position_mode, leverage, tp_ratio, sl_ratio
        ORDER BY total_pnl DESC;
        """
        
        with sqlite3.connect(db_path) as conn:
            # pandas를 이용해 쿼리 결과를 데이터프레임으로 변환
            df = pd.read_sql(query, conn)
        
        if df.empty:
            return {"status": "success", "message": "아직 시뮬레이션 데이터가 없습니다.", "data": []}

        # 승률 계산
        df['win_rate'] = (df['wins'] / df['total_trades'] * 100).round(2)
        
        # 프론트엔드 전송을 위해 리스트로 변환
        ranking_data = df.to_dict(orient="records")
        
        return {
            "status": "success",
            "count": len(ranking_data),
            "data": ranking_data
        }

    except Exception as e:
        print(f"[API ERROR] 랭킹 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"데이터 분석 중 오류 발생: {str(e)}")

@app.post("/api/sync-historical")
async def sync_historical_data_trigger(
    background_tasks: BackgroundTasks,
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("15m"),
    days: int = Query(30)
):
    """
    사용자가 요청한 일수(days)만큼 과거 데이터를 즉시 동기화합니다.
    시간이 오래 걸릴 수 있으므로 BackgroundTasks로 처리합니다.
    """
    try:
        # 이미 history 로직에서 사용하는 backfill_historical_data 함수를 재활용합니다.
        # 이 함수는 내부에서 feed.sync_historical_data(start_days=days)를 호출합니다.
        background_tasks.add_task(backfill_historical_data, symbol, timeframe, days)
        
        return {
            "status": "success",
            "message": f"[{symbol}] {days}일치 데이터 백필 작업을 백그라운드에서 시작했습니다.",
            "params": {"symbol": symbol, "timeframe": timeframe, "days": days}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"동기화 요청 실패: {str(e)}")
    
# --- [7. 시뮬레이션 실행 및 로그 API (추가)] ---

@app.post("/api/simulation/run-full")
async def trigger_full_simulation(
    background_tasks: BackgroundTasks, 
    symbol: str = Query("BTCUSDT"), 
    timeframe: str = Query("15m")
):
    """
    프론트엔드에서 버튼 클릭 시 전체 시뮬레이션을 백그라운드에서 실행합니다.
    """
    current_loop = asyncio.get_running_loop() # 현재 실행 중인 메인 루프 획득
    background_tasks.add_task(run_full_optimization_task, symbol, timeframe, current_loop)
    return {"status": "success", "message": "시뮬레이션이 시작되었습니다."}

@app.websocket("/ws/simulation/logs")
async def websocket_simulation_logs(websocket: WebSocket):
    """
    시뮬레이션 로그만 전문적으로 중계하는 웹소켓 채널입니다.
    """
    await websocket.accept()
    try:
        while True:
            # 큐에 로그가 들어올 때까지 기다렸다가 클라이언트에 전송
            message = await simulation_log_queue.get()
            await websocket.send_text(message)
    except WebSocketDisconnect:
        print("[WS ⚪] 시뮬레이션 로그 소켓 연결 종료")
    except Exception as e:
        print(f"[WS 🔴] 로그 전송 에러: {e}")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)