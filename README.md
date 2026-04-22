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

---

## 🗺️ 프론트엔드 개발 로드맵 (Roadmap)

### ✅ [Done] Step 0: 환경 구축 및 통신 테스트

- [x] Vite + React + TS 환경 세팅
- [x] Axios를 이용한 백엔드 API 데이터 수신 확인 (`index.html`, `main.tsx`, `api.ts` 연결)

### 🚀 [Current] Step 1: 정적 차트 렌더링

- [ ] `lightweight-charts` 엔진 초기화
- [ ] 캔들스틱(Candlestick) 및 거래량(Volume) 차트 구현
- [ ] 타임스케일(Time Scale) 및 다크 테마 적용

### 🛠️ Step 2: 지표 및 매매 신호 레이어 추가

- [ ] 일목균형표(기준선) 및 볼린저 밴드 라인 렌더링
- [ ] `MASTER_LONG/SHORT` 매매 신호 마커(화살표) 표시
- [ ] 가격/지표 툴팁(Tooltip) 구현

### 📡 Step 3: 실시간 웹소켓(WebSocket) 연동

- [ ] 백엔드 웹소켓 엔드포인트 연결
- [ ] 실시간 시세 데이터 수신 및 차트 업데이트(`update()` 메서드)
- [ ] 실시간 신호 발생 시 마커 즉시 갱신

### 🎨 Step 4: UI 고도화 및 대시보드 기능

- [ ] 지표 On/Off 토글 버튼 패널
- [ ] 실시간 신호 알림(Alert) 기능
- [ ] 창 크기 조절에 따른 반응형 차트 최적화

---

## 🚀 시작 가이드 (Quick Start)

### 1. Backend 서버 실행

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### 2. Frontend 개발 서버 실행

```bash
cd frontend
npm install
npm run dev
```

### 3. 접속 주소

- **대시보드**: `http://localhost:5173`
- **백엔드 API**: `http://localhost:8000/api/history`
