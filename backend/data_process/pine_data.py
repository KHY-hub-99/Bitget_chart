import os
import sys
import pandas as pd
import pandas_ta as ta
import numpy as np

def apply_master_strategy(
    df,
    tenkan_len=9, kijun_len=26, senkou_b_len=52, displacement=26,
    rsi_len=14, mfi_len=14, bb_len=20, bb_mult=2.2, vol_mult=1.5
):
    """
    BTC 마스터 최종 통합 전략 (변수명 표준화 적용)
    """
    if df.empty:
        print("[DEBUG] 데이터가 비어 있어 전략을 계산할 수 없습니다.")
        return df
    df = df.copy()

    # === [1. 일목균형표 계산] ===
    tenkan = (df['high'].rolling(tenkan_len).max() + df['low'].rolling(tenkan_len).min()) / 2
    kijun = (df['high'].rolling(kijun_len).max() + df['low'].rolling(kijun_len).min()) / 2
    df['kijun'] = kijun

    senkou_a = (tenkan + kijun) / 2
    senkou_b = (df['high'].rolling(senkou_b_len).max() + df['low'].rolling(senkou_b_len).min()) / 2

    df['senkou_a'] = senkou_a
    df['senkou_b'] = senkou_b

    shift_val = displacement - 1
    senkou_a_calc = senkou_a.shift(shift_val)
    senkou_b_calc = senkou_b.shift(shift_val)

    cloud_top_calc = np.maximum(senkou_a_calc, senkou_b_calc)
    cloud_bottom_calc = np.minimum(senkou_a_calc, senkou_b_calc)

    # === [2. 보조지표 계산] ===
    macd = df.ta.macd(fast=12, slow=26, signal=9)
    df['macd_line'] = macd.iloc[:, 0]
    df['macd_sig'] = macd.iloc[:, 2]

    df['rsi'] = df.ta.rsi(length=rsi_len)
    df['mfi'] = df.ta.mfi(length=mfi_len)

    bb = df.ta.bbands(length=bb_len, std=bb_mult)
    df['bb_lower'] = bb.iloc[:, 0]
    df['bb_middle'] = bb.iloc[:, 1]
    df['bb_upper'] = bb.iloc[:, 2]

    vol_sma = df['volume'].rolling(20).mean()
    vol_confirm = df['volume'] > (vol_sma * vol_mult)

    # === [3. 신호 로직] ===
    high_prev_5_max = df['high'].shift(1).rolling(5).max()
    low_prev_5_min = df['low'].shift(1).rolling(5).min()
    rsi_prev_5_max = df['rsi'].shift(1).rolling(5).max()
    rsi_prev_5_min = df['rsi'].shift(1).rolling(5).min()

    bearish_div = (df['high'] > high_prev_5_max) & (df['rsi'] < rsi_prev_5_max) & (df['rsi'] > 65)
    bullish_div = (df['low'] < low_prev_5_min) & (df['rsi'] > rsi_prev_5_min) & (df['rsi'] < 35)

    # BUG FIX: 중복 조건 제거
    # 기존: (df['mfi'] > 75) & (df['mfi'] > 80) → > 75는 > 80에 포함됨 (dead condition)
    # 기존: (df['mfi'] < 25) & (df['mfi'] < 20) → < 25는 < 20에 포함됨 (dead condition)
    extreme_top = (df['high'] >= df['bb_upper']) & (df['mfi'] > 80)
    extreme_bottom = (df['low'] <= df['bb_lower']) & (df['mfi'] < 20)

    close_cross_cloud_top = (df['close'] > cloud_top_calc) & (df['close'].shift(1) <= cloud_top_calc.shift(1))
    close_cross_cloud_bottom = (df['close'] < cloud_bottom_calc) & (df['close'].shift(1) >= cloud_bottom_calc.shift(1))

    df['master_long'] = close_cross_cloud_top & (df['macd_line'] > df['macd_sig']) & vol_confirm
    df['master_short'] = close_cross_cloud_bottom & (df['macd_line'] < df['macd_sig']) & vol_confirm

    df['top_detected'] = bearish_div | extreme_top
    df['bottom_detected'] = bullish_div | extreme_bottom

    # === [4. 데이터 정제] ===
    indicator_cols = ['kijun', 'senkou_a', 'senkou_b', 'rsi', 'macd_line', 'macd_sig', 'bb_upper', 'bb_middle', 'bb_lower']
    df[indicator_cols] = df[indicator_cols].ffill().bfill()

    for col in ['master_long', 'master_short', 'top_detected', 'bottom_detected']:
        df[col] = df[col].fillna(False).astype(bool)

    return df