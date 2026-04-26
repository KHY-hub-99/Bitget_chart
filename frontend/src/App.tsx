import { useEffect, useState, useRef, useCallback, useMemo, memo } from "react";
import { fetchChartData, subscribeChartData } from "./api";
import TradingChart from "./TradingChart";

// 시뮬레이션 컴포넌트 및 훅 임포트
import { OrderPanel } from "./components/OrderPanel";
import { PositionBoard } from "./components/PositionBoard";
import { useSimulation } from "./hooks/useSimulation";
import { Toast } from "./components/Toast";

// 신규 컴포넌트 임포트
import { ReplayControl } from "./components/ReplayControl";
import SimulationResultsPage from "./components/SimulationResultsPage";

// [최적화] 리렌더링 방지를 위한 메모이제이션
const MemoizedTradingChart = memo(TradingChart);
const MemoizedResultsPage = memo(SimulationResultsPage);
const MemoizedReplayControl = memo(ReplayControl);

function App() {
  // [수정] 뷰 모드 관리: LocalStorage를 사용하여 새로고침 시에도 마지막 탭 유지
  const [view, setView] = useState<"chart" | "results">(() => {
    return (
      (localStorage.getItem("activeTab") as "chart" | "results") || "chart"
    );
  });

  useEffect(() => {
    localStorage.setItem("activeTab", view);
  }, [view]);

  const [chartData, setChartData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLive, setIsLive] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [currentPrice, setCurrentPrice] = useState<number>(0);

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
  const [days, setDays] = useState<number>(365); // 기본 데이터 범위 365일

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
    activePositions,
  } = useSimulation(symbol);

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
        setError("데이터 로드 실패");
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

  const handleModeChange = async (mode: "ONE_WAY" | "HEDGE") => {
    try {
      await changePositionMode(mode);
    } catch (err: any) {
      const msg = err.response?.data?.detail || "모드 변경 실패";
      showToast(msg, "error");
    }
  };

  return (
    <div className="app-container" style={appContainerStyle}>
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      {/* 헤더 섹션 */}
      <header style={headerStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: "30px" }}>
          <h1 style={logoStyle}>
            Crypto Trading <span style={{ color: "#2962FF" }}>Master</span>
          </h1>
          <nav
            style={{
              display: "flex",
              gap: "8px",
              backgroundColor: "#0b0e14",
              padding: "4px",
              borderRadius: "8px",
            }}
          >
            <button
              style={view === "chart" ? activeNavBtnStyle : navBtnStyle}
              onClick={() => setView("chart")}
            >
              차트 분석
            </button>
            <button
              style={view === "results" ? activeNavBtnStyle : navBtnStyle}
              onClick={() => setView("results")}
            >
              전략 랭킹
            </button>
          </nav>
        </div>

        <div
          style={{
            ...statusBadgeStyle,
            backgroundColor: isLive
              ? "rgba(38, 166, 154, 0.1)"
              : "rgba(239, 83, 80, 0.1)",
          }}
        >
          <div
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              backgroundColor: isLive ? "#26a69a" : "#ef5350",
              boxShadow: isLive ? "0 0 8px #26a69a" : "none",
            }}
          ></div>
          <span
            style={{
              color: isLive ? "#26a69a" : "#ef5350",
              fontSize: "0.75rem",
              fontWeight: 700,
              letterSpacing: "0.5px",
            }}
          >
            {isLive ? "LIVE" : "OFFLINE"}
          </span>
        </div>
      </header>

      {/* 메인 콘텐츠 영역 */}
      <main className="app-main" style={mainStyle}>
        {view === "chart" ? (
          /* --- [1] 차트 분석 뷰 --- */
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              flex: 1,
              overflow: "hidden",
            }}
          >
            <div style={toolbarStyle}>
              <div style={filterGroupStyle}>
                <span style={labelStyle}>Market</span>
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
                <span style={labelStyle}>Time</span>
                <select
                  style={selectStyle}
                  value={inputTimeframe}
                  onChange={(e) => setInputTimeframe(e.target.value)}
                >
                  <option value="15m">15m</option>
                  <option value="1h">1h</option>
                  <option value="4h">4h</option>
                  <option value="1d">1d</option>
                  <option value="1w">1w</option>
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
                    style={{ cursor: "pointer" }}
                  />
                  {key.toUpperCase()}
                </label>
              ))}
            </div>

            <div
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
                <div style={centerMsgStyle}>
                  <div className="loading-spinner"></div>
                  <p style={{ marginTop: "10px", color: "#848e9c" }}>
                    데이터를 불러오는 중...
                  </p>
                </div>
              ) : (
                <>
                  <div
                    className="chart-section"
                    style={{ flex: 2, minHeight: "450px" }}
                  >
                    <MemoizedTradingChart
                      key={`${symbol}-${timeframe}`}
                      data={chartData}
                      settings={visibleLayers}
                      symbol={symbol}
                      activePositions={activePositions}
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
                        changePositionMode={handleModeChange}
                        positionMode={status?.position_mode ?? "ONE_WAY"}
                        loading={loading}
                        activePositions={activePositions}
                        availableBalance={status?.available_balance ?? 0}
                      />
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        ) : (
          /* --- [2] 전략 랭킹 및 시뮬레이션 제어 뷰 --- */
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              overflowY: "auto",
              backgroundColor: "#0b0e14",
            }}
          >
            {/* initialSymbol, initialTimeframe으로 전달하여 초기값 설정 */}
            <MemoizedReplayControl
              initialSymbol={symbol}
              initialTimeframe={timeframe}
            />

            <MemoizedResultsPage />
          </div>
        )}
      </main>
    </div>
  );
}

// --- [ 세련된 블랙 & 블루 스타일 설정 ] ---

const appContainerStyle: React.CSSProperties = {
  width: "100vw",
  height: "100vh",
  backgroundColor: "#0b0e14",
  display: "flex",
  flexDirection: "column",
  overflow: "hidden",
  fontFamily: "'Inter', sans-serif",
};

const headerStyle: React.CSSProperties = {
  height: "64px",
  padding: "0 24px",
  backgroundColor: "#131722",
  borderBottom: "1px solid #2a2e39",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  flexShrink: 0,
  boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
};

const logoStyle: React.CSSProperties = {
  margin: 0,
  color: "#ffffff",
  fontSize: "1.2rem",
  fontWeight: 800,
  letterSpacing: "-0.5px",
};

const navBtnStyle: React.CSSProperties = {
  backgroundColor: "transparent",
  color: "#848e9c",
  border: "none",
  padding: "8px 20px",
  borderRadius: "6px",
  cursor: "pointer",
  fontSize: "0.85rem",
  fontWeight: 600,
  transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
};

const activeNavBtnStyle: React.CSSProperties = {
  ...navBtnStyle,
  color: "#ffffff",
  backgroundColor: "#2962FF",
  boxShadow: "0 2px 8px rgba(41, 98, 255, 0.4)",
};

const mainStyle: React.CSSProperties = {
  flex: 1,
  display: "flex",
  flexDirection: "column",
  overflow: "hidden",
};

const toolbarStyle: React.CSSProperties = {
  padding: "12px 24px",
  backgroundColor: "#131722",
  borderBottom: "1px solid #2a2e39",
  display: "flex",
  gap: "24px",
  alignItems: "center",
  flexShrink: 0,
};

const filterGroupStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "10px",
};

const labelStyle: React.CSSProperties = {
  color: "#848e9c",
  fontSize: "0.75rem",
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.5px",
};

const selectStyle: React.CSSProperties = {
  backgroundColor: "#1e222d",
  color: "#ffffff",
  border: "1px solid #363c4e",
  padding: "6px 12px",
  borderRadius: "6px",
  outline: "none",
  cursor: "pointer",
  fontSize: "0.85rem",
  fontWeight: 600,
  transition: "border-color 0.2s",
};

const btnStyle: React.CSSProperties = {
  backgroundColor: "#2962FF",
  color: "#ffffff",
  border: "none",
  padding: "8px 20px",
  borderRadius: "6px",
  cursor: "pointer",
  fontSize: "0.85rem",
  fontWeight: 700,
  transition: "all 0.2s",
  boxShadow: "0 4px 12px rgba(41, 98, 255, 0.3)",
};

const layerToggleStyle: React.CSSProperties = {
  padding: "8px 24px",
  backgroundColor: "#131722",
  borderBottom: "1px solid #2a2e39",
  display: "flex",
  gap: "12px",
  flexShrink: 0,
};

const checkboxLabelStyle: React.CSSProperties = {
  color: "#d1d4dc",
  fontSize: "0.75rem",
  fontWeight: 600,
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  gap: "6px",
  padding: "4px 10px",
  borderRadius: "4px",
  backgroundColor: "#1e222d",
  border: "1px solid #2a2e39",
  transition: "background-color 0.2s",
};

const statusBadgeStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
  padding: "6px 14px",
  borderRadius: "20px",
  border: "1px solid rgba(255,255,255,0.05)",
};

const bottomSectionStyle: React.CSSProperties = {
  flex: 1,
  display: "flex",
  borderTop: "1px solid #2a2e39",
  minHeight: "250px",
  backgroundColor: "#131722",
};

const centerMsgStyle: React.CSSProperties = {
  margin: "auto",
  textAlign: "center",
  color: "#d1d4dc",
};

export default App;
