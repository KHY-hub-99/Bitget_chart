import { useEffect, useState } from "react";
import { fetchChartData, subscribeChartData } from "./api";
import TradingChart from "./TradingChart";

// 🆕 시뮬레이션 컴포넌트 임포트
import { OrderPanel } from "./components/OrderPanel";
import { PositionBoard } from "./components/PositionBoard";

function App() {
  const [chartData, setChartData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLive, setIsLive] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // 현재 시장가(Current Price) 상태
  const [currentPrice, setCurrentPrice] = useState<number>(0);

  const [symbol, setSymbol] = useState<string>("BTCUSDT");
  const [timeframe, setTimeframe] = useState<string>("15m");
  const [days, setDays] = useState<number>(30);

  const [inputSymbol, setInputSymbol] = useState<string>("BTCUSDT");
  const [inputTimeframe, setInputTimeframe] = useState<string>("15m");
  const [inputDays, setInputDays] = useState<number>(30);

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

  // 1️⃣ 데이터 로딩 및 웹소켓 연결
  useEffect(() => {
    let ws: WebSocket | null = null;
    let isActive = true;

    setIsLoading(true);
    setChartData(null);
    setError(null);
    setIsLive(false);

    fetchChartData(symbol, timeframe, days)
      .then((initialData) => {
        if (!isActive) return;
        setChartData({ ...initialData, symbol });
        setIsLoading(false);

        ws = subscribeChartData(symbol, timeframe, (newData) => {
          if (!isActive) return;
          setIsLive(true);

          setChartData((prev: any) => {
            if (!newData || !newData.candles || newData.candles.length === 0)
              return prev;
            if (!prev || prev.symbol !== symbol || newData.symbol !== symbol)
              return { ...newData, symbol };

            const candleMap = new Map();
            prev.candles.forEach((c: any) => candleMap.set(c.time, c));
            newData.candles.forEach((c: any) => candleMap.set(c.time, c));
            const mergedCandles = Array.from(candleMap.values()).sort(
              (a, b) => a.time - b.time,
            );

            const mergeIndicator = (prevIdx: any[], newIdx: any[]) => {
              const iMap = new Map();
              if (prevIdx) prevIdx.forEach((i) => iMap.set(i.time, i));
              if (newIdx) newIdx.forEach((i) => iMap.set(i.time, i));
              return Array.from(iMap.values()).sort((a, b) => a.time - b.time);
            };

            const mergedIndicators = { ...prev.indicators };
            Object.keys(newData.indicators || {}).forEach((key) => {
              mergedIndicators[key] = mergeIndicator(
                prev.indicators[key] || [],
                newData.indicators[key] || [],
              );
            });

            return {
              ...prev,
              candles: mergedCandles,
              indicators: mergedIndicators,
            };
          });
        });
      })
      .catch((err) => {
        if (!isActive) return;
        setError("데이터 로드 실패. 서버 상태를 확인하세요.");
        setIsLoading(false);
      });

    return () => {
      isActive = false;
      if (ws) ws.close();
    };
  }, [symbol, timeframe, days]);

  // 2️⃣ 실시간 가격 추출
  useEffect(() => {
    if (chartData && chartData.candles && chartData.candles.length > 0) {
      const lastCandle = chartData.candles[chartData.candles.length - 1];
      setCurrentPrice(lastCandle.close);
    }
  }, [chartData]);

  // UI 스타일 (기존 유지)
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

  const handleApplySettings = () => {
    setSymbol(inputSymbol);
    setTimeframe(inputTimeframe);
    if (inputDays > 0) setDays(inputDays);
  };

  return (
    <div
      className="app-container"
      style={{
        width: "100vw",
        height: "100vh",
        backgroundColor: "#0b0e14",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* --- 헤더 & 툴바 --- */}
      <header
        style={{
          height: "60px",
          padding: "0 24px",
          backgroundColor: "#131722",
          borderBottom: "1px solid #2a2e39",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexShrink: 0,
        }}
      >
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
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "8px",
            padding: "6px 12px",
            backgroundColor: isLive
              ? "rgba(38, 166, 154, 0.1)"
              : "rgba(239, 83, 80, 0.1)",
            borderRadius: "20px",
          }}
        >
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

      <div
        style={{
          padding: "12px 24px",
          backgroundColor: "#131722",
          borderBottom: "1px solid #2a2e39",
          display: "flex",
          gap: "20px",
          alignItems: "center",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: "#848e9c", fontSize: "0.85rem" }}>Market:</span>
          <select
            style={selectStyle}
            value={inputSymbol}
            onChange={(e) => setInputSymbol(e.target.value)}
          >
            <option value="BTCUSDT">BTC/USDT</option>
            <option value="ETHUSDT">ETH/USDT</option>
          </select>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: "#848e9c", fontSize: "0.85rem" }}>Time:</span>
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
        <button style={btnStyle} onClick={handleApplySettings}>
          적용
        </button>
      </div>

      {/* --- 레이어 토글 --- */}
      <div
        style={{
          padding: "8px 24px",
          backgroundColor: "#131722",
          borderBottom: "1px solid #2a2e39",
          display: "flex",
          gap: "10px",
          flexShrink: 0,
        }}
      >
        {Object.entries(visibleLayers).map(([key, isVisible]) => (
          <label key={key} style={checkboxLabelStyle}>
            <input
              type="checkbox"
              checked={isVisible}
              onChange={() => toggleLayer(key as any)}
            />{" "}
            {key.toUpperCase()}
          </label>
        ))}
      </div>

      {/* --- 🌟 수정된 메인 레이아웃 --- */}
      <main
        className="app-main"
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {error ? (
          <div style={{ margin: "auto", textAlign: "center" }}>
            <h3 style={{ color: "#ef5350" }}>{error}</h3>
          </div>
        ) : isLoading || !chartData ? (
          <div style={{ margin: "auto", color: "#d1d4dc" }}>LOADING...</div>
        ) : (
          <>
            {/* 📈 상단: 차트 섹션 (CSS 클래스 적용으로 Volume 공간 확보) */}
            <div className="chart-section">
              <TradingChart
                key={`${symbol}-${timeframe}`}
                data={chartData}
                settings={visibleLayers}
                symbol={symbol}
              />
            </div>

            {/* 🎮 하단: 패널 섹션 (잘림 방지 고정 레이아웃) */}
            <div className="bottom-section">
              <div className="position-section">
                <PositionBoard currentPrice={currentPrice} />
              </div>
              <div className="order-section">
                <OrderPanel currentPrice={currentPrice} />
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
