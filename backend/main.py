import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pyprojroot import here
# 루트 설정
root = here()
sys.path.append(root)
from backend.data_process.load_data import CryptoDataFeed
from backend.data_process.pine_data import apply_master_strategy

app = FastAPI()

# 프론트엔드(HTML)가 백엔드에 접근할 수 있도록 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 실제 배포 시에는 특정 주소만 허용
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/chart")
async def get_chart():
    feed = CryptoDataFeed()
    feed.initialize_data(days=10)
    result_df = apply_master_strategy(feed.df)
    
    # JS 차트가 읽을 수 있도록 Unix Timestamp(초 단위)로 변환
    chart_data = result_df.reset_index()
    chart_data['time'] = chart_data['time'].apply(lambda x: int(x.timestamp()))
    
    return chart_data.to_dict(orient='records')