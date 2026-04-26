import axios from "axios";

const API_BASE = "http://localhost:8000";
const WS_BASE = "ws://localhost:8000";

//  --- [1. 차트 및 기존 데이터 관련 API] ---
export const fetchChartData = async (
  symbol: string,
  timeframe: string,
  days: number,
) => {
  try {
    const response = await axios.get(`${API_BASE}/api/history`, {
      params: { symbol, timeframe, days },
    });

    // [REST API 데이터 확인]
    console.log("[초기 데이터 로드 성공]");
    console.log("수신 데이터 전체:", response.data);

    if (response.data.indicators) {
      console.log(
        "지표(Indicators) 키 목록:",
        Object.keys(response.data.indicators),
      );
      console.log(
        "RSI 데이터 샘플:",
        response.data.indicators.rsi || "데이터 없음",
      );
    }

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
  const ws = new WebSocket(
    `${WS_BASE}/ws/chart?symbol=${symbol}&timeframe=${timeframe}`,
  );

  ws.onopen = () =>
    console.log(`🟢 웹소켓 연결 성공: ${symbol} (${timeframe})`);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);

      // [웹소켓 실시간 데이터 확인]
      // 로그가 너무 많이 찍히면 정신없으니, 첫 번째 데이터만 자세히 보거나 지표만 찍습니다.
      console.log("[실시간 웹소켓 수신]:", data);

      onMessage(data);
    } catch (error) {
      console.error("웹소켓 파싱 에러:", error);
    }
  };

  ws.onerror = (error) => console.error("🔴 웹소켓 에러:", error);
  ws.onclose = () => console.log("⚪ 웹소켓 연결 종료");

  return ws;
};

//  --- [2. 시뮬레이션(격리 모드) 전용 API] ---
// 타입 정의
export interface Position {
  side: "LONG" | "SHORT";
  leverage: number;
  entry_price: number;
  size: number;
  isolated_margin: number;
  liquidation_price: number;
  unrealized_pnl: number;
  take_profit: number | null;
  stop_loss: number | null;
}

export interface SimulationStatus {
  total_balance: number;
  available_balance: number;
  frozen_margin: number;
  positions: { [symbol: string]: Position };
}

// 시뮬레이션 API 객체로 묶어서 관리
export const simulationApi = {
  // 1. 현재 상태 가져오기 (지갑 및 포지션)
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

  // 3. 캔들 업데이트 시 틱(Tick) 검사 요청 (청산/익절/손절 확인)
  processTick: async (symbol: string, currentPrice: number) => {
    const response = await axios.post(`${API_BASE}/api/simulation/tick`, {
      symbol,
      current_price: currentPrice,
    });
    return response.data;
  },

  // 4. 시뮬레이션 지갑 및 포지션 초기화
  reset: async () => {
    const response = await axios.post(`${API_BASE}/api/simulation/reset`);
    return response.data;
  },
};
