import pandas as pd
import numpy as np

def convert_df_to_chart_data(df: pd.DataFrame, max_points: int = 5000):
    # [1] 최신 데이터 슬라이싱 및 컬럼명 소문자 강제 통일
    df_js = df.tail(max_points).copy().reset_index()
    df_js.columns = [str(c).lower() for c in df_js.columns] 
    
    # 중복 컬럼 제거
    df_js = df_js.loc[:, ~df_js.columns.duplicated()]
    
    # 수정 1: 시간 포맷 변환 안전장치 (이미 int면 그대로, Timestamp면 변환)
    df_js['time'] = df_js['time'].apply(
        lambda x: int(x.timestamp()) if isinstance(x, pd.Timestamp) else int(x)
    )
    
    # 캔들과 거래량 기본 데이터 (OHLCV는 None이 없어야 하므로 fillna 처리)
    df_js = df_js.replace([np.inf, -np.inf], np.nan) # 무한대 방지
    
    candles = df_js[['time', 'open', 'high', 'low', 'close']].to_dict(orient='records')
    volumes = df_js[['time', 'volume']].rename(columns={'volume': 'value'}).to_dict(orient='records')
    
    # 수정 2: 지표 데이터 추출 로직 개선 (NaN 값 필터링 및 반복문 압축)
    # Lightweight Charts 에러 방지를 위해 값이 존재하는(notnull) 데이터만 넘깁니다.
    indicator_names = [
        "kijun", "senkou_a", "senkou_b", 
        "bb_upper", "bb_middle", "bb_lower", 
        "rsi", "macd_line", "macd_sig", "mfi"
    ]
    
    indicators = {}
    for col in indicator_names:
        if col in df_js.columns:
            # 해당 지표 값이 NaN이 아닌 정상 데이터만 추출 (프론트엔드 렌더링 에러 완벽 방지)
            valid_data = df_js[['time', col]].dropna()
            indicators[col] = valid_data.rename(columns={col: 'value'}).to_dict(orient='records')
        else:
            indicators[col] = []
            
    # [3] 마커 생성 로직 (신호 변수명 통일)
    markers = []
    for _, row in df_js.iterrows():
        t = row['time']
        
        # MASTER 매매 신호
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