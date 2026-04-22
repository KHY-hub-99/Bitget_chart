import { useEffect, useState } from "react";
import { fetchChartData } from "./api";
import TradingChart from "./TradingChart";

function App() {
  const [chartData, setChartData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // 앱이 실행될 때 데이터를 가져옵니다.
    fetchChartData()
      .then((data) => {
        console.log("✅ 데이터 수신 성공:", data);
        setChartData(data);
      })
      .catch(() => {
        setError(
          "데이터를 불러오지 못했습니다. 백엔드 서버가 켜져 있는지 확인해 주세요.",
        );
      });
  }, []);

  return (
    <div
      style={{
        width: "100vw",
        height: "100vh",
        backgroundColor: "#131722",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* 상단 헤더 */}
      <header
        style={{
          padding: "15px 20px",
          backgroundColor: "#1e222d",
          borderBottom: "1px solid #2b2b43",
        }}
      >
        <h2 style={{ margin: 0, color: "#d1d4dc", fontSize: "1.2rem" }}>
          📈 BTC/USDT Master Dashboard
        </h2>
      </header>

      {/* 메인 차트 영역 */}
      <main style={{ flex: 1, position: "relative" }}>
        {error ? (
          <div style={{ color: "#ef5350", padding: "20px" }}>{error}</div>
        ) : !chartData ? (
          <div style={{ color: "#d1d4dc", padding: "20px" }}>
            데이터 로딩 중... ⏳
          </div>
        ) : (
          <TradingChart data={chartData} />
        )}
      </main>
    </div>
  );
}

export default App;
