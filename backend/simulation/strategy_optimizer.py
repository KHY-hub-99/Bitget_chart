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
        # 시장가 수수료 0.05%, 슬리피지 0.02% 반영 엔진 초기화
        self.engine = SimulationEngine(
            fee_rate=Decimal('0.0005'), 
            slippage_rate=Decimal('0.0002')
        )
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
        
        # 시뮬레이션 파라미터 설정
        modes = [PositionMode.ONE_WAY, PositionMode.HEDGE]
        leverages = [3, 5, 10, 20, 50]
        tp_rates = [0.01, 0.02, 0.03, 0.05, 0.10]
        sl_rates = [0.01, 0.02, 0.05]
        
        combinations = []
        for mode, lev, tp, sl in itertools.product(modes, leverages, tp_rates, sl_rates):
            if sl >= (1.0 / lev) or tp < sl: continue
            combinations.append((mode, lev, tp, sl))
            
        self.logger(f"[INFO] {symbol} {timeframe} 최적화 시작 (조합: {len(combinations)}개)")
        
        # 동적 증거금 비율 설정 (총 자산의 10%)
        margin_ratio = Decimal('0.10')
        
        ml_data_batch = [] 
        signal_positions = df_sim[(df_sim['master_long'] == True) | (df_sim['master_short'] == True)].index
        total_signals = len(signal_positions)

        for idx, pos_idx in enumerate(signal_positions):
            if idx % 20 == 0 or idx == total_signals - 1:
                self.logger(f"[진행도] {symbol} {timeframe} 분석 중... ({idx + 1}/{total_signals})")
                import time
                time.sleep(0.1)

            row = df_sim.iloc[pos_idx]
            db_time = self.enforce_13_digits(row[time_col])
            
            signal_type = "MASTER_LONG" if row['master_long'] else "MASTER_SHORT"
            side = PositionSide.LONG if row['master_long'] else PositionSide.SHORT
            entry_price = Decimal(str(row['close']))

            for mode, lev, tp_r, sl_r in combinations:
                wallet = Wallet(initial_balance=Decimal('10000'), position_mode=mode)
                
                # 레버리지를 반영하여 실제 코인 가격의 목표 변동률 계산
                price_change_ratio_tp = Decimal(str(tp_r)) / Decimal(str(lev))
                price_change_ratio_sl = Decimal(str(sl_r)) / Decimal(str(lev))

                if side == PositionSide.LONG:
                    tp_p = entry_price * (Decimal('1') + price_change_ratio_tp)
                    sl_p = entry_price * (Decimal('1') - price_change_ratio_sl)
                else:
                    tp_p = entry_price * (Decimal('1') - price_change_ratio_tp)
                    sl_p = entry_price * (Decimal('1') + price_change_ratio_sl)

                # 초기 진입 시 동적 증거금 계산 (잔고 초과 방지)
                calculated_margin = wallet.total_balance * margin_ratio
                actual_margin = min(calculated_margin, wallet.available_balance)

                # 초기 포지션 진입 (최소 주문 금액 방어 - 10 USDT 이상일 때만 진입)
                if actual_margin >= Decimal('10'):
                    self.engine.open_position(
                        wallet=wallet, symbol=symbol, side=side, entry_price=entry_price,
                        leverage=lev, margin=actual_margin,
                        take_profit=tp_p, stop_loss=sl_p
                    )

                future_df = df_sim.iloc[pos_idx + 1 : pos_idx + 201]
                result_status, duration, final_pnl, pyramid_count = "TIMEOUT", 0, Decimal('0'), 0
                
                min_unrealized_pnl = Decimal('0')
                # 해당 포지션에 투입된 전체 증거금을 추적하기 위한 변수 추가
                max_allocated_margin = actual_margin 

                for f_row in future_df.itertuples():
                    duration += 1
                    curr_p = Decimal(str(f_row.close))
                    high_p = Decimal(str(f_row.high))
                    low_p = Decimal(str(f_row.low))
                    
                    m_long = getattr(f_row, 'master_long', False)
                    m_short = getattr(f_row, 'master_short', False)
                    
                    pos_key = self.engine._get_position_key(symbol, side, mode)
                    
                    # [리스크 추적] MDD 계산
                    if pos_key in wallet.positions:
                        pos_obj = wallet.positions[pos_key]
                        pos_obj.update_pnl(curr_p)
                        if pos_obj.unrealized_pnl < min_unrealized_pnl:
                            min_unrealized_pnl = pos_obj.unrealized_pnl

                    # [단방향 스위칭 검사]
                    if mode == PositionMode.ONE_WAY:
                        opp_signal = (side == PositionSide.LONG and m_short) or \
                                    (side == PositionSide.SHORT and m_long)
                        if opp_signal and pos_key in wallet.positions:
                            res = self.engine._close_position(wallet, pos_key, curr_p, "SWITCHED")
                            result_status = "SWITCHED"
                            final_pnl = Decimal(str(res.get('realized_pnl', 0)))
                            break 

                    # [불타기 (Pyramiding) 로직]
                    same_signal = (side == PositionSide.LONG and m_long) or \
                                (side == PositionSide.SHORT and m_short)
                    if same_signal and pos_key in wallet.positions:
                        
                        calc_pyramid_margin = wallet.total_balance * margin_ratio
                        actual_pyramid_margin = min(calc_pyramid_margin, wallet.available_balance)
                        
                        if actual_pyramid_margin >= Decimal('10'):
                            self.engine.open_position(
                                wallet, symbol, side, curr_p, lev, actual_pyramid_margin, tp_p, sl_p
                            )
                            pyramid_count += 1
                            # 물타기에 성공할 때마다 누적 투입 금액 합산
                            max_allocated_margin += actual_pyramid_margin 

                    # 엔진의 check_triggers에 High/Low 가격 전달
                    res_list = self.engine.check_triggers(
                        wallet=wallet, 
                        symbol=symbol, 
                        current_price=curr_p, 
                        high_price=high_p, 
                        low_price=low_p
                    )
                    
                    if res_list:
                        result_status = res_list[0]['status']
                        final_pnl = Decimal(str(res_list[0].get('realized_pnl', 0)))
                        break
                
                # MDD 비율 계산: 분모를 누적된 '최대 투입 증거금'으로 변경
                if max_allocated_margin > 0:
                    mdd_rate = (min_unrealized_pnl / max_allocated_margin) * 100 
                else:
                    mdd_rate = 0

                # 데이터 수집
                ml_data_batch.append((
                    db_time, symbol, timeframe, signal_type, 
                    float(row['open']), float(row['high']), float(row['low']), float(row['close']), float(row['volume']),
                    float(row.get('rsi', 0)), float(row.get('macd_line', 0)), float(row.get('mfi', 0)),
                    (float(row.get('bb_upper', 0)) - float(row.get('bb_lower', 0))) / float(row['close']) if float(row['close']) != 0 else 0,
                    mode.value, lev, float(tp_r), float(sl_r), 
                    result_status, float(final_pnl), duration, pyramid_count, float(mdd_rate)
                ))

        if ml_data_batch:
            self._save_to_db(ml_data_batch)

    def _save_to_db(self, records):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT OR REPLACE INTO ml_trading_dataset 
                    (signal_time, symbol, timeframe, signal_type, entry_open, entry_high, entry_low, entry_close, entry_volume, 
                    entry_rsi, entry_macd, entry_mfi, bb_width, position_mode, leverage, tp_ratio, sl_ratio, 
                    result_status, realized_pnl, duration_candles, pyramid_count, mdd_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, records)
                conn.commit()
            self.logger(f"[DB] {len(records)}건의 데이터 저장/갱신 완료.")
        except Exception as e:
            self.logger(f"[DB] 저장 실패: {e}")