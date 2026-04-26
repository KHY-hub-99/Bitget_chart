import itertools
import sqlite3
import pandas as pd
import asyncio
from decimal import Decimal
from datetime import datetime
from simulation.models import Wallet, PositionSide, PositionMode
from simulation.engine import SimulationEngine

class StrategyOptimizer:
    def __init__(self, db_path):
        self.db_path = db_path
        self.engine = SimulationEngine()
        self.logger = print 

    def set_logger(self, logger_func):
        self.logger = logger_func

    @staticmethod
    def enforce_13_digits(val):
        if pd.isna(val): return 0
        if isinstance(val, pd.Timestamp): return int(val.timestamp() * 1000)
        try:
            num = float(val)
            if num < 10000000000: return int(num * 1000)
            elif num > 100000000000000000: return int(num // 1000000)
            else: return int(num)
        except: return 0

    def run_optimization(self, df: pd.DataFrame, symbol: str, timeframe: str):
        df_sim = df.reset_index(drop=False)
        time_col = 'time' if 'time' in df_sim.columns else 'timestamp' if 'timestamp' in df_sim.columns else 'index'
        
        # 1. 시뮬레이션 파라미터 설정
        modes = [PositionMode.ONE_WAY, PositionMode.HEDGE]
        leverages = [3, 5, 10, 20, 50]
        tp_rates = [0.01, 0.02, 0.03, 0.05, 0.10]
        sl_rates = [0.01, 0.02, 0.05]
        
        combinations = []
        for mode, lev, tp, sl in itertools.product(modes, leverages, tp_rates, sl_rates):
            if sl >= (1.0 / lev) or tp < sl: continue
            combinations.append((mode, lev, tp, sl))
            
        self.logger(f"[INFO] {symbol} {timeframe} 최적화 시작 (조합: {len(combinations)}개)")
        
        ml_data_batch = [] 
        signal_positions = df_sim[(df_sim['master_long'] == True) | (df_sim['master_short'] == True)].index

        for pos in signal_positions:
            row = df_sim.iloc[pos]
            db_time = self.enforce_13_digits(row[time_col])
            
            signal_type = "MASTER_LONG" if row['master_long'] else "MASTER_SHORT"
            side = PositionSide.LONG if row['master_long'] else PositionSide.SHORT
            entry_price = Decimal(str(row['close']))

            for mode, lev, tp_r, sl_r in combinations:
                wallet = Wallet(initial_balance=Decimal('10000'), position_mode=mode)
                
                # 초기 진입 가격 설정
                tp_price = entry_price * (Decimal('1') + Decimal(str(tp_r))) if side == PositionSide.LONG else entry_price * (Decimal('1') - Decimal(str(tp_r)))
                sl_price = entry_price * (Decimal('1') - Decimal(str(sl_r))) if side == PositionSide.LONG else entry_price * (Decimal('1') + Decimal(str(sl_r)))

                self.engine.open_position(
                    wallet=wallet, symbol=symbol, side=side, entry_price=entry_price,
                    leverage=lev, margin=Decimal('1000'),
                    take_profit=tp_price, stop_loss=sl_price
                )

                future_df = df_sim.iloc[pos + 1 : pos + 201]
                result_status, duration, final_pnl, pyramid_count = "TIMEOUT", 0, Decimal('0'), 0

                for _, f_row in future_df.iterrows():
                    duration += 1
                    curr_p = Decimal(str(f_row['close']))
                    
                    # 불타기 로직
                    if (side == PositionSide.LONG and f_row.get('master_long')) or \
                    (side == PositionSide.SHORT and f_row.get('master_short')):
                        new_tp = curr_p * (Decimal('1') + Decimal(str(tp_r))) if side == PositionSide.LONG else curr_p * (Decimal('1') - Decimal(str(tp_r)))
                        new_sl = curr_p * (Decimal('1') - Decimal(str(sl_r))) if side == PositionSide.LONG else curr_p * (Decimal('1') + Decimal(str(sl_r)))
                        self.engine.open_position(wallet, symbol, side, curr_p, lev, Decimal('1000'), new_tp, new_sl)
                        pyramid_count += 1

                    res = self.engine.check_triggers(wallet, symbol, curr_p)
                    # 엔진에서 반환된 리스트 확인 (KeyError 방지)
                    if isinstance(res, list) and len(res) > 0:
                        result_status = res[0].get('status', 'CLOSED')
                        final_pnl = Decimal(str(res[0].get('realized_pnl', 0)))
                        break
                
                # 데이터 수집 (변수명 통일)
                ml_data_batch.append((
                    db_time, symbol, timeframe, signal_type, 
                    float(row['open']), float(row['high']), float(row['low']), float(row['close']), float(row['volume']),
                    float(row.get('rsi', 0)), float(row.get('macd_line', 0)), float(row.get('mfi', 0)),
                    (float(row.get('bb_upper', 0)) - float(row.get('bb_lower', 0))) / float(row['close']) if float(row['close']) != 0 else 0,
                    mode.value, lev, float(tp_r), float(sl_r), result_status, float(final_pnl), duration, pyramid_count
                ))

        if ml_data_batch:
            self._save_to_db(ml_data_batch)

    def _save_to_db(self, records):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # executemany로 수정 및 컬럼 순서 일치 확인
                cursor.executemany("""
                    INSERT INTO ml_trading_dataset 
                    (signal_time, symbol, timeframe, signal_type, entry_open, entry_high, entry_low, entry_close, entry_volume, 
                    entry_rsi, entry_macd, entry_mfi, bb_width, position_mode, leverage, tp_ratio, sl_ratio, 
                    result_status, realized_pnl, duration_candles, pyramid_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, records)
                conn.commit()
            self.logger(f"[DB] {len(records)}건 저장 완료.")
        except Exception as e:
            self.logger(f"[DB] 저장 실패: {e}")