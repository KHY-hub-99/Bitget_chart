import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta, timezone

class CryptoDataFeed:
    """
    초기 대규모 데이터 수집과 실시간 업데이트를 처리하는 데이터 매니저.
    데이터 개수 제한 없이 모든 수집된 데이터를 유지합니다.
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
        """프로그램 최초 실행 시 N일치 데이터를 수집합니다."""
        print(f"[{self.symbol}] 과거 {days}일치 데이터 수집 시작...")
        
        # UTC 기준으로 시작 시간 설정 (시간대 오류 방지)
        now_utc = datetime.now(timezone.utc)
        since = int((now_utc - timedelta(days=days)).timestamp() * 1000)
        all_ohlcv = []

        while True:
            try:
                ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, since=since, limit=1000)
                if not ohlcv: break
                
                all_ohlcv.extend(ohlcv)
                since = ohlcv[-1][0] + 1
                
                print(f"수집 중... 현재 {len(all_ohlcv)}개 캔들 확보", end='\r')
                time.sleep(0.1)

                # 현재 시간 근처까지 가져왔으면 루프 종료
                if ohlcv[-1][0] >= int(time.time() * 1000) - 300000: 
                    break
            except Exception as e:
                print(f"\n데이터 수집 에러: {e}. 5초 뒤 재시도합니다.")
                time.sleep(5)

        # 데이터프레임 생성 및 'time' 컬럼 지정
        df = pd.DataFrame(all_ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
        
        # 시간 변환 및 인덱스 설정
        df['time'] = pd.to_datetime(df['time'], unit='ms')
        df.set_index('time', inplace=True)
        
        # 중복 제거 및 숫자형 변환
        df = df[~df.index.duplicated(keep='last')]
        cols = ['open', 'high', 'low', 'close', 'volume']
        df[cols] = df[cols].apply(pd.to_numeric)

        self.df = df
        print(f"\n[{self.symbol}] {len(self.df)}개의 데이터 로드 완료.")

    def update_data(self):
        """최신 캔들을 가져와서 기존 데이터에 제한 없이 추가합니다."""
        try:
            # 안전하게 최신 5개 캔들을 가져와 업데이트
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=5)
            
            recent_df = pd.DataFrame(ohlcv, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            recent_df['time'] = pd.to_datetime(recent_df['time'], unit='ms')
            recent_df.set_index('time', inplace=True)
            
            cols = ['open', 'high', 'low', 'close', 'volume']
            recent_df[cols] = recent_df[cols].apply(pd.to_numeric)

            # 효율적인 데이터 통합: concat 후 중복된 인덱스(시간)는 최신 값으로 유지
            self.df = pd.concat([self.df, recent_df])
            self.df = self.df[~self.df.index.duplicated(keep='last')]
                
            return self.df
            
        except Exception as e:
            print(f"실시간 업데이트 에러: {e}")
            return self.df

    def get_chart_df(self):
        """차트 라이브러리 및 프론트엔드 전달을 위해 'time'을 컬럼으로 포함해 반환합니다."""
        return self.df.reset_index()