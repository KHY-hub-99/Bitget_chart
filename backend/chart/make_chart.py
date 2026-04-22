import sys
import pandas as pd
from lightweight_charts import Chart
from pyprojroot import here
root = str(here())
sys.path.append(root)
from backend.data_process.data_load import CryptoDataFeed
from backend.data_process.trans_pine_chart import apply_master_strategy

def plot_sophisticated_chart(df, symbol="BTC/USDT"):
    # 1. 차트 초기화 (멀티 레이아웃 및 워터마크 설정)
    chart = Chart(toolbox=True, width=1200, height=900)
    chart.watermark(symbol, color='rgba(180, 180, 200, 0.3)')
    chart.legend(visible=True, font_size=13, percent=True)
    
    # 2. 데이터 시간축 전처리
    df_lw = df.reset_index().rename(columns={'timestamp': 'time'})

    # 3. 메인 캔들스틱 차트 설정
    chart.set(df_lw)

    # 4. 일목균형표 구름대 (선으로 정교하게 표현)
    line_a = chart.create_line(name='Ichimoku A', color='rgba(38, 166, 154, 0.6)', width=1)
    line_b = chart.create_line(name='Ichimoku B', color='rgba(239, 83, 80, 0.6)', width=1)
    
    line_a.set(df_lw[['time', 'senkou_a']].rename(columns={'senkou_a': 'Ichimoku A'}))
    line_b.set(df_lw[['time', 'senkou_b']].rename(columns={'senkou_b': 'Ichimoku B'}))

    bb_upper = chart.create_line(name='BB Upper', color='rgba(33, 150, 243, 0.5)', width=1)
    bb_lower = chart.create_line(name='BB Lower', color='rgba(33, 150, 243, 0.5)', width=1)
    
    bb_upper.set(df_lw[['time', 'BB_upper']].rename(columns={'BB_upper': 'BB Upper'}))
    bb_lower.set(df_lw[['time', 'BB_lower']].rename(columns={'BB_lower': 'BB Lower'}))

    rsi_chart = chart.create_line(name='RSI', color='#9C27B0', width=2)
    rsi_chart.set(df_lw[['time', 'RSI_14']].rename(columns={'RSI_14': 'RSI'}))

    for _, row in df_lw.iterrows():
        if row['MASTER_LONG']:
            chart.marker(
                time=row['time'], position='belowBar', 
                color='#26A69A', shape='arrowUp', text='MASTER LONG'
            )
        elif row['MASTER_SHORT']:
            chart.marker(
                time=row['time'], position='aboveBar', 
                color='#EF5350', shape='arrowDown', text='MASTER SHORT'
            )
        elif row['BOTTOM_DETECTED']:
            chart.marker(
                time=row['time'], position='belowBar', 
                color='#4CAF50', shape='circle', text='BOTTOM'
            )
        elif row['TOP_DETECTED']:
            chart.marker(
                time=row['time'], position='aboveBar', 
                color='#F44336', shape='circle', text='TOP'
            )

    # 차트 실행
    print(f"{symbol} 정밀 분석 차트 렌더링 완료.")
    chart.show(block=True)

if __name__ == "__main__":
    print("==============================================")
    print("BTC 마스터 전략 시각화 모듈 실행 ")
    print("==============================================\n")

    # 1. 데이터 가져오기 (테스트용으로 1000일치 로드)
    feed = CryptoDataFeed(method="swap", symbol="BTC/USDT:USDT", timeframe="1d")
    feed.initialize_data(days=1000)
    raw_df = feed.df

    # 2. 전략 및 지표 연산
    result_df = apply_master_strategy(feed.df)
    
    # 3. 차트 출력
    plot_sophisticated_chart(result_df)