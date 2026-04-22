import sys
from fastapi import APIRouter, Query
from pyprojroot import here
# 루트 설정
root = here()
sys.path.append(root)
from backend.data_process.load_data import CryptoDataFeed
from backend.data_process.pine_data import apply_master_strategy
import pandas as pd

# API 라우터 설정
router = APIRouter(prefix="/api")

@router.get("/chart")
async def get_chart_data(
    symbol: str = Query("BTC/USDT:USDT", description="조회할 심볼"),
    timeframe: str = Query("5m", description="타임프레임 (예: 1m, 5m, 1h, 1d)"),
    days: int = Query(10, description="과거 데이터 수집 기간(일)")
):
    """
    프론트엔드(Lightweight Charts)에서 필요한 캔들, 지표, 신호 데이터를 반환합니다.
    """
    # 1. 데이터 수집 (CryptoDataFeed 사용)
    feed = CryptoDataFeed(symbol=symbol, timeframe=timeframe)
    feed.initialize_data(days=days)
    
    # 2. 전략 및 지표 연산 (apply_master_strategy 사용)
    # feed.df에는 수집된 원본 OHLCV 데이터가 들어있습니다.
    result_df = apply_master_strategy(feed.df)
    
    # 3. 프론트엔드용 데이터 포맷 변환
    # Lightweight Charts JS는 'time' 컬럼을 Unix Timestamp(초 단위 숫자)로 인식합니다.
    chart_df = result_df.reset_index()
    chart_df['time'] = chart_df['time'].apply(lambda x: int(x.timestamp()))
    
    # JSON 변환 시 에러를 방지하기 위해 NaN 값을 None으로 처리 (JS에서는 null이 됨)
    chart_df = chart_df.where(pd.notnull(chart_df), None)
    
    # 레코드(리스트 형태의 딕셔너리) 형식으로 반환
    return chart_df.to_dict(orient='records')