import pandas as pd
import numpy as np

def convert_df_to_chart_data(df: pd.DataFrame, max_points: int = 5000):
    # [1] 최신 데이터 슬라이싱 및 컬럼명 보존 (camelCase 유지)
    df_js = df.tail(max_points).copy().reset_index()
    df_js.columns = [str(c) for c in df_js.columns]
    
    # 중복 컬럼 제거
    df_js = df_js.loc[:, ~df_js.columns.duplicated()]
    
    # 시간 포맷 변환 (초 단위 UNIX 타임스탬프)
    time_col = 'time' if 'time' in df_js.columns else 'index'
    if time_col in df_js.columns:
        df_js['time'] = df_js[time_col].apply(
            lambda x: int(x.timestamp()) if isinstance(x, pd.Timestamp) else int(x)
        )
    
    # 캔들과 거래량 기본 데이터
    df_js = df_js.replace([np.inf, -np.inf], np.nan)
    candles = df_js[['time', 'open', 'high', 'low', 'close']].to_dict(orient='records')
    volumes = df_js[['time', 'volume']].rename(columns={'volume': 'value'}).to_dict(orient='records')
    
    # --- [수정 사항: SQL 리스트에 있는 모든 컬럼을 지표 리스트에 포함] ---
    indicator_names = [
        # 1. 일목균형표 상세 (REAL)
        "tenkan", "kijun", "senkouA", "senkouB", "cloudTop", "cloudBottom", 
        # 2. Whale 세력선 (REAL)
        "sma224", "vwma224", 
        # 3. 기술적 보조지표 (REAL/INTEGER)
        "rsi", "mfi", "macdLine", "signalLine", "bbUpper", "bbMid", "bbLower", "volConfirm",
        # 4. 매매 조건 및 확정 시그널 (INTEGER)
        "longCondition", "shortCondition", "longSig", "shortSig",
        # 5. SMC 구조 분석 지표 (INTEGER)
        "fvgBullish", "fvgBearish", "swingBOS", "swingCHOCH", "internalBOS", "internalCHOCH",
        # 6. 역추세 세부 신호 및 최종 마커 (INTEGER)
        "bearishDiv", "bullishDiv", "extremeTop", "extremeBottom", "TOP", "BOTTOM"
    ]
    
    indicators = {}
    for col in indicator_names:
        if col in df_js.columns:
            # 수치 데이터가 있는 봉만 추출하여 리스트로 변환
            valid_data = df_js[['time', col]].dropna()
            indicators[col] = valid_data.rename(columns={col: 'value'}).to_dict(orient='records')
        else:
            # 컬럼이 없을 경우 빈 리스트 반환 (에러 방지)
            indicators[col] = []
            
    # [3] 마커 생성 로직 (차트 위 시각적 신호)
    markers = []
    for _, row in df_js.iterrows():
        t = row['time']
        
        # A. 메인 매매 신호 (화살표)
        if row.get('longSig') == 1:
            markers.append({"time": t, "position": "belowBar", "color": "#26a69a", "shape": "arrowUp", "text": "LONG"})
        elif row.get('shortSig') == 1:
            markers.append({"time": t, "position": "aboveBar", "color": "#ef5350", "shape": "arrowDown", "text": "SHORT"})
            
        # B. 고점/저점 극점 신호 (원형)
        if row.get('TOP') == 1:
            markers.append({"time": t, "position": "aboveBar", "color": "#ff9800", "shape": "circle", "text": "TOP"})
        elif row.get('BOTTOM') == 1: 
            markers.append({"time": t, "position": "belowBar", "color": "#2196f3", "shape": "circle", "text": "BOTTOM"})

        # C. SMC 구조 변화 (BOS/CHoCH - 사각형)
        if row.get('swingBOS') == 1:
            markers.append({"time": t, "position": "inBar", "color": "#878b94", "shape": "square", "text": "BOS"})
        elif row.get('swingCHOCH') == 1:
            markers.append({"time": t, "position": "inBar", "color": "#d1d4dc", "shape": "square", "text": "CHoCH"})

    return {
        "candles": candles, 
        "volumes": volumes,
        "indicators": indicators, 
        "markers": markers
    }