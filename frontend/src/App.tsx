import { useEffect, useState } from "react";
import { fetchChartData, subscribeChartData } from "./api";
import TradingChart from "./TradingChart";

// 시뮬레이션 컴포넌트 및 훅 임포트
import { OrderPanel } from "./components/OrderPanel";
import { PositionBoard } from "./components/PositionBoard";
import { useSimulation } from "./hooks/useSimulation";

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

  // 🌟 [핵심] 시뮬레이션 상태 통합 관리
  // 여기서 한 번 선언한 sim 객체를 아래에서 자식들에게 Props로 내려줍니다.
  const sim = useSimulation(symbol);

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

          // 1️⃣ [사이드 이펙트 처리] 웹소켓 데이터가 도착하자마자 가격부터 추출합니다.
          if (newData.candles && newData.candles.length > 0) {
            const lastCandle = newData.candles[newData.candles.length - 1];
            const lastPrice = lastCandle.close;

            // 🌟 setState 밖에서 실행해야 정상적으로 상태가 전파됩니다.
            setCurrentPrice(lastPrice);
            sim.checkTick(lastPrice); // 백엔드에 틱을 쏘고, 지갑 상태(Mark Price)를 갱신함
          }

          // 2️⃣ [차트 데이터 업데이트] 이후에 차트의 캔들과 지표를 병합합니다.
          setChartData((prev: any) => {
            if (!newData || !newData.candles || newData.candles.length === 0)
              return prev;

            if (!prev || prev.symbol !== symbol) return { ...newData, symbol };

            const mergeByTime = (prevArr: any[], nextArr: any[]) => {
              const map = new Map();
              (prevArr || []).forEach((item) => map.set(item.time, item));
              (nextArr || []).forEach((item) => map.set(item.time, item));
              return Array.from(map.values()).sort((a, b) => a.time - b.time);
            };

            const mergedCandles = mergeByTime(prev.candles, newData.candles);

            const mergedIndicators = { ...prev.indicators };
            if (newData.indicators) {
              Object.keys(newData.indicators).forEach((key) => {
                mergedIndicators[key] = mergeByTime(
                  prev.indicators?.[key] || [],
                  newData.indicators[key] || [],
                );
              });
            }

            const mergedMarkers = mergeByTime(
              prev.markers || [],
              newData.markers || [],
            );

            // ❌ 여기서 setCurrentPrice나 sim.checkTick을 지웠습니다!

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
        setError("데이터 로드 실패. 서버 상태를 확인하세요.");
        setIsLoading(false);
      });

    return () => {
      isActive = false;
      if (ws) ws.close();
    };
  }, [symbol, timeframe, days]); // days도 의존성에 추가하는 것이 안전합니다.

  const handleApplySettings = () => {
    setSymbol(inputSymbol);
    setTimeframe(inputTimeframe);
  };

  const currentPosition = sim.currentPosition;

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
      {/* --- 헤더 & 툴바 (기존 유지) --- */}
      <header style={headerStyle}>
        <h1 style={logoStyle}>
          Crypto Master <span style={{ color: "#2962FF" }}>Dashboard</span>
        </h1>
        <div
          style={{
            ...statusBadgeStyle,
            backgroundColor: isLive
              ? "rgba(38, 166, 154, 0.1)"
              : "rgba(239, 83, 80, 0.1)",
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

      <div style={toolbarStyle}>
        <div style={filterGroupStyle}>
          <span style={labelStyle}>Market:</span>
          <select
            style={selectStyle}
            value={inputSymbol}
            onChange={(e) => setInputSymbol(e.target.value)}
          >
            <option value="BTCUSDT">BTC/USDT</option>
            <option value="ETHUSDT">ETH/USDT</option>
          </select>
        </div>
        <div style={filterGroupStyle}>
          <span style={labelStyle}>Time:</span>
          <select
            style={selectStyle}
            value={inputTimeframe}
            onChange={(e) => setInputTimeframe(e.target.value)}
          >
            <option value="1m">1m</option>
            <option value="5m">5m</option>
            <option value="15m">15m</option>
            <option value="1h">1h</option>
            <option value="1d">1d</option>
          </select>
        </div>
        <button style={btnStyle} onClick={handleApplySettings}>
          적용
        </button>
      </div>

      {/* --- 레이어 토글 --- */}
      <div style={layerToggleStyle}>
        {Object.entries(visibleLayers).map(([key, isVisible]) => (
          <label key={key} style={checkboxLabelStyle}>
            <input
              type="checkbox"
              checked={isVisible}
              onChange={() => toggleLayer(key as any)}
            />
            {key.toUpperCase()}
          </label>
        ))}
      </div>

      {/* --- 🌟 메인 레이아웃 (데이터 바인딩 수정됨) --- */}
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
          <div style={centerMsgStyle}>
            <h3 style={{ color: "#ef5350" }}>{error}</h3>
          </div>
        ) : isLoading || !chartData ? (
          <div style={centerMsgStyle}>LOADING...</div>
        ) : (
          <>
            <div
              className="chart-section"
              style={{ flex: 2, minHeight: "450px" }}
            >
              <TradingChart
                key={`${symbol}-${timeframe}`}
                data={chartData}
                settings={visibleLayers}
                symbol={symbol}
                currentPosition={currentPosition}
              />
            </div>

            <div
              className="bottom-section"
              style={{
                flex: 1,
                display: "flex",
                borderTop: "1px solid #2a2e39",
                minHeight: "250px",
              }}
            >
              <div
                className="position-section"
                style={{ flex: 1.5, borderRight: "1px solid #2a2e39" }}
              >
                <PositionBoard
                  currentPrice={currentPrice}
                  activeSymbol={symbol} // 이 줄을 반드시 추가해야 합니다.
                  status={sim.status}
                  closeMarketPosition={sim.closeMarketPosition}
                />
              </div>
              <div className="order-section" style={{ flex: 1 }}>
                {/* 🆕 주문 패널에 모든 기능과 리셋 함수 연결 */}
                <OrderPanel
                  currentPrice={currentPrice}
                  placeMarketOrder={sim.placeMarketOrder}
                  resetSimulation={sim.resetSimulation}
                  loading={sim.loading}
                  currentPosition={sim.currentPosition}
                  availableBalance={sim.status?.available_balance ?? 0}
                />
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

// --- 스타일 객체 (가독성을 위해 하단 배치) ---
const headerStyle: React.CSSProperties = {
  height: "60px",
  padding: "0 24px",
  backgroundColor: "#131722",
  borderBottom: "1px solid #2a2e39",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  flexShrink: 0,
};
const logoStyle: React.CSSProperties = {
  margin: 0,
  color: "#d1d4dc",
  fontSize: "1.1rem",
  fontWeight: 600,
};
const statusBadgeStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
  padding: "6px 12px",
  borderRadius: "20px",
};
const toolbarStyle: React.CSSProperties = {
  padding: "12px 24px",
  backgroundColor: "#131722",
  borderBottom: "1px solid #2a2e39",
  display: "flex",
  gap: "20px",
  alignItems: "center",
  flexShrink: 0,
};
const filterGroupStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
};
const labelStyle: React.CSSProperties = {
  color: "#848e9c",
  fontSize: "0.85rem",
};
const selectStyle: React.CSSProperties = {
  backgroundColor: "#1e222d",
  color: "#d1d4dc",
  border: "1px solid #2a2e39",
  padding: "6px 12px",
  borderRadius: "6px",
  outline: "none",
  cursor: "pointer",
  fontSize: "0.85rem",
};
const btnStyle: React.CSSProperties = {
  backgroundColor: "#2962FF",
  color: "#ffffff",
  border: "none",
  padding: "6px 16px",
  borderRadius: "6px",
  cursor: "pointer",
  fontSize: "0.85rem",
  fontWeight: 600,
};
const layerToggleStyle: React.CSSProperties = {
  padding: "8px 24px",
  backgroundColor: "#131722",
  borderBottom: "1px solid #2a2e39",
  display: "flex",
  gap: "10px",
  flexShrink: 0,
};
const checkboxLabelStyle: React.CSSProperties = {
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
const centerMsgStyle: React.CSSProperties = {
  margin: "auto",
  textAlign: "center",
  color: "#d1d4dc",
};

export default App;
