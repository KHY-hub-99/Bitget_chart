import sys
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pyprojroot import here
root = str(here())
sys.path.append(root)
from backend.data_process.data_load import CryptoDataFeed
from backend.data_process.trans_pine_chart import apply_master_strategy

def plot_master_with_plotly(df, symbol="BTC/USDT"):
    # 1. 데이터 복사 및 시간 정렬 (Plotly는 datetime을 사랑합니다)
    df_plot = df.copy()
    if 'time' not in df_plot.columns:
        df_plot = df_plot.reset_index()
    df_plot['time'] = pd.to_datetime(df_plot['time'])
    df_plot = df_plot.sort_values('time')

    # 2. 서브플롯 생성 (Row 1: 캔들차트 + 지표 + 신호, Row 2: 거래량)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, 
                        row_heights=[0.75, 0.25])
    
    # --- [A. 메인 캔들 차트 (Row 1)] ---
    fig.add_trace(go.Candlestick(
        x=df_plot['time'], open=df_plot['open'], high=df_plot['high'],
        low=df_plot['low'], close=df_plot['close'], name='Candle'
    ), row=1, col=1)
    
    # Senkou B를 먼저 그리고, Senkou A를 그린 뒤 그 사이를 채웁니다.
    fig.add_trace(go.Scatter(x=df_plot['time'], y=df_plot['senkou_b'], 
                            line=dict(color='rgba(239, 83, 80, 0.2)', width=1),
                            name='Cloud B', showlegend=False), row=1, col=1)
    
    # fill='tonexty' 옵션으로 이전 Trace(Senkou B)까지 색을 채움
    fig.add_trace(go.Scatter(x=df_plot['time'], y=df_plot['senkou_a'], 
                            line=dict(color='rgba(38, 166, 154, 0.2)', width=1),
                            fill='tonexty', 
                            fillcolor='rgba(100, 100, 100, 0.08)', # 구름대 색상
                            name='Ichimoku Cloud'), row=1, col=1)
    
    # Pine Script와 같이 빨간색 두꺼운 선으로 구현
    fig.add_trace(go.Scatter(x=df_plot['time'], y=df_plot['kijun'], 
                            line=dict(color='red', width=2), name='기준선'), row=1, col=1)
    
    # MASTER LONG (초록색 위 삼각형 + 텍스트)
    long_hits = df_plot[df_plot['MASTER_LONG'] == True]
    fig.add_trace(go.Scatter(x=long_hits['time'], y=long_hits['low'] * 0.98,
                            mode='markers+text', text="MASTER\nLONG", textposition="bottom center",
                            marker=dict(symbol='triangle-up', size=12, color='green'),
                            name='MASTER LONG'), row=1, col=1)
    
    # MASTER SHORT (빨간색 아래 삼각형 + 텍스트)
    short_hits = df_plot[df_plot['MASTER_SHORT'] == True]
    fig.add_trace(go.Scatter(x=short_hits['time'], y=short_hits['high'] * 1.02,
                            mode='markers+text', text="MASTER\nSHORT", textposition="top center",
                            marker=dict(symbol='triangle-down', size=12, color='red'),
                            name='MASTER SHORT'), row=1, col=1)
    
    # TOP DETECTED (빨간 다이아몬드)
    top_hits = df_plot[df_plot['TOP_DETECTED'] == True]
    fig.add_trace(go.Scatter(x=top_hits['time'], y=top_hits['high'] * 1.01,
                            mode='markers', marker=dict(symbol='diamond', size=8, color='red'),
                            name='TOP DETECTED'), row=1, col=1)
    
    # BOTTOM DETECTED (초록 다이아몬드)
    bottom_hits = df_plot[df_plot['BOTTOM_DETECTED'] == True]
    fig.add_trace(go.Scatter(x=bottom_hits['time'], y=bottom_hits['low'] * 0.99,
                            mode='markers', marker=dict(symbol='diamond', size=8, color='green'),
                            name='BOTTOM DETECTED'), row=1, col=1)
    
    # --- [E. 거래량 (Row 2)] ---
    fig.add_trace(go.Bar(x=df_plot['time'], y=df_plot['volume'], name='Volume', 
                        marker_color='rgba(100, 100, 100, 0.5)'), row=2, col=1)
    
    fig.update_layout(
        title=f"{symbol} Master Strategy Analysis (Plotly Ver.)",
        template='plotly_dark',
        xaxis_rangeslider_visible=False,
        height=950,
        showlegend=True,
        xaxis=dict(showgrid=False), # 메인 차트 그리드 제거
        yaxis=dict(showgrid=True, gridcolor='rgba(255, 255, 255, 0.1)'), # 가격 그리드 추가
        plot_bgcolor='black', # 차트 배경색을 완전한 검은색으로
        paper_bgcolor='black'
    )
    
    # X축 마진 조절
    fig.update_xaxes(rangemode='nonnegative')

    fig.show()
    
# 단독 파일 테스트
if __name__ == "__main__":
    print("==============================================")
    print("Plotly 차트 시각화 모듈 실행")
    print("==============================================\n")

    # 1. 데이터 가져오기 (5분봉으로 5일치 테스트)
    feed = CryptoDataFeed(method="swap", symbol="BTC/USDT:USDT", timeframe="5m")
    feed.initialize_data(days=90)
    
    # 2. 전략 및 지표 연산 (이 함수 내에서 kijun, senkou_a, TOP_DETECTED 등이 생성되어야 함)
    print("\n전략 지표 계산 중...")
    result_df = apply_master_strategy(feed.df)
    
    # 3. 차트 출력
    print("\nPlotly 차트 렌더링 중...")
    plot_master_with_plotly(result_df)