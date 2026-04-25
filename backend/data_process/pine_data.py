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
    df = df.copy()

    # === [1. 일목균형표 계산] ===
    tenkan = (df['high'].rolling(tenkan_len).max() + df['low'].rolling(tenkan_len).min()) / 2
    kijun = (df['high'].rolling(kijun_len).max() + df['low'].rolling(kijun_len).min()) / 2
    df['kijun'] = kijun

    # 선행스팬 A/B 계산
    senkou_a = (tenkan + kijun) / 2
    senkou_b = (df['high'].rolling(senkou_b_len).max() + df['low'].rolling(senkou_b_len).min()) / 2

    # 프론트엔드 시각화용 데이터
    df['senkou_a'] = senkou_a
    df['senkou_b'] = senkou_b

    # 매매 신호 연산용 데이터 (현재 캔들과 비교하기 위해 당겨옴)
    shift_val = displacement - 1
    senkou_a_calc = senkou_a.shift(shift_val)
    senkou_b_calc = senkou_b.shift(shift_val)
    
    cloud_top_calc = np.maximum(senkou_a_calc, senkou_b_calc)
    cloud_bottom_calc = np.minimum(senkou_a_calc, senkou_b_calc)

    # === [2. 보조지표 계산] ===
    # 🎯 MACD: macd_line, macd_sig 로 완벽 통일
    macd = df.ta.macd(fast=12, slow=26, signal=9)
    df['macd_line'] = macd.iloc[:, 0]  # MACD_12_26_9
    df['macd_sig'] = macd.iloc[:, 2]   # MACDs_12_26_9

    # 🎯 RSI 및 MFI: 숫자를 빼고 직관적인 이름으로 통일
    df['rsi'] = df.ta.rsi(length=rsi_len)
    df['mfi'] = df.ta.mfi(length=mfi_len)
    
    # 🎯 볼린저 밴드 통일
    bb = df.ta.bbands(length=bb_len, std=bb_mult)
    df['bb_lower'] = bb.iloc[:, 0]  # BBL
    df['bb_middle'] = bb.iloc[:, 1] # BBM
    df['bb_upper'] = bb.iloc[:, 2]  # BBU

    # 거래량 가중치 확인
    vol_sma = df['volume'].rolling(20).mean()
    vol_confirm = df['volume'] > (vol_sma * vol_mult)

    # === [3. 신호 로직] ===
    # A. 역추세: 고점/저점 정밀 타격
    high_prev_5_max = df['high'].shift(1).rolling(5).max()
    low_prev_5_min = df['low'].shift(1).rolling(5).min()
    rsi_prev_5_max = df['rsi'].shift(1).rolling(5).max()
    rsi_prev_5_min = df['rsi'].shift(1).rolling(5).min()

    bearish_div = (df['high'] > high_prev_5_max) & (df['rsi'] < rsi_prev_5_max) & (df['rsi'] > 65)
    bullish_div = (df['low'] < low_prev_5_min) & (df['rsi'] > rsi_prev_5_min) & (df['rsi'] < 35)

    extreme_top = (df['high'] >= df['bb_upper']) & (df['mfi'] > 75) & (df['mfi'] > 80)
    extreme_bottom = (df['low'] <= df['bb_lower']) & (df['mfi'] < 25) & (df['mfi'] < 20)

    close_cross_cloud_top = (df['close'] > cloud_top_calc) & (df['close'].shift(1) <= cloud_top_calc.shift(1))
    close_cross_cloud_bottom = (df['close'] < cloud_bottom_calc) & (df['close'].shift(1) >= cloud_bottom_calc.shift(1))

    # 🎯 매매 신호
    df['master_long'] = close_cross_cloud_top & (df['macd_line'] > df['macd_sig']) & vol_confirm
    df['master_short'] = close_cross_cloud_bottom & (df['macd_line'] < df['macd_sig']) & vol_confirm
    
    df['top_detected'] = bearish_div | extreme_top 
    df['bottom_detected'] = bullish_div | extreme_bottom
    
    # === [4. 데이터 정제] ===
    # 🎯 NaN을 채울 컬럼들을 DB 스키마와 완벽히 맞춤
    indicator_cols = ['kijun', 'senkou_a', 'senkou_b', 'rsi', 'macd_line', 'macd_sig', 'bb_upper', 'bb_middle', 'bb_lower']
    
    df[indicator_cols] = df[indicator_cols].ffill().bfill() 

    for col in ['master_long', 'master_short', 'top_detected', 'bottom_detected']:
        df[col] = df[col].fillna(False).astype(bool)

    # print(f"DEBUG: 계산된 컬럼들 -> {df.columns.tolist()}") # 어떤 이름으로 계산되었는지 확인
    return df