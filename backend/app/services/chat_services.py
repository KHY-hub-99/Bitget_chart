import pandas as pd
import numpy as np

def convert_df_to_chart_data(df: pd.DataFrame):
    """
    Pandas DataFrame을 프론트엔드 차트 라이브러리용 포맷으로 변환
    """
    # 1. 시간축 변환 (초 단위 Unix Timestamp)ㄴ
    df_js = df.reset_index()
    df_js['time'] = df_js['time'].apply(lambda x: int(x.timestamp()))
    
    # 2. NaN 값 처리 (JSON에서 에러 방지)
    df_js = df_js.replace({np.nan: None})
    
    # 3. 캔들스틱 데이터
    candles = df_js[['time', 'open', 'high', 'low', 'close']].to_dict(orient='records')
    
    # 4. 볼륨 데이터
    volumes = df_js[['time', 'volume']].rename(columns={'volume': 'value'}).to_dict(orient='records')
    
    # 5. 지표 데이터 (Line Series)
    indicators = {
        "kijun": df_js[['time', 'kijun']].rename(columns={'kijun': 'value'}).to_dict(orient='records'),
        "bb_upper": df_js[['time', 'BB_upper']].rename(columns={'BB_upper': 'value'}).to_dict(orient='records'),
        "bb_lower": df_js[['time', 'BB_lower']].rename(columns={'BB_lower': 'value'}).to_dict(orient='records'),
        "rsi": df_js[['time', 'RSI_14']].rename(columns={'RSI_14': 'value'}).to_dict(orient='records'),
    }
    
    # 6. 매매 신호 마커 (Markers)
    markers = []
    for _, row in df_js.iterrows():
        if row['MASTER_LONG']:
            markers.append({"time": row['time'], "position": "belowBar", "color": "#26a69a", "shape": "arrowUp", "text": "LONG"})
        elif row['MASTER_SHORT']:
            markers.append({"time": row['time'], "position": "aboveBar", "color": "#ef5350", "shape": "arrowDown", "text": "SHORT"})
        
        # 고점/저점 감지 추가
        if row['TOP_DETECTED']:
            markers.append({"time": row['time'], "position": "aboveBar", "color": "#e91e63", "shape": "circle", "text": "TOP"})
        elif row['BOTTOM_DETECTED']:
            markers.append({"time": row['time'], "position": "belowBar", "color": "#2196f3", "shape": "circle", "text": "BOT"})

    return {
        "candles": candles,
        "volumes": volumes,
        "indicators": indicators,
        "markers": markers
    }