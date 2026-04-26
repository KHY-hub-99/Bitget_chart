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
        """
        [기획 요약]
        1. 신호 활용: 초기 진입, 불타기(동일 신호), 스위칭(반대 신호) 시 사용
        2. 유사성: 슬리피지/수수료 차감 및 ONE_WAY 스위칭 엔진 연동
        3. DB 변경: 리스크 측정 지표 'mdd_rate' 추가
        """
        df_sim = df.reset_index(drop=False)
        time_col = 'time' if 'time' in df_sim.columns else 'timestamp' if 'timestamp' in df_sim.columns else 'index'
        
        # 테스트 조합 설정
        modes = [PositionMode.ONE_WAY, PositionMode.HEDGE]
        leverages = [3, 5, 10, 20, 50]
        tp_rates = [0.01, 0.02, 0.03, 0.05, 0.10]
        sl_rates = [0.01, 0.02, 0.05]
        
        combinations = []
        for mode, lev, tp, sl in itertools.product(modes, leverages, tp_rates, sl_rates):
            if sl >= (1.0 / lev) or tp < sl: continue
            combinations.append((mode, lev, tp, sl))
            
        self.logger(f"[INFO] {symbol} 시뮬레이션 시작 (신호 기반 조합: {len(combinations)}개)")
        
        ml_data_batch = [] 
        # [신호 활용 1] DB에 저장된 마스터 신호 위치 파악
        signal_positions = df_sim[(df_sim['master_long'] == True) | (df_sim['master_short'] == True)].index

        for pos_idx in signal_positions:
            row = df_sim.iloc[pos_idx]
            db_time = self.enforce_13_digits(row[time_col])
            
            # 신호에 따른 방향 결정
            side = PositionSide.LONG if row['master_long'] else PositionSide.SHORT
            entry_price = Decimal(str(row['close']))

            for mode, lev, tp_r, sl_r in combinations:
                # 각 조합별 독립된 지갑 생성 (초기자본 10,000불)
                wallet = Wallet(initial_balance=Decimal('10000'), position_mode=mode)
                
                # 익절/손절가 계산 (고정 비율 방식)
                tp_p = entry_price * (Decimal('1') + Decimal(str(tp_r))) if side == PositionSide.LONG else entry_price * (Decimal('1') - Decimal(str(tp_r)))
                sl_p = entry_price * (Decimal('1') - Decimal(str(sl_r))) if side == PositionSide.LONG else entry_price * (Decimal('1') + Decimal(str(sl_r)))

                # 초기 포지션 진입 (엔진 내에서 수수료/슬리피지 자동 계산)
                self.engine.open_position(
                    wallet=wallet, symbol=symbol, side=side, entry_price=entry_price,
                    leverage=lev, margin=Decimal('1000'),
                    take_profit=tp_p, stop_loss=sl_p
                )

                # 진입 후 최대 200봉까지 추적 시뮬레이션
                future_df = df_sim.iloc[pos_idx + 1 : pos_idx + 201]
                result_status, duration, final_pnl, pyramid_count = "TIMEOUT", 0, Decimal('0'), 0
                min_unrealized_pnl = Decimal('0') # MDD 추적을 위한 변수

                for _, f_row in future_df.iterrows():
                    duration += 1
                    curr_p = Decimal(str(f_row['close']))
                    
                    # [리스크 추적] 현재 포지션의 최저 수익(낙폭) 기록
                    # 식: MDD = min(현재 미실현 손익)
                    pos_key = self.engine._get_position_key(symbol, side, mode)
                    if pos_key in wallet.positions:
                        pos_obj = wallet.positions[pos_key]
                        pos_obj.update_pnl(curr_p)
                        if pos_obj.unrealized_pnl < min_unrealized_pnl:
                            min_unrealized_pnl = pos_obj.unrealized_pnl

                    # [신호 활용 2] 불타기(Same Signal) 또는 스위칭(Opposite Signal)
                    if f_row.get('master_long') or f_row.get('master_short'):
                        new_side = PositionSide.LONG if f_row['master_long'] else PositionSide.SHORT
                        
                        # 같은 방향 신호면 불타기 (Pyramiding)
                        if new_side == side:
                            self.engine.open_position(wallet, symbol, side, curr_p, lev, Decimal('1000'), tp_p, sl_p)
                            pyramid_count += 1
                        # 반대 방향 신호면 ONE_WAY 모드에서 스위칭 발생
                        elif mode == PositionMode.ONE_WAY:
                            res = self.engine.open_position(wallet, symbol, new_side, curr_p, lev, Decimal('1000'), tp_p, sl_p)
                            if res.get('status') in ['CLOSED', 'SWITCH_CLOSE', 'PARTIAL_OR_FULL_CLOSE']:
                                result_status = "SWITCHED"
                                final_pnl = Decimal(str(res.get('realized_pnl', 0)))
                                break

                    # [트리거 감시] 강제청산/익절/손절 체크
                    res_list = self.engine.check_triggers(wallet, symbol, curr_p)
                    if res_list:
                        result_status = res_list[0]['status']
                        final_pnl = Decimal(str(res_list[0].get('realized_pnl', 0)))
                        break
                
                # [식] MDD Rate = (포지션 중 최대 손실액 / 투입 증거금) * 100
                mdd_rate = (min_unrealized_pnl / Decimal('1000')) * 100

                # 데이터 배치에 리스크 지표 포함하여 저장
                ml_data_batch.append((
                    db_time, symbol, timeframe, "MASTER_LONG" if side == PositionSide.LONG else "MASTER_SHORT", 
                    float(row['open']), float(row['high']), float(row['low']), float(row['close']), float(row['volume']),
                    float(row.get('rsi', 0)), float(row.get('macd_line', 0)), float(row.get('mfi', 0)),
                    (float(row.get('bb_upper', 0)) - float(row.get('bb_lower', 0))) / float(row['close']) if float(row['close']) != 0 else 0,
                    mode.value, lev, float(tp_r), float(sl_r), 
                    result_status, float(final_pnl), duration, pyramid_count, float(mdd_rate)
                ))

        if ml_data_batch:
            self._save_to_db(ml_data_batch)

    def _save_to_db(self, records):
        """[DB 변경] mdd_rate 컬럼이 추가된 스키마에 저장"""
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