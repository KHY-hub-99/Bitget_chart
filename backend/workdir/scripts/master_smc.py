"""
@pyne
"""
from pynecore import Series, Persistent
from pynecore.lib import script, ta, math, close, high, low, open, volume, na, nz

@script.indicator("Master SMC Strategy", overlay=True)
def main():
    # --- [1. Parameter Settings] ---
    tenkanLen, kijunLen, senkouBLen, displacement = 9, 26, 52, 26
    rsiLen, mfiLen, bbLen, bbMult, volMult = 14, 14, 20, 2.2, 1.5
    whaleLen, swingsLength, lookback = 224, 50, 3

    # --- [2. Indicator Calculations] ---
    tenkan: Series[float] = (ta.highest(high, tenkanLen) + ta.lowest(low, tenkanLen)) / 2
    kijun: Series[float] = (ta.highest(high, kijunLen) + ta.lowest(low, kijunLen)) / 2
    senkouA: Series[float] = (tenkan + kijun) / 2
    senkouB: Series[float] = (ta.highest(high, senkouBLen) + ta.lowest(low, senkouBLen)) / 2
    cloudTop: Series[float] = math.max(senkouA[displacement-1], senkouB[displacement-1])
    cloudBottom: Series[float] = math.min(senkouA[displacement-1], senkouB[displacement-1])

    sma224: Series[float] = ta.sma(close, whaleLen)
    vwma224: Series[float] = ta.vwma(close, whaleLen)

    macdLine, signalLine, _ = ta.macd(close, 12, 26, 9)
    rsiVal: Series[float] = ta.rsi(close, rsiLen)
    mfiVal: Series[float] = ta.mfi(close, mfiLen)
    bbMid: Series[float] = ta.sma(close, bbLen)
    var_val: Series[float] = ta.variance(close, bbLen)
    
    safe_dev: Series[float] = math.sqrt(math.max(0.0, nz(var_val, 0.0)))
    
    bbUpper: Series[float] = bbMid + (safe_dev * bbMult)
    bbLower: Series[float] = bbMid - (safe_dev * bbMult)

    volConfirm: Series[bool] = volume > ta.sma(volume, 20) * volMult

    # --- [3. SMC Structure] ---
    ph = ta.pivothigh(high, swingsLength, swingsLength)
    pl = ta.pivotlow(low, swingsLength, swingsLength)

    swingHighLevel: Persistent[float] = na
    trailingBottom: Persistent[float] = na
    trend: Persistent[int] = 0 

    # Strong High / Strong Low
    if not na(ph): 
        swingHighLevel = ph
    if not na(pl): 
        trailingBottom = pl

    if not na(swingHighLevel): 
        swingHighLevel = math.max(high, swingHighLevel)
    if not na(trailingBottom): 
        trailingBottom = math.min(low, trailingBottom)

    if not na(swingHighLevel) and close > swingHighLevel: 
        trend = 1
    elif not na(trailingBottom) and close < trailingBottom: 
        trend = -1

    equilibrium = (nz(swingHighLevel) + nz(trailingBottom)) / 2

    # --- [4. Diamond Signals (TP)] ---
    hh5: Series[float] = ta.highest(high, 5)
    ll5: Series[float] = ta.lowest(low, 5)
    rsiH5: Series[float] = ta.highest(rsiVal, 5)
    rsiL5: Series[float] = ta.lowest(rsiVal, 5)

    bearishDiv = (high > hh5[1] and rsiVal < rsiH5[1]) and rsiVal > 65
    bullishDiv = (low < ll5[1] and rsiVal > rsiL5[1]) and rsiVal < 35
    extremeTop = (high >= bbUpper) and (rsiVal > 75) and (mfiVal > 80)
    extremeBottom = (low <= bbLower) and (rsiVal < 25) and (mfiVal < 20)

    topDiamond = bearishDiv or extremeTop
    bottomDiamond = bullishDiv or extremeBottom

    # --- [5. Trading Logic (Rule 1 & Rule 2)] ---
    lowest_3: Series[float] = ta.lowest(low, lookback)
    highest_3: Series[float] = ta.highest(high, lookback)

    # rule 1: SMA/VWMA (Touch Pullback)
    touch_sma_long = (lowest_3[1] > sma224[1]) and (low <= sma224)
    touch_vwma_long = (lowest_3[1] > vwma224[1]) and (low <= vwma224)
    touch_sma_short = (highest_3[1] < sma224[1]) and (high >= sma224)
    touch_vwma_short = (highest_3[1] < vwma224[1]) and (high >= vwma224)

    # rule 2: SMC
    entrySmcLong = not na(pl)
    entrySmcShort = not na(ph)

    longSig_val = 1 if (touch_sma_long or touch_vwma_long or entrySmcLong) else 0
    shortSig_val = 1 if (touch_sma_short or touch_vwma_short or entrySmcShort) else 0

    return {
        "tenkan": tenkan,
        "kijun": kijun,
        "senkouA": senkouA,
        "senkouB": senkouB,
        "cloudTop": cloudTop,
        "cloudBottom": cloudBottom,
        
        "sma224": sma224,
        "vwma224": vwma224,
        
        "rsiVal": rsiVal,
        "mfiVal": mfiVal,
        "macdLine": macdLine,
        "signalLine": signalLine,
        "bbLower": bbLower,
        "bbMid": bbMid,
        "bbUpper": bbUpper,
        
        "swingHighLevel": swingHighLevel,
        "trailingBottom": trailingBottom,
        "equilibrium": equilibrium,
        
        "topDiamond": 1 if topDiamond else 0,
        "bottomDiamond": 1 if bottomDiamond else 0,
        "trend": trend,
        
        "longSig": longSig_val,
        "shortSig": shortSig_val
    }