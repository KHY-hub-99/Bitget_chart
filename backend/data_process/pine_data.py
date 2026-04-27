import pandas as pd
import pandas_ta as ta
import numpy as np

# SMC 상태 관리를 위한 클래스 (camelCase 적용)
class Pivot:
    def __init__(self):
        self.currentLevel = np.nan
        self.crossed = False
        self.barTime = None

def apply_master_strategy(df: pd.DataFrame) -> pd.DataFrame:
    """
    OHLCV 데이터프레임을 받아 마스터 전략 및 SMC 지표를 계산합니다.
    필수 컬럼: 'open', 'high', 'low', 'close', 'volume'
    """
    # 데이터 복사 및 초기화
    df = df.copy()
    
    # --- [1. 파라미터 설정] ---
    # 마스터 전략 파라미터
    tenkanLen, kijunLen, senkouBLen = 9, 26, 52
    displacement = 26
    rsiLen, mfiLen = 14, 14
    bbLen, bbMult = 20, 2.2
    volMult, whaleLen = 1.5, 224
    
    # SMC 파라미터 (지식 파일 기준)
    swingLen = 50 
    internalLen = 5

    # --- [2. 벡터 지표 계산 (기존 마스터 전략)] ---
    # 일목균형표
    tenkan = (df['high'].rolling(window=tenkanLen).max() + df['low'].rolling(window=tenkanLen).min()) / 2
    kijun = (df['high'].rolling(window=kijunLen).max() + df['low'].rolling(window=kijunLen).min()) / 2
    df['tenkan'], df['kijun'] = tenkan, kijun
    df['senkouA'] = (tenkan + kijun) / 2
    df['senkouB'] = (df['high'].rolling(window=senkouBLen).max() + df['low'].rolling(window=senkouBLen).min()) / 2
    
    # 구름대 상하단 (displacement 반영)
    df['cloudTop'] = np.maximum(df['senkouA'].shift(displacement-1), df['senkouB'].shift(displacement-1))
    df['cloudBottom'] = np.minimum(df['senkouA'].shift(displacement-1), df['senkouB'].shift(displacement-1))

    # Whale 및 기타 보조지표
    df['sma224'] = ta.sma(df['close'], length=whaleLen)
    df['vwma224'] = ta.vwma(df['close'], df['volume'], length=whaleLen)
    
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df['macdLine'] = macd['MACD_12_26_9']
    df['signalLine'] = macd['MACDs_12_26_9']
    
    df['rsi'] = ta.rsi(df['close'], length=rsiLen)
    df['mfi'] = ta.mfi(df['high'], df['low'], df['close'], df['volume'], length=mfiLen)
    
    bb = ta.bbands(df['close'], length=bbLen, std=bbMult)
    df['bbLower'] = bb[f'BBL_{bbLen}_{bbMult}']
    df['bbMid'] = bb[f'BBM_{bbLen}_{bbMult}']
    df['bbUpper'] = bb[f'BBU_{bbLen}_{bbMult}']
    
    df['volConfirm'] = df['volume'] > (ta.sma(df['volume'], length=20) * volMult)

    # --- [3. 상태 저장형 로직 (SMC 및 시그널)] ---
    # SMC 상태 변수 초기화
    swingHigh, swingLow = Pivot(), Pivot()
    internalHigh, internalLow = Pivot(), Pivot()
    swingTrend, swingLeg = 0, 0 # 1: Bullish, -1: Bearish
    internalTrend, internalLeg = 0, 0
    
    # 결과를 담을 리스트 초기화
    longSig_list, shortSig_list = [], []
    swingBOS_list, swingCHOCH_list = [False] * len(df), [False] * len(df)
    internalBOS_list, internalCHOCH_list = [False] * len(df), [False] * len(df)
    fvgBullish_list, fvgBearish_list = [False] * len(df), [False] * len(df)
    
    isLongPos, isShortPos = False, False

    # SMC 구조 분석 함수 (Closure)
    def check_structure(idx, size, p_high, p_low, p_trend, p_leg, bos_list, choch_list):
        if idx < 2 * size: return p_trend, p_leg

        # leg 판별 (high[size]가 이전/이후 size개 봉 중 최고가인지 확인)
        newLegHigh = df['high'].iloc[idx-size] > df['high'].iloc[idx-size*2 : idx-size].max() and \
                    df['high'].iloc[idx-size] > df['high'].iloc[idx-size+1 : idx+1].max()
        newLegLow = df['low'].iloc[idx-size] < df['low'].iloc[idx-size*2 : idx-size].min() and \
                    df['low'].iloc[idx-size] < df['low'].iloc[idx-size+1 : idx+1].min()

        if newLegHigh:
            if p_leg == 1: # Leg 변경 (Bull -> Bear): 새로운 High 확정
                p_high.currentLevel = df['high'].iloc[idx-size]
                p_high.crossed = False
            p_leg = 0
        elif newLegLow:
            if p_leg == 0: # Leg 변경 (Bear -> Bull): 새로운 Low 확정
                p_low.currentLevel = df['low'].iloc[idx-size]
                p_low.crossed = False
            p_leg = 1

        # BOS / CHoCH 판별
        close_val = df['close'].iloc[idx]
        if close_val > p_high.currentLevel and not p_high.crossed:
            if p_trend == -1: choch_list[idx] = True
            else: bos_list[idx] = True
            p_high.crossed = True
            p_trend = 1
        elif close_val < p_low.currentLevel and not p_low.crossed:
            if p_trend == 1: choch_list[idx] = True
            else: bos_list[idx] = True
            p_low.crossed = True
            p_trend = -1
        
        return p_trend, p_leg

    # 데이터프레임 순회 (Pine Script 방식 시뮬레이션)
    for i in range(len(df)):
        # A. 기본 진입 조건 (Master Strategy)
        longCond = (df['close'].iloc[i] > df['cloudTop'].iloc[i]) and \
                (i > 0 and df['close'].iloc[i-1] <= df['cloudTop'].iloc[i-1]) and \
                (df['macdLine'].iloc[i] > df['signalLine'].iloc[i]) and \
                df['volConfirm'].iloc[i]
        
        shortCond = (df['close'].iloc[i] < df['cloudBottom'].iloc[i]) and \
                    (i > 0 and df['close'].iloc[i-1] >= df['cloudBottom'].iloc[i-1]) and \
                    (df['macdLine'].iloc[i] < df['signalLine'].iloc[i]) and \
                    df['volConfirm'].iloc[i]

        if longCond: isLongPos, isShortPos = True, False
        elif shortCond: isShortPos, isLongPos = True, False
        
        longSig_list.append(longCond and isLongPos)
        shortSig_list.append(shortCond and isShortPos)

        # B. SMC: FVG (Fair Value Gap) 감지
        if i >= 2:
            if df['low'].iloc[i] > df['high'].iloc[i-2]:
                fvgBullish_list[i-1] = True
            elif df['high'].iloc[i] < df['low'].iloc[i-2]:
                fvgBearish_list[i-1] = True

        # C. SMC: 구조 분석 (Swing & Internal)
        swingTrend, swingLeg = check_structure(i, swingLen, swingHigh, swingLow, swingTrend, swingLeg, swingBOS_list, swingCHOCH_list)
        internalTrend, internalLeg = check_structure(i, internalLen, internalHigh, internalLow, internalTrend, internalLeg, internalBOS_list, internalCHOCH_list)

    # 결과 반영
    df['longSig'], df['shortSig'] = longSig_list, shortSig_list
    df['fvgBullish'], df['fvgBearish'] = fvgBullish_list, fvgBearish_list
    df['swingBOS'], df['swingCHOCH'] = swingBOS_list, swingCHOCH_list
    df['internalBOS'], df['internalCHOCH'] = internalBOS_list, internalCHOCH_list

    # --- [4. 역추세 및 최종 마커] ---
    high_5_prev = df['high'].rolling(5).max().shift(1)
    low_5_prev = df['low'].rolling(5).min().shift(1)
    rsi_5_max_prev = df['rsi'].rolling(5).max().shift(1)
    rsi_5_min_prev = df['rsi'].rolling(5).min().shift(1)

    df['bearishDiv'] = (df['high'] > high_5_prev) & (df['rsi'] < rsi_5_max_prev) & (df['rsi'] > 65)
    df['bullishDiv'] = (df['low'] < low_5_prev) & (df['rsi'] > rsi_5_min_prev) & (df['rsi'] < 35)
    df['extremeTop'] = (df['high'] >= df['bbUpper']) & (df['rsi'] > 75) & (df['mfi'] > 80)
    df['extremeBottom'] = (df['low'] <= df['bbLower']) & (df['rsi'] < 25) & (df['mfi'] < 20)

    df['TOP'] = df['bearishDiv'] | df['extremeTop']
    df['BOTTOM'] = df['bullishDiv'] | df['extremeBottom']

    return df