import itertools
import sqlite3
import pandas as pd
import numpy as np
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
        
        leverages = [10, 15, 20]
        marginRatios = [Decimal('0.2'), Decimal('0.33'), Decimal('0.5')]
        
        TARGET_ROE = Decimal('0.15')
        SL_MULTIPLIER = Decimal('1.1')
        
        combinations = list(itertools.product([PositionMode.ONE_WAY], leverages, marginRatios))
        self.logger(f"[INFO] {symbol} {timeframe} 시뮬레이션 시작 (조합: {len(combinations)}개)")
        
        # [표준 반영] longSig/shortSig가 발생한 시점들 추출
        signal_positions = df_sim[(df_sim['longSig'] == 1) | (df_sim['shortSig'] == 1)].index
        ml_data_batch = []

        for idx, pos_idx in enumerate(signal_positions):
            row = df_sim.iloc[pos_idx]
            db_time = self.enforce_13_digits(row[time_col])
            
            is_long = row.get('longSig') == 1
            signalType = "LONG" if is_long else "SHORT"
            side = PositionSide.LONG if is_long else PositionSide.SHORT
            entryPrice = Decimal(str(row['close']))

            # [표준 반영] SMC 기반 가격 정보 (룰 2용)
            smcSl = Decimal(str(row.get('swingLowLevel' if is_long else 'swingHighLevel', 0)))
            eqP = Decimal(str(row.get('equilibrium', 0)))

            for mode, lev, mRatio in combinations:
                wallet = Wallet(initial_balance=Decimal('10000'), position_mode=mode)
                
                roeSlRatio = (TARGET_ROE / Decimal(str(lev))) * SL_MULTIPLIER
                roeSlDist = entryPrice * roeSlRatio
                roeSlPrice = (entryPrice - roeSlDist) if is_long else (entryPrice + roeSlDist)

                # [표준 반영] 하이브리드 손절 판별 (entrySmcLong/Short)
                isRule2 = row.get('entrySmcLong' if is_long else 'entrySmcShort') == 1
                
                if isRule2 and smcSl > 0:
                    finalSl, slTag = smcSl, "RULE_2_SMC"
                else:
                    finalSl, slTag = roeSlPrice, "RULE_1_ROE"

                # 엔진 진입 실행
                self.engine.open_position(
                    wallet=wallet, symbol=symbol, side=side, entry_price=entryPrice,
                    leverage=lev, margin_ratio=mRatio, sl_price=finalSl, equilibrium=eqP,
                    tag=slTag
                )

                future_df = df_sim.iloc[pos_idx + 1 : pos_idx + 201]
                duration, pyramidCount, minPnl = 0, 0, Decimal('0')
                maxMargin = wallet.frozen_margin
                posKey = self.engine._get_position_key(symbol, side, mode)

                for f_idx in range(len(future_df)):
                    duration += 1
                    curr_data = future_df.iloc[f_idx].to_dict()
                    
                    if posKey in wallet.positions:
                        pos = wallet.positions[posKey]
                        if pos.isolated_margin > maxMargin: maxMargin = pos.isolated_margin
                        unrealized = max(pos.unrealized_pnl, -pos.isolated_margin)
                        if unrealized < minPnl: minPnl = unrealized

                    res_list = self.engine.check_triggers(wallet, curr_data)
                    if res_list:
                        for r in res_list:
                            if "LADDER_ENTRY" in r['status']: pyramidCount += 1
                        if posKey not in wallet.positions:
                            resultStatus = res_list[-1]['status']
                            break
                else:
                    resultStatus = "TIMEOUT"

                finalPnl = wallet.total_balance - Decimal('10000')
                mddRate = float((minPnl / maxMargin) * 100) if maxMargin > 0 else 0.0

                # [표준 반영] ML 데이터 수집 - Dictionary 키값을 DB 컬럼명과 100% 일치시킴
                ml_data_batch.append({
                    "signalTime": db_time, "symbol": symbol, "timeframe": timeframe, "signalType": signalType,
                    "entryOpen": float(row['open']), "entryHigh": float(row['high']), "entryLow": float(row['low']),
                    "entryClose": float(row['close']), "entryVolume": float(row['volume']),
                    "entryTenkan": float(row.get('tenkan', 0)), "entryKijun": float(row.get('kijun', 0)),
                    "entryCloudTop": float(row.get('cloudTop', 0)), "entryCloudBottom": float(row.get('cloudBottom', 0)),
                    "entryRsi": float(row.get('rsi', 0)), "entryMacdLine": float(row.get('macdLine', 0)),
                    "entrySignalLine": float(row.get('signalLine', 0)), "entryMfi": float(row.get('mfi', 0)),
                    "entrySma224": float(row.get('sma224', 0)), "entryVwma224": float(row.get('vwma224', 0)),
                    "entryEquilibrium": float(eqP), "entrySwingLowLevel": float(smcSl),
                    "entryVwmaLong": int(row.get('entryVwmaLong', 0)), "entrySmcLong": int(row.get('entrySmcLong', 0)),
                    "entryVwmaShort": int(row.get('entryVwmaShort', 0)), "entrySmcShort": int(row.get('entrySmcShort', 0)),
                    "positionMode": mode.value, "leverage": lev, "marginRatio": float(mRatio),
                    "appliedSlRatio": float(abs(finalSl - entryPrice) / entryPrice), "slTag": slTag,
                    "resultStatus": resultStatus, "realizedPnl": float(finalPnl),
                    "durationCandles": duration, "pyramidCount": pyramidCount, "mddRate": mddRate
                })

        if ml_data_batch:
            self._save_to_db(ml_data_batch)

    def _save_to_db(self, ml_records: list):
        """상세 데이터(ML) 저장 후 통계 데이터(OPT)를 계산하여 저장합니다."""
        try:
            df_all = pd.DataFrame(ml_records)
            with sqlite3.connect(self.db_path) as conn:
                # 1. ml_trading_dataset 저장 (표준 CamelCase 반영)
                keys = ml_records[0].keys()
                cols_str = ", ".join([f'"{k}"' for k in keys])
                placeholders = ", ".join(["?"] * len(keys))
                conflict_keys = "signalTime, symbol, timeframe, positionMode, leverage, marginRatio"
                update_cols = [k for k in keys if k not in conflict_keys.replace(" ", "").split(",")]
                update_str = ", ".join([f'"{k}"=excluded."{k}"' for k in update_cols])
                
                sql_ml = f"INSERT INTO ml_trading_dataset ({cols_str}) VALUES ({placeholders}) ON CONFLICT({conflict_keys}) DO UPDATE SET {update_str}"
                conn.executemany(sql_ml, [tuple(r.values()) for r in ml_records])

                # 2. strategy_optimization 요약 통계 계산 및 저장 (표준 CamelCase 반영)
                summary = df_all.groupby(['positionMode', 'leverage', 'marginRatio']).agg(
                    totalTrades=('realizedPnl', 'count'),
                    winTrades=('realizedPnl', lambda x: (x > 0).sum()),
                    lossTrades=('realizedPnl', lambda x: (x <= 0).sum()),
                    totalPnl=('realizedPnl', 'sum'),
                    avgPnl=('realizedPnl', 'mean'),
                    maxDrawdown=('mddRate', 'min'),
                    avgDuration=('durationCandles', 'mean'),
                    avgPyramidCount=('pyramidCount', 'mean')
                ).reset_index()
                summary['winRate'] = (summary['winTrades'] / summary['totalTrades']) * 100
                
                opt_records = summary.to_dict('records')
                opt_keys = opt_records[0].keys()
                opt_cols_str = ", ".join([f'"{k}"' for k in opt_keys])
                opt_placeholders = ", ".join(["?"] * len(opt_keys))
                opt_conflict = "positionMode, leverage, marginRatio"
                opt_update_cols = [k for k in opt_keys if k not in opt_conflict.replace(" ", "").split(",")]
                opt_update_str = ", ".join([f'"{k}"=excluded."{k}"' for k in opt_update_cols])

                sql_opt = f"INSERT INTO strategy_optimization ({opt_cols_str}) VALUES ({opt_placeholders}) ON CONFLICT({opt_conflict}) DO UPDATE SET {opt_update_str}, testedAt=CURRENT_TIMESTAMP"
                conn.executemany(sql_opt, [tuple(r.values()) for r in opt_records])
                
                conn.commit()
            self.logger(f"[DB] 상세 기록 {len(ml_records)}건 및 요약 통계 {len(opt_records)}건 갱신 완료.")
        except Exception as e:
            self.logger(f"[DB] 저장 실패: {e}")