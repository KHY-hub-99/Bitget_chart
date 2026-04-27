import pandas as pd
import numpy as np

def convert_df_to_chart_data(df: pd.DataFrame, max_points: int = 5000):
    """
    데이터프레임을 프론트엔드 Lightweight Charts 포맷으로 변환합니다.
    README.md 표준 변수명 및 시뮬레이션 전략 지표를 모두 포함합니다.
    """
    # [1] 데이터 슬라이싱 및 컬럼명 표준화
    df_js = df.tail(max_points).copy().reset_index()
    df_js.columns = [str(c) for c in df_js.columns]
    
    # 중복 컬럼 제거 및 결측치 처리
    df_js = df_js.loc[:, ~df_js.columns.duplicated()]
    df_js = df_js.replace([np.inf, -np.inf], np.nan)
    
    # 시간 포맷 변환 (UNIX Timestamp - 초 단위)
    time_col = 'time' if 'time' in df_js.columns else 'index'
    if time_col in df_js.columns:
        df_js['time'] = df_js[time_col].apply(
            lambda x: int(x.timestamp()) if isinstance(x, pd.Timestamp) else int(x // 1000 if x > 1e12 else x)
        )
    
    # [2] 기본 데이터 (Candles & Volumes)
    candles = df_js[['time', 'open', 'high', 'low', 'close']].to_dict(orient='records')
    volumes = df_js[['time', 'volume']].rename(columns={'volume': 'value'}).to_dict(orient='records')
    
    # [3] 지표 데이터 (Indicators - DB 스키마 및 표준 변수명 기준)
    indicator_names = [
        # 1. 일목균형표 상세
        "tenkan", "kijun", "senkouA", "senkouB", "cloudTop", "cloudBottom", 
        # 2. Whale 세력선 (핵심 진입 지표)
        "sma224", "vwma224", "volConfirm",
        # 3. 기술적 보조지표
        "rsi", "mfi", "macdLine", "signalLine", "bbUpper", "bbMid", "bbLower",
        # 4. SMC 가격 레벨 (시뮬레이션 SL 및 50% 익절 기준선)
        "swingHighLevel", "swingLowLevel", "equilibrium",
        # 5. 매매 조건 및 확정 시그널
        "longCondition", "shortCondition", "longSig", "shortSig",
        # 6. 역추세 및 최종 마커
        "bearishDiv", "bullishDiv", "extremeTop", "extremeBottom", "TOP", "BOTTOM",
        # 7. SMC 구조 분석
        "fvgBullish", "fvgBearish", "swingBOS", "swingCHOCH", "internalBOS", "internalCHOCH"
    ]
    
    indicators = {}
    for col in indicator_names:
        if col in df_js.columns:
            # 값이 존재하는 데이터만 추출 (차트 선 끊김 방지하려면 필요시 dropna 조절)
            valid_data = df_js[['time', col]].dropna()
            indicators[col] = valid_data.rename(columns={col: 'value'}).to_dict(orient='records')
        else:
            indicators[col] = []
            
    # [4] 마커 생성 로직 (시뮬전략.txt 및 README.md 기준)
    markers = []
    for _, row in df_js.iterrows():
        t = row['time']
        
        # A. 메인 매매 진입 신호 (화살표)
        if row.get('longSig') == 1:
            markers.append({"time": t, "position": "belowBar", "color": "#26a69a", "shape": "arrowUp", "text": "LONG"})
        elif row.get('shortSig') == 1:
            markers.append({"time": t, "position": "aboveBar", "color": "#ef5350", "shape": "arrowDown", "text": "SHORT"})
            
        # B. 익절 및 역추세 신호 (시뮬전략 기준: TOP=빨간다이아, BOTTOM=초록다이아)
        if row.get('TOP') == 1:
            # 롱 익절 구간 (빨간다이아) 
            markers.append({"time": t, "position": "aboveBar", "color": "#FF5252", "shape": "diamond", "text": "TP(L)"})
        elif row.get('BOTTOM') == 1: 
            # 숏 익절 구간 (초록다이아) 
            markers.append({"time": t, "position": "belowBar", "color": "#4CAF50", "shape": "diamond", "text": "TP(S)"})

        # C. SMC 구조 변화 (BOS/CHoCH - 텍스트 마킹)
        if row.get('swingBOS') == 1:
            markers.append({"time": t, "position": "inBar", "color": "#878b94", "shape": "square", "text": "BOS"})
        elif row.get('swingCHOCH') == 1:
            markers.append({"time": t, "position": "inBar", "color": "#d1d4dc", "shape": "square", "text": "CHOCH"})

    return {
        "candles": candles, 
        "volumes": volumes,
        "indicators": indicators, 
        "markers": markers
    }