from decimal import Decimal
from typing import Optional, List, Dict, Any
from simulation.models import Wallet, Position, PositionSide, PositionMode

class SimulationEngine:
    def __init__(self, fee_rate: Decimal = Decimal('0.0005'), slippage_rate: Decimal = Decimal('0.0002')):
        self.mmr = Decimal('0.004') # 유지 마진율 (Maintenance Margin Rate)
        self.fee_rate = fee_rate   # 시장가 수수료 0.05%
        self.slippage_rate = slippage_rate # 슬리피지 0.02%

    def calculate_liq_price(self, side: PositionSide, entry_price: Decimal, leverage: int) -> Decimal:
        # 공식: 격리 롱 청산가 = 진입가 * (1 - (1 / 레버리지) + 유지마진율)
        # 공식: 격리 숏 청산가 = 진입가 * (1 + (1 / 레버리지) - 유지마진율)
        lev = Decimal(str(leverage))
        if side == PositionSide.LONG:
            return entry_price * (Decimal('1') - (Decimal('1') / lev) + self.mmr)
        else:
            return entry_price * (Decimal('1') + (Decimal('1') / lev) - self.mmr)
        
    def _get_position_key(self, symbol: str, side: PositionSide, mode: PositionMode) -> str:
        """모드에 따른 포지션 키 생성"""
        if mode == PositionMode.HEDGE:
            return f"{symbol}_{side.value}"
        return symbol

    def open_position(self, wallet: Wallet, symbol: str, side: PositionSide, entry_price: Decimal, leverage: int, margin: Decimal, take_profit: Optional[Decimal] = None, stop_loss: Optional[Decimal] = None):
        """포지션 진입 및 단방향 모드 스위칭 로직"""
        
        # 공식: 실제 진입가 = 시장가 * (1 + 슬리피지) [LONG 기준]
        if side == PositionSide.LONG:
            actual_entry_price = entry_price * (Decimal('1') + self.slippage_rate)
        else:
            actual_entry_price = entry_price * (Decimal('1') - self.slippage_rate)

        # 공식: 포지션 수량 = (투입 증거금 * 레버리지) / 실제 진입가
        new_size = (margin * Decimal(str(leverage))) / actual_entry_price
        pos_key = self._get_position_key(symbol, side, wallet.position_mode)

        if pos_key in wallet.positions:
            existing_pos = wallet.positions[pos_key]

            # [A] 물타기/불타기 시 평단가 및 TP/SL 업데이트
            existing_pos = wallet.positions[pos_key]
            if existing_pos.side == side:
                # 공식: 신규 평단가 = ((기존수량 * 기존평단) + (신규수량 * 신규평단)) / 총수량
                total_size = existing_pos.size + new_size
                new_entry = ((existing_pos.size * existing_pos.entry_price) + (new_size * actual_entry_price)) / total_size
                
                existing_pos.size = total_size
                existing_pos.entry_price = new_entry
                existing_pos.isolated_margin += margin
                # 불타기 시 목표가 갱신 (보수적 접근을 위해 필수)
                if take_profit: existing_pos.take_profit_price = take_profit
                if stop_loss: existing_pos.stop_loss_price = stop_loss

                wallet.sync_balances()
                return {"status": "MERGED", "realized_pnl": Decimal('0')}

            # [B] 반대 방향: 부분청산/스위칭
            else:
                close_size = min(new_size, existing_pos.size)
                exit_price = actual_entry_price 
                
                entry_notional = existing_pos.entry_price * close_size
                exit_notional = exit_price * close_size
                fee = (entry_notional + exit_notional) * self.fee_rate
                
                if existing_pos.side == PositionSide.LONG:
                    gross_pnl = (exit_price - existing_pos.entry_price) * close_size
                else:
                    gross_pnl = (existing_pos.entry_price - exit_price) * close_size
                
                realized_pnl = gross_pnl - fee
                
                # 격리 모드 손실 하한선 적용 (부분 청산 비율만큼의 마진까지만 손실 허용)
                allocated_margin_for_close = existing_pos.isolated_margin * (close_size / existing_pos.size)
                if realized_pnl < -allocated_margin_for_close:
                    realized_pnl = -allocated_margin_for_close

                wallet.total_balance += realized_pnl

                if new_size <= existing_pos.size:
                    if new_size < existing_pos.size:
                        reduction_ratio = new_size / existing_pos.size
                        existing_pos.size -= new_size
                        existing_pos.isolated_margin -= (existing_pos.isolated_margin * reduction_ratio)
                        status = "PARTIAL_CLOSED"
                    else:
                        del wallet.positions[pos_key]
                        status = "CLOSED"
                    
                    wallet.sync_balances()
                    return {"status": status, "realized_pnl": realized_pnl}

                else:
                    del wallet.positions[pos_key] 
                    remaining_size = new_size - existing_pos.size
                    margin = (remaining_size * exit_price) / Decimal(str(leverage))
                    new_size = remaining_size

        # [케이스 2] 신규 진입
        liq_price = self.calculate_liq_price(side, actual_entry_price, leverage)
        new_position = Position(
            symbol=symbol, side=side, leverage=leverage, entry_price=actual_entry_price,
            size=new_size, isolated_margin=margin, liquidation_price=liq_price,
            take_profit_price=take_profit, stop_loss_price=stop_loss
        )
        
        wallet.positions[pos_key] = new_position
        wallet.sync_balances()
        return {"status": "NEW", "realized_pnl": Decimal('0')}

    # high_price와 low_price 파라미터 추가
    def check_triggers(self, wallet: Wallet, symbol: str, current_price: Decimal, high_price: Optional[Decimal] = None, low_price: Optional[Decimal] = None) -> List[Dict[str, Any]]:
        trigger_results = []
        chk_high = high_price if high_price is not None else current_price
        chk_low = low_price if low_price is not None else current_price

        for pos_key, pos in list(wallet.positions.items()):
            # 미실현 손익 업데이트
            pos.update_pnl(current_price, fee_rate=self.fee_rate, slippage_rate=self.slippage_rate)

            # 보수적 접근: 손절(SL) 가능성부터 먼저 체크
            is_sl = pos.stop_loss_price and (
                (pos.side == PositionSide.LONG and low_price <= pos.stop_loss_price) or
                (pos.side == PositionSide.SHORT and high_price >= pos.stop_loss_price)
            )
            is_tp = pos.take_profit_price and (
                (pos.side == PositionSide.LONG and high_price >= pos.take_profit_price) or
                (pos.side == PositionSide.SHORT and low_price <= pos.take_profit_price)
            )

            if is_sl: # 손절이 우선순위를 가짐 (Pessimistic)
                res = self._close_position(wallet, pos_key, pos.stop_loss_price, "STOP_LOSS")
                trigger_results.append(res)
                continue
            elif is_tp: # 손절이 안 났을 때만 익절 체크
                res = self._close_position(wallet, pos_key, pos.take_profit_price, "TAKE_PROFIT")
                trigger_results.append(res)
                continue

            # 손절이 안 나갔을 때만 최후의 수단으로 청산 체크!
            is_liquidated = (pos.side == PositionSide.LONG and chk_low <= pos.liquidation_price) or \
                            (pos.side == PositionSide.SHORT and chk_high >= pos.liquidation_price)
                
            if is_liquidated:
                realized_pnl = -pos.isolated_margin
                wallet.total_balance += realized_pnl
                del wallet.positions[pos_key]
                wallet.sync_balances()
                trigger_results.append({
                    "status": "LIQUIDATED", 
                    "realized_pnl": realized_pnl, 
                    "price": pos.liquidation_price
                })

        return trigger_results

    def _close_position(self, wallet: Wallet, pos_key: str, close_price: Decimal, reason: str) -> Dict[str, Any]:
        """포지션 종료 시 수수료와 슬리피지를 반영하여 실현 손익 계산"""
        pos = wallet.positions[pos_key]
        
        if pos.side == PositionSide.LONG:
            actual_exit_price = close_price * (Decimal('1') - self.slippage_rate)
        else:
            actual_exit_price = close_price * (Decimal('1') + self.slippage_rate)

        entry_notional = pos.entry_price * pos.size
        exit_notional = actual_exit_price * pos.size
        total_fee = (entry_notional + exit_notional) * self.fee_rate

        if pos.side == PositionSide.LONG:
            gross_pnl = (actual_exit_price - pos.entry_price) * pos.size
        else:
            gross_pnl = (pos.entry_price - actual_exit_price) * pos.size
            
        realized_pnl = gross_pnl - total_fee

        # 격리 모드 최대 손실 방어 (Loss 캡핑)
        if realized_pnl < -pos.isolated_margin:
            realized_pnl = -pos.isolated_margin

        wallet.total_balance += realized_pnl
        del wallet.positions[pos_key]
        wallet.sync_balances()
        
        return {
            "status": reason, 
            "realized_pnl": realized_pnl, 
            "price": actual_exit_price,
            "fee": total_fee
        }