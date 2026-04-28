import axios from "axios";

// 백엔드 서버 주소 (FastAPI 기본 포트 8000)
const API_BASE = "http://localhost:8000";
const WS_BASE = "ws://localhost:8000";

// --- [ 0. 데이터 타입 정의 (Type Definitions) ] ---

// 백엔드에서 전달받는 캔들 1개(또는 틱)의 전체 데이터 포맷
export interface StrategyChartData {
  time: number; // Unix Timestamp (초)
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

  // 4. 추적 스윙 및 시장 추세 (NEW)
  trend?: number; // 1 (상승), -1 (하락)
  trailingTop?: number; // 추적 고점
  trailingBottom?: number; // 추적 저점 (SL 기준)
  topType?: string; // 'Strong High' / 'Weak High'
  bottomType?: string; // 'Strong Low' / 'Weak Low'

  // 5. 역추세 및 익절 마커 시그널
  TOP?: number; // 롱 익절 다이아몬드 (1 or 0)
  BOTTOM?: number; // 숏 익절 다이아몬드 (1 or 0)

  // 6. 하이브리드 진입 규칙 시그널 (SMA 추가됨)
  entryVwmaLong?: number;
  entryVwmaShort?: number;
  entrySmaLong?: number; // Rule 2: SMA 터치
  entrySmaShort?: number;
  entrySmcLong?: number; // Rule 3: SMC 터치
  entrySmcShort?: number;
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
    return response.data; // 이제 백엔드에서 chart_data 전체(markers, metadata 포함)를 리턴함
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

// 백엔드의 최신 Position 모델에 맞춤
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
  take_profit?: number | null; // 백엔드의 entry_equilibrium 매핑
  stop_loss?: number | null; // 백엔드의 stop_loss_price 매핑

  // 분할 진입 및 전략 추적 필드
  entry_tags: string[]; // 예: ["SMA", "VWMA"]
  is_partial_closed: boolean; // 50% 익절 여부
  sl_type: string | null; // 예: "SMC_TRAILING_STRONG_LOW"
  entry_rule: string; // 예: "RULE_2_SMA"
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

  // margin 대신 margin_ratio 사용
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

// tp_ratio/sl_ratio 대신 DB 컬럼명에 맞춘 marginRatio 사용
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

  // tp_ratio, sl_ratio 파라미터 삭제, margin_ratio 적용
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
