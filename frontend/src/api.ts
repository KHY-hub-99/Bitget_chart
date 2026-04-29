import axios from "axios";

// 백엔드 서버 주소 (FastAPI 기본 포트 8000)
const API_BASE = "http://localhost:8000";
const WS_BASE = "ws://localhost:8000";

// --- [ 0. 데이터 타입 정의 (Type Definitions) ] ---

// 백엔드에서 전달받는 캔들 1개(또는 틱)의 전체 데이터 포맷 (통일 컬럼 100% 매핑)
export interface StrategyChartData {
  time: number; // Unix Timestamp (초)
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;

  // 1. 일목균형표
  tenkan?: number;
  kijun?: number;
  senkouA?: number;
  senkouB?: number;
  cloudTop?: number;
  cloudBottom?: number;

  // 2. Whale 세력선
  vwma224?: number;
  sma224?: number;

  // 3. 기술적 지표 (RSI, MFI, MACD, BB)
  rsiVal?: number;
  mfiVal?: number;
  macdLine?: number;
  signalLine?: number;
  bbLower?: number;
  bbMid?: number;
  bbUpper?: number;

  // 4. SMC 구조 및 가격 레벨
  swingHighLevel?: number;
  trailingBottom?: number;
  equilibrium?: number;

  // 5. 역추세 세부 신호 및 마커
  topDiamond?: number; // 롱 익절 마커 (1 or 0)
  bottomDiamond?: number; // 숏 익절 마커 (1 or 0)

  // 6. 추적 스윙 및 시장 추세
  trend?: number; // 1 (상승), -1 (하락)

  // 7. 매매 조건 및 최종 확정 시그널 (Rule 분리 적용)
  longSig_Rule1?: number; // SMA/VWMA 터치 기반 롱
  shortSig_Rule1?: number; // SMA/VWMA 터치 기반 숏
  longSig_Rule2?: number; // SMC 구조 기반 롱
  shortSig_Rule2?: number; // SMC 구조 기반 숏
}

// --- [ 1. 차트 및 기존 데이터 관련 API ] ---

export const fetchChartData = async (
  symbol: string,
  timeframe: string,
  days: number,
): Promise<{ data: StrategyChartData[]; markers: any[]; metadata: any }> => {
  try {
    const response = await axios.get(`${API_BASE}/api/history`, {
      params: { symbol, timeframe, days },
    });
    return response.data;
  } catch (error) {
    console.error("🔴 데이터 통신 에러:", error);
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
      console.error("🔴 웹소켓 파싱 에러:", error);
    }
  };
  ws.onerror = (error) => console.error("🔴 웹소켓 에러:", error);

  return {
    ws,
    close: () => {
      ws.close();
      console.log(`⚪ 웹소켓 연결 종료: ${symbol}-${timeframe}`);
    },
  };
};

// --- [ 2. 시뮬레이션(격리 모드) 전용 API ] ---

// 백엔드의 최신 serialize_wallet 출력 포맷에 맞춤
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
  take_profit: number | null; // 백엔드의 entry_equilibrium
  stop_loss: number | null; // 백엔드의 stop_loss_price

  // 분할 진입 및 하이브리드 전략 추적 필드
  is_partial_closed: boolean; // 50% 익절 여부
  entry_tags: string[]; // 예: ["SMA", "VWMA", "SMC"]
  strategy_rule: string; // "RULE_1" 또는 "RULE_2" (기존 entry_rule, sl_type 대체)
  first_entry_line_val: number | null; // 룰 1 추가 진입 시 유리한 평단가 비교를 위한 1차 진입선 값
}

export interface SimulationStatus {
  total_balance: number;
  available_balance: number;
  frozen_margin: number;
  position_mode: "ONE_WAY" | "HEDGE";
  positions: { [key: string]: Position };
}

export const simulationApi = {
  getStatus: async (): Promise<SimulationStatus> => {
    const response = await axios.get(`${API_BASE}/api/simulation/status`);
    return response.data;
  },

  placeOrder: async (orderData: {
    symbol: string;
    side: "LONG" | "SHORT";
    leverage: number;
    margin_ratio: number; // ex: 0.33
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

  closePosition: async (targetKey: string) => {
    const response = await axios.post(
      `${API_BASE}/api/simulation/close`,
      null,
      { params: { symbol: targetKey } },
    );
    return response.data;
  },

  processTick: async (symbol: string, currentPrice: number) => {
    const response = await axios.post(`${API_BASE}/api/simulation/tick`, {
      symbol: symbol,
      current_price: currentPrice,
    });
    return response.data;
  },

  reset: async () => {
    const response = await axios.post(`${API_BASE}/api/simulation/reset`);
    return response.data;
  },

  setMode: async (mode: "ONE_WAY" | "HEDGE") => {
    const response = await axios.post(`${API_BASE}/api/simulation/mode`, {
      mode: mode,
    });
    return response.data;
  },
};

// --- [ 3. 전략 분석 및 최적화 관련 API ] ---

export interface StrategyRank {
  positionMode: string;
  leverage: number;
  marginRatio: number;
  total_trades: number;
  wins: number;
  losses: number;
  total_pnl: number;
  avg_pnl: number;
  total_pyramid_count: number;
  avg_mdd_rate: number;
  max_drawdown: number;
  win_rate?: string;
}

export const analysisApi = {
  getRanking: async (
    symbol: string = "ALL",
    timeframe: string = "ALL",
  ): Promise<StrategyRank[]> => {
    const response = await axios.get(`${API_BASE}/api/strategy-ranking`, {
      params: { symbol, timeframe },
    });
    return response.data.data;
  },

  runFullSimulation: async (symbol: string, timeframe: string) => {
    const response = await axios.post(
      `${API_BASE}/api/simulation/run-full`,
      null,
      { params: { symbol, timeframe } },
    );
    return response.data;
  },

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

  getLogSocketUrl: () => `${WS_BASE}/ws/simulation/logs`,

  getSimulationReplay: async (
    symbol: string,
    timeframe: string,
    mode: string,
    leverage: number,
    margin_ratio: number, // (ex: 0.33)
  ): Promise<{ data: any; markers: any[] }> => {
    const response = await axios.get(`${API_BASE}/api/simulation/replay`, {
      params: {
        symbol,
        timeframe,
        mode,
        leverage,
        margin_ratio,
      },
    });
    return response.data;
  },
};
