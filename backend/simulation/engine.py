from decimal import Decimal
from typing import Optional
from simulation.models import Wallet, Position, PositionSide

class SimulationEngine:
    def __init__(self, maintenance_margin_rate: Decimal = Decimal('0.004')):
        # 빗겟 기준 유지증거금률(MMR) 약 0.4% 기본 세팅
        self.mmr = maintenance_margin_rate
        
    def calculate_liq_price(self, side: PositionSide, entry_price: Decimal, leverage: int) -> Decimal:
        """격리 모드(Isolated) 강제 청산가 계산 공식"""
        lev = Decimal(str(leverage))
        if side == PositionSide.LONG:
            # Long 청산가 = 진입가 * (1 - (1/레버리지) + 유지증거금률)
            return entry_price * (1 - (1 / lev) + self.mmr)
        else:
            # Short 청산가 = 진입가 * (1 + (1/레버리지) - 유지증거금률)
            return entry_price * (1 + (1 / lev) - self.mmr)
        
    def open_position(self, wallet: Wallet, symbol: str, side: PositionSide, 
                    entry_price: Decimal, leverage: int, margin: Decimal,
                    take_profit: Optional[Decimal] = None, stop_loss: Optional[Decimal] = None):
        """새로운 포지션 진입 (주문 체결)"""
        
        # 1. 코인 수량 계산: 수량 = (증거금 * 레버리지) / 진입가
        size = (margin * Decimal(str(leverage))) / entry_price
        
        # 2. 청산가 계산
        liq_price = self.calculate_liq_price(side, entry_price, leverage)
        
        # 3. 포지션 데이터 생성
        new_position = Position(
            symbol=symbol,
            side=side,
            leverage=leverage,
            entry_price=entry_price,
            size=size,
            isolated_margin=margin,
            liquidation_price=liq_price,
            take_profit_price=take_profit,  # 익절가 
            stop_loss_price=stop_loss       # 손절가
        )
        
        # 4. 내 지갑에 포지션 등록하고 사용 가능 잔고 업데이트
        wallet.positions[symbol] = new_position
        wallet.sync_balances()
        
        return new_position
    
    def check_triggers(self, wallet: Wallet, symbol: str, current_price: Decimal):
        """
        [핵심] 차트의 캔들(현재가)이 움직일 때마다 실행되어 
        청산, 익절, 손절을 감시하는 함수
        """
        if symbol not in wallet.positions:
            return None

        pos = wallet.positions[symbol]
        
        # 1. PNL(미실현 손익) 실시간 업데이트
        pos.update_pnl(current_price)

        # 2. 강제 청산(Liquidation) 터치 확인
        is_liquidated = False
        if pos.side == PositionSide.LONG and current_price <= pos.liquidation_price:
            is_liquidated = True
        elif pos.side == PositionSide.SHORT and current_price >= pos.liquidation_price:
            is_liquidated = True
            
        if is_liquidated:
            # 청산 시: 격리 증거금만 날아가고 포지션 삭제
            del wallet.positions[symbol]
            wallet.total_balance -= pos.isolated_margin 
            wallet.sync_balances()
            return {"status": "LIQUIDATED", "price": current_price}

        # 3. 익절(TP) 터치 확인
        if pos.take_profit_price:
            if (pos.side == PositionSide.LONG and current_price >= pos.take_profit_price) or (pos.side == PositionSide.SHORT and current_price <= pos.take_profit_price):
                return self._close_position(wallet, symbol, current_price, "TAKE_PROFIT")

        # 4. 손절(SL) 터치 확인
        if pos.stop_loss_price:
            if (pos.side == PositionSide.LONG and current_price <= pos.stop_loss_price) or (pos.side == PositionSide.SHORT and current_price >= pos.stop_loss_price):
                return self._close_position(wallet, symbol, current_price, "STOP_LOSS")

        return {"status": "RUNNING", "unrealized_pnl": pos.unrealized_pnl}
    
    def _close_position(self, wallet: Wallet, symbol: str, close_price: Decimal, reason: str):
        """포지션 정상 종료 처리 (익절, 손절, 또는 유저 직접 종료)"""
        pos = wallet.positions[symbol]
        pos.update_pnl(close_price) 
        
        # 번 돈(또는 잃은 돈)을 총 자산에 합산
        wallet.total_balance += pos.unrealized_pnl
        del wallet.positions[symbol]
        wallet.sync_balances()
        
        return {"status": reason, "realized_pnl": pos.unrealized_pnl}