import itertools
import sqlite3
import pandas as pd
from decimal import Decimal
from simulation.models import Wallet, PositionSide, PositionMode
from simulation.engine import SimulationEngine

class StrategyOptimizer:
    def __init__(self, db_path):
        self.db_path = db_path
        # 시장가 수수료 0.05%, 슬리피지 0.02% 반영 엔진 초기화
        self.engine = SimulationEngine(fee_rate=Decimal('0.0005'), slippage_rate=Decimal('0.0002'))
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

                # [ML 데이터 수집 - Dictionary 형태로 변경하여 관리 용이하게]
                ml_data_batch.append({
                    "signal_time": db_time, "symbol": symbol, "timeframe": timeframe, "signal_type": signal_type,
                    "entry_open": float(row['open']), "entry_high": float(row['high']), "entry_low": float(row['low']),
                    "entry_close": float(row['close']), "entry_volume": float(row['volume']),
                    "entry_tenkan": float(row.get('tenkan', 0)), "entry_kijun": float(row.get('kijun', 0)),
                    "entry_cloudTop": float(row.get('cloudTop', 0)), "entry_cloudBottom": float(row.get('cloudBottom', 0)),
                    "entry_rsi": float(row.get('rsi', 0)), "entry_macdLine": float(row.get('macdLine', 0)),
                    "entry_signalLine": float(row.get('signalLine', 0)), "entry_mfi": float(row.get('mfi', 0)),
                    "entry_sma224": float(row.get('sma224', 0)), "entry_vwma224": float(row.get('vwma224', 0)),
                    "entry_equilibrium": float(eq_p), "entry_smc_sl": float(smc_sl),
                    "position_mode": mode.value, "leverage": lev, "margin_ratio": float(m_ratio),
                    "applied_sl_ratio": float(abs(final_sl - entry_price) / entry_price), "sl_tag": sl_tag,
                    "result_status": result_status, "realized_pnl": float(final_pnl),
                    "duration_candles": duration, "pyramid_count": pyramid_count, "mdd_rate": mdd_rate
                })

        if ml_data_batch:
            self._save_to_db(ml_data_batch)

    def _save_to_db(self, ml_records: list):
        """상세 데이터(ML) 저장 후 통계 데이터(OPT)를 계산하여 저장합니다."""
        try:
            df_all = pd.DataFrame(ml_records)
            with sqlite3.connect(self.db_path) as conn:
                # 1. ml_trading_dataset 저장 (UPSERT)
                keys = ml_records[0].keys()
                cols_str = ", ".join([f'"{k}"' for k in keys])
                placeholders = ", ".join(["?"] * len(keys))
                conflict_keys = "signal_time, symbol, timeframe, position_mode, leverage, margin_ratio"
                update_str = ", ".join([f'"{k}"=excluded."{k}"' for k in keys if k not in conflict_keys.replace(" ", "").split(",")])
                
                sql_ml = f"INSERT INTO ml_trading_dataset ({cols_str}) VALUES ({placeholders}) ON CONFLICT({conflict_keys}) DO UPDATE SET {update_str}"
                conn.executemany(sql_ml, [tuple(r.values()) for r in ml_records])

                # 2. strategy_optimization 요약 통계 계산 및 저장
                # 특정 조합(모드, 레버리지, 비중)별로 그룹화하여 통계 산출
                summary = df_all.groupby(['position_mode', 'leverage', 'margin_ratio']).agg(
                    total_trades=('realized_pnl', 'count'),
                    win_trades=('realized_pnl', lambda x: (x > 0).sum()),
                    loss_trades=('realized_pnl', lambda x: (x <= 0).sum()),
                    total_pnl=('realized_pnl', 'sum'),
                    avg_pnl=('realized_pnl', 'mean'),
                    max_drawdown=('mdd_rate', 'min'), # MDD는 음수값이므로 min이 가장 큰 낙폭
                    avg_duration=('duration_candles', 'mean'),
                    avg_pyramid_count=('pyramid_count', 'mean')
                ).reset_index()
                summary['win_rate'] = (summary['win_trades'] / summary['total_trades']) * 100
                
                opt_records = summary.to_dict('records')
                opt_keys = opt_records[0].keys()
                opt_cols_str = ", ".join([f'"{k}"' for k in opt_keys])
                opt_placeholders = ", ".join(["?"] * len(opt_keys))
                opt_conflict = "position_mode, leverage, margin_ratio"
                opt_update = ", ".join([f'"{k}"=excluded."{k}"' for k in opt_keys if k not in opt_conflict.replace(" ", "").split(",")])

                sql_opt = f"INSERT INTO strategy_optimization ({opt_cols_str}) VALUES ({opt_placeholders}) ON CONFLICT({opt_conflict}) DO UPDATE SET {opt_update}, tested_at=CURRENT_TIMESTAMP"
                conn.executemany(sql_opt, [tuple(r.values()) for r in opt_records])
                
                conn.commit()
            self.logger(f"[DB] 상세 기록 {len(ml_records)}건 및 요약 통계 {len(opt_records)}건 갱신 완료.")
        except Exception as e:
            self.logger(f"[DB] 저장 실패: {e}")