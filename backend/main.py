import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pyprojroot import here
# 루트 설정
root = str(here())
sys.path.append(root)
from backend.data_process.load_data import CryptoDataFeed
from backend.data_process.pine_data import apply_master_strategy
from backend.api.chart_api import router as chart_router

app = FastAPI(title="Master Strategy API")

# 프론트엔드(HTML/JS)에서 API에 접근할 수 있도록 CORS 설정 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 로컬 테스트 시에는 모두 허용, 배포 시 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 차트 API 라우터 등록
app.include_router(chart_router)

@app.get("/")
async def root():
    return {"message": "Bitget Master Strategy Backend is running!"}

if __name__ == "__main__":
    import uvicorn
    # 서버 실행: http://localhost:8000
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)