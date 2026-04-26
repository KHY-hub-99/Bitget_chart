import { useEffect, useState } from "react";
import { fetchChartData, subscribeChartData } from "./api";
import TradingChart from "./TradingChart";

// 🆕 새로 만든 시뮬레이션 컴포넌트 임포트
import { OrderPanel } from "./components/OrderPanel";
import { PositionBoard } from "./components/PositionBoard";

function App() {
  const [chartData, setChartData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLive, setIsLive] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // 🆕 현재 시장가(Current Price)를 추적하는 상태 (주문 패널과 포지션 현황판에 전달)
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

  // 1️⃣ 기존 데이터 로딩 및 웹소켓 훅 유지
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

            if (!prev || prev.symbol !== symbol || newData.symbol !== symbol) {
              return { ...newData, symbol };
            }

            const lastPrice = newData.candles[newData.candles.length - 1].close;
            if (symbol === "ETHUSDT" && lastPrice > 10000) {
              return prev;
            }

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

            const markerMap = new Map();
            prev.markers?.forEach((m: any) =>
              markerMap.set(`${m.time}-${m.text}`, m),
            );
            newData.markers?.forEach((m: any) =>
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
        if (!isActive) return;
        console.error(err);
        setError("데이터 로드 실패. 서버 상태를 확인하세요.");
        setIsLoading(false);
      });

    return () => {
      isActive = false;
      if (ws) ws.close();
    };
  }, [symbol, timeframe, days]);

  // 2️⃣ 🆕 ChartData가 갱신될 때마다 가장 마지막 캔들의 종가를 currentPrice로 설정!
  useEffect(() => {
    if (chartData && chartData.candles && chartData.candles.length > 0) {
      const lastCandle = chartData.candles[chartData.candles.length - 1];
      setCurrentPrice(lastCandle.close);
    }
  }, [chartData]);

  // --- 스타일 정의 ---
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
      style={{
        width: "100vw",
        height: "100vh",
        backgroundColor: "#0b0e14",
        display: "flex",
        flexDirection: "column",
        fontFamily: "Inter, sans-serif",
        overflow: "hidden",
      }}
    >
      {/* --- 기존 헤더 유지 --- */}
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

      {/* --- 기존 툴바 유지 --- */}
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
          <span style={{ color: "#848e9c", fontSize: "0.85rem" }}>
            Timeframe:
          </span>
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
        <button style={btnStyle} onClick={handleApplySettings}>
          적용
        </button>
      </div>

      <div
        style={{
          padding: "8px 24px",
          backgroundColor: "#131722",
          borderBottom: "1px solid #2a2e39",
          display: "flex",
          gap: "10px",
          flexWrap: "wrap",
          flexShrink: 0,
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

      {/* --- 🌟 메인 레이아웃 구역 (차트 + 하단 패널 분할) --- */}
      <main
        style={{
          flex: 1,
          padding: "10px",
          display: "flex",
          flexDirection: "column", // 세로 분할 (위: 차트, 아래: 패널)
          gap: "10px",
          minHeight: 0, // Flex 자식이 넘칠 때 찌그러짐 방지
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
              margin: "auto",
            }}
          >
            <h3 style={{ color: "#ef5350" }}>Connection Failed</h3>
            <p style={{ color: "#a3a6af" }}>{error}</p>
          </div>
        ) : isLoading || !chartData ? (
          <div style={{ margin: "auto", color: "#d1d4dc" }}>LOADING...</div>
        ) : (
          <>
            {/* 📈 1. 상단: 차트 영역 (남은 공간의 비율을 크게 차지하도록 flex: 1 설정) */}
            <div
              style={{
                flex: 1, // 남은 세로 공간 다 차지
                minHeight: "40%", // 최소 높이 보장
                backgroundColor: "#131722",
                borderRadius: "12px",
                border: "1px solid #2a2e39",
                overflow: "hidden", // 차트가 삐져나가지 않게
              }}
            >
              <TradingChart
                key={`${symbol}-${timeframe}`}
                data={chartData}
                settings={visibleLayers}
                symbol={symbol}
              />
            </div>

            {/* 🎮 2. 하단: 패널 영역 (고정 높이 부여) */}
            <div
              style={{
                display: "flex", // 가로 분할 (좌: 포지션, 우: 주문)
                height: "320px", // 하단 패널 고정 높이
                flexShrink: 0,
                gap: "10px",
              }}
            >
              {/* 좌측: 포지션 현황판 (나머지 가로 공간 모두 차지) */}
              <div
                style={{
                  flex: 1,
                  backgroundColor: "#131722",
                  borderRadius: "12px",
                  border: "1px solid #2a2e39",
                  overflow: "hidden",
                }}
              >
                <PositionBoard currentPrice={currentPrice} />
              </div>

              {/* 우측: 주문 패널 (너비 320px 고정) */}
              <div
                style={{
                  width: "320px",
                  minWidth: "320px",
                  backgroundColor: "#131722",
                  borderRadius: "12px",
                  border: "1px solid #2a2e39",
                  overflow: "hidden",
                }}
              >
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
