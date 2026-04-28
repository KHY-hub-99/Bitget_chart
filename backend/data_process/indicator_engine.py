import pandas as pd
import numpy as np

class MasterIndicatorEngine:
    def __init__(self):
        # [1. 파라미터 설정] Standard CamelCase 준수
        self.p = {
            "tenkanLen": 9, "kijunLen": 26, "senkouBLen": 52, "displacement": 26,
            "rsiLen": 14, "mfiLen": 14, "bbLen": 20, "bbMult": 2.2,
            "volMult": 1.5, "whaleLen": 224, "swingLen": 50
        }

    def _rma(self, series: pd.Series, length: int):
        """Pine Script의 ta.rma (Smoothed Moving Average) 구현"""
        alpha = 1 / length
        return series.ewm(alpha=alpha, min_periods=length, adjust=False).mean()

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        # --- [2. 보조지표 (Indicators)] ---
        
        # 일목균형표
        df['tenkan'] = (df['high'].rolling(self.p['tenkanLen']).max() + df['low'].rolling(self.p['tenkanLen']).min()) / 2
        df['kijun'] = (df['high'].rolling(self.p['kijunLen']).max() + df['low'].rolling(self.p['kijunLen']).min()) / 2
        df['senkouA'] = (df['tenkan'] + df['kijun']) / 2
        df['senkouB'] = (df['high'].rolling(self.p['senkouBLen']).max() + df['low'].rolling(self.p['senkouBLen']).min()) / 2
        
        shift_val = self.p['displacement'] - 1
        df['cloudTop'] = np.maximum(df['senkouA'].shift(shift_val), df['senkouB'].shift(shift_val))
        df['cloudBottom'] = np.minimum(df['senkouA'].shift(shift_val), df['senkouB'].shift(shift_val))

        # Whale 224 & 볼륨
        df['sma224'] = df['close'].rolling(self.p['whaleLen']).mean()
        df['vwma224'] = (df['close'] * df['volume']).rolling(self.p['whaleLen']).sum() / df['volume'].rolling(self.p['whaleLen']).sum()
        df['volConfirm'] = df['volume'] > (df['volume'].rolling(20).mean() * self.p['volMult'])

        # 기술적 지표 (RSI, MFI, MACD, BB)
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        df['rsi'] = 100 - (100 / (1 + self._rma(gain, self.p['rsiLen']) / self._rma(loss, self.p['rsiLen'])))

        raw_mf = df['close'].diff() * df['volume']
        pos_mf = raw_mf.where(raw_mf > 0, 0.0).rolling(self.p['mfiLen']).sum()
        neg_mf = abs(raw_mf.where(raw_mf < 0, 0.0)).rolling(self.p['mfiLen']).sum()
        df['mfi'] = 100 - (100 / (1 + (pos_mf / neg_mf)))

        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macdLine'] = ema12 - ema26
        df['signalLine'] = df['macdLine'].ewm(span=9, adjust=False).mean()

        df['bbMid'] = df['close'].rolling(self.p['bbLen']).mean()
        std_dev = df['close'].rolling(self.p['bbLen']).std(ddof=0)
        df['bbUpper'] = df['bbMid'] + (std_dev * self.p['bbMult'])
        df['bbLower'] = df['bbMid'] - (std_dev * self.p['bbMult'])

        # --- [3. SMC 구조 및 가격 레벨 (LuxAlgo 1:1 완벽 직역본)] ---
        s_len = self.p['swingLen']

        high_past = df['high'].shift(s_len)
        low_past = df['low'].shift(s_len)
        
        hi_recent = df['high'].rolling(window=s_len).max()
        lo_recent = df['low'].rolling(window=s_len).min()
        
        new_leg_high = high_past > hi_recent
        new_leg_low = low_past < lo_recent
        
        leg = pd.Series(np.nan, index=df.index)
        leg.loc[new_leg_low] = 1   # BULLISH_LEG
        leg.loc[new_leg_high] = 0  # BEARISH_LEG
        leg = leg.ffill().fillna(0)
        
        leg_change = leg.diff()
        
        df['swingHighLevel'] = np.where(leg_change == -1, high_past, np.nan)
        df['swingLowLevel'] = np.where(leg_change == 1, low_past, np.nan)
        
        df['swingHighLevel'] = df['swingHighLevel'].ffill()
        df['swingLowLevel'] = df['swingLowLevel'].ffill()
        df['equilibrium'] = (df['swingHighLevel'] + df['swingLowLevel']) / 2

        # --- [추가됨] 3-1. Trailing Extremes (추적 스윙 및 Strong/Weak 판별) ---
        # A. 시장 추세(Trend) 판별 (1: 상승장, -1: 하락장)
        df['trend'] = np.nan
        df.loc[df['close'] > df['swingHighLevel'], 'trend'] = 1
        df.loc[df['close'] < df['swingLowLevel'], 'trend'] = -1
        df['trend'] = df['trend'].ffill().fillna(1) 

        # B. Trailing Extremes (추적 고점/저점) 누적 계산
        block_high = (leg_change == -1).cumsum()
        block_low = (leg_change == 1).cumsum()

        df['trailingTop'] = df.groupby(block_high)['high'].cummax()
        df['trailingBottom'] = df.groupby(block_low)['low'].cummin()

        # C. Strong / Weak 라벨링
        df['topType'] = np.where(df['trend'] == -1, 'Strong High', 'Weak High')
        df['bottomType'] = np.where(df['trend'] == 1, 'Strong Low', 'Weak Low')

        # --- [4. 역추세 세부 신호 및 마커 (TOP/BOTTOM)] ---
        h5_prev = df['high'].shift(1).rolling(5).max()
        l5_prev = df['low'].shift(1).rolling(5).min()
        r5_max_prev = df['rsi'].shift(1).rolling(5).max()
        r5_min_prev = df['rsi'].shift(1).rolling(5).min()

        df['bearishDiv'] = (df['high'] > h5_prev) & (df['rsi'] < r5_max_prev) & (df['rsi'] > 65)
        df['bullishDiv'] = (df['low'] < l5_prev) & (df['rsi'] > r5_min_prev) & (df['rsi'] < 35)
        
        df['extremeTop'] = (df['high'] >= df['bbUpper']) & (df['rsi'] > 75) & (df['mfi'] > 80)
        df['extremeBottom'] = (df['low'] <= df['bbLower']) & (df['rsi'] < 25) & (df['mfi'] < 20)

        df['TOP'] = df['bearishDiv'] | df['extremeTop']
        df['BOTTOM'] = df['bullishDiv'] | df['extremeBottom']

        # --- [5. 하이브리드 전략 진입 규칙 (Rule 1 & Rule 2)] ---
        trend_long = df['close'] > df['vwma224']
        trend_short = df['close'] < df['vwma224']

        is_above_confirm = (df['low'] > df['vwma224']).rolling(window=4).min() == 1
        is_below_confirm = (df['high'] < df['vwma224']).rolling(window=4).min() == 1
        is_above_confirm = is_above_confirm.fillna(False)
        is_below_confirm = is_below_confirm.fillna(False)
        
        df['entryVwmaLong'] = is_above_confirm.shift(1) & (df['low'] <= df['vwma224']) & trend_long
        df['entryVwmaShort'] = is_below_confirm.shift(1) & (df['high'] >= df['vwma224']) & trend_short
        
        df['entrySmaLong'] = is_above_confirm.shift(1) & (df['low'] <= df['sma224']) & trend_long
        df['entrySmaShort'] = is_below_confirm.shift(1) & (df['high'] >= df['sma224']) & trend_short
        
        tolerance = df['close'] * 0.002
        df['entrySmcLong'] = is_above_confirm.shift(1) & (df['low'] <= (df['swingLowLevel'] + tolerance)) & trend_long
        df['entrySmcShort'] = is_below_confirm.shift(1) & (df['high'] >= (df['swingHighLevel'] - tolerance)) & trend_short

        df['longCondition'] = df['entryVwmaLong'] | df['entrySmaLong'] | df['entrySmcLong']
        df['shortCondition'] = df['entryVwmaShort'] | df['entrySmaShort'] | df['entrySmcShort']

        df['longSig'] = df['longCondition'] & ~df['longCondition'].shift(1, fill_value=False)
        df['shortSig'] = df['shortCondition'] & ~df['shortCondition'].shift(1, fill_value=False)

        return df