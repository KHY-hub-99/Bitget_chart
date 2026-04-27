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

from data_process.load_data import CryptoDataFeed
from services.chat_services import convert_df_to_chart_data

from simulation.models import Wallet, PositionSide, PositionMode
from simulation.engine import SimulationEngine
from simulation.strategy_optimizer import StrategyOptimizer

# --- [1. 경로 및 초기 설정] ---
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_folder = os.path.join(base_dir, "backend", "market_data")
db_path = os.path.join(db_folder, "crypto_dashboard.db")

sim_wallet = Wallet(initial_balance=Decimal('10000.0'))
# 표준 수수료 및 슬리피지가 반영된 엔진 전역 인스턴스
sim_engine = SimulationEngine(fee_rate=Decimal('0.0005'), slippage_rate=Decimal('0.0002'))

class OrderRequest(BaseModel):
    symbol: str = "BTCUSDT"
    side: PositionSide
    leverage: int
    margin_ratio: float = 0.33  # [변경] 금액 대신 자산 대비 비중으로 요청
    current_price: Decimal
    take_profit: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None

class TickRequest(BaseModel):
    symbol: str = "BTCUSDT"
    current_price: Decimal

class ModeRequest(BaseModel):
    mode: PositionMode

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

# --- [2. 백그라운드 데이터 작업 로직] ---
def preload_initial_market_data():
    symbols = ["BTCUSDT", "ETHUSDT"]
    # 기획 요청: 15m, 30m, 1h, 4h
    timeframes = ["15m", "30m", "1h", "4h"]
    
    print("\n" + "="*60)
    print("[STARTUP] 지정된 5개 타임프레임의 365일 데이터 동기화 시작...")
    print("="*60)

    for sym in symbols:
        for tf in timeframes:
            try:
                print(f"[STARTUP] {sym} ({tf}) 365일치 데이터 수집 중...")
                feed = CryptoDataFeed(symbol=sym, timeframe=tf)
                feed.sync_historical_data(start_days=365)
                feed.refresh_indicators()
                time.sleep(1) 
            except Exception as e:
                print(f"[STARTUP ERROR] {sym} ({tf}) 데이터 수집 실패: {e}")

    print("\n[STARTUP] 모든 기초 데이터 준비 완료\n")

async def continuous_data_sync_worker():
    symbols = ["BTCUSDT", "ETHUSDT"]
    timeframes = ["15m", "30m", "1h", "4h"]

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
                    feed.update_data()

                    if not feed.df.empty:
                        last_price = feed.df.iloc[-1]['close']
                        now_str = datetime.now().strftime("%H:%M:%S")
                        print(f"[{now_str}] [백그라운드 저장 완료] {sym:8} | {tf:3} | 현재가: {last_price:,.2f}")

                    await asyncio.sleep(1)

                except Exception as e:
                    print(f"[BACKGROUND 🔴] {sym} ({tf}) 수집 중 오류: {e}")

        elapsed = time.time() - start_time
        print(f"\n[INFO] 전체 8종 데이터 한 사이클 업데이트 완료 ({elapsed:.2f}초 소요). 15초 대기...")
        print("-" * 50 + "\n")
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
                "stop_loss": float(p.stop_loss_price) if p.stop_loss_price else None,
                "is_partial_closed": getattr(p, 'is_partial_closed', False) # 부분 익절 상태 반환
            }
            for sym, p in wallet.positions.items()
        }
    }

def run_full_optimization_task(symbol: str, timeframe: str, loop: asyncio.AbstractEventLoop):
    def socket_logger(msg):
        loop.call_soon_threadsafe(
            lambda: asyncio.create_task(manager.broadcast(msg))
        )

    try:
        socket_logger(f"[{symbol} | {timeframe}] 전체 데이터 시뮬레이션 시작...")
        optimizer = StrategyOptimizer(db_path)
        optimizer.set_logger(socket_logger)
        feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
        df = feed.load_latest_from_db(limit=1000000)

        if df is None or df.empty:
            socket_logger("데이터가 없습니다.")
            return

        optimizer.run_optimization(df, symbol, timeframe)
        socket_logger("시뮬레이션 완료")

    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        socket_logger(f"시뮬레이션 중 오류 발생: {str(e)}")
        print(f"Detail Error: {error_msg}")

# --- [3. 서버 연동 작업] ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "="*60)
    print("Crypto Trading Dashboard API 서버 가동")
    print("데이터베이스: market_data/crypto_dashboard.db")
    print("="*60 + "\n")

    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, preload_initial_market_data)

    sync_task = asyncio.create_task(continuous_data_sync_worker())

    yield
    print("\n서버를 안전하게 종료합니다.")
    sync_task.cancel()

app = FastAPI(title="Crypto Trading Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 프론트엔드 통신 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- [4. 수동 시뮬레이션 제어 API (Live 테스트용)] ---
@app.get("/api/simulation/status")
async def get_simulation_status():
    return serialize_wallet(sim_wallet)

@app.post("/api/simulation/order")
async def place_market_order(req: OrderRequest):
    # 엔진이 이제 margin_ratio를 요구하므로 맞춰서 전달
    sim_engine.open_position(
        wallet=sim_wallet,
        symbol=req.symbol,
        side=req.side,
        entry_price=req.current_price,
        leverage=req.leverage,
        margin_ratio=Decimal(str(req.margin_ratio)),
        take_profit=req.take_profit,
        stop_loss=req.stop_loss
    )
    return {"message": "주문 체결 성공", "status": "success"}

@app.post("/api/simulation/close")
async def close_position(symbol: str = Query(...)):
    if symbol not in sim_wallet.positions:
        raise HTTPException(status_code=400, detail="종료할 포지션이 없습니다.")
    pos = sim_wallet.positions.pop(symbol)
    sim_wallet.total_balance += pos.unrealized_pnl
    sim_wallet.sync_balances()
    return {"message": f"{symbol} 포지션이 종료되었습니다."}

@app.post("/api/simulation/tick")
async def process_price_tick(req: TickRequest):
    # 수동 틱에서는 지표 데이터가 없으므로 현재가로 최소 구조체 생성
    current_data = {
        'close': req.current_price, 'high': req.current_price, 'low': req.current_price,
        'TOP': 0, 'BOTTOM': 0, 'vwma224': 0, 'sma224': 0
    }
    for pos_key, pos in list(sim_wallet.positions.items()):
        if pos.symbol == req.symbol:
            pos.update_pnl(Decimal(str(req.current_price)))

    result = sim_engine.check_triggers(sim_wallet, current_data)
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
    sim_wallet = Wallet(
        initial_balance=Decimal('10000.0'),
        total_balance=Decimal('10000.0'),
        available_balance=Decimal('10000.0'),
        frozen_margin=Decimal('0.0'),
        positions={}
    )
    return {"message": "시뮬레이션이 초기화되었습니다."}

# --- [5. 히스토리 및 웹소켓 엔드포인트] ---
def backfill_historical_data(symbol: str, timeframe: str, days: int):
    print(f"\n[BACKGROUND] {days}일치 과거 데이터 백필 시작")
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
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

    feed.load_latest_from_db(limit=fixed_limit)

    tf_map = {
        "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800,
        "1h": 3600, "2h": 7200, "4h": 14400, "6h": 21600, "8h": 28800, "12h": 43200,
        "1d": 86400, "3d": 259200, "1w": 604800
    }
    interval_seconds = tf_map.get(timeframe, 900)

    is_outdated = False
    if not feed.df.empty:
        last_time = feed.df.index[-1]
        now = datetime.now(timezone.utc)
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
        gap_seconds = (now - last_time).total_seconds()
        if gap_seconds > (interval_seconds + 10):
            is_outdated = True
            print(f"[{symbol}] 시간 격차 감지: {gap_seconds}초 (기준: {interval_seconds}초)")

    if feed.df.empty or len(feed.df) < fixed_limit or is_outdated:
        print(f"[{symbol}] 데이터 동기화 필요 (이유: {'비어있음' if feed.df.empty else '오래됨' if is_outdated else '개수부족'})")
        feed.sync_recent_data(required_limit=fixed_limit)
        feed.load_latest_from_db(limit=fixed_limit)
    else:
        if 'rsi' not in feed.df.columns or feed.df['rsi'].isnull().all():
            feed.refresh_indicators()
            feed.load_latest_from_db(limit=fixed_limit)

    background_tasks.add_task(backfill_historical_data, symbol, timeframe, days)

    chart_df = feed.get_chart_df(limit=fixed_limit)
    return convert_df_to_chart_data(chart_df)

@app.websocket("/ws/chart/{symbol}/{timeframe}")
async def websocket_endpoint(websocket: WebSocket, symbol: str, timeframe: str):
    await websocket.accept()
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    print(f"\n[WS 🟢] {symbol} ({timeframe}) 실시간 데이터 스트림 시작\n")

    try:
        prev_price = 0
        while True:
            feed.update_data()
            latest_chart_df = feed.get_chart_df(limit=2)

            if not latest_chart_df.empty:
                latest_data = convert_df_to_chart_data(latest_chart_df)
                latest_data['symbol'] = symbol
                await websocket.send_json(latest_data)

                last_candle = latest_chart_df.iloc[-1]
                current_price = last_candle['close']
                
                if current_price != prev_price:
                    prev_price = current_price

            await asyncio.sleep(5)

    except WebSocketDisconnect:
        print(f"[WS ⚪] 연결 종료: {symbol}")
    except Exception as e:
        print(f"[WS 🔴] 에러 발생: {e}")

@app.get("/api/db-status")
async def get_db_status(symbol: str = "BTCUSDT", timeframe: str = "15m"):
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(f'SELECT COUNT(*) as count, MIN(time) as min_t, MAX(time) as max_t FROM "{symbol}" WHERE timeframe = ?', (timeframe,))
            stats = cursor.fetchone()

            if stats['count'] == 0:
                return {"status": "Empty", "message": "데이터가 없습니다."}

            cursor.execute(f'SELECT * FROM "{symbol}" WHERE timeframe = ? ORDER BY time DESC LIMIT 5', (timeframe,))
            samples = [dict(row) for row in cursor.fetchall()]

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
    
# --- [6. 분석 및 최적화 데이터 API] ---
@app.get("/api/strategy-ranking")
async def get_strategy_ranking(
    symbol: str = Query("ALL", description="조회할 코인 심볼 (예: BTCUSDT, ALL)"),
    timeframe: str = Query("ALL", description="조회할 타임프레임 (예: 15m, ALL)")
):
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="데이터베이스 파일을 찾을 수 없습니다.")

    try:
        where_clauses = []
        params = []

        if symbol != "ALL":
            where_clauses.append("symbol = ?")
            params.append(symbol)
        if timeframe != "ALL":
            where_clauses.append("timeframe = ?")
            params.append(timeframe)

        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        query = f"""
        SELECT
            position_mode, leverage, tp_ratio, sl_ratio,
            COUNT(*) as total_trades,
            SUM(CASE WHEN result_status = 'TAKE_PROFIT' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result_status = 'STOP_LOSS' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result_status = 'LIQUIDATED' THEN 1 ELSE 0 END) as liquidations,
            SUM(CASE WHEN result_status = 'SWITCHED' THEN 1 ELSE 0 END) as switches,
            SUM(CASE WHEN result_status = 'TIMEOUT' THEN 1 ELSE 0 END) as timeouts,
            ROUND(SUM(realized_pnl), 2) as total_pnl,
            ROUND(AVG(realized_pnl), 2) as avg_pnl,
            SUM(pyramid_count) as total_pyramid_count,
            ROUND(AVG(mdd_rate), 2) as avg_mdd_rate,
            ROUND(MIN(mdd_rate), 2) as max_drawdown
        FROM ml_trading_dataset
        {where_sql}
        GROUP BY position_mode, leverage, tp_ratio, sl_ratio
        ORDER BY total_pnl DESC;
        """

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            ranking_data = [dict(row) for row in cursor.fetchall()]

            return {"status": "success", "count": len(ranking_data), "data": ranking_data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"데이터 분석 중 오류 발생: {str(e)}")

@app.post("/api/sync-historical")
async def sync_historical_data_trigger(
    background_tasks: BackgroundTasks,
    symbol: str = Query("BTCUSDT"), timeframe: str = Query("15m"), days: int = Query(30)
):
    background_tasks.add_task(backfill_historical_data, symbol, timeframe, days)
    return {
        "status": "success",
        "message": f"[{symbol}] {days}일치 데이터 백필 작업을 시작했습니다."
    }
    
# --- [7. 시뮬레이션 실행 및 로그 API] ---
@app.post("/api/simulation/run-full")
async def trigger_full_simulation(
    background_tasks: BackgroundTasks,
    symbol: str = Query("BTCUSDT"), timeframe: str = Query("15m")
):
    current_loop = asyncio.get_running_loop()
    background_tasks.add_task(run_full_optimization_task, symbol, timeframe, current_loop)
    return {"status": "success", "message": "시뮬레이션이 시작되었습니다."}

@app.websocket("/ws/simulation/logs")
async def websocket_simulation_logs(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        
# --- [8. 차트 시각화 전용 Replay API (엔진 고도화 연동)] ---
@app.get("/api/simulation/replay")
async def get_simulation_replay(
    symbol: str = Query("BTCUSDT"),
    timeframe: str = Query("15m"),
    mode: str = Query("ONE_WAY"),
    leverage: int = Query(10),
    margin_ratio: float = Query(0.33, description="자산 대비 진입 비중 (0.33 = 33%)")
):
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    df = feed.load_latest_from_db(limit=1000)

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="시뮬레이션 데이터가 없습니다.")

    chart_data = convert_df_to_chart_data(feed.get_chart_df(limit=1000))
    
    # 격리 모드 시뮬레이션용 독립 지갑 및 엔진 할당
    engine = SimulationEngine()
    pos_mode = PositionMode.ONE_WAY if mode == "ONE_WAY" else PositionMode.HEDGE
    temp_wallet = Wallet(initial_balance=Decimal('10000.0'), position_mode=pos_mode)
    
    markers = []
    m_ratio_dec = Decimal(str(margin_ratio))
    TARGET_ROE, SL_MULTIPLIER = Decimal('0.15'), Decimal('1.1') # 하이브리드 손절 상수

    for row in df.itertuples():
        curr_p = Decimal(str(row.close))
        curr_data = {
            'close': curr_p, 'high': Decimal(str(row.high)), 'low': Decimal(str(row.low)),
            'TOP': getattr(row, 'TOP', 0), 'BOTTOM': getattr(row, 'BOTTOM', 0),
            'vwma224': getattr(row, 'vwma224', 0), 'sma224': getattr(row, 'sma224', 0)
        }
        ts = int(row.Index.timestamp()) if hasattr(row, 'Index') and pd.notnull(row.Index) else 0
        if not ts: continue

        # [1] 엔진 트리거 체크 (분할 익절, 다이아몬드, 분할 진입 등)
        res_list = engine.check_triggers(wallet=temp_wallet, current_data=curr_data)
        if res_list:
            for res in res_list:
                status = res.get('status', 'CLOSED')
                # 마커 시각화 (엔진의 액션을 차트에 표기)
                if "LADDER_ENTRY" in status:
                    markers.append({"time": ts, "action": "BUY" if "LONG" in status else "SELL", "price": float(res['price']), "reason": status})
                elif "TP" in status or "LOSS" in status or "LIQUIDATED" in status:
                    markers.append({"time": ts, "action": "SELL", "price": float(res['price']), "reason": status})

        # [2] 메인 진입 시그널 감지 (longSig, shortSig)
        m_long = getattr(row, 'longSig', 0) == 1
        m_short = getattr(row, 'shortSig', 0) == 1

        if m_long or m_short:
            side = PositionSide.LONG if m_long else PositionSide.SHORT
            action = "BUY" if side == PositionSide.LONG else "SELL"

            # SMC 레벨 추출
            smc_sl_val = getattr(row, 'swingLowLevel' if m_long else 'swingHighLevel', 0)
            smc_sl = Decimal(str(smc_sl_val)) if not pd.isna(smc_sl_val) else Decimal('0')
            eq_val = getattr(row, 'equilibrium', 0)
            eq_p = Decimal(str(eq_val)) if not pd.isna(eq_val) else None
            
            # 하이브리드 손절 계산 (15% ROE * 1.1)
            roe_sl_ratio = (TARGET_ROE / Decimal(str(leverage))) * SL_MULTIPLIER
            roe_sl_dist = curr_p * roe_sl_ratio
            roe_sl_price = (curr_p - roe_sl_dist) if m_long else (curr_p + roe_sl_dist)

            # [수정] 표준 CamelCase 컬럼명 반영
            is_rule2 = getattr(row, 'entrySmcLong' if m_long else 'entrySmcShort', 0) == 1
            
            if is_rule2 and smc_sl > 0:
                final_sl, sl_tag = smc_sl, "RULE_2_SMC"
            else:
                final_sl, sl_tag = roe_sl_price, "RULE_1_ROE"

            # 엔진 진입 실행
            entry_res = engine.open_position(
                wallet=temp_wallet, symbol=symbol, side=side, entry_price=curr_p,
                leverage=leverage, margin_ratio=m_ratio_dec,
                sl_price=final_sl, equilibrium=eq_p, tag=sl_tag
            )
            
            markers.append({"time": ts, "action": action, "price": float(curr_p), "reason": entry_res['status']})

    return {"status": "success", "data": chart_data, "markers": markers}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)