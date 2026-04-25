import { useEffect, useState } from "react";
import { fetchChartData, subscribeChartData } from "./api";
import TradingChart from "./TradingChart";

function App() {
  const [chartData, setChartData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLive, setIsLive] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // 1️⃣ 🎯 실제 차트에 적용되는 상태 (useEffect가 바라보는 값)
  const [symbol, setSymbol] = useState<string>("BTC/USDT:USDT");
  const [timeframe, setTimeframe] = useState<string>("15m");
  const [days, setDays] = useState<number>(365);

  // 1-1️⃣ 🎯 UI(선택창/입력창)에만 보여지는 상태 (적용 버튼을 눌러야 위 상태로 덮어씌워짐)
  const [inputSymbol, setInputSymbol] = useState<string>("BTC/USDT:USDT");
  const [inputTimeframe, setInputTimeframe] = useState<string>("15m");
  const [inputDays, setInputDays] = useState<number>(365);

  // 2️⃣ 지표 가시성(On/Off) 상태 추가
  const [visibleLayers, setVisibleLayers] = useState({
    kijun: true,
    ichimoku: true,
    bollinger: true,
    rsi: true,
    macd: true,
  });

  const toggleLayer = (layer: keyof typeof visibleLayers) => {
    setVisibleLayers((prev) => ({ ...prev, [layer]: !prev[layer] }));
  };

  useEffect(() => {
    let ws: WebSocket | null = null;

    setIsLoading(true);
    setChartData(null);
    setError(null);
    setIsLive(false);

    // 초기 데이터 로드 (실제 symbol, timeframe, days 값이 바뀔 때만 실행됨)
    fetchChartData(symbol, timeframe, days)
      .then((initialData) => {
        setChartData(initialData);
        setIsLoading(false);

        // 실시간 웹소켓 구독 시작
        ws = subscribeChartData(symbol, timeframe, (newData) => {
          setIsLive(true);
          setChartData((prev: any) => {
            if (!prev) return newData;

            // [데이터 병합]
            const candleMap = new Map();
            prev.candles.forEach((c: any) => candleMap.set(c.time, c));
            newData.candles.forEach((c: any) => candleMap.set(c.time, c));
            const mergedCandles = Array.from(candleMap.values()).sort(
              (a, b) => a.time - b.time,
            );

            // [지표 병합]
            const mergeIndicator = (prevIdx: any[], newIdx: any[]) => {
              const iMap = new Map();
              if (prevIdx) prevIdx.forEach((i) => iMap.set(i.time, i));
              if (newIdx) newIdx.forEach((i) => iMap.set(i.time, i));
              return Array.from(iMap.values()).sort((a, b) => a.time - b.time);
            };

            const mergedIndicators = { ...prev.indicators };
            Object.keys(newData.indicators).forEach((key) => {
              mergedIndicators[key] = mergeIndicator(
                prev.indicators[key],
                newData.indicators[key],
              );
            });

            // [마커 병합]
            const markerMap = new Map();
            prev.markers.forEach((m: any) =>
              markerMap.set(`${m.time}-${m.text}`, m),
            );
            newData.markers.forEach((m: any) =>
              markerMap.set(`${m.time}-${m.text}`, m),
            );
            const mergedMarkers = Array.from(markerMap.values()).sort(
              (a, b) => a.time - b.time,
            );

            return {
              ...prev,
              candles: mergedCandles,
              indicators: mergedIndicators,
              markers: mergedMarkers,
            };
          });
        });
      })
      .catch((err) => {
        console.error(err);
        setError("데이터 로드 실패. 서버 상태를 확인하세요.");
        setIsLoading(false);
      });

    return () => {
      if (ws) ws.close();
    };
  }, [symbol, timeframe, days]); // 🎯 실제 상태가 바뀔 때만 재실행됨

  const selectStyle = {
    backgroundColor: "#1e222d",
    color: "#d1d4dc",
    border: "1px solid #2a2e39",
    padding: "6px 12px",
    borderRadius: "6px",
    outline: "none",
    cursor: "pointer",
    fontSize: "0.85rem",
  };

  const inputStyle = {
    backgroundColor: "#1e222d",
    color: "#d1d4dc",
    border: "1px solid #2a2e39",
    padding: "6px 12px",
    borderRadius: "6px",
    outline: "none",
    fontSize: "0.85rem",
    width: "70px",
  };

  const btnStyle = {
    backgroundColor: "#2962FF",
    color: "#ffffff",
    border: "none",
    padding: "6px 16px",
    borderRadius: "6px",
    cursor: "pointer",
    fontSize: "0.85rem",
    fontWeight: 600,
    marginLeft: "10px",
  };

  const checkboxLabelStyle = {
    color: "#848e9c",
    fontSize: "0.8rem",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    gap: "6px",
    padding: "4px 8px",
    borderRadius: "4px",
    backgroundColor: "#1e222d",
  };

  // 🎯 [적용] 버튼 클릭 핸들러 (입력된 상태를 실제 상태로 한 번에 동기화)
  const handleApplySettings = () => {
    setSymbol(inputSymbol);
    setTimeframe(inputTimeframe);
    if (inputDays > 0) {
      setDays(inputDays);
    }
  };

  return (
    <div
      style={{
        width: "100vw",
        height: "100vh",
        backgroundColor: "#0b0e14",
        display: "flex",
        flexDirection: "column",
        fontFamily: "Inter, sans-serif",
      }}
    >
      {/* 🚀 상단 헤더 */}
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
              fontSize: "0.8rem",
              fontWeight: 600,
            }}
          >
            {isLive ? "LIVE CONNECTED" : "OFFLINE"}
          </span>
        </div>
      </header>

      {/* 🛠️ 컨트롤 툴바 (마켓/분봉/기간 통합) */}
      <div
        style={{
          padding: "12px 24px",
          backgroundColor: "#131722",
          borderBottom: "1px solid #2a2e39",
          display: "flex",
          gap: "20px",
          alignItems: "center",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: "#848e9c", fontSize: "0.85rem" }}>Market:</span>
          {/* 🎯 value와 onChange를 input 상태로 변경 */}
          <select
            style={selectStyle}
            value={inputSymbol}
            onChange={(e) => setInputSymbol(e.target.value)}
          >
            <option value="BTC/USDT:USDT">BTC/USDT</option>
            <option value="ETH/USDT:USDT">ETH/USDT</option>
          </select>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: "#848e9c", fontSize: "0.85rem" }}>
            Timeframe:
          </span>
          {/* 🎯 value와 onChange를 input 상태로 변경 */}
          <select
            style={selectStyle}
            value={inputTimeframe}
            onChange={(e) => setInputTimeframe(e.target.value)}
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
            History (Days):
          </span>
          <input
            type="number"
            min="1"
            style={inputStyle}
            value={inputDays}
            onChange={(e) => setInputDays(Number(e.target.value))}
            onKeyDown={(e) => e.key === "Enter" && handleApplySettings()}
          />
        </div>

        {/* 🎯 [수정됨] 모든 변경사항을 한 번에 적용하는 버튼 */}
        <button style={btnStyle} onClick={handleApplySettings}>
          적용
        </button>
      </div>

      {/* 🎯 지표 가시성 토글 바 */}
      <div
        style={{
          padding: "8px 24px",
          backgroundColor: "#131722",
          borderBottom: "1px solid #2a2e39",
          display: "flex",
          gap: "10px",
          flexWrap: "wrap",
        }}
      >
        {Object.entries(visibleLayers).map(([key, isVisible]) => (
          <label key={key} style={checkboxLabelStyle}>
            <input
              type="checkbox"
              checked={isVisible}
              onChange={() => toggleLayer(key as any)}
              style={{ accentColor: "#2962FF" }}
            />
            {key.toUpperCase()}
          </label>
        ))}
      </div>

      {/* 메인 차트 영역 */}
      <main
        style={{
          flex: 1,
          padding: "20px",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        {error ? (
          <div
            style={{
              backgroundColor: "#1e222d",
              padding: "30px",
              borderRadius: "12px",
              border: "1px solid #ef5350",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: "32px" }}>🔌</div>
            <h3 style={{ color: "#ef5350" }}>Connection Failed</h3>
            <p style={{ color: "#a3a6af" }}>{error}</p>
          </div>
        ) : isLoading || !chartData ? (
          <div style={{ textAlign: "center" }}>
            <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
            <div
              style={{
                width: "40px",
                height: "40px",
                border: "3px solid rgba(41, 98, 255, 0.2)",
                borderTop: "3px solid #2962FF",
                borderRadius: "50%",
                animation: "spin 1s linear infinite",
                margin: "0 auto 16px",
              }}
            />
            <div style={{ color: "#848e9c", letterSpacing: "1px" }}>
              LOADING...
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
            <TradingChart data={chartData} settings={visibleLayers} />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
