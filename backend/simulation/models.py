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
    symbol: str = Field(..., description="거래 쌍 (예: BTC/USDT)")
    side: PositionSide = Field(..., description="포지션 방향 (LONG/SHORT)")
    leverage: int = Field(default=1, ge=1, le=125, description="레버리지 (1x ~ 125x)")
    
    # Decimal을 사용하여 소수점 오차 방지
    entry_price: Decimal = Field(default=Decimal('0.0'), description="진입 평균가")
    size: Decimal = Field(default=Decimal('0.0'), description="포지션 크기 (코인 수량)")
    
    # 격리 모드의 핵심 변수들
    isolated_margin: Decimal = Field(default=Decimal('0.0'), description="이 포지션에 묶인 격리 증거금(USDT)")
    liquidation_price: Decimal = Field(default=Decimal('0.0'), description="강제 청산 가격")
    unrealized_pnl: Decimal = Field(default=Decimal('0.0'), description="미실현 손익(USDT)")
    
    # 익절(TP) / 손절(SL) 타겟 프라이스 추가
    take_profit_price: Optional[Decimal] = Field(default=None, description="목표 익절가 (TP)")
    stop_loss_price: Optional[Decimal] = Field(default=None, description="목표 손절가 (SL)")
    
    def update_pnl(self, current_price: Decimal):
        """현재 가격을 바탕으로 미실현 손익(PNL)을 업데이트하는 헬퍼 함수"""
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
    initial_balance: Decimal = Field(default=Decimal('10000.0'), description="초기 지급 자본금(USDT)")
    total_balance: Decimal = Field(default=Decimal('10000.0'), description="총 자산 (초기 자본금 + 실현 손익)")
    available_balance: Decimal = Field(default=Decimal('10000.0'), description="주문 가능 잔액(USDT)")
    frozen_margin: Decimal = Field(default=Decimal('0.0'), description="현재 포지션 및 미체결 주문에 묶인 증거금 총합")
    
    # 현재 보유 중인 포지션 목록 (예: {"BTC/USDT": Position})
    positions: Dict[str, Position] = Field(default_factory=dict, description="현재 활성화된 포지션 목록")
    
    def sync_balances(self):
        """포지션 상태에 맞춰 지갑의 사용 가능 잔액과 묶인 증거금을 동기화"""
        total_frozen = sum(pos.isolated_margin for pos in self.positions.values())
        self.frozen_margin = total_frozen
        self.available_balance = self.total_balance - self.frozen_margin