import { useEffect, useState, useRef, useCallback } from "react";
import { fetchChartData, subscribeChartData } from "./api";
import TradingChart from "./TradingChart";

// 시뮬레이션 컴포넌트 및 훅 임포트
import { OrderPanel } from "./components/OrderPanel";
import { PositionBoard } from "./components/PositionBoard";
import { useSimulation } from "./hooks/useSimulation";
import { Toast } from "./components/Toast"; // 🌟 추가

function App() {
  const [chartData, setChartData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLive, setIsLive] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [currentPrice, setCurrentPrice] = useState<number>(0);

  // 🌟 Toast 상태 관리
  const [toast, setToast] = useState<{
    message: string;
    type: "success" | "error" | "info";
  } | null>(null);
  const showToast = useCallback(
    (message: string, type: "success" | "error" | "info" = "info") => {
      setToast({ message, type });
    },
    [],
  );

  const [symbol, setSymbol] = useState<string>("BTCUSDT");
  const [timeframe, setTimeframe] = useState<string>("15m");
  const [days, setDays] = useState<number>(30);

  const [inputSymbol, setInputSymbol] = useState<string>("BTCUSDT");
  const [inputTimeframe, setInputTimeframe] = useState<string>("15m");

  const {
    status,
    loading,
    placeMarketOrder,
    closeMarketPosition,
    checkTick,
    resetSimulation,
    changePositionMode,
    currentPosition,
  } = useSimulation(symbol);

  // 🌟 무한 새로고침 방지를 위한 Ref 패턴
  const checkTickRef = useRef(checkTick);
  useEffect(() => {
    checkTickRef.current = checkTick;
  }, [checkTick]);

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

          if (newData.candles && newData.candles.length > 0) {
            const lastCandle = newData.candles[newData.candles.length - 1];
            const lastPrice = lastCandle.close;

            setCurrentPrice(lastPrice);
            if (checkTickRef.current) {
              checkTickRef.current(lastPrice);
            }
          }

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
        setError("데이터 로드 실패.");
        setIsLoading(false);
      });

    return () => {
      isActive = false;
      if (ws) ws.close();
    };
  }, [symbol, timeframe, days]);

  const handleApplySettings = () => {
    setSymbol(inputSymbol);
    setTimeframe(inputTimeframe);
  };

  // 🌟 모드 변경 핸들러 (Toast 연동)
  const handleModeChange = async (mode: "ONE_WAY" | "HEDGE") => {
    try {
      await changePositionMode(mode);
      // 성공 시에는 별도 알림 없이 UI만 바뀌도록 기획됨
    } catch (err: any) {
      const msg = err.response?.data?.detail || "모드 변경에 실패했습니다.";
      showToast(msg, "error");
    }
  };

  return (
    <div className="app-container" style={appContainerStyle}>
      {/* 🌟 Toast 렌더링 */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      <header style={headerStyle}>
        <h1 style={logoStyle}>
          Crypto Trading <span style={{ color: "#2962FF" }}>Master</span>
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
            {isLive ? "LIVE" : "OFFLINE"}
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
          </select>
        </div>
        <button style={btnStyle} onClick={handleApplySettings}>
          적용
        </button>
      </div>

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

      <main className="app-main" style={mainStyle}>
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

            <div className="bottom-section" style={bottomSectionStyle}>
              <div
                className="position-section"
                style={{ flex: 1.5, borderRight: "1px solid #2a2e39" }}
              >
                <PositionBoard
                  currentPrice={currentPrice}
                  activeSymbol={symbol}
                  status={status}
                  closeMarketPosition={closeMarketPosition}
                />
              </div>

              <div className="order-section" style={{ flex: 1 }}>
                <OrderPanel
                  currentPrice={currentPrice}
                  placeMarketOrder={placeMarketOrder}
                  resetSimulation={resetSimulation}
                  // 🌟 수정: 직접 changePositionMode 대신 handleModeChange 사용
                  changePositionMode={handleModeChange}
                  positionMode={status?.position_mode ?? "ONE_WAY"}
                  loading={loading}
                  currentPosition={currentPosition}
                  availableBalance={status?.available_balance ?? 0}
                />
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

// --- 스타일 객체 (기존 유지) ---
const appContainerStyle: React.CSSProperties = {
  width: "100vw",
  height: "100vh",
  backgroundColor: "#0b0e14",
  display: "flex",
  flexDirection: "column",
  overflow: "hidden",
};
const mainStyle: React.CSSProperties = {
  flex: 1,
  display: "flex",
  flexDirection: "column",
  overflow: "hidden",
};
const bottomSectionStyle: React.CSSProperties = {
  flex: 1,
  display: "flex",
  borderTop: "1px solid #2a2e39",
  minHeight: "250px",
};
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
