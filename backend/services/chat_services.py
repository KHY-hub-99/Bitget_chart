import pandas as pd
import numpy as np

def convert_df_to_chart_data(df: pd.DataFrame, max_points: int = 5000):
    """
    데이터프레임을 프론트엔드 Lightweight Charts 포맷으로 변환합니다.
    새로 추가된 Trailing Extremes 및 Trend를 포함하여 Standard CamelCase를 완벽 준수합니다.
    """
    # [1] 데이터 슬라이싱 및 컬럼명 표준화
    df_js = df.tail(max_points).copy().reset_index()
    df_js.columns = [str(c) for c in df_js.columns]
    
    # 중복 컬럼 제거 및 결측치 처리
    df_js = df_js.loc[:, ~df_js.columns.duplicated()]
    df_js = df_js.replace([np.inf, -np.inf], np.nan)
    
    # 시간 포맷 변환 (UNIX Timestamp - Lightweight Charts는 초 단위를 사용함)
    time_col = 'time' if 'time' in df_js.columns else 'index'
    if time_col in df_js.columns:
        df_js['time'] = df_js[time_col].apply(
            lambda x: int(x.timestamp()) if isinstance(x, pd.Timestamp) else int(x // 1000 if x > 1e12 else x)
        )
    
    # [2] 기본 차트 데이터 (Candles & Volumes)
    candles = df_js[['time', 'open', 'high', 'low', 'close']].to_dict(orient='records')
    volumes = df_js[['time', 'volume']].rename(columns={'volume': 'value'}).to_dict(orient='records')
    
    # [3] 지표 데이터 그룹화 (Standard CamelCase 기준)
    indicator_names = [
        # 1. 일목균형표 (Ichimoku)
        "tenkan", "kijun", "senkouA", "senkouB", "cloudTop", "cloudBottom", 
        # 2. Whale 세력선 및 거래량
        "sma224", "vwma224", "volConfirm",
        # 3. 기술적 지표 (RSI, MFI, MACD, BB)
        "rsi", "mfi", "macdLine", "signalLine", "bbLower", "bbMid", "bbUpper",
        # 4. SMC 구조 및 가격 레벨
        "swingHighLevel", "swingLowLevel", "equilibrium",
        # 5. 추적 스윙 및 시장 추세 (Trailing Extremes & Trend)
        "trend", "trailingTop", "trailingBottom",
        # 6. 역추세 세부 신호 (T/B 신호는 마커에서 처리하므로 여기선 값만 추출)
        "bearishDiv", "bullishDiv", "extremeTop", "extremeBottom",
        # 7. 하이브리드 전략 진입 규칙
        "entryVwmaLong", "entrySmcLong", "entryVwmaShort", "entrySmcShort"
    ]
    
    indicators = {}
    for col in indicator_names:
        if col in df_js.columns:
            # 선 차트의 끊김을 방지하기 위해 유효한 값만 전송
            # topType, bottomType 같은 문자열은 indicators에서 제외하고 마커나 별도 로직으로 활용
            valid_data = df_js[['time', col]].dropna()
            indicators[col] = valid_data.rename(columns={col: 'value'}).to_dict(orient='records')
        else:
            indicators[col] = []
            
    # [4] 마커 생성 로직 (시뮬전략 및 마스터 지표 마킹)
    markers = []
    for _, row in df_js.iterrows():
        t = row['time']
        
        # A. 메인 진입 신호 (화살표)
        if row.get('longSig') == 1:
            # SMC Strong Low에서 진입한 경우 별도 표시
            is_smc = row.get('entrySmcLong') == 1
            markers.append({
                "time": t, 
                "position": "belowBar", 
                "color": "#26a69a", 
                "shape": "arrowUp", 
                "text": "LONG(SMC)" if is_smc else "LONG"
            })
            
        elif row.get('shortSig') == 1:
            # SMC Strong High에서 진입한 경우 별도 표시
            is_smc = row.get('entrySmcShort') == 1
            markers.append({
                "time": t, 
                "position": "aboveBar", 
                "color": "#ef5350", 
                "shape": "arrowDown", 
                "text": "SHORT(SMC)" if is_smc else "SHORT"
            })
            
        # B. 역추세 및 익절 신호 (다이아몬드)
        # TOP (빨강) = 롱 익절/숏 경고, BOTTOM (초록) = 숏 익절/롱 경고
        if row.get('TOP') == 1:
            markers.append({"time": t, "position": "aboveBar", "color": "#FF5252", "shape": "diamond", "text": "TOP"})
        elif row.get('BOTTOM') == 1: 
            markers.append({"time": t, "position": "belowBar", "color": "#4CAF50", "shape": "diamond", "text": "BOTTOM"})

        # C. 시장 구조 강도 마킹 (Strong High / Low 확정 시점 표시)
        # trailingTop/Bottom 값이 갱신되는 시점에 텍스트를 띄우고 싶을 때 활용
        if pd.notna(row.get('swingHighLevel')) and row.get('shl_diff') != 0:
            markers.append({
                "time": t, 
                "position": "aboveBar", 
                "color": "#878b94", # 회색
                "shape": "circle", 
                "text": str(row.get('topType', 'High')) 
            })

    return {
        "candles": candles, 
        "volumes": volumes,
        "indicators": indicators, 
        "markers": markers,
        # topType 등 텍스트 기반 메타데이터는 별도 전달 가능
        "metadata": {
            "topType": df_js[['time', 'topType']].dropna().to_dict(orient='records'),
            "bottomType": df_js[['time', 'bottomType']].dropna().to_dict(orient='records')
        }
    }