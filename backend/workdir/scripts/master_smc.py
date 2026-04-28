"""
@pyne
"""
from pynecore import Series, Persistent
from pynecore.lib import script, ta, math, close, high, low, open, volume, na, nz, plot, plotshape, color

# [1. Script Definition]
@script.indicator("Master SMC Strategy", overlay=True)
def main():
    # --- [Parameter Settings] ---
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
    swingsLength = 50

    # --- [2. Indicator Calculations] ---
    tenkan: Series[float] = (ta.highest(high, tenkanLen) + ta.lowest(low, tenkanLen)) / 2
    kijun: Series[float] = (ta.highest(high, kijunLen) + ta.lowest(low, kijunLen)) / 2
    
    # Leading Span Calculation
    senkouA: Series[float] = (tenkan + kijun) / 2
    senkouB: Series[float] = (ta.highest(high, senkouBLen) + ta.lowest(low, senkouBLen)) / 2

    # [Update] Reference series to fetch past values by displacement-1
    # In PyneCore, Series variables allow square bracket referencing.
    cloudTop: Series[float] = math.max(senkouA[displacement-1], senkouB[displacement-1])
    cloudBottom: Series[float] = math.min(senkouA[displacement-1], senkouB[displacement-1])

    # Whale 224
    sma224: Series[float] = ta.sma(close, whaleLen)
    vwma224: Series[float] = ta.vwma(close, whaleLen)

    # Technical Indicators
    macdLine, signalLine, _ = ta.macd(close, 12, 26, 9)
    rsiVal: Series[float] = ta.rsi(close, rsiLen)
    mfiVal: Series[float] = ta.mfi(close, mfiLen)
    bbMid, bbUpper, bbLower = ta.bb(close, bbLen, bbMult)
    
    volSma = ta.sma(volume, 20)
    volConfirm = volume > volSma * volMult

    # --- [3. Signal Logic] ---
    isLongPos: Persistent[bool] = False
    isShortPos: Persistent[bool] = False
    wasLongPos: Persistent[bool] = False
    wasShortPos: Persistent[bool] = False

    longCondition = ta.crossover(close, cloudTop) and macdLine > signalLine and volConfirm
    if longCondition:
        isLongPos = True
        isShortPos = False

    shortCondition = ta.crossunder(close, cloudBottom) and macdLine < signalLine and volConfirm
    if shortCondition:
        isShortPos = True
        isLongPos = False

    # [Update] Persistent variables do not support [1], so using wasLongPos (previous value)
    # This prevents duplicate signals by checking the previous bar's state
    longSig = longCondition and (isLongPos and not wasLongPos)
    shortSig = shortCondition and (isShortPos and not wasShortPos)
    
    # Store current value as previous value for the next bar
    wasLongPos = isLongPos
    wasShortPos = isShortPos

    # --- [4. Counter-trend Diamond Signal Update] ---
    # [Update] Attaching [1] directly to ta.highest() result causes a float error.
    # Must assign to a Series variable first before referencing [1].
    hh5: Series[float] = ta.highest(high, 5)
    ll5: Series[float] = ta.lowest(low, 5)
    rsiH5: Series[float] = ta.highest(rsiVal, 5)
    rsiL5: Series[float] = ta.lowest(rsiVal, 5)

    bearishDiv = (high > hh5[1] and rsiVal < rsiH5[1]) and rsiVal > 65
    bullishDiv = (low < ll5[1] and rsiVal > rsiL5[1]) and rsiVal < 35
    
    extremeTop = high >= bbUpper and rsiVal > 75 and mfiVal > 80
    extremeBottom = low <= bbLower and rsiVal < 25 and mfiVal < 20

    topDiamond = bearishDiv or extremeTop
    bottomDiamond = bullishDiv or extremeBottom

    # --- [5. SMC Structure Tracking] ---
    ph = ta.pivothigh(high, swingsLength, swingsLength)
    pl = ta.pivotlow(low, swingsLength, swingsLength)

    # Declare persistent state variables
    swingHighLevel: Persistent[float] = na
    trailingBottom: Persistent[float] = na
    trend: Persistent[int] = 0 # 1: Bull, -1: Bear

    # Update when pivot occurs
    if not na(ph):
        swingHighLevel = ph
    if not na(pl):
        trailingBottom = pl

    # Real-time Trailing expansion (when price pushes boundaries)
    if not na(swingHighLevel):
        swingHighLevel = math.max(high, swingHighLevel)
    if not na(trailingBottom):
        trailingBottom = math.min(low, trailingBottom)

    # Trend determination
    if not na(swingHighLevel) and close > swingHighLevel:
        trend = 1
    elif not na(trailingBottom) and close < trailingBottom:
        trend = -1

    # Equilibrium calculation (average of upper/lower levels)
    # Use nz() to prevent errors when values are na
    equilibrium = (nz(swingHighLevel) + nz(trailingBottom)) / 2

    # --- [6. Return] ---
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
        "bbUpper": bbUpper,
        "bbLower": bbLower,
        "bbMid": bbMid,
        "longSig": longSig,
        "shortSig": shortSig,
        "topDiamond": topDiamond,
        "bottomDiamond": bottomDiamond,
        "swingHighLevel": swingHighLevel,
        "trailingBottom": trailingBottom,
        "equilibrium": equilibrium,
        "trend": trend
    }