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
            return entry_price * (Decimal('1') - (Decimal('1') / lev) + self.mmr)
        else:
            return entry_price * (Decimal('1') + (Decimal('1') / lev) - self.mmr)

    def open_position(self, wallet: Wallet, symbol: str, side: PositionSide, entry_price: Decimal, 
                    leverage: int, margin_ratio: Decimal, strategy_rule: str = "RULE_1",
                    sl_price: Optional[Decimal] = None, equilibrium: Optional[Decimal] = None, 
                    tag: str = "", first_entry_val: Optional[Decimal] = None):
        """
        신규 진입 및 추가 분할 진입(Scaling-in)을 통합 관리합니다.
        """
        pos_key = symbol if wallet.position_mode == PositionMode.ONE_WAY else f"{symbol}_{side.value}"
        
        actual_entry = entry_price * (Decimal('1') + self.slippage_rate) if side == PositionSide.LONG else entry_price * (Decimal('1') - self.slippage_rate)
        actual_margin = wallet.available_balance * margin_ratio 
        new_size = (actual_margin * Decimal(str(leverage))) / actual_entry

        # 스마트 블로킹 로직 (불타기 / 2차 진입)
        if pos_key in wallet.positions:
            pos = wallet.positions[pos_key]
            
            # 1. 이미 같은 기준선(태그)으로 들어왔다면 진입 차단 (폭주 방지)
            if tag in pos.entry_tags:
                return {"status": "SKIPPED_ALREADY_TAGGED", "tag": tag}
            
            # 2. 새로운 기준선(태그)이라면 '불타기(Scaling-in)' 실행
            total_size = pos.size + new_size
            pos.entry_price = ((pos.size * pos.entry_price) + (new_size * actual_entry)) / total_size
            pos.size = total_size
            pos.isolated_margin += actual_margin
            
            if tag: pos.entry_tags.append(tag)
            
            # 평단이 바뀌었으므로 청산가 재계산
            pos.liquidation_price = self.calculate_liq_price(pos.side, pos.entry_price, pos.leverage)
            wallet.sync()
            return {"status": f"LADDER_MERGED_{tag}", "entry_price": pos.entry_price}

        # 3. 포지션이 아예 없는 경우 (최초 신규 진입)
        new_pos = Position(
            symbol=symbol, side=side, leverage=leverage, entry_price=actual_entry,
            size=new_size, isolated_margin=actual_margin, 
            liquidation_price=self.calculate_liq_price(side, actual_entry, leverage),
            strategy_rule=strategy_rule,
            stop_loss_price=sl_price, 
            entry_equilibrium=equilibrium, 
            first_entry_line_val=first_entry_val,
            allocated_unit_margin_ratio=margin_ratio # 다음 분할 진입 시 사용할 비중
        )
        if tag: new_pos.entry_tags.append(tag)
        
        wallet.positions[pos_key] = new_pos
        wallet.sync()
        return {"status": "NEW_ENTRY", "entry_price": actual_entry, "rule": strategy_rule}

    def check_triggers(self, wallet: Wallet, current_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """시뮬전략.txt의 지표 기반 익절/손절/청산 로직을 체크합니다."""
        results = []
        curr_price = Decimal(str(current_data['close']))
        high_price = Decimal(str(current_data['high']))
        low_price = Decimal(str(current_data['low']))
        
        # 최신 Standard CamelCase 컬럼명 기준 추출
        vwma = Decimal(str(current_data.get('vwma224', 0)))
        sma = Decimal(str(current_data.get('sma224', 0)))
        is_top = current_data.get('topDiamond') == 1       # 빨간다이아 (롱 종료)
        is_bottom = current_data.get('bottomDiamond') == 1 # 초록다이아 (숏 종료)

        for pos_key, pos in list(wallet.positions.items()):
            pos.update_state(curr_price, self.fee_rate, self.slippage_rate) 
            
            # [룰 1 전용] 분할 추가 진입 로직 (Laddering) - 평단가 유리할 때만
            if pos.strategy_rule == "RULE_1" and pos.first_entry_line_val is not None:
                if pos.side == PositionSide.LONG:
                    # SMA 진입 후 VWMA가 '더 아래에' 있고 닿았을 때
                    if "SMA" in pos.entry_tags and "VWMA" not in pos.entry_tags:
                        if 0 < vwma < pos.first_entry_line_val and low_price <= vwma:
                            self.open_position(wallet, pos.symbol, pos.side, vwma, pos.leverage, pos.allocated_unit_margin_ratio, tag="VWMA")
                            results.append({"status": "LADDER_LONG_VWMA", "price": vwma})
                    # VWMA 진입 후 SMA가 '더 아래에' 있고 닿았을 때
                    elif "VWMA" in pos.entry_tags and "SMA" not in pos.entry_tags:
                        if 0 < sma < pos.first_entry_line_val and low_price <= sma:
                            self.open_position(wallet, pos.symbol, pos.side, sma, pos.leverage, pos.allocated_unit_margin_ratio, tag="SMA")
                            results.append({"status": "LADDER_LONG_SMA", "price": sma})

                elif pos.side == PositionSide.SHORT:
                    # SMA 진입 후 VWMA가 '더 위에' 있고 닿았을 때
                    if "SMA" in pos.entry_tags and "VWMA" not in pos.entry_tags:
                        if vwma > pos.first_entry_line_val and high_price >= vwma:
                            self.open_position(wallet, pos.symbol, pos.side, vwma, pos.leverage, pos.allocated_unit_margin_ratio, tag="VWMA")
                            results.append({"status": "LADDER_SHORT_VWMA", "price": vwma})
                    # VWMA 진입 후 SMA가 '더 위에' 있고 닿았을 때
                    elif "VWMA" in pos.entry_tags and "SMA" not in pos.entry_tags:
                        if sma > pos.first_entry_line_val and high_price >= sma:
                            self.open_position(wallet, pos.symbol, pos.side, sma, pos.leverage, pos.allocated_unit_margin_ratio, tag="SMA")
                            results.append({"status": "LADDER_SHORT_SMA", "price": sma})

            # --- [공통: 청산 체크] ---
            is_liq = (pos.side == PositionSide.LONG and low_price <= pos.liquidation_price) or \
                    (pos.side == PositionSide.SHORT and high_price >= pos.liquidation_price)
            if is_liq:
                results.append(self._execute_liquidation(wallet, pos_key))
                continue

            # --- [공통: 손절 체크] ---
            if pos.stop_loss_price:
                is_sl = (pos.side == PositionSide.LONG and low_price <= pos.stop_loss_price) or \
                        (pos.side == PositionSide.SHORT and high_price >= pos.stop_loss_price)
                if is_sl:
                    reason = "STOP_LOSS_BREAKEVEN" if pos.is_breakeven_set else "STOP_LOSS"
                    results.append(self._close_all(wallet, pos_key, pos.stop_loss_price, reason))
                    continue

            # [룰 2 전용] 50% 동적 선익절 로직 (Equilibrium vs SMA/VWMA)
            if pos.strategy_rule == "RULE_2" and not pos.is_partial_closed and pos.entry_equilibrium:
                eq = pos.entry_equilibrium
                is_partial = False
                tp_trigger_price = eq
                
                if pos.side == PositionSide.LONG:
                    # VWMA나 SMA가 equilibrium보다 아래에 있다면 먼저 터치될 때 50% 익절
                    if 0 < vwma < eq and high_price >= vwma:
                        is_partial, tp_trigger_price = True, vwma
                    elif 0 < sma < eq and high_price >= sma:
                        is_partial, tp_trigger_price = True, sma
                    elif high_price >= eq:
                        is_partial, tp_trigger_price = True, eq
                
                elif pos.side == PositionSide.SHORT:
                    # VWMA나 SMA가 equilibrium보다 위에 있다면 먼저 터치될 때 50% 익절
                    if vwma > eq and low_price <= vwma:
                        is_partial, tp_trigger_price = True, vwma
                    elif sma > eq and low_price <= sma:
                        is_partial, tp_trigger_price = True, sma
                    elif low_price <= eq:
                        is_partial, tp_trigger_price = True, eq

                if is_partial:
                    results.append(self._execute_partial_tp(wallet, pos_key, tp_trigger_price))
                    continue 

            # --- [공통: 최종 전량 익절 (다이아몬드)] ---
            if (pos.side == PositionSide.LONG and is_top) or (pos.side == PositionSide.SHORT and is_bottom):
                results.append(self._close_all(wallet, pos_key, curr_price, "TAKE_PROFIT_DIAMOND"))

        return results

    def _execute_partial_tp(self, wallet: Wallet, pos_key: str, price: Decimal) -> Dict[str, Any]:
        """50% 익절을 실행하고 남은 물량의 손절가를 본절가로 수정합니다."""
        pos = wallet.positions[pos_key]
        half_size = pos.size / Decimal('2')
        
        gross_pnl = (price - pos.entry_price) * half_size if pos.side == PositionSide.LONG else (pos.entry_price - price) * half_size
        fee = (pos.entry_price * half_size + price * half_size) * self.fee_rate
        realized = gross_pnl - fee
        
        wallet.total_balance += realized 
        pos.size -= half_size 
        pos.isolated_margin /= Decimal('2') 
        
        # [본절 로스 셋팅]
        pos.stop_loss_price = pos.entry_price 
        pos.is_partial_closed = True 
        pos.is_breakeven_set = True
        
        wallet.sync() 
        return {"status": "PARTIAL_TP", "pnl": realized, "price": price}
    
    def _close_all(self, wallet: Wallet, pos_key: str, price: Decimal, reason: str) -> Dict[str, Any]:
        """포지션을 전량 종료하고 최종 수익을 정산합니다."""
        pos = wallet.positions[pos_key]
        exit_price = price * (Decimal('1') - self.slippage_rate) if pos.side == PositionSide.LONG else price * (Decimal('1') + self.slippage_rate)
        
        gross = (exit_price - pos.entry_price) * pos.size if pos.side == PositionSide.LONG else (pos.entry_price - exit_price) * pos.size
        fee = (pos.entry_price * pos.size + exit_price * pos.size) * self.fee_rate
        realized = gross - fee

        if realized < -pos.isolated_margin: 
            realized = -pos.isolated_margin

        wallet.total_balance += realized 
        del wallet.positions[pos_key] 
        wallet.sync() 
        return {"status": reason, "pnl": realized, "price": exit_price}
    
    def _execute_liquidation(self, wallet: Wallet, pos_key: str) -> Dict[str, Any]:
        """강제 청산 시 포지션 증거금을 전량 몰수합니다."""
        pos = wallet.positions[pos_key]
        loss = -pos.isolated_margin 
        wallet.total_balance += loss 
        del wallet.positions[pos_key] 
        wallet.sync() 
        return {"status": "LIQUIDATED", "pnl": loss, "price": pos.liquidation_price}