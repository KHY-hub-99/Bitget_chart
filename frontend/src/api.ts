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
  // 쿼리 스트링(?) 방식에서 경로(/) 방식으로 수정
  const ws = new WebSocket(`${WS_BASE}/ws/chart/${symbol}/${timeframe}`);

  ws.onopen = () => console.log(`🟢 웹소켓 연결 성공: ${symbol}-${timeframe}`);
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      console.log("[실시간 웹소켓 수신]:", data);
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
  positions: { [symbol: string]: Position };
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

  // 3. 🆕 포지션 시장가 종료 (추가됨 - 버튼 작동 핵심)
  closePosition: async (symbol: string) => {
    const response = await axios.post(
      `${API_BASE}/api/simulation/close`,
      null,
      {
        params: { symbol }, // Query Parameter로 전달
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
};
