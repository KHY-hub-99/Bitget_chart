import sys
import pandas as pd
import pandas_ta as ta
import numpy as np
from pyprojroot import here
# 루트 경로 설정
root = str(here())
sys.path.append(root)
from app.data_process.load_data import CryptoDataFeed

def apply_master_strategy(
    df,
    tenkan_len=9, kijun_len=26, senkou_b_len=52, displacement=26,
    rsi_len=14, mfi_len=14, bb_len=20, bb_mult=2.2, vol_mult=1.5
):
    """
    BTC 마스터 최종 통합 전략
    지표 계산 및 매매 신호 생성 로직
    """
    df = df.copy()

    # === [1. 일목균형표 계산] ===
    # 전환선 및 기준선
    tenkan = (df['high'].rolling(tenkan_len).max() + df['low'].rolling(tenkan_len).min()) / 2
    kijun = (df['high'].rolling(kijun_len).max() + df['low'].rolling(kijun_len).min()) / 2
    df['kijun'] = kijun # 프론트엔드 시각화용

    # 선행스팬 A/B 계산
    senkou_a = (tenkan + kijun) / 2
    senkou_b = (df['high'].rolling(senkou_b_len).max() + df['low'].rolling(senkou_b_len).min()) / 2

    # 선행스팬을 displacement 만큼 미래로 보낸 것을 현재 시점과 비교하기 위해 시프트
    # (TradingView의 offset 기능 구현)
    shift_val = displacement - 1
    df['senkou_a'] = senkou_a.shift(shift_val)
    df['senkou_b'] = senkou_b.shift(shift_val)

    # 구름대 상단/하단 결정
    cloud_top = np.maximum(df['senkou_a'], df['senkou_b'])
    cloud_bottom = np.minimum(df['senkou_a'], df['senkou_b'])

    # === [2. 보조지표 계산] ===
    # MACD (안정적인 iloc 선택 방식)
    macd = df.ta.macd(fast=12, slow=26, signal=9)
    df['MACD_line'] = macd.iloc[:, 0]   # MACD Line
    df['MACD_signal'] = macd.iloc[:, 2] # Signal Line

    # RSI 및 MFI
    df['RSI_14'] = df.ta.rsi(length=rsi_len)
    df['MFI_14'] = df.ta.mfi(length=mfi_len)
    
    # 볼린저 밴드
    bb = df.ta.bbands(length=bb_len, std=bb_mult)
    df['BB_upper'] = bb.iloc[:, 2] # BBU
    df['BB_lower'] = bb.iloc[:, 0] # BBL
    df['BB_middle'] = bb.iloc[:, 1] # BBM

    # 거래량 가중치 확인
    vol_sma = df['volume'].rolling(20).mean()
    vol_confirm = df['volume'] > (vol_sma * vol_mult)

    # === [3. 신호 로직] ===
    # A. 역추세: 고점/저점 정밀 타격 (Divergence + Extreme)
    high_prev_5_max = df['high'].shift(1).rolling(5).max()
    low_prev_5_min = df['low'].shift(1).rolling(5).min()
    rsi_prev_5_max = df['RSI_14'].shift(1).rolling(5).max()
    rsi_prev_5_min = df['RSI_14'].shift(1).rolling(5).min()

    # 하락 다이버전스 & 상승 다이버전스
    bearish_div = (df['high'] > high_prev_5_max) & (df['RSI_14'] < rsi_prev_5_max) & (df['RSI_14'] > 65)
    bullish_div = (df['low'] < low_prev_5_min) & (df['RSI_14'] > rsi_prev_5_min) & (df['RSI_14'] < 35)

    # 극한 도달 (볼린저 상단 돌파 + 과매수/도)
    extreme_top = (df['high'] >= df['BB_upper']) & (df['RSI_14'] > 75) & (df['MFI_14'] > 80)
    extreme_bottom = (df['low'] <= df['BB_lower']) & (df['RSI_14'] < 25) & (df['MFI_14'] < 20)

    # B. 추세: MASTER 신호 (구름대 돌파 + MACD 정배열 + 거래량)
    close_cross_cloud_top = (df['close'] > cloud_top) & (df['close'].shift(1) <= cloud_top.shift(1))
    close_cross_cloud_bottom = (df['close'] < cloud_bottom) & (df['close'].shift(1) >= cloud_bottom.shift(1))

    df['MASTER_LONG'] = close_cross_cloud_top & (df['MACD_line'] > df['MACD_signal']) & vol_confirm
    df['MASTER_SHORT'] = close_cross_cloud_bottom & (df['MACD_line'] < df['MACD_signal']) & vol_confirm
    
    df['TOP_DETECTED'] = bearish_div | extreme_top 
    df['BOTTOM_DETECTED'] = bullish_div | extreme_bottom 
    
    # === [4. 데이터 정제] ===
    # 프론트엔드(JS)에서 지표 선이 끊기지 않도록 NaN을 이전 값으로 채우거나 0으로 처리
    indicator_cols = ['kijun', 'senkou_a', 'senkou_b', 'RSI_14', 'MFI_14', 'BB_upper', 'BB_lower', 'BB_middle']
    df[indicator_cols] = df[indicator_cols].ffill() 

    # 신호 컬럼은 확실하게 Boolean으로 변환
    for col in ['MASTER_LONG', 'MASTER_SHORT', 'TOP_DETECTED', 'BOTTOM_DETECTED']:
        df[col] = df[col].fillna(False).astype(bool)

    return df

if __name__ == "__main__":
    # 데이터 로드 (UTC 기준)
    feed = CryptoDataFeed(method="swap", symbol="BTC/USDT:USDT", timeframe="1d")
    feed.initialize_data(days=90)
    
    # 전략 실행
    result_df = apply_master_strategy(feed.df)
    
    print(f"전략 연산 완료: {len(result_df)}개 행")
    print(result_df[['kijun', 'MASTER_LONG', 'TOP_DETECTED']].tail())