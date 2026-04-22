import pandas as pd
import numpy as np

def convert_df_to_chart_data(df: pd.DataFrame):
    # [DEBUG] 현재 데이터프레임에 어떤 컬럼들이 있는지 출력
    print(f"\n[BACKEND DEBUG] 원본 컬럼 목록: {df.columns.tolist()}")
    
    df_js = df.reset_index()
    df_js['time'] = df_js['time'].apply(lambda x: int(x.timestamp()))
    df_js = df_js.replace({np.nan: None})
    
    # [DEBUG] 각 신호의 개수 파악
    for col in ['MASTER_LONG', 'MASTER_SHORT', 'TOP_DETECTED', 'BOTTOM_DETECTED']:
        if col in df_js.columns:
            count = df_js[df_js[col] == True].shape[0]
            print(f"[BACKEND DEBUG] {col} 신호 개수: {count}개")
        else:
            print(f"[BACKEND DEBUG] 경고: {col} 컬럼이 데이터프레임에 없습니다!")

    candles = df_js[['time', 'open', 'high', 'low', 'close']].to_dict(orient='records')
    volumes = df_js[['time', 'volume']].rename(columns={'volume': 'value'}).to_dict(orient='records')
    
    # 프론트엔드와 이름을 맞춘 최종 indicators
    indicators = {
        "kijun": df_js[['time', 'kijun']].rename(columns={'kijun': 'value'}).to_dict(orient='records'),
        "senkou_a": df_js[['time', 'senkou_a']].rename(columns={'senkou_a': 'value'}).to_dict(orient='records'),
        "senkou_b": df_js[['time', 'senkou_b']].rename(columns={'senkou_b': 'value'}).to_dict(orient='records'),
        "bb_upper": df_js[['time', 'BB_upper']].rename(columns={'BB_upper': 'value'}).to_dict(orient='records'),
        "bb_lower": df_js[['time', 'BB_lower']].rename(columns={'BB_lower': 'value'}).to_dict(orient='records'),
        "rsi": df_js[['time', 'RSI_14']].rename(columns={'RSI_14': 'value'}).to_dict(orient='records'),
        "macd_line": df_js[['time', 'MACD_line']].rename(columns={'MACD_line': 'value'}).to_dict(orient='records'),
        "macd_sig": df_js[['time', 'MACD_signal']].rename(columns={'MACD_signal': 'value'}).to_dict(orient='records'),
    }
    
    markers = []
    for _, row in df_js.iterrows():
        # 컬럼명이 MASTER_LONG/SHORT 인지 MASTER_L/S 인지 엑셀 이미지와 대조 필요!
        if row.get('MASTER_LONG'):
            markers.append({"time": row['time'], "text": "MASTER LONG"})
        elif row.get('MASTER_SHORT'):
            markers.append({"time": row['time'], "text": "MASTER SHORT"})
            
        if row.get('TOP_DETECTED'):
            markers.append({"time": row['time'], "text": "TOP"})
        elif row.get('BOTTOM_DETECTED'): # 🎯 텍스트를 확실히 BOTTOM으로 설정
            markers.append({"time": row['time'], "text": "BOTTOM"})

    print(f"[BACKEND DEBUG] 최종 생성된 마커 총 개수: {len(markers)}개\n")

    return {
        "candles": candles, "volumes": volumes,
        "indicators": indicators, "markers": markers
    }