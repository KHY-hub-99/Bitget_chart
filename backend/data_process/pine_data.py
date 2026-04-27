import pandas as pd
import pandas_ta as ta
import numpy as np

def apply_master_strategy(df: pd.DataFrame) -> pd.DataFrame:
    """
    OHLCV 데이터프레임을 받아 마스터 전략 지표와 신호를 계산합니다.
    필수 컬럼: 'open', 'high', 'low', 'close', 'volume'
    """
    
    # --- [1. 파라미터 설정] ---
    tenkanLen = 9
    kijunLen = 26
    senkouBLen = 52
    displacement = 26
    rsiLen = 14
    mfiLen = 14
    bbLen = 20
    bbMult = 2.2
    volMult = 1.5
    whaleLen = 224

    # --- [2. 지표 계산] ---
    # 일목균형표
    tenkan = (df['high'].rolling(window=tenkanLen).max() + df['low'].rolling(window=tenkanLen).min()) / 2
    kijun = (df['high'].rolling(window=kijunLen).max() + df['low'].rolling(window=kijunLen).min()) / 2
    senkouA = (tenkan + kijun) / 2
    senkouB = (df['high'].rolling(window=senkouBLen).max() + df['low'].rolling(window=senkouBLen).min()) / 2
    
    # Python에서 선행스팬은 shift를 통해 미래로 밀거나, 현재 캔들 기준으로 과거 값을 참조합니다.
    # Pine Script의 [displacement-1] 참조를 반영하여 과거 값을 가져옵니다.
    df['cloudTop'] = np.maximum(senkouA.shift(displacement-1), senkouB.shift(displacement-1))
    df['cloudBottom'] = np.minimum(senkouA.shift(displacement-1), senkouB.shift(displacement-1))

    # Whale 224 (SMA & VWMA)
    df['sma224'] = ta.sma(df['close'], length=whaleLen)
    # VWMA: (Close * Volume)의 SMA / Volume의 SMA
    df['vwma224'] = ta.vwma(df['close'], df['volume'], length=whaleLen)

    # 기타 보조지표
    macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df['macdLine'] = macd['MACD_12_26_9']
    df['signalLine'] = macd['MACDs_12_26_9']
    
    df['rsi'] = ta.rsi(df['close'], length=rsiLen)
    df['mfi'] = ta.mfi(df['high'], df['low'], df['close'], df['volume'], length=mfiLen)
    
    bb = ta.bbands(df['close'], length=bbLen, std=bbMult)
    df['bbLower'] = bb[f'BBL_{bbLen}_{bbMult}']
    df['bbMid'] = bb[f'BBM_{bbLen}_{bbMult}']
    df['bbUpper'] = bb[f'BBU_{bbLen}_{bbMult}']
    
    vol_sma = ta.sma(df['volume'], length=20)
    df['volConfirm'] = df['volume'] > (vol_sma * volMult)

    # --- [3. 신호 로직] ---
    df['longCondition'] = (
        (df['close'] > df['cloudTop']) & 
        (df['close'].shift(1) <= df['cloudTop'].shift(1)) & # crossover
        (df['macdLine'] > df['signalLine']) & 
        df['volConfirm']
    )
    
    df['shortCondition'] = (
        (df['close'] < df['cloudBottom']) & 
        (df['close'].shift(1) >= df['cloudBottom'].shift(1)) & # crossunder
        (df['macdLine'] < df['signalLine']) & 
        df['volConfirm']
    )

    # 포지션 상태 시뮬레이션 (var bool isLongPos = false)
    # 파이썬에서는 순차적(Iterative)으로 포지션을 추적해야 정확합니다.
    isLongPos = False
    isShortPos = False
    
    longSig_list = []
    shortSig_list = []

    for i in range(len(df)):
        if df['longCondition'].iloc[i]:
            isLongPos = True
            isShortPos = False
        elif df['shortCondition'].iloc[i]:
            isShortPos = True
            isLongPos = False
            
        # 이전 포지션 상태 확인 (and not isLongPos[1])
        # 간략화를 위해 현재 신호 진입점만 True로 마킹
        longSig_list.append(df['longCondition'].iloc[i] and isLongPos)
        shortSig_list.append(df['shortCondition'].iloc[i] and isShortPos)

    df['longSig'] = longSig_list
    df['shortSig'] = shortSig_list

    # --- [4. 시각화 데이터 (역추세 다이아몬드)] ---
    # Rolling highest/lowest
    high_5_prev = df['high'].rolling(5).max().shift(1)
    low_5_prev = df['low'].rolling(5).min().shift(1)
    rsi_5_max_prev = df['rsi'].rolling(5).max().shift(1)
    rsi_5_min_prev = df['rsi'].rolling(5).min().shift(1)

    df['bearishDiv'] = (df['high'] > high_5_prev) & (df['rsi'] < rsi_5_max_prev) & (df['rsi'] > 65)
    df['bullishDiv'] = (df['low'] < low_5_prev) & (df['rsi'] > rsi_5_min_prev) & (df['rsi'] < 35)
    df['extremeTop'] = (df['high'] >= df['bbUpper']) & (df['rsi'] > 75) & (df['mfi'] > 80)
    df['extremeBottom'] = (df['low'] <= df['bbLower']) & (df['rsi'] < 25) & (df['mfi'] < 20)

    # 최종 차트 마커용 (TOP, BOTTOM)
    df['TOP'] = df['bearishDiv'] | df['extremeTop']
    df['BOTTOM'] = df['bullishDiv'] | df['extremeBottom']

    return df