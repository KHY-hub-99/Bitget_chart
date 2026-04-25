import { useEffect, useState } from "react";
import { fetchChartData } from "./api";
import TradingChart from "./TradingChart";

function App() {
  const [chartData, setChartData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLive, setIsLive] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true); // 로딩 상태 명시적 관리

  // 🎯 사용자가 선택할 상태 변수들
  const [symbol, setSymbol] = useState<string>("BTC/USDT:USDT");
  const [timeframe, setTimeframe] = useState<string>("5m");
  const [days, setDays] = useState<number>(90);

  // 파라미터가 변경될 때마다 데이터를 새로 불러옵니다.
  useEffect(() => {
    setIsLoading(true);
    setChartData(null); // 기존 차트 지우기
    setError(null);

    fetchChartData(symbol, timeframe, days)
      .then((data) => {
        setChartData(data);
        setIsLive(true);
        setIsLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setError("데이터를 불러오지 못했습니다. 백엔드 서버를 확인해 주세요.");
        setIsLive(false);
        setIsLoading(false);
      });
  }, [symbol, timeframe, days]); // 이 3개 중 하나라도 바뀌면 useEffect 재실행

  // 공통 셀렉트 박스 스타일
  const selectStyle = {
    backgroundColor: "#1e222d",
    color: "#d1d4dc",
    border: "1px solid #2a2e39",
    padding: "6px 12px",
    borderRadius: "6px",
    outline: "none",
    cursor: "pointer",
    fontSize: "0.9rem",
  };

  return (
    <div
      style={{
        width: "100vw",
        height: "100vh",
        backgroundColor: "#0b0e14",
        display: "flex",
        flexDirection: "column",
        fontFamily: "'Inter', sans-serif",
      }}
    >
      {/* 헤더 영역 (기존과 동일) */}
      <header
        style={{
          height: "60px",
          padding: "0 24px",
          backgroundColor: "#131722",
          borderBottom: "1px solid #2a2e39",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          zIndex: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="#2962FF" />
            <path
              d="M2 17L12 22L22 17M2 12L12 17L22 12"
              stroke="#2962FF"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <h1
            style={{
              margin: 0,
              color: "#d1d4dc",
              fontSize: "1.1rem",
              fontWeight: 600,
            }}
          >
            Crypto Master <span style={{ color: "#2962FF" }}>Dashboard</span>
          </h1>
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "6px 12px",
            backgroundColor: isLive
              ? "rgba(38, 166, 154, 0.1)"
              : "rgba(239, 83, 80, 0.1)",
            border: `1px solid ${isLive ? "rgba(38, 166, 154, 0.3)" : "rgba(239, 83, 80, 0.3)"}`,
            borderRadius: "20px",
          }}
        >
          <div
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              backgroundColor: isLive ? "#26a69a" : "#ef5350",
              boxShadow: `0 0 8px ${isLive ? "#26a69a" : "#ef5350"}`,
            }}
          />
          <span
            style={{
              color: isLive ? "#26a69a" : "#ef5350",
              fontSize: "0.85rem",
              fontWeight: 600,
            }}
          >
            {isLive ? "LIVE CONNECTED" : "OFFLINE"}
          </span>
        </div>
      </header>

      {/* 🎯 컨트롤 툴바 영역 (신규 추가) */}
      <div
        style={{
          padding: "10px 24px",
          backgroundColor: "#131722",
          borderBottom: "1px solid #2a2e39",
          display: "flex",
          gap: "16px",
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: "#848e9c", fontSize: "0.85rem" }}>Market:</span>
          <select
            style={selectStyle}
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
          >
            <option value="BTC/USDT:USDT">BTC/USDT (Bitcoin)</option>
            <option value="ETH/USDT:USDT">ETH/USDT (Ethereum)</option>
          </select>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: "#848e9c", fontSize: "0.85rem" }}>
            Timeframe:
          </span>
          <select
            style={selectStyle}
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
          >
            <option value="1m">1m</option>
            <option value="5m">5m</option>
            <option value="15m">15m</option>
            <option value="1h">1h</option>
            <option value="4h">4h</option>
            <option value="1d">1d</option>
          </select>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: "#848e9c", fontSize: "0.85rem" }}>
            History:
          </span>
          <select
            style={selectStyle}
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={7}>7 Days</option>
            <option value={30}>30 Days</option>
            <option value={90}>90 Days</option>
          </select>
        </div>
      </div>

      {/* 메인 차트 영역 */}
      <main
        style={{
          flex: 1,
          padding: "20px",
          position: "relative",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        {error ? (
          <div
            style={{
              backgroundColor: "#1e222d",
              padding: "30px 40px",
              borderRadius: "12px",
              border: "1px solid #ef5350",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: "40px", marginBottom: "10px" }}>🔌</div>
            <h3 style={{ color: "#ef5350", margin: "0 0 10px 0" }}>
              Connection Failed
            </h3>
            <p style={{ color: "#a3a6af", margin: 0 }}>{error}</p>
          </div>
        ) : isLoading || !chartData ? (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "16px",
            }}
          >
            <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
            <div
              style={{
                width: "40px",
                height: "40px",
                border: "3px solid rgba(41, 98, 255, 0.2)",
                borderTop: "3px solid #2962FF",
                borderRadius: "50%",
                animation: "spin 1s linear infinite",
              }}
            />
            <div
              style={{
                color: "#848e9c",
                fontSize: "0.9rem",
                fontWeight: 500,
                letterSpacing: "1px",
              }}
            >
              LOADING MARKET DATA...
            </div>
          </div>
        ) : (
          <div
            style={{
              width: "100%",
              height: "100%",
              backgroundColor: "#131722",
              borderRadius: "12px",
              border: "1px solid #2a2e39",
              overflow: "hidden",
            }}
          >
            <TradingChart data={chartData} />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
