# 📈 Crypto Trading Master Dashboard

`ccxt`를 활용한 실시간 데이터 수집과 `pandas-ta` 기반의 **BTC 마스터 전략**을 시각화하는 전문 트레이딩 대시보드 프로젝트입니다.

## 🏗️ 시스템 아키텍처 (Architecture)

1.  **Data Engine**: Bitget 거래소로부터 90일치 이상의 과거 데이터를 로드하고 실시간 캔들을 업데이트합니다.
2.  **Strategy Engine**: 일목균형표, 볼린저 밴드, MACD, RSI, MFI를 조합하여 역추세(Divergence) 및 추세(Cloud Breakout) 신호를 생성합니다.
3.  **Backend (FastAPI)**: 계산된 데이터를 JSON 형태로 직렬화하여 REST API 및 WebSocket으로 전달합니다.
4.  **Frontend (React + TS)**: `lightweight-charts`를 사용하여 고성능 차트를 렌더링하고 지표와 신호를 마킹합니다.

---

## 📂 폴더 구조 (Folder Structure)

```text
Bitget_chart/
├── backend/                        # [Python] FastAPI 서버
│   ├── main.py                     # API 서버 엔트리포인트 & 실시간 로직
│   ├── data_process/               # 핵심 연산 로직
│   │   ├── __init__.py
│   │   ├── load_data.py            # 데이터 수집 (Bitget)
│   │   └── pine_data.py            # 전략 계산 (Master Strategy)
│   ├── services/                   # 데이터 가공
│   │   ├── __init__.py
│   │   └── chart_service.py        # DF -> Chart JSON 변환
│   ├── requirements.txt            # 필수 패키지 목록
│   ├── .env                        # API Key 등 환경 변수
│   └── Dockerfile                  # 백엔드 컨테이너 설정
│
├── frontend/                       # [React] Vite + TS
│   ├── src/
│   │   ├── main.tsx                # 엔트리 포인트
│   │   ├── App.tsx                 # 메인 화면 및 데이터 흐름 제어
│   │   ├── TradingChart.tsx        # [Core] Lightweight Charts 엔진
│   │   └── api.ts                  # 백엔드 Axios 통신 정의
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
    └── Dockerfile                  # 프론트엔드 컨테이너 설정
│
├── .gitignore                      # Git 제외 설정
├── README.md                       # 프로젝트 문서
└── docker-compose.yml              # 백엔드/프론트엔드 컨테이너화 관리
```
