import pandas as pd
from pathlib import Path
from datetime import datetime

# 사용자님이 확인하신 경로로 임포트
from pynecore.core.script_runner import ScriptRunner 
from pynecore.core.syminfo import SymInfo
from pynecore.core.ohlcv_file import OHLCV

def process_binance_data(df, script_file, symbol, timeframe):
    # 심볼 정보 (바이낸스 기준)
    si = SymInfo(
        ticker=symbol,
        period=timeframe,
        timezone="UTC",
        currency="USDT",
        prefix="BINANCE",               # 거래소
        description=f"{symbol}/USDT",   # 설명
        type="crypto",                  # 자산 타입
        mintick=0.01,                   # 최소 가격 변동폭
        pricescale=100,                 # 가격 소수점 배수 (0.01이면 100)
        pointvalue=1,                   # 포인트 가치 (보통 1)
        opening_hours="24x7",           # 영업 시간 텍스트
        session_starts=[0],             # 세션 시작 (자정부터의 초 단위: 0)
        session_ends=[86400]            # 세션 종료 (24시간 = 86400초)
    )

    # DataFrame -> PyneCore OHLCV 객체 리스트 변환
    ohlcv_list = [
    OHLCV(
        int(row['timestamp'] / 1000), # 1. timestamp
        float(row['open']),           # 2. open
        float(row['high']),           # 3. high
        float(row['low']),            # 4. low
        float(row['close']),          # 5. close
        float(row['volume']),         # 6. volume
        {}                            # 7. extra_fields
    ) for _, row in df.iterrows()
]

    # ScriptRunner 생성 및 실행
    runner = ScriptRunner(
        script_path=Path(script_file),
        ohlcv_iter=ohlcv_list,
        syminfo=si
    )

    results = []
    # 한 바(Bar)씩 계산하며 지표 수집
    for candle, plot_data in runner.run_iter():
        combined = {
            # 생성할 때 'timestamp'라고 이름 붙였으므로 꺼낼 때도 'timestamp'!
            "time": datetime.fromtimestamp(candle.timestamp), 
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            **plot_data
        }
        results.append(combined)

    return pd.DataFrame(results)