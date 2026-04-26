from decimal import Decimal
from typing import Optional, List, Dict, Any
from simulation.models import Wallet, Position, PositionSide, PositionMode

class SimulationEngine:
    def __init__(self, fee_rate: Decimal = Decimal('0.0005'), slippage_rate: Decimal = Decimal('0.0002')):
        self.mmr = Decimal('0.004') # 유지 마진율 (Maintenance Margin Rate)
        self.fee_rate = fee_rate   # 시장가 수수료 0.05%
        self.slippage_rate = slippage_rate # 슬리피지 0.02%

    def calculate_liq_price(self, side: PositionSide, entry_price: Decimal, leverage: int) -> Decimal:
        """격리 모드(Isolated) 강제 청산가 계산 공식"""
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

    def open_position(self, wallet: Wallet, symbol: str, side: PositionSide, 
                    entry_price: Decimal, leverage: int, margin: Decimal,
                    take_profit: Optional[Decimal] = None, stop_loss: Optional[Decimal] = None):
        """
        포지션 진입 및 단방향 모드 스위칭 로직
        식 1. 진입 슬리피지: actual_price = market_price * (1 ± slippage_rate)
        """
        
        # 1. 진입 시 슬리피지 반영 (매수는 비싸게, 매도는 싸게 체결)
        if side == PositionSide.LONG:
            actual_entry_price = entry_price * (Decimal('1') + self.slippage_rate)
        else:
            actual_entry_price = entry_price * (Decimal('1') - self.slippage_rate)

        # 식 2. 수량 계산: size = (margin * leverage) / actual_entry_price
        new_size = (margin * Decimal(str(leverage))) / actual_entry_price
        pos_key = self._get_position_key(symbol, side, wallet.position_mode)

        # [케이스 1] 기존 포지션이 존재하는 경우
        if pos_key in wallet.positions:
            existing_pos = wallet.positions[pos_key]

            # [A] 같은 방향일 때: 물타기 (Average Entry Price)
            # 식: new_entry = (sum(price * size)) / sum(size)
            if existing_pos.side == side:
                total_size = existing_pos.size + new_size
                new_entry = ((existing_pos.size * existing_pos.entry_price) + (new_size * actual_entry_price)) / total_size
                
                existing_pos.size = total_size
                existing_pos.entry_price = new_entry
                existing_pos.isolated_margin += margin
                existing_pos.liquidation_price = self.calculate_liq_price(side, new_entry, leverage)
                
                wallet.sync_balances()
                return {"status": "MERGED", "realized_pnl": Decimal('0')}

            # [B] 반대 방향 주문 (단방향 모드 스위칭/부분청산)
            else:
                # 1단계: 청산할 수량 결정 (주문량과 기존량 중 작은 값)
                close_size = min(new_size, existing_pos.size)
                exit_price = actual_entry_price # 현재 진입가가 기존 포지션의 종료가 됨
                
                # 식 3. 수수료 계산: fee = (진입가 * 수량 + 종료가 * 수량) * 수수료율
                entry_notional = existing_pos.entry_price * close_size
                exit_notional = exit_price * close_size
                fee = (entry_notional + exit_notional) * self.fee_rate
                
                # 식 4. 미실현 손익 계산 (Gross PNL)
                # Long: (종료가 - 진입가) * 수량 | Short: (진입가 - 종료가) * 수량
                if existing_pos.side == PositionSide.LONG:
                    gross_pnl = (exit_price - existing_pos.entry_price) * close_size
                else:
                    gross_pnl = (existing_pos.entry_price - exit_price) * close_size
                
                # 식 5. 최종 실현 손익: realized_pnl = gross_pnl - fee
                realized_pnl = gross_pnl - fee
                wallet.total_balance += realized_pnl

                # 2단계: 포지션 상태 업데이트
                if new_size <= existing_pos.size:
                    if new_size < existing_pos.size:
                        # [B-1] 부분 청산 (Partial Close)
                        # 식: 남은 마진 = 기존 마진 * (남은 수량 / 기존 수량)
                        reduction_ratio = new_size / existing_pos.size
                        existing_pos.size -= new_size
                        existing_pos.isolated_margin -= (existing_pos.isolated_margin * reduction_ratio)
                        status = "PARTIAL_CLOSED"
                    else:
                        # [B-2] 전량 청산 (Full Close)
                        del wallet.positions[pos_key]
                        status = "CLOSED"
                    
                    wallet.sync_balances()
                    return {"status": status, "realized_pnl": realized_pnl}

                # [B-3] 스위칭 (Switching): 기존 다 털고 반대로 새로 진입
                else:
                    del wallet.positions[pos_key] # 기존 포지션 전량 제거
                    
                    # 식 6. 남은 수량에 대한 신규 마진 재계산
                    # remaining_margin = (남은수량 * 가격) / 레버리지
                    remaining_size = new_size - existing_pos.size
                    margin = (remaining_size * exit_price) / Decimal(str(leverage))
                    
                    # 업데이트된 new_size와 margin으로 하단 [케이스 2] 신규 진입 로직 실행
                    new_size = remaining_size
                    # actual_entry_price와 side는 입력값 그대로 유지됨

        # [케이스 2] 신규 진입 (최초 진입 혹은 스위칭 후 남은 분량)
        liq_price = self.calculate_liq_price(side, actual_entry_price, leverage)
        new_position = Position(
            symbol=symbol, side=side, leverage=leverage, entry_price=actual_entry_price,
            size=new_size, isolated_margin=margin, liquidation_price=liq_price,
            take_profit_price=take_profit, stop_loss_price=stop_loss
        )
        
        wallet.positions[pos_key] = new_position
        wallet.sync_balances()
        return {"status": "NEW", "realized_pnl": Decimal('0')}

    def check_triggers(self, wallet: Wallet, symbol: str, current_price: Decimal) -> List[Dict[str, Any]]:
        """청산/익절/손절 실시간 감시"""
        trigger_results = []
        
        for pos_key, pos in list(wallet.positions.items()):
            if pos.symbol != symbol:
                continue
            
            pos.update_pnl(current_price)

            # 1. 강제 청산 체크
            is_liquidated = (pos.side == PositionSide.LONG and current_price <= pos.liquidation_price) or \
                            (pos.side == PositionSide.SHORT and current_price >= pos.liquidation_price)
                
            if is_liquidated:
                # 격리 마진 전액 손실 + 종료 수수료(청산가 기준) 차감
                exit_fee = (pos.liquidation_price * pos.size) * self.fee_rate
                realized_pnl = -(pos.isolated_margin + exit_fee)
                
                wallet.total_balance += realized_pnl
                del wallet.positions[pos_key]
                wallet.sync_balances()
                
                trigger_results.append({
                    "status": "LIQUIDATED", 
                    "realized_pnl": realized_pnl, 
                    "price": pos.liquidation_price
                })
                continue

            # 2. 익절/손절 체크
            is_tp = pos.take_profit_price and (
                (pos.side == PositionSide.LONG and current_price >= pos.take_profit_price) or
                (pos.side == PositionSide.SHORT and current_price <= pos.take_profit_price)
            )
            is_sl = pos.stop_loss_price and (
                (pos.side == PositionSide.LONG and current_price <= pos.stop_loss_price) or
                (pos.side == PositionSide.SHORT and current_price >= pos.stop_loss_price)
            )

            if is_tp or is_sl:
                reason = "TAKE_PROFIT" if is_tp else "STOP_LOSS"
                res = self._close_position(wallet, pos_key, current_price, reason)
                trigger_results.append(res)

        return trigger_results

    def _close_position(self, wallet: Wallet, pos_key: str, close_price: Decimal, reason: str) -> Dict[str, Any]:
        """포지션 종료 시 수수료와 슬리피지를 반영하여 실현 손익 계산"""
        pos = wallet.positions[pos_key]
        
        # 종료 시 슬리피지 반영
        if pos.side == PositionSide.LONG:
            actual_exit_price = close_price * (Decimal('1') - self.slippage_rate)
        else:
            actual_exit_price = close_price * (Decimal('1') + self.slippage_rate)

        # 수수료 계산: (진입 노미널 + 종료 노미널) * 수수료율
        entry_notional = pos.entry_price * pos.size
        exit_notional = actual_exit_price * pos.size
        total_fee = (entry_notional + exit_notional) * self.fee_rate

        # Gross PNL 계산
        if pos.side == PositionSide.LONG:
            gross_pnl = (actual_exit_price - pos.entry_price) * pos.size
        else:
            gross_pnl = (pos.entry_price - actual_exit_price) * pos.size
            
        # Net PNL = Gross PNL - 수수료
        realized_pnl = gross_pnl - total_fee

        wallet.total_balance += realized_pnl
        del wallet.positions[pos_key]
        wallet.sync_balances()
        
        return {
            "status": reason, 
            "realized_pnl": realized_pnl, 
            "price": actual_exit_price,
            "fee": total_fee
        }