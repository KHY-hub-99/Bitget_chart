import axios from "axios";

// 백엔드 서버 주소 (FastAPI 기본 포트 8000)
const API_BASE = "http://localhost:8000";
const WS_BASE = "ws://localhost:8000";

// --- [ 1. 차트 및 기존 데이터 관련 API ] ---

export const fetchChartData = async (
  symbol: string,
  timeframe: string,
  days: number,
) => {
  try {
    const response = await axios.get(`${API_BASE}/api/history`, {
      params: { symbol, timeframe, days },
    });
    return response.data;
  } catch (error) {
    console.error("데이터 통신 에러:", error);
    throw error;
  }
};

export const subscribeChartData = (
  symbol: string,
  timeframe: string,
  onMessage: (data: any) => void,
) => {
  const ws = new WebSocket(`${WS_BASE}/ws/chart/${symbol}/${timeframe}`);

  ws.onopen = () => console.log(`🟢 웹소켓 연결 성공: ${symbol}-${timeframe}`);
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (error) {
      console.error("웹소켓 파싱 에러:", error);
    }
  };
  ws.onerror = (error) => console.error("🔴 웹소켓 에러:", error);
  return ws;
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
    // 💡 심볼이 아닌 '포지션 키'를 보내도록 이름 변경 (Hedge 대응)
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

  // 6. 포지션 모드 변경 API 추가 (이게 빠져있어서 에러가 났던 것입니다!)
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
  liquidations: number; // 추가
  switches: number; // 추가
  total_pnl: number;
  avg_pnl: number;
  total_pyramid_count: number;
  avg_mdd_rate: number; // 추가
  max_drawdown: number; // 추가
  win_rate?: string; // 백엔드에서 계산해서 주거나 프론트에서 계산
}

export const analysisApi = {
  // 1. 전략 랭킹 가져오기
  getRanking: async (): Promise<StrategyRank[]> => {
    const response = await axios.get(`${API_BASE}/api/strategy-ranking`);
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

  // 4. 시뮬레이션 로그 웹소켓 주소 반환 (컴포넌트에서 사용)
  getLogSocketUrl: () => `${WS_BASE}/ws/simulation/logs`,
};
