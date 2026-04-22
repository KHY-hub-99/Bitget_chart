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
crypto-trading-dashboard/
├── backend/                        # Python 기반 FastAPI 서버
│   ├── app/
│   │   ├── main.py                 # API 서버 엔트리포인트 & 라우팅
│   │   ├── data_process/           # [Core] 데이터 수집 및 전략 로직
│   │   │   ├── load_data.py        # ccxt 기반 데이터 피드 클래스
│   │   │   └── pine_data.py        # 마스터 전략 연산 로직
│   │   ├── services/
│   │   │   └── chart_service.py    # DF 데이터를 차트용 JSON(Time/Value)으로 변환
│   │   └── utils/
│   │       └── config.py           # 심볼, 타임프레임, API 설정
│   ├── requirements.txt            # 의존성 패키지 (ccxt, pandas-ta, fastapi 등)
│   └── .env                        # 환경 변수 관리
│
├── frontend/                       # React (Vite) + TypeScript
│   ├── src/
│   │   ├── components/
│   │   │   └── Chart/
│   │   │       ├── TradingChart.tsx   # Lightweight Charts 메인 컴포넌트
│   │   │       └── IndicatorPanel.tsx # 지표 On/Off 토글 UI
│   │   ├── hooks/
│   │   │   ├── useChartData.ts     # API 데이터 Fetching 커스텀 훅
│   │   │   └── useWebSocket.ts     # 실시간 시세 업데이트 훅
│   │   ├── types/
│   │   │   └── chart.ts            # 차트 데이터 인터페이스 정의
│   │   └── App.tsx                 # 메인 레이아웃
│   ├── package.json
│   └── vite.config.ts
│
└── docker-compose.yml              # 백엔드/프론트엔드 컨테이너화 관리
```
