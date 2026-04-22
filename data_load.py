import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta

class CryptoDataFeed:
    """
    초기 대규모 데이터 수집과 실시간 업데이트를 한 번에 처리하는 데이터 매니저
    """
    def __init__(self, method="swap", symbol="BTC/USDT:USDT", timeframe="5m"):
        self.symbol = symbol
        self.timeframe = timeframe
        # 객체 생성 (단 한 번만 실행됨)
        self.exchange = ccxt.bitget({
            'options': {'defaultType': method},
            'enableRateLimit': True
        })
        # 전체 데이터를 계속 품고 있을 변수
        self.df = pd.DataFrame()
    
    def initialize_data(self, days=90):
        """프로그램 최초 실행 시 N일치 데이터를 긁어오는 함수"""
        print(f"[{self.symbol}] 과거 {days}일치 데이터 수집 시작... (최초 1회)")
        since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        all_ohlcv = []

        while True:
            try:
                ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, since=since, limit=1000)
                if not ohlcv: break
                
                all_ohlcv.extend(ohlcv)
                since = ohlcv[-1][0] + 1 # 마지막 캔들 다음 시간부터 다시 요청
                
                print(f"수집 중... 현재 {len(all_ohlcv)}개 캔들 확보", end='\r')
                time.sleep(0.1)

                # 최신 시간까지 다 가져왔으면 루프 종료
                if ohlcv[-1][0] >= int(time.time() * 1000) - 300000: 
                    break
            except Exception as e:
                print(f"\n데이터 수집 에러: {e}. 5초 뒤 재시도합니다.")
                time.sleep(5)

        # 수집한 데이터를 데이터프레임으로 변환 후 저장
        df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # 중복 제거 및 숫자형 변환
        df = df[~df.index.duplicated(keep='last')]
        cols = ['open', 'high', 'low', 'close', 'volume']
        df[cols] = df[cols].apply(pd.to_numeric)

        self.df = df

    def update_data(self):
        """무한 루프 안에서 최신 캔들 10개만 가져와서 기존 데이터에 덧붙이는 함수"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=2)
            recent_df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            recent_df['timestamp'] = pd.to_datetime(recent_df['timestamp'], unit='ms')
            recent_df.set_index('timestamp', inplace=True)
            
            cols = ['open', 'high', 'low', 'close', 'volume']
            recent_df[cols] = recent_df[cols].apply(pd.to_numeric)

            # 기존 데이터(self.df)에 최신 캔들을 인덱스 기준으로 덮어쓰기/추가
            for idx, row in recent_df.iterrows():
                self.df.loc[idx] = row
                
            return self.df # 항상 최신화된 전체 3개월치 데이터가 반환됨
            
        except Exception as e:
            print(f"실시간 업데이트 에러: {e}")
            return self.df