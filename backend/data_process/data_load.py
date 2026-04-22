import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta

class CryptoDataFeed:
    """
    초기 대규모 데이터 수집과 실시간 업데이트를 처리하는 데이터 매니저
    컬럼명을 처음부터 'time'으로 설정하여 차트 라이브러리와의 호환성을 높임
    """
    def __init__(self, method="swap", symbol="BTC/USDT:USDT", timeframe="5m"):
        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange = ccxt.bitget({
            'options': {'defaultType': method},
            'enableRateLimit': True
        })
        self.df = pd.DataFrame()
    
    def initialize_data(self, days=90):
        """프로그램 최초 실행 시 N일치 데이터를 긁어오는 함수"""
        print(f"[{self.symbol}] 과거 {days}일치 데이터 수집 시작...")
        
        # 시작 시간 설정
        since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        all_ohlcv = []

        while True:
            try:
                # 컬럼명을 애초에 'time'으로 관리하기 위해 순서 기억: 0:time, 1:open...
                ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, since=since, limit=1000)
                if not ohlcv: break
                
                all_ohlcv.extend(ohlcv)
                since = ohlcv[-1][0] + 1
                
                print(f"수집 중... 현재 {len(all_ohlcv)}개 캔들 확보", end='\r')
                time.sleep(0.1)

                # 현재 시간 근처까지 가져왔으면 종료
                if ohlcv[-1][0] >= int(time.time() * 1000) - 300000: 
                    break
            except Exception as e:
                print(f"\n데이터 수집 에러: {e}. 5초 뒤 재시도합니다.")
                time.sleep(5)

        # 1. 데이터프레임 생성 시 'time'으로 컬럼명 지정
        df = pd.DataFrame(all_ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        
        # 2. 시간 변환 및 인덱스 설정
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        df.set_index('time', inplace=True) # 업데이트 편의를 위해 인덱스로 사용
        
        # 중복 제거 및 숫자형 변환
        df = df[~df.index.duplicated(keep='last')]
        cols = ['open', 'high', 'low', 'close', 'volume']
        df[cols] = df[cols].apply(pd.to_numeric)

        self.df = df
        print(f"\n[{self.symbol}] {len(self.df)}개의 데이터 로드 완료.")

    def update_data(self):
        """실시간 최신 캔들을 가져와서 기존 데이터에 덧붙이는 함수"""
        try:
            # 최신 캔들 2개 수집 (진행 중인 캔들 포함)
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=2)
            
            # 컬럼명을 'time'으로 생성
            recent_df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            recent_df['time'] = pd.to_datetime(recent_df['time'], unit='ms')
            recent_df.set_index('time', inplace=True)
            
            cols = ['open', 'high', 'low', 'close', 'volume']
            recent_df[cols] = recent_df[cols].apply(pd.to_numeric)

            # 기존 데이터(self.df)에 인덱스(time) 기준으로 덮어쓰기
            for idx, row in recent_df.iterrows():
                self.df.loc[idx] = row
                
            return self.df # 'time'이 인덱스인 상태로 반환됨
            
        except Exception as e:
            print(f"실시간 업데이트 에러: {e}")
            return self.df

    def get_chart_df(self):
        """차트 라이브러리에 전달하기 위해 'time'을 컬럼으로 뺀 데이터프레임 반환"""
        return self.df.reset_index()