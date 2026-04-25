import pandas as pd
import numpy as np

def convert_df_to_chart_data(df: pd.DataFrame, max_points: int = 5000):
    # [1] 최신 데이터 슬라이싱 및 컬럼명 소문자 통일 (대소문자 에러 방지 핵심!)
    df_js = df.tail(max_points).copy().reset_index()
    df_js.columns = [c.lower() for c in df_js.columns] # 모든 컬럼명을 소문자로 강제 변환
    df_js = df_js.loc[:, ~df_js.columns.duplicated()]
    
    # [DEBUG] 컬럼 확인
    # print(f"\n[BACKEND DEBUG] 처리 중인 컬럼: {df_js.columns.tolist()}")
    
    df_js['time'] = df_js['time'].apply(lambda x: int(x.timestamp()))
    df_js = df_js.replace({np.nan: None})
    
    # [DEBUG] 신호 개수 파악 (소문자로 체크)
    for col in ['master_long', 'master_short', 'top_detected', 'bottom_detected']:
        if col in df_js.columns:
            # 신호가 1(True)인 행의 개수 계산
            count = df_js[df_js[col].astype(float) == 1.0].shape[0]
            print(f"[BACKEND DEBUG] {col.upper()} 신호 발견: {count}개")

    candles = df_js[['time', 'open', 'high', 'low', 'close']].to_dict(orient='records')
    volumes = df_js[['time', 'volume']].rename(columns={'volume': 'value'}).to_dict(orient='records')
    
    # [2] 지표 데이터 추출 (모두 소문자 컬럼 사용)
    indicators = {
        "kijun": df_js[['time', 'kijun']].rename(columns={'kijun': 'value'}).to_dict(orient='records'),
        "senkou_a": df_js[['time', 'senkou_a']].rename(columns={'senkou_a': 'value'}).to_dict(orient='records'),
        "senkou_b": df_js[['time', 'senkou_b']].rename(columns={'senkou_b': 'value'}).to_dict(orient='records'),
        "bb_upper": df_js[['time', 'bb_upper']].rename(columns={'bb_upper': 'value'}).to_dict(orient='records'),
        "bb_middle": df_js[['time', 'bb_middle']].rename(columns={'bb_middle': 'value'}).to_dict(orient='records'),
        "bb_lower": df_js[['time', 'bb_lower']].rename(columns={'bb_lower': 'value'}).to_dict(orient='records'),
        "rsi": df_js[['time', 'rsi']].rename(columns={'rsi': 'value'}).to_dict(orient='records'),
        "macd_line": df_js[['time', 'macd_line']].rename(columns={'macd_line': 'value'}).to_dict(orient='records'),
        "macd_sig": df_js[['time', 'macd_sig']].rename(columns={'macd_sig': 'value'}).to_dict(orient='records'),
    }
    
    # [3] 마커 생성 로직 (소문자 키값 사용)
    markers = []
    for _, row in df_js.iterrows():
        t = row['time']
        
        # MASTER 신호
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
            
        # TOP/BOTTOM 검출 신호
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

    print(f"[BACKEND DEBUG] 최종 생성된 마커 총 개수: {len(markers)}개\n")

    return {
        "candles": candles, "volumes": volumes,
        "indicators": indicators, "markers": markers
    }