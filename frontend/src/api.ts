import axios from "axios";

// 백엔드 서버 주소 (FastAPI 기본 포트 8000)
const API_BASE = "http://localhost:8000";
const WS_BASE = "ws://localhost:8000";

// --- [ 0. 데이터 타입 정의 (Type Definitions) ] ---

// 백엔드에서 전달받는 캔들 1개(또는 틱)의 전체 데이터 포맷
export interface StrategyChartData {
  time: number; // Unix Timestamp (초 또는 밀리초)
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;

  // 1. 일목균형표
  senkouA?: number;
  senkouB?: number;

  // 2. Whale 세력선 (핵심 지표)
  vwma224?: number;
  sma224?: number;

  // 3. SMC 구조 및 가격 레벨
  swingHighLevel?: number;
  swingLowLevel?: number;
  equilibrium?: number;

  // 4. 역추세 및 익절 마커 시그널 (1 or 0, true or false)
  TOP?: number; // 숏 익절 다이아몬드
  BOTTOM?: number; // 롱 익절 다이아몬드

  // 5. 진입 규칙 시그널 (1 or 0)
  entrySmcLong?: number;
  entrySmcShort?: number;
  entryVwmaLong?: number;
  entryVwmaShort?: number;
}

// --- [ 1. 차트 및 기존 데이터 관련 API ] ---

export const fetchChartData = async (
  symbol: string,
  timeframe: string,
  days: number,
): Promise<StrategyChartData[]> => {
  try {
    const response = await axios.get(`${API_BASE}/api/history`, {
      params: { symbol, timeframe, days },
    });
    // 백엔드에서 내려주는 데이터가 response.data.data 배열 형태라면 맞게 수정 필요
    return response.data;
  } catch (error) {
    console.error("🔴 데이터 통신 에러:", error);
    throw error;
  }
};

export const subscribeChartData = (
  symbol: string,
  timeframe: string,
  onMessage: (data: StrategyChartData) => void, // any 대신 명시적 타입 사용
) => {
  const ws = new WebSocket(`${WS_BASE}/ws/chart/${symbol}/${timeframe}`);

  ws.onopen = () => console.log(`🟢 웹소켓 연결 성공: ${symbol}-${timeframe}`);
  ws.onmessage = (event) => {
    try {
      const data: StrategyChartData = JSON.parse(event.data);
      onMessage(data);
    } catch (error) {
      console.error("🔴 웹소켓 파싱 에러:", error);
    }
  };
  ws.onerror = (error) => console.error("🔴 웹소켓 에러:", error);

  // 컴포넌트 언마운트 시 구독 해제를 위해 close 함수를 포함한 객체 반환을 권장
  return {
    ws,
    close: () => {
      ws.close();
      console.log(`⚪ 웹소켓 연결 종료: ${symbol}-${timeframe}`);
    },
  };
};

// --- [ 2. 시뮬레이션(격리 모드) 전용 API ] ---

export interface Position {
  symbol: string;
  side: "LONG" | "SHORT";
  leverage: number;
  entry_price: number;
  size: number;
  mark_price: number;
  isolated_margin: number;
  liquidation_price: number;
  unrealized_pnl: number;
  take_profit_price: number | null;
  stop_loss_price: number | null;
}

export interface SimulationStatus {
  total_balance: number;
  available_balance: number;
  frozen_margin: number;
  position_mode: "ONE_WAY" | "HEDGE"; // 모드 상태 추가
  positions: { [key: string]: Position };
}

export const simulationApi = {
  // 1. 현재 지갑/포지션 상태 가져오기
  getStatus: async (): Promise<SimulationStatus> => {
    const response = await axios.get(`${API_BASE}/api/simulation/status`);
    return response.data;
  },

  // 2. 시장가 주문 넣기
  placeOrder: async (orderData: {
    symbol: string;
    side: "LONG" | "SHORT";
    leverage: number;
    margin: number;
    current_price: number;
    take_profit?: number;
    stop_loss?: number;
  }) => {
    const response = await axios.post(
      `${API_BASE}/api/simulation/order`,
      orderData,
    );
    return response.data;
  },

  // 3. 포지션 시장가 종료
  closePosition: async (targetKey: string) => {
    const response = await axios.post(
      `${API_BASE}/api/simulation/close`,
      null,
      {
        params: { symbol: targetKey },
      },
    );
    return response.data;
  },

  // 4. 틱 검사 (청산/TP/SL 확인)
  processTick: async (symbol: string, currentPrice: number) => {
    const response = await axios.post(`${API_BASE}/api/simulation/tick`, {
      symbol: symbol,
      current_price: currentPrice,
    });
    return response.data;
  },

  // 5. 초기화
  reset: async () => {
    const response = await axios.post(`${API_BASE}/api/simulation/reset`);
    return response.data;
  },

  // 6. 포지션 모드 변경
  setMode: async (mode: "ONE_WAY" | "HEDGE") => {
    const response = await axios.post(`${API_BASE}/api/simulation/mode`, {
      mode: mode,
    });
    return response.data;
  },
};

// --- [ 3. 전략 분석 및 최적화 관련 API (신규 추가) ] ---

export interface StrategyRank {
  position_mode: string;
  leverage: number;
  tp_ratio: number;
  sl_ratio: number;
  total_trades: number;
  wins: number;
  losses: number;
  liquidations: number;
  switches: number;
  total_pnl: number;
  avg_pnl: number;
  total_pyramid_count: number;
  avg_mdd_rate: number;
  max_drawdown: number;
  win_rate?: string;
}

export const analysisApi = {
  // 1. 전략 랭킹 가져오기
  getRanking: async (
    symbol: string = "ALL",
    timeframe: string = "ALL",
  ): Promise<StrategyRank[]> => {
    const response = await axios.get(`${API_BASE}/api/strategy-ranking`, {
      params: { symbol, timeframe },
    });
    return response.data.data;
  },

  // 2. 전체 시뮬레이션 실행 트리거
  runFullSimulation: async (symbol: string, timeframe: string) => {
    const response = await axios.post(
      `${API_BASE}/api/simulation/run-full`,
      null,
      {
        params: { symbol, timeframe },
      },
    );
    return response.data;
  },

  // 3. 과거 데이터 동기화 (Days 기반)
  syncHistoricalData: async (
    symbol: string,
    timeframe: string,
    days: number,
  ) => {
    const response = await axios.post(`${API_BASE}/api/sync-historical`, null, {
      params: { symbol, timeframe, days },
    });
    return response.data;
  },

  // 4. 시뮬레이션 로그 웹소켓 주소 반환
  getLogSocketUrl: () => `${WS_BASE}/ws/simulation/logs`,

  // 🟢 [추가됨] 5. 차트 복기(Replay) 데이터 요청
  getSimulationReplay: async (
    symbol: string,
    timeframe: string,
    mode: string,
    leverage: number,
    tp_ratio: number,
    sl_ratio: number,
  ): Promise<{ data: any[]; markers: any[] }> => {
    const response = await axios.get(`${API_BASE}/api/simulation/replay`, {
      params: {
        symbol,
        timeframe,
        mode,
        leverage,
        tp_ratio,
        sl_ratio,
        limit: 1000, // 최근 1,000개 캔들 기준 (필요시 조절 가능)
      },
    });
    return response.data;
  },
};
