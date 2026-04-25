import { useEffect, useState } from "react";
import { fetchChartData, subscribeChartData } from "./api";
import TradingChart from "./TradingChart";

function App() {
  const [chartData, setChartData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLive, setIsLive] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // 1️⃣ 🎯 바이낸스 심볼 규격으로 기본값 변경 ("BTCUSDT")
  const [symbol, setSymbol] = useState<string>("BTCUSDT");
  const [timeframe, setTimeframe] = useState<string>("15m");
  const [days, setDays] = useState<number>(30); // 기본 로딩 속도를 위해 30일로 세팅

  // 1-1️⃣ 🎯 UI 상태도 바이낸스 규격으로!
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

  useEffect(() => {
    let ws: WebSocket | null = null;

    // 1️⃣ 새로운 심볼 로딩 시작 시 기존 상태 초기화 (BTC 잔상 제거)
    setIsLoading(true);
    setChartData(null);
    setError(null);
    setIsLive(false);

    // 2️⃣ 과거 데이터 로드
    fetchChartData(symbol, timeframe, days)
      .then((initialData) => {
        // 초기 데이터에는 심볼 정보를 포함해서 저장하는 것이 좋습니다.
        setChartData({ ...initialData, symbol });
        setIsLoading(false);

        // 3️⃣ 실시간 데이터 구독 (중첩 호출 제거)
        ws = subscribeChartData(symbol, timeframe, (newData) => {
          setIsLive(true);

          setChartData((prev: any) => {
            // 🎯 [핵심 1] 들어온 데이터 자체가 없거나 심볼 정보가 없으면 무시
            if (!newData || !newData.candles || newData.candles.length === 0)
              return prev;

            // 🎯 [핵심 2] 현재 보고 있는 심볼과 데이터의 심볼이 다르면 "병합"하지 않고 "교체"
            // 백엔드에서 newData.symbol을 보내준다는 가정하에 작동합니다.
            if (!prev || prev.symbol !== symbol || newData.symbol !== symbol) {
              console.log(
                `[System] Symbol Changed or Mismatch: ${symbol}. Resetting state.`,
              );
              return { ...newData, symbol }; // 기존 BTC 데이터(prev)를 버리고 ETH(newData)로 완전히 갈아치움
            }

            // 🎯 [핵심 3] 가격 범위 안전장치 (ETH인데 비정상적으로 높은 가격 차단)
            const lastPrice = newData.candles[newData.candles.length - 1].close;
            if (symbol === "ETHUSDT" && lastPrice > 10000) {
              console.warn("BTC data detected in ETH channel. Blocked.");
              return prev; // 병합하지 않고 기존 상태 유지
            }

            // 이후 데이터 병합 로직 수행 (심볼이 확실히 일치할 때만 실행됨) [cite: 508]
            const candleMap = new Map();
            prev.candles.forEach((c: any) => candleMap.set(c.time, c));
            newData.candles.forEach((c: any) => candleMap.set(c.time, c));
            const mergedCandles = Array.from(candleMap.values()).sort(
              (a, b) => a.time - b.time,
            );

            // 지표 병합 (kijun, rsi, macd_line 등) [cite: 706, 828]
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

            // 마커 병합 (master_long, master_short 등) [cite: 559, 618]
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
        console.error(err);
        setError("데이터 로드 실패. 서버 상태를 확인하세요.");
        setIsLoading(false);
      });

    // 4️⃣ 클린업: 심볼 변경 시 이전 웹소켓 연결 종료
    return () => {
      if (ws) {
        console.log(`Closing connection for ${symbol}`);
        ws.close();
      }
    };
  }, [symbol, timeframe, days]);

  // 스타일 생략 (기존과 동일하게 유지하시면 됩니다)
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
      }}
    >
      {/* 헤더 생략 (기존과 동일) */}
      <header
        style={{
          height: "60px",
          padding: "0 24px",
          backgroundColor: "#131722",
          borderBottom: "1px solid #2a2e39",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        {/* 생략... */}
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
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: "#848e9c", fontSize: "0.85rem" }}>Market:</span>
          {/* 🎯 바이낸스 심볼 벨류 변경 */}
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
            <h3 style={{ color: "#ef5350" }}>Connection Failed</h3>
            <p style={{ color: "#a3a6af" }}>{error}</p>
          </div>
        ) : isLoading || !chartData ? (
          <div>LOADING...</div>
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
            {/* 🎯 TradingChart에 현재 심볼 전달 */}
            <TradingChart
              key={`${symbol}-${timeframe}`}
              data={chartData}
              settings={visibleLayers}
              symbol={symbol}
            />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
