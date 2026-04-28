from pydantic import BaseModel, Field
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, List

class PositionSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class PositionMode(str, Enum):
    ONE_WAY = "ONE_WAY"
    HEDGE = "HEDGE"

class Position(BaseModel):
    """
    격리 모드(Isolated) 포지션 모델.
    Standard CamelCase 지표 및 n분할 진입(SMA/VWMA/SMC) 전략 추적에 최적화됨.
    """
    symbol: str = Field(..., description="거래 쌍 (예: BTCUSDT)")
    side: PositionSide = Field(..., description="방향 (LONG/SHORT)")
    leverage: int = Field(default=1, ge=1, le=125, description="레버리지 배수")
    
    # [가격 및 수량 정보]
    entry_price: Decimal = Field(default=Decimal('0.0'), description="평단가 (슬리피지 반영)")
    size: Decimal = Field(default=Decimal('0.0'), description="보유 수량 (코인 수)")
    mark_price: Decimal = Field(default=Decimal('0.0'), description="현재 시장가")
    isolated_margin: Decimal = Field(default=Decimal('0.0'), description="투입된 총 격리 증거금")
    liquidation_price: Decimal = Field(default=Decimal('0.0'), description="강제 청산 가격")
    position_mode: PositionMode = Field(default=PositionMode.ONE_WAY, description="포지션 모드 (ONE_WAY 또는 HEDGE)")
    
    # [분할 진입 상태 추적 - n분할 핵심]
    entry_tags: List[str] = Field(
        default_factory=list, 
        description="진입 완료된 기준선 태그 (예: ['SMA', 'VWMA']). 중복 진입 방지용"
    )
    allocated_unit_margin_ratio: Decimal = Field(
        default=Decimal('0.0'), 
        description="n분할 시 1회 진입당 사용할 증거금 비중 (예: 0.33)"
    )

    # --- [Standard CamelCase 기반 전략 필드] ---
    
    # 1. 손절 및 추적 (Trailing Extremes 연동)
    # Long: trailingBottom(Strong/Weak Low), Short: trailingTop(Strong/Weak High)
    stop_loss_price: Optional[Decimal] = Field(default=None, description="trailingBottom/Top 기반 손절가")
    sl_type: Optional[str] = Field(default=None, description="현재 SL의 성격 (Strong/Weak)")
    
    # 2. 익절 로직 (Equilibrium 및 다이아몬드 신호)
    entry_equilibrium: Optional[Decimal] = Field(default=None, description="진입 시점의 equilibrium 값 (50% 익절 기준)")
    is_partial_closed: bool = Field(default=False, description="50% 부분 익절 완료 여부")
    is_breakeven_set: bool = Field(default=False, description="부분 익절 후 손절가를 본절(entry_price)로 이동했는지 여부")
    
    # 3. 진입 규칙 태그 (Rule 1, 2, 3)
    entry_rule: str = Field(default="entryVwma", description="최초 진입 규칙 (entryVwma, entrySma, entrySmc)")
    
    # [통계 및 분석 데이터]
    unrealized_pnl: Decimal = Field(default=Decimal('0.0'), description="수수료 반영 미실현 손익")
    max_unrealized_pnl: Decimal = Field(default=Decimal('0.0'), description="보유 중 기록한 최고 수익")
    mdd_during_trade: Decimal = Field(default=Decimal('0.0'), description="보유 중 기록한 최대 낙폭")
    entry_time: Optional[int] = Field(default=None, description="진입 시점 (ms 단위)")

    def update_state(self, current_price: Decimal, fee_rate: Decimal, slippage_rate: Decimal):
        """가격 변동에 따른 PNL 및 통계 데이터 실시간 갱신"""
        self.mark_price = current_price
        
        # 슬리피지 반영 예상 종료가 계산
        if self.side == PositionSide.LONG:
            est_exit = current_price * (Decimal('1') - slippage_rate)
            gross_pnl = (est_exit - self.entry_price) * self.size
        else:
            est_exit = current_price * (Decimal('1') + slippage_rate)
            gross_pnl = (self.entry_price - est_exit) * self.size
            
        # 진입 시 수수료 + 종료 시 예상 수수료
        total_fee = (self.entry_price * self.size + est_exit * self.size) * fee_rate
        self.unrealized_pnl = gross_pnl - total_fee
        
        # 최대 수익 및 MDD 기록 갱신
        if self.unrealized_pnl > self.max_unrealized_pnl:
            self.max_unrealized_pnl = self.unrealized_pnl
        
        drawdown = self.max_unrealized_pnl - self.unrealized_pnl
        if drawdown > self.mdd_during_trade:
            self.mdd_during_trade = drawdown

class Wallet(BaseModel):
    """
    격리 증거금 관리에 최적화된 사용자 지갑 모델.
    """
    initial_balance: Decimal = Field(default=Decimal('10000.0'))
    total_balance: Decimal = Field(default=Decimal('10000.0'), description="실현된 지갑 잔고")
    available_balance: Decimal = Field(default=Decimal('10000.0'), description="주문 가능 잔액")
    frozen_margin: Decimal = Field(default=Decimal('0.0'), description="현재 포지션들에 묶인 총 격리 증거금")
    
    position_mode: PositionMode = Field(default=PositionMode.ONE_WAY)
    positions: Dict[str, Position] = Field(default_factory=dict, description="활성화된 포지션 목록")

    @property
    def equity(self) -> Decimal:
        """순자산 = 실현 잔고 + 모든 포지션의 미실현 손익"""
        unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        return self.total_balance + unrealized

    def sync(self):
        """증거금 현황 및 가용 잔고 동기화"""
        self.frozen_margin = sum(p.isolated_margin for p in self.positions.values())
        self.available_balance = self.total_balance - self.frozen_margin