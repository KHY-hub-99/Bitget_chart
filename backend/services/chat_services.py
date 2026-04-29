import pandas as pd
import numpy as np

def convert_df_to_chart_data(df: pd.DataFrame, max_points: int = 5000):
    """
    데이터프레임을 프론트엔드 Lightweight Charts 포맷으로 변환합니다.
    사용자가 제시한 최종 통일 컬럼 기준만을 100% 엄격하게 준수합니다.
    """
    # [1] 데이터 슬라이싱 및 표준화
    df_js = df.tail(max_points).copy().reset_index()
    df_js.columns = [str(c) for c in df_js.columns]
    
    # 중복 컬럼 제거 및 결측치 처리
    df_js = df_js.loc[:, ~df_js.columns.duplicated()]
    df_js = df_js.replace([np.inf, -np.inf], np.nan)
    
    # 시간 포맷 변환 (UNIX Timestamp)
    # ※ 주의: Lightweight Charts v4 이상에서 일봉 미만(15m 등)은 반드시 UTC 초(s) 단위여야 합니다.
    # 이전 코드에서 밀리초(ms)로 넘기고 있었다면 /1000 을 해주는 이 로직이 맞습니다.
    time_col = 'time' if 'time' in df_js.columns else 'index'
    if time_col in df_js.columns:
        df_js['time'] = df_js[time_col].apply(
            lambda x: int(x.timestamp()) if isinstance(x, pd.Timestamp) else int(x // 1000 if x > 1e12 else x)
        )
    
    # [2] 기본 데이터 (Candles & Volumes)
    candles = df_js[['time', 'open', 'high', 'low', 'close']].to_dict(orient='records')
    
    # 볼륨은 기본 차트 구성 요소이므로 존재할 경우에만 포함
    if 'volume' in df_js.columns:
        volumes = df_js[['time', 'volume']].dropna().rename(columns={'volume': 'value'}).to_dict(orient='records')
    else:
        volumes = []
    
    # [3] 지표 데이터 그룹화 (최종 통일 리스트 기준 반영)
    indicator_names = [
        # 일목
        "tenkan", "kijun", "senkouA", "senkouB", "cloudTop", "cloudBottom",
        # Whale
        "sma224", "vwma224",
        # 기술적 지표
        "rsiVal", "mfiVal", "macdLine", "signalLine", "bbLower", "bbMid", "bbUpper",
        # SMC 구조
        "swingHighLevel", "trailingBottom", "equilibrium",
        # 역추세
        "topDiamond", "bottomDiamond",
        # 추세
        "trend",
        # [수정됨] 매매 조건 및 최종 확정 시그널
        "longSig_Rule1", "shortSig_Rule1", "longSig_Rule2", "shortSig_Rule2"
    ]
    
    indicators = {}
    for col in indicator_names:
        if col in df_js.columns:
            valid_data = df_js[['time', col]].dropna()
            indicators[col] = valid_data.rename(columns={col: 'value'}).to_dict(orient='records')
        else:
            indicators[col] = []
            
    # [4] 마커 생성 로직 (오직 허용된 컬럼만 활용)
    markers = []
    
    # SMC 레벨 확정 시점 포착을 위한 변화량 계산
    if 'swingHighLevel' in df_js.columns:
        df_js['shl_diff'] = df_js['swingHighLevel'].diff()
    else:
        df_js['shl_diff'] = 0

    if 'trailingBottom' in df_js.columns:
        df_js['tb_diff'] = df_js['trailingBottom'].diff()
    else:
        df_js['tb_diff'] = 0

    for _, row in df_js.iterrows():
        t = row['time']
        
        # A. 메인 진입 신호 (Rule1, Rule2 세분화 반영 및 프론트엔드 연동 텍스트 삽입)
        if row.get('longSig_Rule1') == 1:
            markers.append({"time": t, "position": "belowBar", "color": "#26a69a", "shape": "arrowUp", "text": "longSig_Rule1"})
        elif row.get('longSig_Rule2') == 1:
            markers.append({"time": t, "position": "belowBar", "color": "#26a69a", "shape": "arrowUp", "text": "longSig_Rule2"})
            
        if row.get('shortSig_Rule1') == 1:
            markers.append({"time": t, "position": "aboveBar", "color": "#ef5350", "shape": "arrowDown", "text": "shortSig_Rule1"})
        elif row.get('shortSig_Rule2') == 1:
            markers.append({"time": t, "position": "aboveBar", "color": "#ef5350", "shape": "arrowDown", "text": "shortSig_Rule2"})
            
        # B. 역추세 및 익절 신호 (다이아몬드)
        # 프론트엔드의 `m.text.includes("topDiamond")` 등에 완벽히 대응
        if row.get('topDiamond') == 1:
            markers.append({"time": t, "position": "aboveBar", "color": "#FF5252", "shape": "diamond", "text": "topDiamond"})
        elif row.get('bottomDiamond') == 1: 
            markers.append({"time": t, "position": "belowBar", "color": "#4CAF50", "shape": "diamond", "text": "bottomDiamond"})

        # C. 시장 구조 강도 마킹 (레벨 변화 확정 시점)
        # 상단 레벨 확정
        if pd.notna(row.get('swingHighLevel')) and row.get('shl_diff') != 0:
            markers.append({
                "time": t, "position": "aboveBar", "color": "#878b94", 
                "shape": "circle", "text": "High"
            })
            
        # 하단 레벨 확정
        if pd.notna(row.get('trailingBottom')) and row.get('tb_diff') != 0:
            markers.append({
                "time": t, "position": "belowBar", "color": "#878b94", 
                "shape": "circle", "text": "Low"
            })

    return {
        "candles": candles, 
        "volumes": volumes,
        "indicators": indicators, 
        "markers": markers,
        "metadata": {} 
    }