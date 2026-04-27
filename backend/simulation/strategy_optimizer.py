import itertools
import sqlite3
import pandas as pd
from decimal import Decimal
from simulation.models import Wallet, PositionSide, PositionMode
from simulation.engine import SimulationEngine

class StrategyOptimizer:
    def __init__(self, db_path):
        self.db_path = db_path
        # 시장가 수수료 0.06%, 슬리피지 0.02% 반영 엔진 초기화
        self.engine = SimulationEngine(fee_rate=Decimal('0.0006'), slippage_rate=Decimal('0.0002'))
        self.logger = print 

    @staticmethod
    def enforce_13_digits(val):
        """시간 데이터를 13자리 UNIX 타임스탬프(ms)로 표준화합니다."""
        if pd.isna(val): return 0
        if isinstance(val, pd.Timestamp): return int(val.timestamp() * 1000)
        num = float(val)
        return int(num * 1000) if num < 10000000000 else int(num)

    def run_optimization(self, df: pd.DataFrame, symbol: str, timeframe: str):
        df_sim = df.reset_index(drop=False)
        time_col = 'time' if 'time' in df_sim.columns else 'index'
        
        # 최적화 대상: 레버리지와 진입 비중 (ROE 15%는 고정 전략으로 적용)
        leverages = [10, 15, 20]
        # 진입가 5분할, 3분할, 2분할
        margin_ratios = [Decimal('0.2'), Decimal('0.33'), Decimal('0.5')]
        
        # [기획 반영] 손절 기준: ROE 15% (0.15)에 1.1배의 여유를 둠
        TARGET_ROE = Decimal('0.15')
        SL_MULTIPLIER = Decimal('1.1')
        
        combinations = list(itertools.product([PositionMode.ONE_WAY], leverages, margin_ratios))
        self.logger(f"[INFO] {symbol} {timeframe} 시뮬레이션 시작 (조합: {len(combinations)}개)")
        
        # longSig/shortSig가 발생한 시점들 추출
        signal_positions = df_sim[(df_sim['longSig'] == 1) | (df_sim['shortSig'] == 1)].index
        ml_data_batch = []

        for idx, pos_idx in enumerate(signal_positions):
            row = df_sim.iloc[pos_idx]
            db_time = self.enforce_13_digits(row[time_col])
            
            # 신호 타입 정의 [사용자 요청: "LONG" / "SHORT"]
            is_long = row.get('longSig') == 1
            signal_type = "LONG" if is_long else "SHORT"
            side = PositionSide.LONG if is_long else PositionSide.SHORT
            entry_price = Decimal(str(row['close']))

            # SMC 기반 가격 정보 (룰 2용)
            smc_sl = Decimal(str(row.get('swingLowLevel' if is_long else 'swingHighLevel', 0)))
            eq_p = Decimal(str(row.get('equilibrium', 0)))

            for mode, lev, m_ratio in combinations:
                wallet = Wallet(initial_balance=Decimal('10000'), position_mode=mode)
                
                # --- [하이브리드 손절가 결정 로직] ---
                # 1. 15% ROE 기반 기본 손절 거리 계산: (0.15 / 레버리지) * 1.1
                roe_sl_ratio = (TARGET_ROE / Decimal(str(lev))) * SL_MULTIPLIER
                roe_sl_dist = entry_price * roe_sl_ratio
                roe_sl_price = (entry_price - roe_sl_dist) if is_long else (entry_price + roe_sl_dist)

                # 2. 우선순위 결정: 룰 2(SMC 박스권)가 포함되어 있다면 Strong Low/High를 최우선 적용
                # 룰 2 조건 컬럼(entry_smc_long/short) 확인
                is_rule2 = row.get('entry_smc_long' if is_long else 'entry_smc_short') == 1
                
                if is_rule2 and smc_sl > 0:
                    final_sl = smc_sl # SMC 구조적 바닥/천장을 손절가로 채택
                    sl_tag = "RULE_2_SMC"
                else:
                    final_sl = roe_sl_price # 룰 1 단독 발생 시 15% ROE 손절 채택
                    sl_tag = "RULE_1_ROE"

                # 엔진 진입 실행
                self.engine.open_position(
                    wallet=wallet, symbol=symbol, side=side, entry_price=entry_price,
                    leverage=lev, margin_ratio=m_ratio, sl_price=final_sl, equilibrium=eq_p,
                    tag=sl_tag
                )
                # 미래 200캔들 동안 시뮬레이션 진행
                future_df = df_sim.iloc[pos_idx + 1 : pos_idx + 201]
                duration, pyramid_count, min_pnl = 0, 0, Decimal('0')
                max_margin = wallet.frozen_margin
                pos_key = self.engine._get_position_key(symbol, side, mode)

                for f_idx in range(len(future_df)):
                    duration += 1
                    curr_data = future_df.iloc[f_idx].to_dict()
                    
                    if pos_key in wallet.positions:
                        pos = wallet.positions[pos_key]
                        if pos.isolated_margin > max_margin: max_margin = pos.isolated_margin
                        # 미실현 손익 추적 (MDD 계산용)
                        unrealized = max(pos.unrealized_pnl, -pos.isolated_margin)
                        if unrealized < min_pnl: min_pnl = unrealized

                    # 엔진 트리거 체크 (분할진입, 50% 익절, 본절로스, 다이아몬드 익절 등 실행)
                    res_list = self.engine.check_triggers(wallet, curr_data)
                    if res_list:
                        for r in res_list:
                            if "LADDER_ENTRY" in r['status']: pyramid_count += 1
                        if pos_key not in wallet.positions:
                            result_status = res_list[-1]['status']
                            break
                else:
                    result_status = "TIMEOUT"

                # 결과 요약 및 저장
                final_pnl = wallet.total_balance - Decimal('10000')
                mdd_rate = float((min_pnl / max_margin) * 100) if max_margin > 0 else 0.0

                ml_data_batch.append((
                    db_time, symbol, timeframe, signal_type, 
                    float(row['open']), float(row['high']), float(row['low']), float(row['close']), float(row['volume']),
                    float(row.get('tenkan', 0)), float(row.get('kijun', 0)), float(row.get('cloudTop', 0)), float(row.get('cloudBottom', 0)),
                    float(row.get('rsi', 0)), float(row.get('macdLine', 0)), float(row.get('signalLine', 0)), float(row.get('mfi', 0)),
                    float(row.get('sma224', 0)), float(row.get('vwma224', 0)),
                    float(abs(final_sl - entry_price) / entry_price), # 실제 적용된 sl_ratio
                    mode.value, lev, float(abs(eq_p - entry_price) / entry_price) if eq_p else 0.0, 
                    result_status, float(final_pnl), duration, pyramid_count, mdd_rate
                ))

        if ml_data_batch: self._save_to_db(ml_data_batch)

    def _save_to_db(self, records):
        """시뮬레이션 결과를 DB에 UPSERT합니다."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.executemany("""
                    INSERT INTO ml_trading_dataset 
                    (signal_time, symbol, timeframe, signal_type, entry_open, entry_high, entry_low, entry_close, entry_volume, 
                    entry_tenkan, entry_kijun, entry_cloudTop, entry_cloudBottom, entry_rsi, entry_macd, entry_signal, entry_mfi,
                    entry_sma224, entry_vwma224, sl_ratio, position_mode, leverage, tp_ratio, 
                    result_status, realized_pnl, duration_candles, pyramid_count, mdd_rate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(signal_time, symbol, timeframe, position_mode, leverage, tp_ratio, sl_ratio) 
                    DO UPDATE SET result_status=excluded.result_status, realized_pnl=excluded.realized_pnl
                """, records)
                conn.commit()
        except Exception as e:
            self.logger(f"[DB] 저장 실패: {e}")