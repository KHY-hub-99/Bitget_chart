from decimal import Decimal
from typing import Optional
from simulation.models import Wallet, Position, PositionSide, PositionMode

class SimulationEngine:
    def __init__(self, maintenance_margin_rate: Decimal = Decimal('0.004')):
        self.mmr = maintenance_margin_rate
        
    def calculate_liq_price(self, side: PositionSide, entry_price: Decimal, leverage: int) -> Decimal:
        """격리 모드(Isolated) 강제 청산가 계산 공식"""
        lev = Decimal(str(leverage))
        if side == PositionSide.LONG:
            return entry_price * (1 - (1 / lev) + self.mmr)
        else:
            return entry_price * (1 + (1 / lev) - self.mmr)
        
    def _get_position_key(self, symbol: str, side: PositionSide, mode: PositionMode) -> str:
        """모드에 따른 딕셔너리 키 생성 (양방향은 LONG/SHORT을 분리)"""
        if mode == PositionMode.HEDGE:
            return f"{symbol}_{side.value}"
        return symbol
        
    def open_position(self, wallet: Wallet, symbol: str, side: PositionSide, 
                    entry_price: Decimal, leverage: int, margin: Decimal,
                    take_profit: Optional[Decimal] = None, stop_loss: Optional[Decimal] = None):
        """새로운 주문 체결 (물타기 및 스위칭 포함)"""
        
        new_size = (margin * Decimal(str(leverage))) / entry_price
        pos_key = self._get_position_key(symbol, side, wallet.position_mode)
        
        # 케이스 1: 기존 포지션이 있을 경우 (단방향 or 양방향의 같은 방향)
        if pos_key in wallet.positions:
            existing_pos = wallet.positions[pos_key]
            
            # [A] 같은 방향이면 물타기 (가중 평균)
            if existing_pos.side == side:
                total_size = existing_pos.size + new_size
                # 평단가 = ((기존수량*기존평단) + (신규수량*신규평단)) / 총수량
                new_entry = ((existing_pos.size * existing_pos.entry_price) + (new_size * entry_price)) / total_size
                
                existing_pos.size = total_size
                existing_pos.entry_price = new_entry
                existing_pos.isolated_margin += margin
                existing_pos.liquidation_price = self.calculate_liq_price(side, new_entry, leverage)
                
                # TP/SL 업데이트 (새로 들어온 값으로 덮어씌움)
                if take_profit: existing_pos.take_profit_price = take_profit
                if stop_loss: existing_pos.stop_loss_price = stop_loss
                
                wallet.sync_balances()
                return {"status": "MERGED", "message": "물타기 체결", "position": existing_pos}
                
            # [B] 단방향 모드인데 반대 방향 주문이 들어온 경우 (부분 청산 / 스위칭)
            else:
                realized_pnl = Decimal('0.0')
                
                # B-1. 부분 청산 (새 주문 수량이 기존 수량보다 작을 때)
                if new_size < existing_pos.size:
                    if existing_pos.side == PositionSide.LONG:
                        realized_pnl = (entry_price - existing_pos.entry_price) * new_size
                    else:
                        realized_pnl = (existing_pos.entry_price - entry_price) * new_size
                        
                    reduction_ratio = new_size / existing_pos.size
                    margin_reduction = existing_pos.isolated_margin * reduction_ratio
                    
                    existing_pos.size -= new_size
                    existing_pos.isolated_margin -= margin_reduction
                    
                    wallet.total_balance += realized_pnl
                    wallet.sync_balances()
                    return {"status": "PARTIAL_CLOSED", "message": "부분 청산", "realized_pnl": realized_pnl}
                    
                # B-2. 전량 청산 (정확히 같은 수량)
                elif new_size == existing_pos.size:
                    if existing_pos.side == PositionSide.LONG:
                        realized_pnl = (entry_price - existing_pos.entry_price) * existing_pos.size
                    else:
                        realized_pnl = (existing_pos.entry_price - entry_price) * existing_pos.size
                        
                    wallet.total_balance += realized_pnl
                    del wallet.positions[pos_key]
                    wallet.sync_balances()
                    return {"status": "CLOSED", "message": "포지션 전량 종료", "realized_pnl": realized_pnl}
                    
                # B-3. 스위칭 (새 주문 수량이 더 커서, 기존거 다 청산하고 반대로 진입)
                else:
                    if existing_pos.side == PositionSide.LONG:
                        realized_pnl = (entry_price - existing_pos.entry_price) * existing_pos.size
                    else:
                        realized_pnl = (existing_pos.entry_price - entry_price) * existing_pos.size
                    
                    remaining_size = new_size - existing_pos.size
                    remaining_margin = (remaining_size * entry_price) / Decimal(str(leverage))
                    
                    wallet.total_balance += realized_pnl
                    del wallet.positions[pos_key] # 기존 포지션 날림
                    
                    # 아래에서 남은 수량으로 신규 진입을 위해 new_size와 margin 덮어쓰기
                    new_size = remaining_size
                    margin = remaining_margin
                    # 로직이 아래 케이스 2로 자연스럽게 흘러가서 신규 진입됨

        # 케이스 2: 신규 진입 (포지션이 없거나 스위칭 후 남은 수량)
        liq_price = self.calculate_liq_price(side, entry_price, leverage)
        new_position = Position(
            symbol=symbol,
            side=side,
            leverage=leverage,
            entry_price=entry_price,
            size=new_size,
            isolated_margin=margin,
            liquidation_price=liq_price,
            take_profit_price=take_profit,
            stop_loss_price=stop_loss
        )
        
        wallet.positions[pos_key] = new_position
        wallet.sync_balances()
        return {"status": "NEW", "message": "신규 포지션 진입", "position": new_position}
    
    def check_triggers(self, wallet: Wallet, symbol: str, current_price: Decimal):
        """차트의 캔들이 움직일 때마다 실행되어 청산, 익절, 손절을 감시"""
        trigger_results = []
        
        # 🟢 딕셔너리 키가 아닌, 포지션 내부의 symbol 속성으로 모두 찾아서 감시합니다.
        for pos_key, pos in list(wallet.positions.items()):
            if pos.symbol != symbol:
                continue

            # 1. 강제 청산 터치
            is_liquidated = False
            if pos.side == PositionSide.LONG and current_price <= pos.liquidation_price:
                is_liquidated = True
            elif pos.side == PositionSide.SHORT and current_price >= pos.liquidation_price:
                is_liquidated = True
                
            if is_liquidated:
                del wallet.positions[pos_key] # 🟢 symbol 대신 pos_key로 삭제
                wallet.total_balance -= pos.isolated_margin 
                wallet.sync_balances()
                trigger_results.append({"status": "LIQUIDATED", "price": current_price, "side": pos.side})
                continue

            # 2. 익절(TP) / 손절(SL) 터치
            if pos.take_profit_price:
                if (pos.side == PositionSide.LONG and current_price >= pos.take_profit_price) or \
                (pos.side == PositionSide.SHORT and current_price <= pos.take_profit_price):
                    res = self._close_position(wallet, pos_key, current_price, "TAKE_PROFIT") # 🟢 pos_key 전달
                    trigger_results.append(res)
                    continue

            if pos.stop_loss_price:
                if (pos.side == PositionSide.LONG and current_price <= pos.stop_loss_price) or \
                (pos.side == PositionSide.SHORT and current_price >= pos.stop_loss_price):
                    res = self._close_position(wallet, pos_key, current_price, "STOP_LOSS") # 🟢 pos_key 전달
                    trigger_results.append(res)

        return trigger_results if trigger_results else {"status": "RUNNING"}
    
    # 🟢 _close_position 파라미터도 symbol 대신 pos_key를 받도록 수정해야 합니다.
    def _close_position(self, wallet: Wallet, pos_key: str, close_price: Decimal, reason: str):
        pos = wallet.positions[pos_key]
        pos.update_pnl(close_price) 
        
        wallet.total_balance += pos.unrealized_pnl
        del wallet.positions[pos_key]
        wallet.sync_balances()
        
        return {"status": reason, "realized_pnl": pos.unrealized_pnl}