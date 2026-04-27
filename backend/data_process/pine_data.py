import pandas as pd
import pandas_ta as ta
import numpy as np

def apply_master_strategy(
    df,
    tenkan_len=9, kijun_len=26, senkou_b_len=52, displacement=26,
    rsi_len=14, mfi_len=14, bb_len=20, bb_mult=2.2, vol_mult=1.5,
    whale_len=224, swing_len=50, fvg_threshold=0.0
):
    if df.empty: return df
    df = df.copy()

    # [1] 지표 계산 (일목, Whale, MACD, RSI, BB)
    df['tenkan'] = (df['high'].rolling(tenkan_len).max() + df['low'].rolling(tenkan_len).min()) / 2
    df['kijun'] = (df['high'].rolling(kijun_len).max() + df['low'].rolling(kijun_len).min()) / 2
    df['senkou_a'] = ((df['tenkan'] + df['kijun']) / 2).shift(displacement - 1)
    df['senkou_b'] = ((df['high'].rolling(senkou_b_len).max() + df['low'].rolling(senkou_b_len).min()) / 2).shift(displacement - 1)
    
    df['cloud_top'] = np.maximum(df['senkou_a'], df['senkou_b']) 
    df['cloud_bottom'] = np.minimum(df['senkou_a'], df['senkou_b'])

    df['sma_224'] = ta.sma(df['close'], length=whale_len)
    df['vwma_224'] = ta.vwma(df['close'], df['volume'], length=whale_len)

    macd = df.ta.macd(fast=12, slow=26, signal=9)
    df['macd_line'], df['macd_sig'] = macd.iloc[:, 0], macd.iloc[:, 2]

    df['rsi'] = df.ta.rsi(length=rsi_len)
    df['mfi'] = df.ta.mfi(length=mfi_len)

    bb = df.ta.bbands(length=bb_len, std=bb_mult)
    df['bb_lower'], df['bb_middle'], df['bb_upper'] = bb.iloc[:, 0], bb.iloc[:, 1], bb.iloc[:, 2]
    df['vol_confirm'] = df['volume'] > (df['volume'].rolling(20).mean() * vol_mult)

    # [2] SMC (FVG & Swing)
    df['fvg_bullish'] = (df['low'] > df['high'].shift(2)) & (df['close'].shift(1) > df['high'].shift(2))
    df['fvg_bearish'] = (df['high'] < df['low'].shift(2)) & (df['close'].shift(1) < df['low'].shift(2))
    df['swing_high'] = df['high'] == df['high'].rolling(window=swing_len*2+1, center=True).max()
    df['swing_low'] = df['low'] == df['low'].rolling(window=swing_len*2+1, center=True).min()

    # [3] 신호 로직 (중복 방지 State 반영)
    long_cond = (df['close'] > df['cloud_top']) & (df['macd_line'] > df['macd_sig']) & df['vol_confirm']
    short_cond = (df['close'] < df['cloud_bottom']) & (df['macd_line'] < df['macd_sig']) & df['vol_confirm']

    df['pos_state'] = np.nan
    df.loc[long_cond, 'pos_state'] = 1
    df.loc[short_cond, 'pos_state'] = -1
    df['pos_state'] = df['pos_state'].ffill().fillna(0)
    
    df['is_long_pos'] = df['pos_state'] == 1
    df['is_short_pos'] = df['pos_state'] == -1

    df['long_sig'] = long_cond & (df['is_long_pos'] & ~df['is_long_pos'].shift(1).fillna(False))
    df['short_sig'] = short_cond & (df['is_short_pos'] & ~df['is_short_pos'].shift(1).fillna(False))

    # 역추세 다이아몬드
    df['bearish_div'] = (df['high'] > df['high'].shift(1).rolling(5).max()) & (df['rsi'] < df['rsi'].shift(1).rolling(5).max()) & (df['rsi'] > 65)
    df['bullish_div'] = (df['low'] < df['low'].shift(1).rolling(5).min()) & (df['rsi'] > df['rsi'].shift(1).rolling(5).min()) & (df['rsi'] < 35)
    df['extreme_top'] = (df['high'] >= df['bb_upper']) & (df['rsi'] > 75) & (df['mfi'] > 80)
    df['extreme_bottom'] = (df['low'] <= df['bb_lower']) & (df['rsi'] < 25) & (df['mfi'] < 20)

    df['top'] = df['bearish_div'] | df['extreme_top']
    df['bottom'] = df['bullish_div'] | df['extreme_bottom']

    # [4] 데이터 정제 및 리턴
    indicator_cols = ['tenkan', 'kijun', 'senkou_a', 'senkou_b', 'cloud_top', 'cloud_bottom', 'sma_224', 'vwma_224', 'rsi', 'mfi', 'macd_line', 'macd_sig', 'bb_upper', 'bb_middle', 'bb_lower']
    df[indicator_cols] = df[indicator_cols].ffill().bfill()
    
    bool_cols = ['vol_confirm', 'fvg_bullish', 'fvg_bearish', 'swing_high', 'swing_low', 'is_long_pos', 'is_short_pos', 'long_sig', 'short_sig', 'bearish_div', 'bullish_div', 'extreme_top', 'extreme_bottom', 'top', 'bottom']
    for col in bool_cols: df[col] = df[col].fillna(False).astype(bool)

    return df.drop(columns=['pos_state'])