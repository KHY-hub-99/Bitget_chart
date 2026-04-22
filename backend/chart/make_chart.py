import sys
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from pyprojroot import here
root = str(here())
sys.path.append(root)
from backend.data_process.data_load import CryptoDataFeed
from backend.data_process.trans_pine_chart import apply_master_strategy

def plot_tradingview_chart(df, symbol="BTC/USDT:USDT"):
    """
    Plotly를 이용한 트레이딩뷰 스타일 인터랙티브 차트 생성기
    """
    print(f"\n[{symbol}] 차트 렌더링을 준비 중입니다...")

    # 1. 화면 분할 (위: 캔들 차트 80%, 아래: 거래량 20%)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.03, row_heights=[0.8, 0.2])
    
    # 2. 메인 캔들스틱 차트 (암호화폐 표준: 상승-초록, 하락-빨강)
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['open'], high=df['high'], low=df['low'], close=df['close'],
        increasing_line_color='#26A69A', decreasing_line_color='#EF5350', 
        name='Price'
    ), row=1, col=1)

    # 3. 일목균형표 구름대 (Senkou A & B)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['senkou_a'], 
        line=dict(color='rgba(0,0,0,0)'), showlegend=False, hoverinfo='skip'
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=df.index, y=df['senkou_b'], 
        fill='tonexty', fillcolor='rgba(239, 83, 80, 0.15)', 
        line=dict(color='rgba(0,0,0,0)'), name='Cloud'
    ), row=1, col=1)

    # 4. 거래량 바 차트
    vol_colors = ['#26A69A' if row['close'] >= row['open'] else '#EF5350' for idx, row in df.iterrows()]
    fig.add_trace(go.Bar(
        x=df.index, y=df['volume'], marker_color=vol_colors, name='Volume'
    ), row=2, col=1)

    # 5. 매매 신호 마커 추가
    # MASTER LONG (초록색 위쪽 삼각형)
    longs = df[df['MASTER_LONG']]
    fig.add_trace(go.Scatter(
        x=longs.index, y=longs['low'] * 0.995, mode='markers+text',
        marker=dict(symbol='triangle-up', color='#26A69A', size=16),
        text="MASTER<br>LONG", textposition="bottom center", 
        textfont=dict(color='#2196F3', size=10), name='MASTER LONG'
    ), row=1, col=1)

    # MASTER SHORT (빨간색 아래쪽 삼각형)
    shorts = df[df['MASTER_SHORT']]
    fig.add_trace(go.Scatter(
        x=shorts.index, y=shorts['high'] * 1.005, mode='markers+text',
        marker=dict(symbol='triangle-down', color='#EF5350', size=16),
        text="MASTER<br>SHORT", textposition="top center", 
        textfont=dict(color='#2196F3', size=10), name='MASTER SHORT'
    ), row=1, col=1)

    # BOTTOM DETECTED (초록색 다이아몬드)
    bottoms = df[df['BOTTOM_DETECTED']]
    fig.add_trace(go.Scatter(
        x=bottoms.index, y=bottoms['low'] * 0.998, mode='markers',
        marker=dict(symbol='diamond', color='#4CAF50', size=10), name='BOTTOM (Diamond)'
    ), row=1, col=1)

    # TOP DETECTED (빨간색 다이아몬드)
    tops = df[df['TOP_DETECTED']]
    fig.add_trace(go.Scatter(
        x=tops.index, y=tops['high'] * 1.002, mode='markers',
        marker=dict(symbol='diamond', color='#F44336', size=10), name='TOP (Diamond)'
    ), row=1, col=1)

    # 6. 차트 레이아웃 디자인 다듬기
    fig.update_layout(
        title=f"{symbol} Master Strategy Chart (Interactive)",
        yaxis_title="Price (USDT)",
        xaxis_rangeslider_visible=False, # 하단 스크롤바 숨김
        template='plotly_white',         # 밝은 배경
        height=850,
        hovermode='x unified',           # 십자선 정보 표시
        showlegend=True
    )
    
    # 그리드 연하게 설정
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(200,200,200,0.3)')
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(200,200,200,0.3)')

    # 브라우저에 띄우기
    print("웹 브라우저에서 차트를 확인하세요!")
    fig.show()

if __name__ == "__main__":
    print("==============================================")
    print(" 📈 BTC 마스터 전략 시각화 모듈 실행 ")
    print("==============================================\n")

    # 1. 데이터 가져오기 (테스트용으로 10일치만 빠르게 로드)
    feed = CryptoDataFeed(method="swap", symbol="BTC/USDT:USDT", timeframe="1d")
    feed.initialize_data(days=1000)
    raw_df = feed.df

    if raw_df.empty:
        print("데이터를 불러오지 못했습니다.")
    else:
        # 2. 전략 연산 적용
        print("전략 지표 및 신호 연산 중...")
        result_df = apply_master_strategy(raw_df)
        
        # 3. 차트 출력 (브라우저 버벅임을 방지하기 위해 최근 500개 캔들만 출력)
        # 더 많은 과거를 보고 싶다면 500을 1000이나 2000으로 늘리시면 됩니다.
        plot_tradingview_chart(result_df, symbol="BTC/USDT:USDT")