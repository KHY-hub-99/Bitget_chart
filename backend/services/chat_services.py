import pandas as pd
import numpy as np

def convert_df_to_chart_data(df: pd.DataFrame, max_points: int = 5000):
    # [1] 최신 데이터 슬라이싱 및 컬럼명 소문자 강제 통일
    # 🎯 변수명 표준화의 시작점입니다.
    df_js = df.tail(max_points).copy().reset_index()
    df_js.columns = [str(c).lower() for c in df_js.columns] 
    
    # 중복 컬럼 제거 (혹시 모를 index 중복 방지)
    df_js = df_js.loc[:, ~df_js.columns.duplicated()]
    
    # 시간 포맷 변환 (Unix Timestamp - Seconds)
    df_js['time'] = df_js['time'].apply(lambda x: int(x.timestamp()))
    
    # NaN 값을 None으로 변환하여 JSON 직렬화 에러 방지
    df_js = df_js.replace({np.nan: None})
    
    # 캔들과 거래량 기본 데이터
    candles = df_js[['time', 'open', 'high', 'low', 'close']].to_dict(orient='records')
    volumes = df_js[['time', 'volume']].rename(columns={'volume': 'value'}).to_dict(orient='records')
    
    # [2] 지표 데이터 추출 (pine_data.py의 변수명과 1:1 매칭)
    # 🎯 프론트엔드 TradingChart.tsx가 찾는 키값과 일치시켰습니다.
    indicators = {
        "kijun": df_js[['time', 'kijun']].rename(columns={'kijun': 'value'}).to_dict(orient='records'),
        "senkou_a": df_js[['time', 'senkou_a']].rename(columns={'senkou_a': 'value'}).to_dict(orient='records'),
        "senkou_b": df_js[['time', 'senkou_b']].rename(columns={'senkou_b': 'value'}).to_dict(orient='records'),
        "bb_upper": df_js[['time', 'bb_upper']].rename(columns={'bb_upper': 'value'}).to_dict(orient='records'),
        "bb_middle": df_js[['time', 'bb_middle']].rename(columns={'bb_middle': 'value'}).to_dict(orient='records'),
        "bb_lower": df_js[['time', 'bb_lower']].rename(columns={'bb_lower': 'value'}).to_dict(orient='records'),
        "rsi": df_js[['time', 'rsi']].rename(columns={'rsi': 'value'}).to_dict(orient='records'),
        "macd_line": df_js[['time', 'macd_line']].rename(columns={'macd_line': 'value'}).to_dict(orient='records'),
        "macd_sig": df_js[['time', 'macd_sig']].rename(columns={'macd_sig': 'value'}).to_dict(orient='records'), # 🎯 macd_signal에서 수정
        "mfi": df_js[['time', 'mfi']].rename(columns={'mfi': 'value'}).to_dict(orient='records') if 'mfi' in df_js.columns else []
    }
    
    # [3] 마커 생성 로직 (신호 변수명 통일)
    markers = []
    for _, row in df_js.iterrows():
        t = row['time']
        
        # MASTER 매매 신호 (DB 저장된 1/0 값을 기반으로 판정)
        if row.get('master_long') == 1:
            markers.append({
                "time": t, "position": "belowBar", "color": "#26a69a", 
                "shape": "arrowUp", "text": "MASTER LONG"
            })
        elif row.get('master_short') == 1:
            markers.append({
                "time": t, "position": "aboveBar", "color": "#ef5350", 
                "shape": "arrowDown", "text": "MASTER SHORT"
            })
            
        # TOP/BOTTOM 과매수/도 검출 신호
        if row.get('top_detected') == 1:
            markers.append({
                "time": t, "position": "aboveBar", "color": "#ff9800", 
                "shape": "circle", "text": "TOP"
            })
        elif row.get('bottom_detected') == 1: 
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