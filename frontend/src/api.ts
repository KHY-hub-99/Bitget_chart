import axios from "axios";

const API_BASE = "http://localhost:8000"; // 127.0.0.1 대신 localhost로 통일
const WS_BASE = "ws://localhost:8000";

// 🎯 파라미터를 받아 GET 요청의 Query String으로 전달
export const fetchChartData = async (
  symbol: string,
  timeframe: string,
  days: number,
) => {
  try {
    const response = await axios.get(`${API_BASE}/api/history`, {
      params: { symbol, timeframe, days }, // -> ?symbol=BTC/USDT...&timeframe=5m&days=90
    });
    return response.data;
  } catch (error) {
    console.error("데이터 통신 에러:", error);
    throw error;
  }
};

// 🎯 웹소켓도 어떤 코인/분봉을 구독할지 파라미터로 전달
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
      onMessage(data);
    } catch (error) {
      console.error("웹소켓 파싱 에러:", error);
    }
  };
  ws.onerror = (error) => console.error("🔴 웹소켓 에러:", error);
  ws.onclose = () => console.log("⚪ 웹소켓 연결 종료");

  return ws;
};
