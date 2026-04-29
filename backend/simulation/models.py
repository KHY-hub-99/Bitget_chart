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
    Standard CamelCase 지표 통일 기준과 하이브리드 전략(Rule 1, Rule 2) 추적에 최적화됨.
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
    
    # --- [하이브리드 전략 상태 추적 필드 (Rule 1 & Rule 2)] ---
    
    strategy_rule: str = Field(
        default="RULE_1", 
        description="현재 포지션에 적용된 전략 룰 ('RULE_1' 또는 'RULE_2')"
    )
    
    # [룰 1 전용: SMA/VWMA 분할 진입 추적]
    entry_tags: List[str] = Field(
        default_factory=list, 
        description="진입 완료된 라인 태그 (예: ['sma224', 'vwma224']). 중복 진입 방지용"
    )
    first_entry_line_val: Optional[Decimal] = Field(
        default=None, 
        description="룰 1에서 1차 진입했던 선의 당시 가격. 2차 진입 시 더 유리한 위치인지(고저) 비교하기 위해 저장"
    )
    allocated_unit_margin_ratio: Decimal = Field(
        default=Decimal('0.0'), 
        description="룰 1 분할 진입 시 1회 진입당 사용할 증거금 비중"
    )

    # [손절(SL) 상태]
    stop_loss_price: Optional[Decimal] = Field(
        default=None, 
        description="룰 1: 진입가 기준 고정 15%*1.1 / 룰 2: trailingBottom(Long) 또는 swingHighLevel(Short)"
    )
    
    # [룰 2 전용: 익절(TP) 및 본절 로스 추적]
    entry_equilibrium: Optional[Decimal] = Field(
        default=None, 
        description="룰 2 진입 시점의 equilibrium 값 (50% 익절 기준선)"
    )
    is_partial_closed: bool = Field(
        default=False, 
        description="룰 2에서 equilibrium 또는 하/상단에 위치한 sma224/vwma224 도달로 50% 부분 익절 완료 여부"
    )
    is_breakeven_set: bool = Field(
        default=False, 
        description="부분 익절 후 남은 50% 물량의 손절가를 본절(entry_price)로 이동했는지 여부"
    )
    # ※ 최종 전량 익절 트리거: 엔진에서 topDiamond(Long), bottomDiamond(Short) 마커 발생 시 처리
    
    # [통계 및 분석 데이터]
    unrealized_pnl: Decimal = Field(default=Decimal('0.0'), description="수수료 반영 미실현 손익")
    max_unrealized_pnl: Decimal = Field(default=Decimal('0.0'), description="보유 중 기록한 최고 수익")
    mdd_during_trade: Decimal = Field(default=Decimal('0.0'), description="보유 중 기록한 최대 낙폭")
    entry_time: Optional[int] = Field(default=None, description="최초 진입 시점 (ms 단위)")

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