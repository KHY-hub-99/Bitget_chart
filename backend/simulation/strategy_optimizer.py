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
        total_signals = len(signal_positions)

        # [수정 1] UI 멈춤 방지: 모든 로그를 보내지 않고 진행률을 10개 단위로 스로틀링(Throttling)
        for idx, pos_idx in enumerate(signal_positions):
            if idx % 10 == 0 or idx == total_signals - 1:
                self.logger(f"[진행도] {symbol} {timeframe} 분석 중... ({idx + 1}/{total_signals})")

            row = df_sim.iloc[pos_idx]
            db_time = self.enforce_13_digits(row[time_col])
            
            signal_type = "MASTER_LONG" if row['master_long'] else "MASTER_SHORT"
            side = PositionSide.LONG if row['master_long'] else PositionSide.SHORT
            entry_price = Decimal(str(row['close']))

            for mode, lev, tp_r, sl_r in combinations:
                wallet = Wallet(initial_balance=Decimal('10000'), position_mode=mode)
                
                # 초기 진입 가격 설정
                tp_p = entry_price * (Decimal('1') + Decimal(str(tp_r))) if side == PositionSide.LONG else entry_price * (Decimal('1') - Decimal(str(tp_r)))
                sl_p = entry_price * (Decimal('1') - Decimal(str(sl_r))) if side == PositionSide.LONG else entry_price * (Decimal('1') + Decimal(str(sl_r)))

                # 초기 포지션 진입
                self.engine.open_position(
                    wallet=wallet, symbol=symbol, side=side, entry_price=entry_price,
                    leverage=lev, margin=Decimal('1000'),
                    take_profit=tp_p, stop_loss=sl_p
                )

                future_df = df_sim.iloc[pos_idx + 1 : pos_idx + 201]
                result_status, duration, final_pnl, pyramid_count = "TIMEOUT", 0, Decimal('0'), 0
                min_unrealized_pnl = Decimal('0')

                # [수정 2] 속도 최적화를 위해 itertuples 사용
                for f_row in future_df.itertuples():
                    duration += 1
                    curr_p = Decimal(str(f_row.close))
                    
                    # [수정 3] getattr 사용: itertuples는 namedtuple이므로 .get() 대신 getattr 사용
                    m_long = getattr(f_row, 'master_long', False)
                    m_short = getattr(f_row, 'master_short', False)
                    
                    pos_key = self.engine._get_position_key(symbol, side, mode)
                    
                    # [리스크 추적] MDD 계산
                    if pos_key in wallet.positions:
                        pos_obj = wallet.positions[pos_key]
                        pos_obj.update_pnl(curr_p)
                        if pos_obj.unrealized_pnl < min_unrealized_pnl:
                            min_unrealized_pnl = pos_obj.unrealized_pnl

                    # [수정 4] 단방향(ONE_WAY) 모드 스위칭 명확화
                    # 해당 신호에 대한 추적을 종료하고 스위칭 PNL을 정확히 기록하기 위해 직접 종료 호출
                    if mode == PositionMode.ONE_WAY:
                        opp_signal = (side == PositionSide.LONG and m_short) or \
                                    (side == PositionSide.SHORT and m_long)
                        if opp_signal and pos_key in wallet.positions:
                            res = self.engine._close_position(wallet, pos_key, curr_p, "SWITCHED")
                            result_status = "SWITCHED"
                            final_pnl = Decimal(str(res.get('realized_pnl', 0)))
                            break # 스위칭 발생 시 해당 신호 관찰 종료

                    # [수정 5] 불타기(Pyramiding) 로직 
                    same_signal = (side == PositionSide.LONG and m_long) or \
                                (side == PositionSide.SHORT and m_short)
                    if same_signal and pos_key in wallet.positions:
                        self.engine.open_position(wallet, symbol, side, curr_p, lev, Decimal('1000'), tp_p, sl_p)
                        pyramid_count += 1

                    # [트리거 감시] 강제청산/익절/손절 체크
                    res_list = self.engine.check_triggers(wallet, symbol, curr_p)
                    if res_list:
                        result_status = res_list[0]['status']
                        final_pnl = Decimal(str(res_list[0].get('realized_pnl', 0)))
                        break
                
                # MDD Rate = (포지션 중 최대 손실액 / 투입 증거금) * 100
                mdd_rate = (min_unrealized_pnl / Decimal('1000')) * 100

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
                    INSERT INTO ml_trading_dataset 
                    (signal_time, symbol, timeframe, signal_type, entry_open, entry_high, entry_low, entry_close, entry_volume, 
                    entry_rsi, entry_macd, entry_mfi, bb_width, position_mode, leverage, tp_ratio, sl_ratio, 
                    result_status, realized_pnl, duration_candles, pyramid_count, mdd_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, records)
                conn.commit()
            self.logger(f"[DB] {len(records)}건의 시뮬레이션 결과 저장 완료.")
        except Exception as e:
            self.logger(f"[DB] 저장 실패: {e}")