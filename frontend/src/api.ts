import axios from "axios";

const API_BASE = "http://localhost:8000";
const WS_BASE = "ws://localhost:8000";

export const fetchChartData = async (
  symbol: string,
  timeframe: string,
  days: number,
) => {
  try {
    const response = await axios.get(`${API_BASE}/api/history`, {
      params: { symbol, timeframe, days },
    });

    // 🎯 [REST API 데이터 확인]
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

      // 🎯 [웹소켓 실시간 데이터 확인]
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
