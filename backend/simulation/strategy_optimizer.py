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
        marginRatios = [Decimal('0.2'), Decimal('0.33'), Decimal('0.5')] # 분할 진입용 1회 비중
        
        TARGET_ROE = Decimal('0.15')
        SL_MULTIPLIER = Decimal('1.1')
        
        combinations = list(itertools.product([PositionMode.ONE_WAY], leverages, marginRatios))
        self.logger(f"[INFO] {symbol} {timeframe} 시뮬레이션 시작 (조합: {len(combinations)}개)")
        
        # 최초 진입 신호 추출 (엄격한 통일 기준: longSig, shortSig)
        signal_positions = df_sim[(df_sim['longSig'] == 1) | (df_sim['shortSig'] == 1)].index
        ml_data_batch = []

        for idx, pos_idx in enumerate(signal_positions):
            row = df_sim.iloc[pos_idx]
            db_time = self.enforce_13_digits(row[time_col])
            
            is_long = row.get('longSig') == 1
            signalType = "LONG" if is_long else "SHORT"
            side = PositionSide.LONG if is_long else PositionSide.SHORT
            entryPrice = Decimal(str(row['close']))
            
            # --- [전략 룰 판별 로직] ---
            vwma = Decimal(str(row.get('vwma224', 0)))
            sma = Decimal(str(row.get('sma224', 0)))
            lowP = Decimal(str(row['low']))
            highP = Decimal(str(row['high']))
            eqP = Decimal(str(row.get('equilibrium', 0)))
            
            trailing_bottom = Decimal(str(row.get('trailingBottom', 0)))
            swing_high = Decimal(str(row.get('swingHighLevel', 0)))

            is_rule1 = False
            entry_tag = ""
            first_entry_val = None

            if is_long:
                # 롱 진입 시 저가가 VWMA 또는 SMA를 밟았는지 확인 (Rule 1)
                if vwma > 0 and lowP <= vwma:
                    is_rule1, entry_tag, first_entry_val = True, "VWMA", vwma
                elif sma > 0 and lowP <= sma:
                    is_rule1, entry_tag, first_entry_val = True, "SMA", sma
            else:
                # 숏 진입 시 고가가 VWMA 또는 SMA에 닿았는지 확인 (Rule 1)
                if vwma > 0 and highP >= vwma:
                    is_rule1, entry_tag, first_entry_val = True, "VWMA", vwma
                elif sma > 0 and highP >= sma:
                    is_rule1, entry_tag, first_entry_val = True, "SMA", sma

            strategy_rule = "RULE_1" if is_rule1 else "RULE_2"
            if not is_rule1:
                entry_tag = "SMC" # 룰 2인 경우 태그를 SMC로 통일

            for mode, lev, mRatio in combinations:
                wallet = Wallet(initial_balance=Decimal('10000'), position_mode=mode)
                
                # [손절(SL) 계산]
                if strategy_rule == "RULE_1":
                    # 룰 1: 진입가 기준 고정 15% * 1.1
                    roeSlRatio = (TARGET_ROE / Decimal(str(lev))) * SL_MULTIPLIER
                    roeSlDist = entryPrice * roeSlRatio
                    finalSl = (entryPrice - roeSlDist) if is_long else (entryPrice + roeSlDist)
                    slTag = "RULE_1_ROE"
                else:
                    # 룰 2: 롱은 trailingBottom, 숏은 swingHighLevel
                    finalSl = trailing_bottom if is_long else swing_high
                    slTag = "RULE_2_SMC_STRUCT"

                # 엔진 진입 실행 (최신 엔진 파라미터 규격 준수)
                self.engine.open_position(
                    wallet=wallet, symbol=symbol, side=side, entry_price=entryPrice,
                    leverage=lev, margin_ratio=mRatio, strategy_rule=strategy_rule,
                    sl_price=finalSl, equilibrium=eqP, tag=entry_tag, 
                    first_entry_val=first_entry_val
                )

                future_df = df_sim.iloc[pos_idx + 1 : pos_idx + 201]
                duration, pyramidCount, minPnl = 0, 0, Decimal('0')
                maxMargin = wallet.frozen_margin
                posKey = symbol if mode == PositionMode.ONE_WAY else f"{symbol}_{side.value}"

                # 미래 캔들을 순회하며 엔진의 트리거 작동 확인
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
                            # 엔진이 불타기(추가 진입)를 수행했을 경우 카운트
                            if "LADDER" in r['status']: pyramidCount += 1
                        if posKey not in wallet.positions:
                            resultStatus = res_list[-1]['status']
                            break
                else:
                    resultStatus = "TIMEOUT"

                finalPnl = wallet.total_balance - Decimal('10000')
                mddRate = float((minPnl / maxMargin) * 100) if maxMargin > 0 else 0.0

                # --- [ML 데이터 수집: 통일 컬럼(Standard CamelCase) 100% 매핑] ---
                ml_data_batch.append({
                    "signalTime": db_time, "symbol": symbol, "timeframe": timeframe, "signalType": signalType,
                    "entryOpen": float(row['open']), "entryHigh": float(row['high']), "entryLow": float(row['low']),
                    "entryClose": float(row['close']), "entryVolume": float(row.get('volume', 0)),
                    
                    # 일목균형표
                    "entryTenkan": float(row.get('tenkan', 0)), "entryKijun": float(row.get('kijun', 0)),
                    "entrySenkouA": float(row.get('senkouA', 0)), "entrySenkouB": float(row.get('senkouB', 0)),
                    "entryCloudTop": float(row.get('cloudTop', 0)), "entryCloudBottom": float(row.get('cloudBottom', 0)),
                    
                    # 기술적 지표
                    "entryRsiVal": float(row.get('rsiVal', 0)), "entryMfiVal": float(row.get('mfiVal', 0)),
                    "entryMacdLine": float(row.get('macdLine', 0)), "entrySignalLine": float(row.get('signalLine', 0)),
                    "entryBbLower": float(row.get('bbLower', 0)), "entryBbMid": float(row.get('bbMid', 0)), "entryBbUpper": float(row.get('bbUpper', 0)),
                    
                    # Whale
                    "entrySma224": float(row.get('sma224', 0)), "entryVwma224": float(row.get('vwma224', 0)),
                    
                    # SMC 구조
                    "entrySwingHighLevel": float(row.get('swingHighLevel', 0)), 
                    "entryTrailingBottom": float(row.get('trailingBottom', 0)), 
                    "entryEquilibrium": float(eqP),
                    
                    # 트렌드 및 전략 메타데이터
                    "entryTrend": int(row.get('trend', 0)),
                    "strategyRule": strategy_rule,
                    
                    # 결과 및 통계 파라미터
                    "positionMode": mode.value, "leverage": lev, "marginRatio": float(mRatio),
                    "appliedSlRatio": float(abs(finalSl - entryPrice) / entryPrice) if entryPrice > 0 else 0, 
                    "slTag": slTag,
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
                # 1. ml_trading_dataset 저장
                keys = ml_records[0].keys()
                cols_str = ", ".join([f'"{k}"' for k in keys])
                placeholders = ", ".join(["?"] * len(keys))
                conflict_keys = "signalTime, symbol, timeframe, positionMode, leverage, marginRatio"
                update_cols = [k for k in keys if k not in conflict_keys.replace(" ", "").split(",")]
                update_str = ", ".join([f'"{k}"=excluded."{k}"' for k in update_cols])
                
                sql_ml = f"INSERT INTO ml_trading_dataset ({cols_str}) VALUES ({placeholders}) ON CONFLICT({conflict_keys}) DO UPDATE SET {update_str}"
                conn.executemany(sql_ml, [tuple(r.values()) for r in ml_records])

                # 2. strategy_optimization 통계 저장
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