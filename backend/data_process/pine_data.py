import pandas as pd
import pandas_ta as ta
import numpy as np

def apply_master_strategy(df: pd.DataFrame) -> pd.DataFrame:
    """
    OHLCV 데이터프레임을 받아 README.md 표준 변수명(CamelCase)에 맞춰 전략 지표를 계산합니다.
    (Null 방지 Non-Repainting SMC 로직 적용 완료)
    """
    df = df.copy()
    
    # --- [1. 파라미터 (Parameters)] ---
    tenkanLen, kijunLen, senkouBLen = 9, 26, 52
    displacement = 26
    rsiLen, mfiLen = 14, 14
    bbLen, bbMult = 20, 2.2
    volMult, whaleLen = 1.5, 224
    swingLen = 50 

    # --- [2. 보조지표 (Indicators)] ---
    
    # 일목균형표 (Ichimoku)
    df['tenkan'] = (df['high'].rolling(window=tenkanLen).max() + df['low'].rolling(window=tenkanLen).min()) / 2
    df['kijun'] = (df['high'].rolling(window=kijunLen).max() + df['low'].rolling(window=kijunLen).min()) / 2
    df['senkouA'] = (df['tenkan'] + df['kijun']) / 2
    df['senkouB'] = (df['high'].rolling(window=senkouBLen).max() + df['low'].rolling(window=senkouBLen).min()) / 2
    
    # 구름대 상하단
    df['cloudTop'] = np.maximum(df['senkouA'].shift(displacement-1), df['senkouB'].shift(displacement-1))
    df['cloudBottom'] = np.minimum(df['senkouA'].shift(displacement-1), df['senkouB'].shift(displacement-1))

    # Whale(세력) 및 거래량
    df['sma224'] = ta.sma(df['close'], length=whaleLen)
    df['vwma224'] = ta.vwma(df['close'], df['volume'], length=whaleLen)
    df['volConfirm'] = df['volume'] > (ta.sma(df['volume'], length=20) * volMult)
    
    # RSI & MFI (Pine Script와 동일하게 Close 기준 MFI 산출)
    df['rsi'] = ta.rsi(df['close'], length=rsiLen)
    raw_money_flow = df['close'].diff() * df['volume']
    positive_flow = raw_money_flow.where(raw_money_flow > 0, 0).rolling(14).sum()
    negative_flow = abs(raw_money_flow.where(raw_money_flow < 0, 0)).rolling(14).sum()
    df['mfi'] = 100 - (100 / (1 + (positive_flow / negative_flow)))
    
    # MACD
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df['macdLine'] = macd['MACD_12_26_9']
    df['signalLine'] = macd['MACDs_12_26_9']
    
    # 볼린저 밴드
    bb = ta.bbands(df['close'], length=bbLen, std=bbMult)
    if bb is not None and not bb.empty:
        df['bbLower'] = bb.iloc[:, 0]
        df['bbMid'] = bb.iloc[:, 1]
        df['bbUpper'] = bb.iloc[:, 2]
    else:
        df['bbLower'] = np.nan
        df['bbMid'] = np.nan
        df['bbUpper'] = np.nan

    # --- [3. SMC 구조 및 상태 계산 (Non-Repainting 로직)] ---
    
    high_pivots = (df['high'].shift(swingLen) == df['high'].rolling(window=swingLen * 2, center=False).max())
    low_pivots = (df['low'].shift(swingLen) == df['low'].rolling(window=swingLen * 2, center=False).min())

    df['swingHighLevel'] = df['high'].shift(swingLen).where(high_pivots).ffill()
    df['swingLowLevel'] = df['low'].shift(swingLen).where(low_pivots).ffill()
    
    df['equilibrium'] = (df['swingHighLevel'] + df['swingLowLevel']) / 2

    # --- [4. 매매 신호 (Signals)] ---
    
    # 1. 역추세 세부 신호 (Divergence & Extreme)
    high_5_prev = df['high'].rolling(5).max().shift(1)
    low_5_prev = df['low'].rolling(5).min().shift(1)
    rsi_5_max_prev = df['rsi'].rolling(5).max().shift(1)
    rsi_5_min_prev = df['rsi'].rolling(5).min().shift(1)

    df['bearishDiv'] = (df['high'] > high_5_prev) & (df['rsi'] < rsi_5_max_prev) & (df['rsi'] > 65)
    df['bullishDiv'] = (df['low'] < low_5_prev) & (df['rsi'] > rsi_5_min_prev) & (df['rsi'] < 35)
    
    df['extremeTop'] = (df['high'] >= df['bbUpper']) & (df['rsi'] > 75) & (df['mfi'] > 80)
    df['extremeBottom'] = (df['low'] <= df['bbLower']) & (df['rsi'] < 25) & (df['mfi'] < 20)

    # 최종 역추세 마커 (TOP: 빨강 / BOTTOM: 초록)
    df['TOP'] = df['bearishDiv'] | df['extremeTop']
    df['BOTTOM'] = df['bullishDiv'] | df['extremeBottom']
    
    # 2. 매크로 트렌드 확인: 종가가 VWMA224 위면 Long 유리, 아래면 Short 유리
    trend_long = df['close'] > df['vwma224']
    trend_short = df['close'] < df['vwma224']

    # 4캔들 연속 VWMA 위/아래에 있었는지 확인 (이격 확인용)
    is_above_confirm = (df['low'] > df['vwma224']).rolling(window=4).min() == 1
    is_below_confirm = (df['high'] < df['vwma224']).rolling(window=4).min() == 1
    
    is_above_confirm = is_above_confirm.fillna(False)
    is_below_confirm = is_below_confirm.fillna(False)
    
    # 3. 하이브리드 전략 세부 진입 규칙 (Rule 1 & Rule 2)
    # 룰 1: 이평선 이격 후 터치 (VWMA 정수리 밟기) + 트렌드 유지
    df['entryVwmaLong'] = is_above_confirm.shift(1) & (df['low'] <= df['vwma224']) & trend_long
    df['entryVwmaShort'] = is_below_confirm.shift(1) & (df['high'] >= df['vwma224']) & trend_short
    
    # 룰 2: SMC 구조적 바닥/천장 진입 (Tolerance 0.2% 적용)
    tolerance = df['close'] * 0.002
    
    # (파란 박스권 진입)
    df['entrySmcLong'] = (
        is_above_confirm.shift(1) & 
        (df['low'] <= (df['swingLowLevel'] + tolerance)) & 
        trend_long
    )
    
    # (빨간 박스권 진입)
    df['entrySmcShort'] = (
        is_below_confirm.shift(1) & 
        (df['high'] >= (df['swingHighLevel'] - tolerance)) & 
        trend_short
    )

    # 최종 조건 결합
    df['longCondition'] = df['entryVwmaLong'] | df['entrySmcLong']
    df['shortCondition'] = df['entryVwmaShort'] | df['entrySmcShort']

    # 최종 매매 신호 (Sig) - 중복 진입 방지 (첫 캔들에서만 발생)
    df['longSig'] = df['longCondition'] & ~df['longCondition'].shift(1, fill_value=False)
    df['shortSig'] = df['shortCondition'] & ~df['shortCondition'].shift(1, fill_value=False)

    return df