import sys
from fastapi import APIRouter, Query
from pyprojroot import here
# 루트 설정
root = str(here())
sys.path.append(root)
from backend.data_process.load_data import CryptoDataFeed
from backend.data_process.pine_data import apply_master_strategy
import pandas as pd

# API 라우터 설정
router = APIRouter(prefix="/api")

@router.get("/chart")
async def get_chart_data(
    symbol: str = Query("BTC/USDT:USDT", description="조회할 심볼"),
    timeframe: str = Query("1d", description="타임프레임 (예: 1m, 5m, 1h, 1d)"),
    days: int = Query(90, description="과거 데이터 수집 기간(일)")
):
    """
    프론트엔드(Lightweight Charts)에서 필요한 캔들, 지표, 신호 데이터를 반환합니다.
    """
    # 1. 데이터 수집
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    feed.initialize_data(days=days)
    
    # 2. 전략 및 지표 연산
    result_df = apply_master_strategy(feed.df)
    
    # === [핵심 수정 구간] ===
    # 지표 연산으로 인해 발생한 앞부분의 결측치(NaN) 캔들 뭉치를 깔끔하게 버림
    result_df = result_df.dropna()
    
    # 3. 프론트엔드용 데이터 포맷 변환
    chart_df = result_df.reset_index()
    chart_df['time'] = chart_df['time'].apply(lambda x: int(x.timestamp()))
    
    # 혹시 모를 중간 결측치 방어를 위해 전체를 object로 캐스팅한 뒤 확실하게 None으로 변환
    chart_df = chart_df.astype(object).where(pd.notnull(chart_df), None)
    # =========================

    # 레코드(리스트 형태의 딕셔너리) 형식으로 반환
    return chart_df.to_dict(orient='records')