import pandas as pd
import pandas_ta as ta
import numpy as np

# SMC 상태 관리를 위한 클래스
class Pivot:
    def __init__(self):
        self.currentLevel = np.nan
        self.crossed = False

def apply_master_strategy(df: pd.DataFrame) -> pd.DataFrame:
    """
    OHLCV 데이터프레임을 받아 README.md 표준 변수명에 맞춰 전략 지표를 계산합니다.
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
    
    # RSI & MFI
    df['rsi'] = ta.rsi(df['close'], length=rsiLen)
    df['mfi'] = ta.mfi(df['high'], df['low'], df['close'], df['volume'], length=mfiLen)
    
    # MACD
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df['macdLine'] = macd['MACD_12_26_9']
    df['signalLine'] = macd['MACDs_12_26_9']
    
    # 볼린저 밴드
    bb = ta.bbands(df['close'], length=bbLen, std=bbMult)
    if bb is not None and not bb.empty:
        # pandas_ta의 bbands 결과 순서: 0:Lower, 1:Mid, 2:Upper
        df['bbLower'] = bb.iloc[:, 0]
        df['bbMid'] = bb.iloc[:, 1]
        df['bbUpper'] = bb.iloc[:, 2]
    else:
        # 데이터가 부족하여 계산되지 않았을 경우 결측치 처리
        df['bbLower'] = np.nan
        df['bbMid'] = np.nan
        df['bbUpper'] = np.nan
    

    # --- [3. SMC 구조 및 상태 계산 (내부 로직)] ---
    swingHigh, swingLow = Pivot(), Pivot()
    swingHighLevel, swingLowLevel = [np.nan] * len(df), [np.nan] * len(df)
    swingTrend, swingLeg = 0, 0

    def check_structure(idx, size, p_high, p_low, p_trend, p_leg):
        if idx < 2 * size: return p_trend, p_leg
        
        # 피벗 판별
        is_p_high = df['high'].iloc[idx-size] == df['high'].iloc[idx-2*size : idx+1].max()
        is_p_low = df['low'].iloc[idx-size] == df['low'].iloc[idx-2*size : idx+1].min()

        if is_p_high:
            if p_leg == 1:
                p_high.currentLevel = df['high'].iloc[idx-size]
                p_high.crossed = False
            p_leg = 0
        elif is_p_low:
            if p_leg == 0:
                p_low.currentLevel = df['low'].iloc[idx-size]
                p_low.crossed = False
            p_leg = 1

        close_val = df['close'].iloc[idx]
        if not np.isnan(p_high.currentLevel) and close_val > p_high.currentLevel:
            p_high.crossed = True
            p_trend = 1
        elif not np.isnan(p_low.currentLevel) and close_val < p_low.currentLevel:
            p_low.crossed = True
            p_trend = -1
        
        return p_trend, p_leg

    for i in range(len(df)):
        swingTrend, swingLeg = check_structure(i, swingLen, swingHigh, swingLow, swingTrend, swingLeg)
        swingHighLevel[i] = swingHigh.currentLevel
        swingLowLevel[i] = swingLow.currentLevel

    df['swingHighLevel'] = swingHighLevel
    df['swingLowLevel'] = swingLowLevel
    df['equilibrium'] = (df['swingHighLevel'] + df['swingLowLevel']) / 2

    # --- [4. 매매 신호 (Signals)] ---
    
    # 역추세 세부 신호 (Divergence & Extreme)
    high_5_prev = df['high'].rolling(5).max().shift(1)
    low_5_prev = df['low'].rolling(5).min().shift(1)
    rsi_5_max_prev = df['rsi'].rolling(5).max().shift(1)
    rsi_5_min_prev = df['rsi'].rolling(5).min().shift(1)

    df['bearishDiv'] = (df['high'] > high_5_prev) & (df['rsi'] < rsi_5_max_prev) & (df['rsi'] > 65)
    df['bullishDiv'] = (df['low'] < low_5_prev) & (df['rsi'] > rsi_5_min_prev) & (df['rsi'] < 35)
    df['extremeTop'] = (df['high'] >= df['bbUpper']) & (df['rsi'] > 75) & (df['mfi'] > 80)
    df['extremeBottom'] = (df['low'] <= df['bbLower']) & (df['rsi'] < 25) & (df['mfi'] < 20)

    # 최종 역추세 신호 (TOP / BOTTOM)
    df['TOP'] = df['bearishDiv'] | df['extremeTop']
    df['BOTTOM'] = df['bullishDiv'] | df['extremeBottom']
    
    # 매크로 트렌드: 종가가 VWMA224 위면 Long 유리, 아래면 Short 유리
    trend_long = df['close'] > df['vwma224']
    trend_short = df['close'] < df['vwma224']

    # 4캔들 연속 VWMA 위/아래에 있었는지 확인
    is_above_confirm = (df['low'] > df['vwma224']).rolling(window=4).min() == 1
    is_below_confirm = (df['high'] < df['vwma224']).rolling(window=4).min() == 1
    
    is_above_confirm = is_above_confirm.fillna(False)
    is_below_confirm = is_below_confirm.fillna(False)
    
    # 룰 1: 이평선 이격 후 터치 (정수리 밟기) + 꼬리 달고 종가는 트렌드 유지할 때만!
    df['entryVwmaLong'] = is_above_confirm.shift(1) & (df['low'] <= df['vwma224']) & trend_long
    df['entryVwmaShort'] = is_below_confirm.shift(1) & (df['high'] >= df['vwma224']) & trend_short
    
    # 룰 2: SMC 구조적 바닥/천장 진입 + [추세 필터 추가]
    df['entrySmcLong'] = is_above_confirm.shift(1) & (df['low'] <= df['swingLowLevel']) & (df['low'] >= df['swingLowLevel']) & trend_long
    df['entrySmcShort'] = is_below_confirm.shift(1) & (df['high'] >= df['swingHighLevel']) & (df['high'] <= df['swingHighLevel']) & trend_short

    # 최종 조건 결합
    df['longCondition'] = df['entryVwmaLong'] | df['entrySmcLong']
    df['shortCondition'] = df['entryVwmaShort'] | df['entrySmcShort']

    # 최종 매매 신호 (Sig) - 조건 충족 시 첫 캔들에서만 발생
    df['longSig'] = df['longCondition'] & ~df['longCondition'].shift(1, fill_value=False)
    df['shortSig'] = df['shortCondition'] & ~df['shortCondition'].shift(1, fill_value=False)

    return df