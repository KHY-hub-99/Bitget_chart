"""
@pyne
"""
from pynecore import Series, Persistent
from pynecore.lib import script, ta, math, close, high, low, open, volume, na, nz, plot, plotshape, color

@script.indicator("Master SMC Strategy", overlay=True)
def main():
    # --- [파라미터 설정] ---
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

    # --- [2. 지표 계산] ---
    tenkan: Series[float] = (ta.highest(high, tenkanLen) + ta.lowest(low, tenkanLen)) / 2
    kijun: Series[float] = (ta.highest(high, kijunLen) + ta.lowest(low, kijunLen)) / 2
    
    # 선행스팬 계산
    senkouA: Series[float] = (tenkan + kijun) / 2
    senkouB: Series[float] = (ta.highest(high, senkouBLen) + ta.lowest(low, senkouBLen)) / 2

    # [수정] displacement-1 만큼 과거의 값을 가져오기 위해 시리즈 참조
    # PyneCore에서 Series 변수는 대괄호 참조가 가능합니다.
    cloudTop: Series[float] = math.max(senkouA[displacement-1], senkouB[displacement-1])
    cloudBottom: Series[float] = math.min(senkouA[displacement-1], senkouB[displacement-1])

    sma224: Series[float] = ta.sma(close, whaleLen)
    vwma224: Series[float] = ta.vwma(close, whaleLen)

    macdLine, signalLine, _ = ta.macd(close, 12, 26, 9)
    rsiVal: Series[float] = ta.rsi(close, rsiLen)
    mfiVal: Series[float] = ta.mfi(close, mfiLen)
    bbMid, bbUpper, bbLower = ta.bb(close, bbLen, bbMult)
    
    volSma = ta.sma(volume, 20)
    volConfirm = volume > volSma * volMult

    # --- [3. 신호 로직] ---
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

    # [수정] Persistent 변수는 [1]이 안되므로 wasLongPos(어제값)를 사용
    longSig = longCondition and (isLongPos and not wasLongPos)
    shortSig = shortCondition and (isShortPos and not wasShortPos)
    
    # 다음 바를 위해 현재 값을 어제 값으로 저장
    wasLongPos = isLongPos
    wasShortPos = isShortPos

    # --- [4. 역추세 다이아몬드 신호 수정] ---
    # [수정] ta.highest() 결과에 바로 [1]을 붙이면 float 에러가 납니다.
    # Series 변수에 먼저 할당한 후 [1]을 참조해야 합니다.
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

    # --- [5. SMC 구조 추적] ---
    ph = ta.pivothigh(high, swingsLength, swingsLength)
    pl = ta.pivotlow(low, swingsLength, swingsLength)

    swingHighLevel: Persistent[float] = na
    trailingBottom: Persistent[float] = na
    trend: Persistent[int] = 0 

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

    # nz()를 사용하여 값이 na일 경우 에러 방지
    equilibrium = (nz(swingHighLevel) + nz(trailingBottom)) / 2

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