import axios from "axios";

// 백엔드 API 주소 (로컬)
const API_BASE = "http://127.0.0.1:8000";

export const fetchChartData = async () => {
  try {
    const response = await axios.get(`${API_BASE}/api/history`);
    return response.data;
  } catch (error) {
    console.error("데이터 통신 에러:", error);
    throw error;
  }
};
