import pandas as pd
import numpy as np

def convert_df_to_chart_data(df: pd.DataFrame, max_points: int = 5000):
    # [1] 최신 데이터 슬라이싱 및 컬럼명 문자열 변환 (소문자 강제 통일 제거 -> 원래 변수명 보존)
    df_js = df.tail(max_points).copy().reset_index()
    df_js.columns = [str(c) for c in df_js.columns]
    
    # 중복 컬럼 제거
    df_js = df_js.loc[:, ~df_js.columns.duplicated()]
    
    # 시간 포맷 변환 안전장치 (index가 초기화되면서 'time' 또는 'index' 컬럼에 시간이 존재)
    time_col = 'time' if 'time' in df_js.columns else 'index'
    if time_col in df_js.columns:
        df_js['time'] = df_js[time_col].apply(
            lambda x: int(x.timestamp()) if isinstance(x, pd.Timestamp) else int(x)
        )
    
    # 캔들과 거래량 기본 데이터
    df_js = df_js.replace([np.inf, -np.inf], np.nan) # 무한대 방지
    
    candles = df_js[['time', 'open', 'high', 'low', 'close']].to_dict(orient='records')
    volumes = df_js[['time', 'volume']].rename(columns={'volume': 'value'}).to_dict(orient='records')
    
    # --- [수정 사항: pine_data.py 변수명 규격(camelCase)에 맞춘 지표 데이터 추출] ---
    indicator_names = [
        "cloudTop", "cloudBottom",              # 일목균형표
        "sma224", "vwma224",                    # 세력선
        "bbUpper", "bbMid", "bbLower",          # 볼린저 밴드
        "rsi", "macdLine", "signalLine", "mfi"  # 기타 보조지표
    ]
    
    indicators = {}
    for col in indicator_names:
        if col in df_js.columns:
            # 해당 지표 값이 NaN이 아닌 정상 데이터만 추출
            valid_data = df_js[['time', col]].dropna()
            indicators[col] = valid_data.rename(columns={col: 'value'}).to_dict(orient='records')
        else:
            indicators[col] = []
            
    # [3] 마커 생성 로직 (pine_data.py 매매 신호 변수명 적용)
    markers = []
    for _, row in df_js.iterrows():
        t = row['time']
        
        # 진입 확정 시그널 (longSig, shortSig)
        if row.get('longSig') == 1 or row.get('longSig') is True:
            markers.append({
                "time": t, "position": "belowBar", "color": "#26a69a", 
                "shape": "arrowUp", "text": "LONG"
            })
        elif row.get('shortSig') == 1 or row.get('shortSig') is True:
            markers.append({
                "time": t, "position": "aboveBar", "color": "#ef5350", 
                "shape": "arrowDown", "text": "SHORT"
            })
            
        # 역추세 극점 시그널 (TOP, BOTTOM)
        if row.get('TOP') == 1 or row.get('TOP') is True:
            markers.append({
                "time": t, "position": "aboveBar", "color": "#ff9800", 
                "shape": "circle", "text": "TOP"
            })
        elif row.get('BOTTOM') == 1 or row.get('BOTTOM') is True: 
            markers.append({
                "time": t, "position": "belowBar", "color": "#2196f3", 
                "shape": "circle", "text": "BOTTOM"
            })

    return {
        "candles": candles, 
        "volumes": volumes,
        "indicators": indicators, 
        "markers": markers
    }