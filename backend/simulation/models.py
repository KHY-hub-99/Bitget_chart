from pydantic import BaseModel, Field
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, List, Union

class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class PositionMode(str, Enum):
    ONE_WAY = "ONE_WAY"
    HEDGE = "HEDGE"

class Position(BaseModel):
    """
    격리 모드(Isolated) 포지션 모델.
    pine_data.py의 Standard CamelCase 지표들과 연동되도록 설계됨.
    """
    symbol: str = Field(..., description="거래 쌍 (예: BTCUSDT)")
    side: PositionSide = Field(..., description="방향 (LONG/SHORT)")
    leverage: int = Field(default=1, ge=1, le=125)
    
    entry_price: Decimal = Field(default=Decimal('0.0'), description="진입 평균가")
    size: Decimal = Field(default=Decimal('0.0'), description="수량")
    mark_price: Decimal = Field(default=Decimal('0.0'), description="현재가")
    isolated_margin: Decimal = Field(default=Decimal('0.0'), description="할당된 증거금")
    
    # [전략 실행 상태 추적]
    entry_tags: List[str] = Field(
        default_factory=list, 
        description="진입이 완료된 기준선 태그 리스트 (예: ['SMA', 'VWMA']). 동일 선 중복 진입 방지용"
    )
    allocated_unit_margin_ratio: Decimal = Field(
        default=Decimal('0.0'), 
        description="n분할 진입 시, 1회 진입당 투입할 가용 잔고의 비중 (예: 3분할이면 0.33)"
    )
    
    # --- [Standard CamelCase 기반 전략 필드] ---
    
    # 1. 손절 및 추적 로직 (Trailing Extremes 연동)
    # Long 시 trailingBottom(Strong Low), Short 시 trailingTop(Strong High) 참조
    stop_loss_price: Optional[Decimal] = Field(default=None, description="trailingBottom/Top 기반 SL")
    sl_type: Optional[str] = Field(default=None, description="Strong/Weak 기반 SL 종류")
    
    # 2. 익절 로직 (Equilibrium 및 다이아몬드 신호)
    entry_equilibrium: Optional[Decimal] = Field(default=None, description="진입 시점의 equilibrium 값")
    is_partial_closed: bool = Field(default=False, description="Equilibrium 50% 익절 여부")
    is_breakeven_set: bool = Field(default=False, description="본절가 SL 전환 여부")
    
    # 3. 진입 규칙 기록 (Rule 1 & Rule 2)
    entry_rule: str = Field(default="RULE_1_VWMA", description="entryVwma vs entrySmc 구분")
    
    # --- [통계 데이터] ---
    unrealized_pnl: Decimal = Field(default=Decimal('0.0'))
    max_unrealized_pnl: Decimal = Field(default=Decimal('0.0'))
    mdd_during_trade: Decimal = Field(default=Decimal('0.0'))
    entry_time: Optional[int] = Field(default=None, description="진입 시점 Timestamp")

    def update_state(self, current_price: Decimal, fee_rate: Decimal, slippage_rate: Decimal):
        """가격 변동에 따른 PNL 및 통계 갱신"""
        self.mark_price = current_price
        
        # 슬리피지 적용가 계산
        if self.side == PositionSide.LONG:
            est_exit = current_price * (Decimal('1') - slippage_rate)
            gross_pnl = (est_exit - self.entry_price) * self.size
        else:
            est_exit = current_price * (Decimal('1') + slippage_rate)
            gross_pnl = (self.entry_price - est_exit) * self.size
            
        total_fee = (self.entry_price * self.size + est_exit * self.size) * fee_rate
        self.unrealized_pnl = gross_pnl - total_fee
        
        # 통계 갱신
        if self.unrealized_pnl > self.max_unrealized_pnl:
            self.max_unrealized_pnl = self.unrealized_pnl
        
        drawdown = self.max_unrealized_pnl - self.unrealized_pnl
        if drawdown > self.mdd_during_trade:
            self.mdd_during_trade = drawdown

class Wallet(BaseModel):
    """
    격리 증거금 관리에 최적화된 지갑 모델.
    """
    initial_balance: Decimal = Field(default=Decimal('10000.0'))
    total_balance: Decimal = Field(default=Decimal('10000.0'), description="실현 잔고")
    available_balance: Decimal = Field(default=Decimal('10000.0'), description="주문 가능 잔고")
    frozen_margin: Decimal = Field(default=Decimal('0.0'), description="포지션에 묶인 증거금")
    
    positions: Dict[str, Position] = Field(default_factory=dict)

    @property
    def equity(self) -> Decimal:
        """순자산 (잔고 + 미실현 손익)"""
        unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        return self.total_balance + unrealized

    def sync(self):
        """증거금 현황 동기화"""
        self.frozen_margin = sum(p.isolated_margin for p in self.positions.values())
        self.available_balance = self.total_balance - self.frozen_margin