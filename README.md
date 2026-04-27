# 📈 Crypto Trading Master Dashboard

`ccxt`를 활용한 실시간 데이터 수집과 `pandas-ta` 기반의 **BTC 마스터 전략**을 시각화하는 전문 트레이딩 대시보드 프로젝트입니다.

### 🏗️ 시스템 아키텍처 (Architecture)

1.  **Data Engine**: Bitget 거래소로부터 90일치 이상의 과거 데이터를 로드하고 실시간 캔들을 업데이트합니다.
2.  **Strategy Engine**: 일목균형표, 볼린저 밴드, MACD, RSI, MFI를 조합하여 역추세(Divergence) 및 추세(Cloud Breakout) 신호를 생성합니다.
3.  **Backend (FastAPI)**: 계산된 데이터를 JSON 형태로 직렬화하여 REST API 및 WebSocket으로 전달합니다.
4.  **Frontend (React + TS)**: `lightweight-charts`를 사용하여 고성능 차트를 렌더링하고 지표와 신호를 마킹합니다.

---

### pine_data.py 생성 컬럼명 리스트 (Standard CamelCase)

**일목균형표 (Ichimoku)**

- `tenkan`
- `kijun`
- `senkouA`
- `senkouB`
- `cloudTop`
- `cloudBottom`

**Whale 세력선 및 거래량**

- `sma224`
- `vwma224`
- `volConfirm`

**기술적 지표 (RSI, MFI, MACD, BB)**

- `rsi`
- `mfi`
- `macdLine`
- `signalLine`
- `bbLower`
- `bbMid`
- `bbUpper`

**SMC 구조 및 가격 레벨**

- `swingHighLevel`
- `swingLowLevel`
- `equilibrium`

**역추세 세부 신호 및 마커**

- `bearishDiv`
- `bullishDiv`
- `extremeTop`
- `extremeBottom`
- `TOP`
- `BOTTOM`

**하이브리드 전략 세부 진입 규칙 (Rule 1 & Rule 2)**

- `entryVwmaLong`
- `entrySmcLong`
- `entryVwmaShort`
- `entrySmcShort`

**매매 조건 및 최종 확정 시그널**

- `longCondition`
- `shortCondition`
- `longSig`
- `shortSig`

---

### 📂 폴더 구조 (Folder Structure)

```text
Bitget_chart/
├── backend/                        # [Python] FastAPI 서버
│   ├── main.py                     # API 서버 엔트리포인트 & 라우터 등록 [UPDATE]
│   ├── check_db_detail.py          # db 적재 및 계산 확인용
│   ├── data_process/               # 핵심 연산 로직
│   │   ├── __init__.py
│   │   ├── load_data.py            # 데이터 수집 (Bitget)
│   │   └── pine_data.py            # 전략 계산 (Master Strategy)
│   ├── simulation/                 # 가상 시뮬레이션 엔진 (격리 모드)
│   │   ├── __init__.py
│   │   ├── engine.py               # 주문 체결, 청산가 계산, 틱(Tick) 업데이트 로직
│   │   ├── models.py               # Wallet, Position 상태 데이터 모델 (Pydantic)
│   │   └── strategy_optimizer.py   # 시뮬레이션 계산용 스크립트
│   ├── market_data/                # SQLite db 저장소
│   │   └── crypto_dashboard.db
│   ├── services/                   # 데이터 가공 및 비즈니스 로직
│   │   ├── __init__.py
│   │   └── chart_service.py        # DF -> Chart JSON 변환
│   ├── requirements.txt            # 필수 패키지 목록
│   ├── .env                        # API Key 등 환경 변수
│   └── Dockerfile                  # 백엔드 컨테이너 설정
│
├── frontend/                       # [React] Vite + TS
│   ├── src/
│   │   ├── components/             # UI 컴포넌트 폴더
│   │   │   ├── OrderPanel.tsx      # 격리 모드 주문 패널 (레버리지, 수량, Long/Short)
│   │   │   ├── PositionBoard.tsx   # 하단 포지션 상태바 (PNL, 마진, 청산가 표시)
│   │   │   └── ReplayControl.tsx   # 과거 데이터 재생 컨트롤러 (Play, Pause 등)
│   │   ├── hooks/                  # 커스텀 훅 (상태 관리)
│   │   │   └── useSimulation.ts    # 백엔드 API 연동, 지갑/포지션 상태 관리
│   │   ├── main.tsx                # 엔트리 포인트
│   │   ├── App.tsx                 # 메인 화면 및 레이아웃 구성 [UPDATE]
│   │   ├── App.css                 # 메인 화면 꾸미기
│   │   ├── TradingChart.tsx        # [Core] 차트 렌더링 및 진입/청산 라인(PriceLine) 표시 [UPDATE]
│   │   └── api.ts                  # 백엔드 Axios 통신 정의 (+ WebSocket 추가 권장)
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile                  # 프론트엔드 컨테이너 설정
│
├── .gitignore                      # Git 제외 설정
├── README.md                       # 프로젝트 기본 문서
└── docker-compose.yml              # 백엔드/프론트엔드 컨테이너화 관리
```

---

# 🗺️ 프론트엔드 개발 로드맵 (Roadmap)

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

# 🎮 코인 선물 가상 시뮬레이션 (ISOLATED 모드) 구축 로드맵

과거 데이터를 기반으로 실제 빗겟(Bitget) 거래소와 동일한 환경에서 매매를 연습하고 전략을 검증할 수 있는 **격리(Isolated) 모드 선물 거래 시뮬레이터** 개발 프로세스입니다.

### 🏗️ Step 1: 시뮬레이션 데이터 모델링 및 상태 관리 설계 (Backend)

격리 모드는 포지션별로 증거금이 독립적으로 관리되므로, 지갑(Wallet)과 포지션(Position)의 상태 분리가 핵심입니다.

- **Wallet (지갑 상태)**
  - `total_balance`: 총 자산 (초기 자본금, 예: 10,000 USDT)
  - `available_balance`: 사용 가능 자산 (주문에 사용할 수 있는 잔액)
  - `frozen_margin`: 현재 포지션에 묶여있는 총 증거금
- **Position (포지션 상태 - 격리 모드 기준)**
  - `symbol`: 거래 쌍 (예: BTC/USDT)
  - `side`: Long / Short
  - `leverage`: 레버리지 (예: 10x, 50x)
  - `entry_price`: 진입 가격
  - `size`: 포지션 크기 (코인 수량)
  - `isolated_margin`: 해당 포지션에 할당된 격리 증거금
  - `liquidation_price`: 청산가 (격리 증거금 기반 계산)
  - `unrealized_pnl`: 미실현 손익

### ⚙️ Step 2: 주문 처리 및 청산 엔진 구현 (Backend - FastAPI)

과거 OHLCV 캔들 데이터를 순차적으로 재생하면서, 주문과 청산 로직을 처리하는 핵심 엔진을 구현합니다.

- **[주문 실행 로직]**
  1.  사용자가 레버리지, 수량(Size), 포지션(Long/Short)을 입력하여 시장가/지정가 주문 요청.
  2.  `필요 증거금 = (진입가 * 수량) / 레버리지` 계산.
  3.  `available_balance`가 필요 증거금보다 크면 주문 체결.
  4.  지갑의 `available_balance` 차감, 포지션 `isolated_margin`에 할당.
- **[격리 청산가(Liquidation Price) 계산 로직]**
  - **Long:** `진입가 * (1 - (1 / 레버리지) + 유지증거금률)`
  - **Short:** `진입가 * (1 + (1 / 레버리지) - 유지증거금률)`
- **[Tick 및 캔들 업데이트]**
  - 과거 캔들의 `High`/`Low`/`Close`가 업데이트될 때마다 현재 포지션의 PNL을 재계산.
  - 현재 가격이 `liquidation_price`에 도달하면 즉시 포지션 강제 종료(청산) 처리 및 `isolated_margin` 0원 처리.

### 🖥️ Step 3: 트레이딩 인터페이스 구현 (Frontend - React + TS)

기존 `TradingChart.tsx` (Lightweight Charts) 우측 또는 하단에 실제 거래소와 유사한 주문 패널을 구성합니다.

- **[주문 패널 (Order Panel)]**
  - 레버리지 조절 슬라이더 (1x ~ 125x)
  - 주문 타입 (Market / Limit) 및 수량(USDT 또는 BTC 기준) 입력 폼
  - Buy / Long (초록색) 및 Sell / Short (빨간색) 버튼
  - 주문 실행 시 FastAPI 백엔드로 `POST /api/simulation/order` 전송
- **[포지션 상태바 (Position Dashboard)]**
  - 현재 진입한 포지션 목록 렌더링.
  - 실시간 PNL (수익률 %), 진입가, 현재가, 마진율, 청산가 표시.
  - [포지션 종료 (Close All)] 버튼 구현.
- **[차트 상호작용 (Lightweight Charts)]**
  - `lightweight-charts`의 `createPriceLine`을 활용하여 차트 위에 **진입가(Entry)**와 **청산가(Liquidation)**를 수평선으로 시각화.

### ⏪ Step 4: 시뮬레이터 재생 컨트롤러 (Replay System)

과거 데이터를 활용한 백테스팅 및 트레이딩 연습을 위해 시간(Time) 제어 기능을 도입합니다.

- **시간 축 이동 기능:** 특정 과거 날짜(예: 2023년 1월 1일 하락장)로 차트 이동.
- **재생 컨트롤:** \* ▶️ Play (1초당 1캔들씩 자동 진행 등 속도 조절)
  - ⏸️ Pause (차트 정지 후 심도 있는 차트 분석 및 주문 대기)
  - ⏭️ Next Candle (수동으로 1캔들씩 넘기며 매매 복기)
- **동기화:** 프론트엔드에서 재생 버튼을 누르면 백엔드의 Time Index가 전진하며 새로운 캔들과 갱신된 PNL 데이터를 WebSocket 또는 Polling으로 전달.

#### 시뮬레이션 저장 값

##### 1. 전략 최적화 최종 통계 테이블 (`strategy_optimization`)

전체 기간 동안 특정 파라미터(경우의 수)로 돌렸을 때의 최종 성적표를 저장합니다.

| Column Name     | Data Type | Description              | Example             |
| :-------------- | :-------- | :----------------------- | :------------------ |
| `id`            | INTEGER   | 기본 키 (Auto Increment) | 1                   |
| `position_mode` | TEXT      | 포지션 모드              | 'HEDGE' / 'ONE_WAY' |
| `leverage`      | INTEGER   | 사용된 레버리지          | 10, 20, 50          |
| `tp_ratio`      | REAL      | 익절 비율                | 0.03 (3%)           |
| `sl_ratio`      | REAL      | 손절 비율                | 0.015 (1.5%)        |
| `total_trades`  | INTEGER   | 총 매매 횟수             | 150                 |
| `win_rate`      | REAL      | 승률 (%)                 | 55.4                |
| `net_profit`    | REAL      | 최종 순수익 (USDT)       | 2450.50             |
| `max_drawdown`  | REAL      | 최대 낙폭 (MDD, %)       | -15.2               |
| `tested_at`     | TIMESTAMP | 테스트 실행 시간         | 2023-10-25 14:30:00 |

##### 2. 인공지능 학습용 상세 데이터셋 (`ml_trading_dataset`)

매매 신호가 발생한 매 순간(Tick)의 시장 원본 데이터와 해당 매매의 최종 결과를 기록합니다.

| Column Name        | Data Type | Feature Type  | Description                                               |
| :----------------- | :-------- | :------------ | :-------------------------------------------------------- |
| `id`               | INTEGER   | Meta          | 기본 키 (Auto Increment)                                  |
| `signal_time`      | TIMESTAMP | Meta          | 진입 시간                                                 |
| `signal_type`      | TEXT      | Feature (X)   | 발생한 신호 타입 ('MASTER_LONG', 'TOP_DIAMOND' 등)        |
| `entry_open`       | REAL      | Feature (X)   | 진입 캔들 시가 (Open)                                     |
| `entry_high`       | REAL      | Feature (X)   | 진입 캔들 고가 (High)                                     |
| `entry_low`        | REAL      | Feature (X)   | 진입 캔들 저가 (Low)                                      |
| `entry_close`      | REAL      | Feature (X)   | 진입 캔들 종가 (Close)                                    |
| `entry_volume`     | REAL      | Feature (X)   | 진입 캔들 거래량 (Volume)                                 |
| `entry_rsi`        | REAL      | Feature (X)   | 진입 시점 RSI 값                                          |
| `entry_macd`       | REAL      | Feature (X)   | 진입 시점 MACD 값                                         |
| `entry_mfi`        | REAL      | Feature (X)   | 진입 시점 MFI 값                                          |
| `bb_width`         | REAL      | Feature (X)   | 볼린저 밴드 폭 (변동성 파악용)                            |
| `position_mode`    | TEXT      | Setting       | 시뮬레이션에 적용한 모드                                  |
| `leverage`         | INTEGER   | Setting       | 시뮬레이션에 적용한 레버리지                              |
| `tp_ratio`         | REAL      | Setting       | 시뮬레이션 익절 세팅값                                    |
| `sl_ratio`         | REAL      | Setting       | 시뮬레이션 손절 세팅값                                    |
| `result_status`    | TEXT      | Label (y)     | 최종 매매 결과 ('TAKE_PROFIT', 'STOP_LOSS', 'LIQUIDATED') |
| `realized_pnl`     | REAL      | Label (y)     | 최종 실현 수익 (USDT)                                     |
| `duration_candles` | INTEGER   | Label (y)     | 진입부터 종료까지 걸린 캔들 수                            |
| `pyramid_count`    | INTEGER   | Label/Feature | 추세가 이어져 불타기(추가 진입)가 발생한 횟수             |

### 🤖 Step 5: Master 전략(Indicator) 시그널 연동 및 자동화

기존의 `pandas-ta` 기반 지표들과 시뮬레이터를 연결하여 반자동/자동 매매 환경을 구성합니다.

- **매매 타점 시각화:** 전략 엔진(일목균형표, 볼린저밴드 등)에서 발생한 `master_long`, `master_short` 시그널을 차트에 마커(Marker)로 표시.
- **시그널 기반 자동 진입 (Auto-Trading Mode):** \* 사용자가 수동 매매뿐만 아니라 "시그널 자동 매매" 토글을 켜면, 과거 데이터 재생 중 시그널 발생 시 설정된 레버리지와 시드로 자동 격리 포지션 진입.
- **결과 리포트 출력:** 시뮬레이션 종료 시 총 거래 횟수, 승률(Win Rate), 최대 낙폭(MDD), 최종 수익금을 차트로 요약하여 보여주는 모달 창 구현.

---

# 🚀 시작 가이드 (Quick Start)

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
