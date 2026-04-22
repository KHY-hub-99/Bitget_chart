import pandas as pd
import pandas_ta as ta
import numpy as np

def apply_master_strategy(
    df,
    # === [1. 파라미터 설정] ===
    # 일목균형표
    tenkan_len=9,       # 전환선
    kijun_len=26,       # 기준선
    senkou_b_len=52,    # 선행스팬B
    displacement=26,    # 이동 (차트 시각화할 때 매우 중요함)
    
    # 보조지표
    rsi_len=14,         # RSI 기간
    mfi_len=14,         # MFI 기간
    bb_len=20,          # 볼린저밴드 기간
    bb_mult=2.2,        # 볼린저밴드 승수 (표준편차)
    vol_mult=1.5        # 거래량 가중치
):
    """
    BTC 마스터 최종 통합전략 (Diamond Ver.)
    차트 시각화 및 백테스트를 위한 상태 최적화 함수
    """
    df = df.copy()

    # === [2. 지표 계산] ===
    # 일목균형표 (Ichimoku Cloud)
    tenkan = (df['high'].rolling(tenkan_len).max() + df['low'].rolling(tenkan_len).min()) / 2
    kijun = (df['high'].rolling(kijun_len).max() + df['low'].rolling(kijun_len).min()) / 2

    senkou_a = (tenkan + kijun) / 2
    senkou_b = (df['high'].rolling(senkou_b_len).max() + df['low'].rolling(senkou_b_len).min()) / 2

    # 선행스팬을 차트에 그리고 전략에 사용하기 위해 displacement 처리 (과거 데이터를 현재로 당겨옴)
    shift_val = displacement - 1

    df['senkou_a'] = senkou_a.shift(shift_val)
    df['senkou_b'] = senkou_b.shift(shift_val)

    # numpy(np)를 사용하여 구름대 상단과 하단을 직관적으로 계산
    cloud_top = np.maximum(df['senkou_a'], df['senkou_b'])
    cloud_bottom = np.minimum(df['senkou_a'], df['senkou_b'])

    # 보조지표 계산 (MACD, RSI, MFI, 볼린저 밴드)
    # MACD 계산 (고정값 12, 26, 9 사용)
    # pandas-ta의 macd는 여러 컬럼(MACD선, 시그널선, 히스토그램)을 가진 DataFrame을 반환합니다.
    macd = df.ta.macd(fast=12, slow=26, signal=9)
    macd_line = macd['MACD_12_26_9']     # MACD 라인
    signal_line = macd['MACDs_12_26_9']  # Signal 라인

    # RSI와 MFI 계산 (파라미터 변수 활용)
    rsi = df.ta.rsi(length=rsi_len)
    mfi = df.ta.mfi(length=mfi_len)

    # 볼린저 밴드 계산 (에러 방어 로직 적용!)
    bb = df.ta.bbands(length=bb_len, std=bb_mult)

    # 라이브러리 버전에 상관없이 상단/하단 밴드를 정확히 잡아냅니다.
    bbu_col = [col for col in bb.columns if col.startswith('BBU')][0]
    bbl_col = [col for col in bb.columns if col.startswith('BBL')][0]

    bb_upper = bb[bbu_col]
    bb_lower = bb[bbl_col]

    # 2-3. 거래량 확인 (Volume Confirmation)
    # 파인 스크립트의 ta.sma(volume, 20)은 파이썬의 rolling(20).mean()으로 직관적 번역이 가능합니다.
    vol_sma = df['volume'].rolling(20).mean()
    vol_confirm = df['volume'] > (vol_sma * vol_mult)

    # === [3. 신호 로직] ===

    # A. 고점/저점 정밀 타격 (다이버전스 + 극한 과매수/도)
    
    # 1. 다이버전스를 구하기 위한 과거 5봉 데이터 전처리
    # Pine Script의 ta.highest(high, 5)[1] -> "어제(shift(1)) 기준 과거 5일치(rolling(5))의 최댓값(max)"
    high_prev_5_max = df['high'].shift(1).rolling(5).max()
    low_prev_5_min = df['low'].shift(1).rolling(5).min()

    rsi_prev_5_max = rsi.shift(1).rolling(5).max()
    rsi_prev_5_min = rsi.shift(1).rolling(5).min()

    # 2. 다이버전스 판별
    # 파이썬 pandas에서는 여러 조건을 묶을 때 'and' 대신 '&' 기호를 사용하고, 각 조건을 괄호()로 묶어야 합니다.
    bearish_div = (df['high'] > high_prev_5_max) & (rsi < rsi_prev_5_max) & (rsi > 65)
    bullish_div = (df['low'] < low_prev_5_min) & (rsi > rsi_prev_5_min) & (rsi < 35)

    # 3. 극한 타점 판별 (볼린저 밴드 이탈 + RSI/MFI 동시 조건 만족)
    extreme_top = (df['high'] >= bb_upper) & (rsi > 75) & (mfi > 80)
    extreme_bottom = (df['low'] <= bb_lower) & (rsi < 25) & (mfi < 20)

    # B. 추세 진입 (MASTER 신호)
    
    # 1. 크로스오버/크로스언더 논리적 구현
    # 상향 돌파 (Crossover): 오늘 종가는 구름대 상단보다 크고(&), 어제 종가는 어제 구름대 상단보다 작거나 같다.
    close_cross_cloud_top = (df['close'] > cloud_top) & (df['close'].shift(1) <= cloud_top.shift(1))

    # 하향 이탈 (Crossunder): 오늘 종가는 구름대 하단보다 작고(&), 어제 종가는 어제 구름대 하단보다 크거나 같다.
    close_cross_cloud_bottom = (df['close'] < cloud_bottom) & (df['close'].shift(1) >= cloud_bottom.shift(1))

    # 2. 최종 MASTER 신호 조합 (돌파 + MACD 방향 + 거래량 조건 동시 만족)
    long_sig = close_cross_cloud_top & (macd_line > signal_line) & vol_confirm
    short_sig = close_cross_cloud_bottom & (macd_line < signal_line) & vol_confirm

    df['TOP_DETECTED'] = bearish_div | extreme_top       # 빨간 다이아몬드 (고점 징후)
    df['BOTTOM_DETECTED'] = bullish_div | extreme_bottom # 초록 다이아몬드 (저점 징후)
    df['MASTER_LONG'] = long_sig                         # 초록색 위 화살표 (강력 매수)
    df['MASTER_SHORT'] = short_sig                       # 빨간색 아래 화살표 (강력 매도)

    df.fillna(False, inplace=True)
    
    signal_columns = ['TOP_DETECTED', 'BOTTOM_DETECTED', 'MASTER_LONG', 'MASTER_SHORT']
    df[signal_columns] = df[signal_columns].fillna(False)
    df.fillna(0, inplace=True)

    return df