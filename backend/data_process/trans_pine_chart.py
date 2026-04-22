import sys
import pandas as pd
import pandas_ta as ta
import numpy as np
from pyprojroot import here
root = str(here())
sys.path.append(root)
from backend.data_process.data_load import CryptoDataFeed

def apply_master_strategy(
    df,
    tenkan_len=9, kijun_len=26, senkou_b_len=52, displacement=26,
    rsi_len=14, mfi_len=14, bb_len=20, bb_mult=2.2, vol_mult=1.5
):
    df = df.copy()

    # === [2. 지표 계산] ===
    # 일목균형표 (Ichimoku Cloud)
    tenkan = (df['high'].rolling(tenkan_len).max() + df['low'].rolling(tenkan_len).min()) / 2
    kijun = (df['high'].rolling(kijun_len).max() + df['low'].rolling(kijun_len).min()) / 2

    # 시각화 모듈에서 'kijun'을 찾으므로 저장해줍니다.
    df['kijun'] = kijun

    senkou_a = (tenkan + kijun) / 2
    senkou_b = (df['high'].rolling(senkou_b_len).max() + df['low'].rolling(senkou_b_len).min()) / 2

    # 선행스팬을 현재 시점으로 시프트 (과거에 계산된 구름을 현재 가격과 비교하기 위함)
    shift_val = displacement - 1
    df['senkou_a'] = senkou_a.shift(shift_val)
    df['senkou_b'] = senkou_b.shift(shift_val)

    cloud_top = np.maximum(df['senkou_a'], df['senkou_b'])
    cloud_bottom = np.minimum(df['senkou_a'], df['senkou_b'])

    # MACD 계산 및 안정적인 컬럼 선택
    macd = df.ta.macd(fast=12, slow=26, signal=9)
    macd_line = macd.iloc[:, 0]   # 첫 번째 컬럼이 보통 MACD 라인
    signal_line = macd.iloc[:, 2] # 세 번째 컬럼이 보통 Signal 라인
    
    df['MACD_line'] = macd_line
    df['MACD_signal'] = signal_line

    # RSI, MFI, 볼린저 밴드
    df['RSI_14'] = df.ta.rsi(length=rsi_len)
    df['MFI_14'] = df.ta.mfi(length=mfi_len)
    
    bb = df.ta.bbands(length=bb_len, std=bb_mult)
    df['BB_upper'] = bb.iloc[:, 2] # 보통 BBU
    df['BB_lower'] = bb.iloc[:, 0] # 보통 BBL
    df['BB_middle'] = bb.iloc[:, 1] # 보통 BBM

    # 거래량 확인
    vol_sma = df['volume'].rolling(20).mean()
    vol_confirm = df['volume'] > (vol_sma * vol_mult)

    # === [3. 신호 로직] ===
    # A. 고점/저점 정밀 타격 (Divergence + Extreme)
    high_prev_5_max = df['high'].shift(1).rolling(5).max()
    low_prev_5_min = df['low'].shift(1).rolling(5).min()
    rsi_prev_5_max = df['RSI_14'].shift(1).rolling(5).max()
    rsi_prev_5_min = df['RSI_14'].shift(1).rolling(5).min()

    bearish_div = (df['high'] > high_prev_5_max) & (df['RSI_14'] < rsi_prev_5_max) & (df['RSI_14'] > 65)
    bullish_div = (df['low'] < low_prev_5_min) & (df['RSI_14'] > rsi_prev_5_min) & (df['RSI_14'] < 35)

    extreme_top = (df['high'] >= df['BB_upper']) & (df['RSI_14'] > 75) & (df['MFI_14'] > 80)
    extreme_bottom = (df['low'] <= df['BB_lower']) & (df['RSI_14'] < 25) & (df['MFI_14'] < 20)

    # B. 추세 진입 (MASTER 신호)
    # 구름대 돌파 판별
    close_cross_cloud_top = (df['close'] > cloud_top) & (df['close'].shift(1) <= cloud_top.shift(1))
    close_cross_cloud_bottom = (df['close'] < cloud_bottom) & (df['close'].shift(1) >= cloud_bottom.shift(1))

    # 최종 신호 조합
    df['MASTER_LONG'] = close_cross_cloud_top & (df['MACD_line'] > df['MACD_signal']) & vol_confirm
    df['MASTER_SHORT'] = close_cross_cloud_bottom & (df['MACD_line'] < df['MACD_signal']) & vol_confirm
    
    df['TOP_DETECTED'] = bearish_div | extreme_top 
    df['BOTTOM_DETECTED'] = bullish_div | extreme_bottom 
    
    # 신호 컬럼 결측치 및 타입 정리
    for col in ['MASTER_LONG', 'MASTER_SHORT', 'TOP_DETECTED', 'BOTTOM_DETECTED']:
        df[col] = df[col].fillna(False).astype(bool)

    return df

# 단독 파일 테스트
if __name__ == "__main__":
    feed = CryptoDataFeed(method="swap", symbol="BTC/USDT:USDT", timeframe="1d")
    feed.initialize_data(days=90)
    raw_df = feed.df

    print(raw_df.head())
    print("=" * 60)

    result_df = apply_master_strategy(feed.df)

    print(result_df.head())