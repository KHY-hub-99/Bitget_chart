import React, { useState, useEffect, useRef } from "react";
import { analysisApi } from "../api";

interface ReplayControlProps {
  initialSymbol: string; // App에서 넘겨주는 기본값
  initialTimeframe: string; // App에서 넘겨주는 기본값
}

export const ReplayControl: React.FC<ReplayControlProps> = ({
  initialSymbol,
  initialTimeframe,
}) => {
  const [logs, setLogs] = useState<string[]>([]);
  const [days, setDays] = useState<number>(365);

  // [추가] 시뮬레이션 및 데이터 저장을 위한 독립적 선택 상태
  const [selectedSymbol, setSelectedSymbol] = useState<string>(initialSymbol);
  const [selectedTimeframe, setSelectedTimeframe] =
    useState<string>(initialTimeframe);

  const [isSimulating, setIsSimulating] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

  const logEndRef = useRef<HTMLDivElement>(null);
  const socketRef = useRef<WebSocket | null>(null);

  // 실시간 로그 웹소켓 연결
  useEffect(() => {
    let reconnectTimeout: number;
    const connectSocket = () => {
      const url = analysisApi.getLogSocketUrl();
      const ws = new WebSocket(url);
      ws.onmessage = (event) => {
        setLogs((prev) => [...prev, event.data].slice(-100));
      };
      ws.onclose = () => {
        reconnectTimeout = window.setTimeout(connectSocket, 3000);
      };
      socketRef.current = ws;
    };
    connectSocket();
    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      socketRef.current?.close();
    };
  }, []);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // 전체 시뮬레이션 실행 (선택된 symbol, timeframe 사용)
  const handleStartSimulation = async (e: React.MouseEvent) => {
    e.preventDefault();
    if (isSimulating) return;

    setIsSimulating(true);
    setLogs((prev) => [
      ...prev,
      `[${selectedSymbol} | ${selectedTimeframe}] 시뮬레이션 시작 요청...`,
    ]);

    try {
      await analysisApi.runFullSimulation(selectedSymbol, selectedTimeframe);
    } catch (error) {
      setLogs((prev) => [...prev, "시뮬레이션 실행 실패"]);
    } finally {
      setIsSimulating(false);
    }
  };

  // 과거 데이터 동기화 (선택된 symbol, timeframe 사용)
  const handleSyncHistorical = async (e: React.MouseEvent) => {
    e.preventDefault();
    if (isSyncing) return;

    setIsSyncing(true);
    setLogs((prev) => [
      ...prev,
      `${selectedSymbol} (${selectedTimeframe}) ${days}일치 데이터 저장 시작...`,
    ]);

    try {
      await analysisApi.syncHistoricalData(
        selectedSymbol,
        selectedTimeframe,
        days,
      );
    } catch (error) {
      setLogs((prev) => [...prev, "데이터 저장 실패"]);
    } finally {
      setIsSyncing(false);
    }
  };

  const clearLogs = (e: React.MouseEvent) => {
    e.preventDefault();
    setLogs([]);
  };

  return (
    <div style={containerStyle}>
      <div style={controlBarStyle}>
        {/* 대상 선택 영역 */}
        <div style={inputGroupStyle}>
          <span style={labelStyle}>대상:</span>
          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            style={innerSelectStyle}
          >
            <option value="BTCUSDT">BTCUSDT</option>
            <option value="ETHUSDT">ETHUSDT</option>
          </select>
          <select
            value={selectedTimeframe}
            onChange={(e) => setSelectedTimeframe(e.target.value)}
            style={innerSelectStyle}
          >
            <option value="15m">15m</option>
            <option value="1h">1h</option>
            <option value="4h">4h</option>
            <option value="1d">1d</option>
            <option value="1w">1w</option>
          </select>

          <span style={{ ...labelStyle, marginLeft: "10px" }}>기간(일):</span>
          <input
            type="number"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            style={inputStyle}
          />
          <button
            type="button"
            onClick={handleSyncHistorical}
            disabled={isSyncing}
            style={isSyncing ? disabledBtnStyle : syncBtnStyle}
          >
            {isSyncing ? "수집 중..." : "데이터 저장"}
          </button>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          <button
            type="button"
            onClick={handleStartSimulation}
            disabled={isSimulating}
            style={isSimulating ? disabledBtnStyle : runBtnStyle}
          >
            전체 시뮬레이션 실행
          </button>
          <button type="button" onClick={clearLogs} style={clearBtnStyle}>
            로그 지우기
          </button>
        </div>
      </div>

      {/* 로그 터미널 */}
      <div style={terminalStyle}>
        <div style={terminalHeaderStyle}>
          <span>Real-time Strategy Optimizer Logs</span>
          <span style={{ color: "#2962FF", fontWeight: "bold" }}>
            대상: {selectedSymbol} | {selectedTimeframe}
          </span>
        </div>
        <div style={logAreaStyle}>
          {logs.map((log, i) => (
            <div key={i} style={getLogItemStyle(log)}>
              {log}
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
};

// --- [스타일 추가 및 수정] ---
const innerSelectStyle: React.CSSProperties = {
  backgroundColor: "#1e222d",
  color: "#fff",
  border: "1px solid #2a2e39",
  padding: "5px 10px",
  borderRadius: "4px",
  fontSize: "0.85rem",
  outline: "none",
};

const containerStyle: React.CSSProperties = {
  padding: "20px 24px",
  backgroundColor: "#131722",
  display: "flex",
  flexDirection: "column",
  gap: "15px",
  borderBottom: "1px solid #2a2e39",
};

// ... 기존 스타일 코드들 (controlBarStyle, terminalStyle 등) 동일 유지
const controlBarStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
};
const terminalStyle: React.CSSProperties = {
  backgroundColor: "#000",
  borderRadius: "8px",
  border: "1px solid #2a2e39",
  overflow: "hidden",
};
const terminalHeaderStyle: React.CSSProperties = {
  padding: "8px 15px",
  backgroundColor: "#1e222d",
  borderBottom: "1px solid #2a2e39",
  fontSize: "0.75rem",
  color: "#d1d4dc",
  display: "flex",
  justifyContent: "space-between",
};
const logAreaStyle: React.CSSProperties = {
  height: "200px",
  padding: "15px",
  overflowY: "auto",
  fontFamily: "monospace",
  fontSize: "0.85rem",
};
const inputGroupStyle = { display: "flex", alignItems: "center", gap: "10px" };
const labelStyle = { color: "#848e9c", fontSize: "0.85rem" };
const inputStyle = {
  backgroundColor: "#1e222d",
  color: "#fff",
  border: "1px solid #2a2e39",
  padding: "6px 10px",
  borderRadius: "4px",
  width: "70px",
};
const baseBtn = {
  border: "none",
  padding: "8px 16px",
  borderRadius: "4px",
  cursor: "pointer",
  fontSize: "0.85rem",
  fontWeight: 600,
};
const syncBtnStyle = { ...baseBtn, backgroundColor: "#E91E63", color: "#fff" };
const runBtnStyle = { ...baseBtn, backgroundColor: "#2962FF", color: "#fff" };
const clearBtnStyle = {
  ...baseBtn,
  backgroundColor: "#363c4e",
  color: "#d1d4dc",
};
const disabledBtnStyle = {
  ...baseBtn,
  backgroundColor: "#555",
  color: "#888",
  cursor: "not-allowed",
};
const getLogItemStyle = (log: string): React.CSSProperties => {
  let color = "#d1d4dc";
  if (log.includes("TAKE_PROFIT")) color = "#26a69a";
  if (log.includes("STOP_LOSS")) color = "#ef5350";
  if (log.includes("[진행도]")) color = "#ffa726";
  return { color, marginBottom: "4px" };
};
