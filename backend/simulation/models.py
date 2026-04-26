from pydantic import BaseModel, Field
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict

class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    
class Position(BaseModel):
    """
    격리 모드(Isolated) 개별 포지션 상태 모델
    """
    symbol: str = Field(..., description="거래 쌍 (예: BTCUSDT)")
    side: PositionSide = Field(..., description="포지션 방향 (LONG/SHORT)")
    leverage: int = Field(default=1, ge=1, le=125, description="레버리지")
    
    entry_price: Decimal = Field(default=Decimal('0.0'), description="진입 평균가")
    size: Decimal = Field(default=Decimal('0.0'), description="포지션 크기 (코인 수량)")
    
    mark_price: Decimal = Field(default=Decimal('0.0'), description="해당 심볼의 최신 시장 가격")
    
    isolated_margin: Decimal = Field(default=Decimal('0.0'), description="격리 증거금(USDT)")
    liquidation_price: Decimal = Field(default=Decimal('0.0'), description="강제 청산 가격")
    unrealized_pnl: Decimal = Field(default=Decimal('0.0'), description="미실현 손익(USDT)")
    
    take_profit_price: Optional[Decimal] = Field(default=None, description="목표 익절가")
    stop_loss_price: Optional[Decimal] = Field(default=None, description="목표 손절가")
    
    def update_pnl(self, current_price: Decimal):
        """현재 가격을 바탕으로 PNL을 업데이트하고, 현재 마크 프라이스를 저장"""
        # 포지션 자체의 현재가를 업데이트합니다. 
        self.mark_price = current_price

        if self.size == Decimal('0.0'):
            self.unrealized_pnl = Decimal('0.0')
            return

        if self.side == PositionSide.LONG:
            self.unrealized_pnl = (current_price - self.entry_price) * self.size
        else: # SHORT
            self.unrealized_pnl = (self.entry_price - current_price) * self.size
            
class Wallet(BaseModel):
    """
    사용자 지갑 상태 모델
    """
    initial_balance: Decimal = Field(default=Decimal('10000.0'), description="초기 자본금")
    total_balance: Decimal = Field(default=Decimal('10000.0'), description="총 자산")
    available_balance: Decimal = Field(default=Decimal('10000.0'), description="주문 가능 잔액")
    frozen_margin: Decimal = Field(default=Decimal('0.0'), description="사용 중인 증거금")
    
    positions: Dict[str, Position] = Field(default_factory=dict, description="활성화된 포지션 목록")
    
    def sync_balances(self):
        """지갑 잔액 동기화"""
        total_frozen = sum(pos.isolated_margin for pos in self.positions.values())
        self.frozen_margin = total_frozen
        self.available_balance = self.total_balance - self.frozen_margin