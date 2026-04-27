from decimal import Decimal
from typing import Optional, List, Dict, Any
from simulation.models import Wallet, Position, PositionSide, PositionMode

class SimulationEngine:
    def __init__(self, fee_rate: Decimal = Decimal('0.0005'), slippage_rate: Decimal = Decimal('0.0002')):
        self.mmr = Decimal('0.004') # 유지 마진율(Maintenance Margin Rate) 0.4% 설정
        self.fee_rate = fee_rate   # 거래 시 적용되는 표준 수수료율
        self.slippage_rate = slippage_rate # 시장가 주문 시 발생하는 체결 오차율

    def calculate_liq_price(self, side: PositionSide, entry_price: Decimal, leverage: int) -> Decimal:
        """격리 모드 청산 가격을 계산합니다."""
        lev = Decimal(str(leverage))
        if side == PositionSide.LONG:
            # 롱 청산가 = 진입가 * (1 - (1 / 레버리지) + 유지마진율)
            return entry_price * (Decimal('1') - (Decimal('1') / lev) + self.mmr)
        else:
            # 숏 청산가 = 진입가 * (1 + (1 / 레버리지) - 유지마진율)
            return entry_price * (Decimal('1') + (Decimal('1') / lev) - self.mmr)

    def open_position(self, wallet: Wallet, symbol: str, side: PositionSide, entry_price: Decimal, leverage: int, margin_ratio: Decimal, sl_price: Optional[Decimal] = None, equilibrium: Optional[Decimal] = None, tag: str = ""):
        """진입 비중(margin_ratio)을 사용하여 신규 진입 또는 분할 진입을 수행합니다."""
        
        # 투입 증거금 = 현재 가용 잔고 * 설정된 진입 비중 (예: 1/3인 경우 0.33)
        actual_margin = wallet.available_balance * margin_ratio 
        # 실제 체결가 = 시장가 * (1 + 슬리피지) [LONG 기준]
        actual_entry = entry_price * (Decimal('1') + self.slippage_rate) if side == PositionSide.LONG else entry_price * (Decimal('1') - self.slippage_rate)
        # 진입 수량 = (투입 증거금 * 레버리지) / 실제 체결가
        new_size = (actual_margin * Decimal(str(leverage))) / actual_entry
        # 포지션 모드(단방향/헷지)에 따른 포지션 키 생성
        pos_key = symbol if wallet.position_mode == PositionMode.ONE_WAY else f"{symbol}_{side.value}"

        if pos_key in wallet.positions:
            pos = wallet.positions[pos_key]
            # [분할 진입] 신규 평단가 = ((기존수량 * 기존평단) + (추가수량 * 추가평단)) / 총수량
            total_size = pos.size + new_size
            pos.entry_price = ((pos.size * pos.entry_price) + (new_size * actual_entry)) / total_size
            pos.size = total_size # 포지션 전체 수량 업데이트
            pos.isolated_margin += actual_margin # 격리 증거금 합산 업데이트
            if tag: pos.entry_tags.append(tag) # 진입에 사용된 지표 태그(vwma/sma) 기록
            
            # 평단가 변경에 따른 청산가 재계산
            pos.liquidation_price = self.calculate_liq_price(pos.side, pos.entry_price, pos.leverage)
            wallet.sync_balances() # 지갑 잔액 현행화
            return {"status": "MERGED", "entry_price": pos.entry_price}

        # [신규 진입] 포지션 객체 생성 및 초기 전략 데이터 저장
        liq_price = self.calculate_liq_price(side, actual_entry, leverage)
        new_pos = Position(
            symbol=symbol, side=side, leverage=leverage, entry_price=actual_entry,
            size=new_size, isolated_margin=actual_margin, liquidation_price=liq_price,
            stop_loss_price=sl_price, entry_equilibrium=equilibrium,
            allocated_unit_margin_ratio=margin_ratio # 추가 진입을 위한 단위 비중 저장
        )
        if tag: new_pos.entry_tags.append(tag) # 첫 진입 지표 태그 기록
        
        wallet.positions[pos_key] = new_pos
        wallet.sync_balances() # 지갑 잔고 현행화
        return {"status": "NEW", "entry_price": actual_entry}

    def check_triggers(self, wallet: Wallet, current_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """시뮬전략.txt의 지표 기반 분할 진입 및 익절/손절 로직을 체크합니다."""
        results = []
        curr_price = Decimal(str(current_data['close'])) # 현재가
        high_price = Decimal(str(current_data['high'])) # 고가
        low_price = Decimal(str(current_data['low'])) # 저가
        
        # 표준 변수명(vwma224, sma224, TOP, BOTTOM)을 사용하여 지표 추출
        is_top = current_data.get('TOP') == 1 # 빨간다이아 (롱 최종익절)
        is_bottom = current_data.get('BOTTOM') == 1 # 초록다이아 (숏 최종익절)
        vwma = Decimal(str(current_data.get('vwma224', 0))) # VWMA224 가격
        sma = Decimal(str(current_data.get('sma224', 0))) # SMA224 가격

        for pos_key, pos in list(wallet.positions.items()):
            pos.update_pnl(curr_price, self.fee_rate, self.slippage_rate) # 실시간 미실현 손익 업데이트

            # --- [1. 분할 진입(Laddering) 체크] ---
            # VWMA/SMA 중 아직 진입하지 않은 선이 있다면 1/3(저장된 비중)만큼 추가 진입
            target_lines = {"vwma": vwma, "sma": sma}
            for tag, line_price in target_lines.items():
                if tag not in pos.entry_tags:
                    # 롱: 저가가 선을 밟을 때 / 숏: 고가가 선에 닿을 때
                    is_touched = (pos.side == PositionSide.LONG and low_price <= line_price) or \
                                (pos.side == PositionSide.SHORT and high_price >= line_price)
                    if is_touched:
                        self.open_position(wallet, pos.symbol, pos.side, line_price, pos.leverage, pos.allocated_unit_margin_ratio, tag=tag)
                        results.append({"status": f"LADDER_ENTRY_{tag.upper()}", "price": line_price})

            # --- [2. 청산 체크] ---
            # 격리 증거금 전액 손실 구간(청산가) 도달 여부 확인
            is_liq = (pos.side == PositionSide.LONG and low_price <= pos.liquidation_price) or \
                    (pos.side == PositionSide.SHORT and high_price >= pos.liquidation_price)
            if is_liq:
                results.append(self._execute_liquidation(wallet, pos_key))
                continue

            # --- [3. 손절 체크] ---
            # Strong Low/High 기반 SL 또는 본절 로스 도달 확인
            is_sl = (pos.side == PositionSide.LONG and low_price <= pos.stop_loss_price) or \
                    (pos.side == PositionSide.SHORT and high_price >= pos.stop_loss_price)
            if is_sl:
                results.append(self._close_all(wallet, pos_key, pos.stop_loss_price, "STOP_LOSS"))
                continue

            # --- [4. 50% 분할 익절 로직] ---
            # Equilibrium 도달 시 물량 50% 익절 및 손절가를 진입가(Break-even)로 변경
            if not pos.is_partial_closed and pos.entry_equilibrium:
                is_partial = (pos.side == PositionSide.LONG and high_price >= pos.entry_equilibrium) or \
                            (pos.side == PositionSide.SHORT and low_price <= pos.entry_equilibrium)
                if is_partial:
                    results.append(self._execute_partial_tp(wallet, pos_key, pos.entry_equilibrium))
                    continue 

            # --- [5. 최종 익절 체크] ---
            # 다이아몬드 신호 발생 시 전량 익절 종료
            if (pos.side == PositionSide.LONG and is_top) or (pos.side == PositionSide.SHORT and is_bottom):
                results.append(self._close_all(wallet, pos_key, curr_price, "TAKE_PROFIT_DIAMOND"))

        return results

    def _execute_partial_tp(self, wallet: Wallet, pos_key: str, price: Decimal) -> Dict[str, Any]:
        """50% 익절을 실행하고 남은 물량의 손절가를 본절가로 수정합니다."""
        pos = wallet.positions[pos_key]
        # 부분 수익 = ((익절가 - 진입가) * 수량 * 0.5) - 수수료
        half_size = pos.size / Decimal('2')
        gross_pnl = (price - pos.entry_price) * half_size if pos.side == PositionSide.LONG else (pos.entry_price - price) * half_size
        fee = (pos.entry_price * half_size + price * half_size) * self.fee_rate # 매수/매도 수수료 합산
        realized = gross_pnl - fee
        
        wallet.total_balance += realized # 실현 손익 지갑 반영
        pos.size -= half_size # 보유 수량 50% 감소
        pos.isolated_margin /= Decimal('2') # 격리 증거금 50% 회수 및 업데이트
        pos.stop_loss_price = pos.entry_price # 손절가를 평단가로 변경하여 본절 로스 설정
        pos.is_partial_closed = True # 부분 익절 상태 저장
        
        wallet.sync_balances() # 지갑 상태 동기화
        return {"status": "PARTIAL_TP", "pnl": realized, "price": price}
    
    def _close_all(self, wallet: Wallet, pos_key: str, price: Decimal, reason: str) -> Dict[str, Any]:
        """포지션을 전량 종료하고 최종 수익을 정산합니다."""
        pos = wallet.positions[pos_key]
        # 실제 종료가 = 종료가 * (1 - 슬리피지) [LONG 기준]
        exit_price = price * (Decimal('1') - self.slippage_rate) if pos.side == PositionSide.LONG else price * (Decimal('1') + self.slippage_rate)
        # 최종 실현 손익 = ((종료가 - 진입가) * 수량) - 수수료
        gross = (exit_price - pos.entry_price) * pos.size if pos.side == PositionSide.LONG else (pos.entry_price - exit_price) * pos.size
        fee = (pos.entry_price * pos.size + exit_price * pos.size) * self.fee_rate # 총 거래 수수료 계산
        realized = gross - fee

        # 격리 모드 손실 캡핑: 최대 손실은 투입된 격리 증거금으로 제한
        if realized < -pos.isolated_margin: realized = -pos.isolated_margin

        wallet.total_balance += realized # 최종 손익 지갑 반영
        del wallet.positions[pos_key] # 포지션 제거
        wallet.sync_balances() # 지갑 상태 동기화
        return {"status": reason, "pnl": realized, "price": exit_price}
    
    def _execute_liquidation(self, wallet: Wallet, pos_key: str) -> Dict[str, Any]:
        """강제 청산 시 포지션 증거금을 전량 몰수합니다."""
        pos = wallet.positions[pos_key]
        loss = -pos.isolated_margin # 격리 증거금 전체 손실 처리
        wallet.total_balance += loss # 지갑 잔고 차감
        del wallet.positions[pos_key] # 포지션 제거
        wallet.sync_balances() # 지갑 상태 동기화
        return {"status": "LIQUIDATED", "pnl": loss, "price": pos.liquidation_price}