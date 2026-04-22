# 1. 데이터 가져오기
import pandas as pd
from data_load import CryptoDataFeed
from trans_pine_chart import apply_master_strategy # C 대신 실제 만든 함수명으로 수정

# 터미널에서 표가 잘리지 않게 출력하기 위한 pandas 설정
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

print("==============================================")
print(" 🚀 BTC 마스터 전략 시스템 테스트 (시각화 전) ")
print("==============================================\n")

# 1. 데이터 매니저 초기화 및 데이터 수집
print("1️⃣ 거래소 데이터를 불러오는 중입니다...")
feed = CryptoDataFeed()

# 빠른 테스트를 위해 10일치 데이터만 불러옵니다. (필요시 90으로 변경)
feed.initialize_data(days=10)
raw_df = feed.df

if raw_df.empty:
    print("\n🚨 [오류] 데이터를 불러오지 못했습니다. 네트워크 상태를 확인하세요.")
else:
    print(f"\n✅ 원본 데이터 {len(raw_df)}개 수집 완료! 전략 연산을 시작합니다...")
    
    # 2. 마스터 전략(지표 및 신호) 적용
    try:
        result_df = apply_master_strategy(raw_df)
        print("✅ 전략 연산 및 지표 결합 완료!\n")
        
        # 3. 결과 확인 (핵심 데이터만 추출해서 출력)
        print("2️⃣ 최근 5개의 캔들 데이터 및 신호 상태입니다:")
        
        # 보기 편하게 종가와 우리가 만든 4개의 신호 컬럼만 골라서 출력합니다.
        check_columns = ['close', 'TOP_DETECTED', 'BOTTOM_DETECTED', 'MASTER_LONG', 'MASTER_SHORT']
        print(result_df[check_columns].tail())
        
        # 4. (보너스) 신호 발생 통계 확인
        # 10일치 데이터 안에서 실제로 신호가 몇 번이나 터졌는지 검증합니다.
        total_long = result_df['MASTER_LONG'].sum()
        total_short = result_df['MASTER_SHORT'].sum()
        total_top = result_df['TOP_DETECTED'].sum()
        total_bottom = result_df['BOTTOM_DETECTED'].sum()
        
        print("\n3️⃣ [테스트 기간 신호 발생 통계]")
        print(f" - 🚀 MASTER LONG (상승 돌파): {total_long}회")
        print(f" - 🩸 MASTER SHORT (하락 이탈): {total_short}회")
        print(f" - 🔴 TOP DETECTED (고점 징후): {total_top}회")
        print(f" - 🟢 BOTTOM DETECTED (저점 징후): {total_bottom}회")
        print("\n모든 시스템이 정상적으로 작동하고 있습니다! 시각화 단계로 넘어가셔도 좋습니다. 🎉")

    except Exception as e:
        print(f"\n🚨 [오류] 전략 연산 중 에러가 발생했습니다: {e}")