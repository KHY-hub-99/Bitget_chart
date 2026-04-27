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
    격리 모드(Isolated) 개별 포지션 상태 모델.
    전략 실행 상태를 추적하기 위한 필드들이 추가되었습니다.
    """
    symbol: str = Field(..., description="거래 쌍 (예: BTCUSDT)")
    side: PositionSide = Field(..., description="포지션 방향 (LONG/SHORT)")
    leverage: int = Field(default=1, ge=1, le=125, description="레버리지")
    entry_price: Decimal = Field(default=Decimal('0.0'), description="진입 평균가")
    size: Decimal = Field(default=Decimal('0.0'), description="포지션 크기 (코인 수량)")
    mark_price: Decimal = Field(default=Decimal('0.0'), description="최신 시장 가격")
    isolated_margin: Decimal = Field(default=Decimal('0.0'), description="격리 증거금(USDT)")
    liquidation_price: Decimal = Field(default=Decimal('0.0'), description="강제 청산 가격")
    unrealized_pnl: Decimal = Field(default=Decimal('0.0'), description="미실현 손익(USDT)")
    
    # --- [전략 핵심 필드] ---
    stop_loss_price: Optional[Decimal] = Field(default=None, description="현재 손절가 (Strong Low/High)")
    take_profit_price: Optional[Decimal] = Field(default=None, description="최종 익절가 (Diamonds 신호용)")
    
    # 분할 익절 및 상태 추적 
    entry_equilibrium: Optional[Decimal] = Field(default=None, description="진입 시점의 Equilibrium 값")
    is_partial_closed: bool = Field(default=False, description="50% 부분 익절 완료 여부")
    is_breakeven_set: bool = Field(default=False, description="본절 로스(Break-even) 전환 여부")
    
    # 통계용 데이터
    max_unrealized_pnl: Decimal = Field(default=Decimal('0.0'), description="보유 중 기록한 최대 미실현 수익")
    mdd_during_trade: Decimal = Field(default=Decimal('0.0'), description="보유 중 기록한 최대 낙폭")
    
    # [추가] 분할 진입 추적용 필드
    entry_tags: List[str] = Field(default_factory=list, description="진입이 완료된 지표 태그 (예: 'vwma', 'sma')")
    allocated_unit_margin: Decimal = Field(default=Decimal('0.0'), description="1회 진입 시 사용하는 단위 증거금")

    def update_pnl(self, current_price: Decimal, fee_rate: Decimal = Decimal('0.0005'), slippage_rate: Decimal = Decimal('0.0002')):
        """미실현 손익 및 거래 중 최대 수익/낙폭 갱신"""
        self.mark_price = current_price
        
        # 슬리피지 반영 예상 종료가
        if self.side == PositionSide.LONG:
            est_exit = current_price * (Decimal('1') - slippage_rate)
        else:
            est_exit = current_price * (Decimal('1') + slippage_rate)
            
        # 수수료 계산 (진입 + 종료)
        total_fee = (self.entry_price * self.size + est_exit * self.size) * fee_rate
        
        # PNL 계산
        if self.side == PositionSide.LONG:
            gross_pnl = (est_exit - self.entry_price) * self.size
        else:
            gross_pnl = (self.entry_price - est_exit) * self.size
            
        self.unrealized_pnl = gross_pnl - total_fee
        
        # 최대 수익 및 MDD 업데이트 (통계용)
        if self.unrealized_pnl > self.max_unrealized_pnl:
            self.max_unrealized_pnl = self.unrealized_pnl
        
        current_drawdown = self.max_unrealized_pnl - self.unrealized_pnl
        if current_drawdown > self.mdd_during_trade:
            self.mdd_during_trade = current_drawdown
            
class Wallet(BaseModel):
    """
    사용자 지갑 상태 모델. 격리 모드 증거금 관리에 최적화됨.
    """
    initial_balance: Decimal = Field(default=Decimal('10000.0'), description="초기 자본금")
    total_balance: Decimal = Field(default=Decimal('10000.0'), description="총 자산 (실현된 잔고)")
    available_balance: Decimal = Field(default=Decimal('10000.0'), description="주문 가능 잔액")
    frozen_margin: Decimal = Field(default=Decimal('0.0'), description="현재 포지션들에 할당된 총 격리 증거금")
    
    position_mode: PositionMode = Field(default=PositionMode.ONE_WAY, description="단방향/헷지 모드")
    positions: Dict[str, Position] = Field(default_factory=dict, description="활성화된 포지션 목록")
    
    @property
    def equity(self) -> Decimal:
        """순자산 = 지갑 잔고 + 미실현 손익"""
        total_unrealized = sum(pos.unrealized_pnl for pos in self.positions.values())
        return self.total_balance + total_unrealized
    
    def sync_balances(self):
        """격리 증거금을 제외한 실제 사용 가능 금액 동기화 [cite: 103]"""
        self.frozen_margin = sum(pos.isolated_margin for pos in self.positions.values())
        self.available_balance = self.total_balance - self.frozen_margin