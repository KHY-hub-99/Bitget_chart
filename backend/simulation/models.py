from pydantic import BaseModel, Field
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict

class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class PositionMode(str, Enum):
    ONE_WAY = "ONE_WAY"
    HEDGE = "HEDGE"
    
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
    
    # 수정 1 & 2: 엔진에서 수수료와 슬리피지 비율을 주입받고, 종료 시점의 불리한 가격을 반영
    def update_pnl(self, current_price: Decimal, fee_rate: Decimal = Decimal('0.0005'), slippage_rate: Decimal = Decimal('0.0002')):
        self.mark_price = current_price
        
        # 1. 시장가 종료를 가정하여 슬리피지를 적용한 '예상 체결가' 계산
        if self.side == PositionSide.LONG:
            estimated_exit_price = current_price * (Decimal('1') - slippage_rate)
        else:
            estimated_exit_price = current_price * (Decimal('1') + slippage_rate)
            
        # 2. 예상 수수료 계산 (진입 노미널 + 종료 예상 노미널)
        estimated_fee = (self.entry_price * self.size + estimated_exit_price * self.size) * fee_rate
        
        # 3. 총수익(Gross) 계산
        if self.side == PositionSide.LONG:
            gross_pnl = (estimated_exit_price - self.entry_price) * self.size
        else:
            gross_pnl = (self.entry_price - estimated_exit_price) * self.size
            
        # 4. 순수익(Net) 반영
        self.unrealized_pnl = gross_pnl - estimated_fee 
            
class Wallet(BaseModel):
    """
    사용자 지갑 상태 모델
    """
    initial_balance: Decimal = Field(default=Decimal('10000.0'), description="초기 자본금")
    total_balance: Decimal = Field(default=Decimal('10000.0'), description="총 자산 (실현된 잔고)")
    available_balance: Decimal = Field(default=Decimal('10000.0'), description="주문 가능 잔액")
    frozen_margin: Decimal = Field(default=Decimal('0.0'), description="사용 중인 증거금")
    
    position_mode: PositionMode = Field(default=PositionMode.ONE_WAY, description="포지션 모드")
    
    positions: Dict[str, Position] = Field(default_factory=dict, description="활성화된 포지션 목록")
    
    # 수정 3: 프론트엔드 대시보드 표시용 '순자산(Equity)' 동적 계산 속성 추가
    @property
    def equity(self) -> Decimal:
        """총 자산 가치(Equity) = 지갑 잔고 + 총 미실현 손익"""
        total_unrealized = sum(pos.unrealized_pnl for pos in self.positions.values())
        return self.total_balance + total_unrealized
    
    def sync_balances(self):
        """지갑 잔액 동기화"""
        total_frozen = sum(pos.isolated_margin for pos in self.positions.values())
        self.frozen_margin = total_frozen
        self.available_balance = self.total_balance - self.frozen_margin