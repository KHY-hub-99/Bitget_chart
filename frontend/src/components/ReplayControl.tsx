import React, { useState, useEffect, useRef } from "react";
import { analysisApi } from "../api";

interface ReplayControlProps {
  initialSymbol: string;
  initialTimeframe: string;
}

export const ReplayControl: React.FC<ReplayControlProps> = ({
  initialSymbol,
  initialTimeframe,
}) => {
  const [logs, setLogs] = useState<string[]>([]);
  const [days, setDays] = useState<number>(365);

  const [selectedSymbol, setSelectedSymbol] = useState<string>(initialSymbol);
  const [selectedTimeframe, setSelectedTimeframe] =
    useState<string>(initialTimeframe);

  const [isSimulating, setIsSimulating] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

  const logEndRef = useRef<HTMLDivElement>(null);
  const socketRef = useRef<WebSocket | null>(null);

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

  const handleStartSimulation = async (e: React.MouseEvent) => {
    e.preventDefault();
    if (isSimulating) return;

    setIsSimulating(true);
    setLogs((prev) => [
      ...prev,
      `[${selectedSymbol} | ${selectedTimeframe}] 전체 시뮬레이션 시작...`,
    ]);

    try {
      await analysisApi.runFullSimulation(selectedSymbol, selectedTimeframe);
    } catch (error) {
      setLogs((prev) => [...prev, "시뮬레이션 실행 실패"]);
    } finally {
      setIsSimulating(false);
    }
  };

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
        {/* 왼쪽: 컨트롤 그룹 */}
        <div style={inputGroupStyle}>
          <div style={fieldGroup}>
            <span style={labelStyle}>Target</span>
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
          </div>

          <div style={fieldGroup}>
            <span style={labelStyle}>Range(Days)</span>
            <input
              type="number"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              style={inputStyle}
            />
          </div>

          <button
            type="button"
            onClick={handleSyncHistorical}
            disabled={isSyncing}
            style={isSyncing ? disabledBtnStyle : syncBtnStyle}
          >
            {isSyncing ? "Syncing..." : "데이터 저장"}
          </button>
        </div>

        {/* 오른쪽: 액션 버튼 그룹 */}
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
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <div style={pulseDot}></div>
            <span style={{ fontWeight: 600 }}>STRATEGY OPTIMIZER LOGS</span>
          </div>
          <span
            style={{ color: "#2962FF", fontWeight: 700, fontSize: "0.7rem" }}
          >
            CONFIG: {selectedSymbol} / {selectedTimeframe}
          </span>
        </div>
        <div style={logAreaStyle}>
          {logs.length === 0 && (
            <div style={{ color: "#363c4e", fontStyle: "italic" }}>
              대기 중... 작업을 시작하면 실시간 로그가 표시됩니다.
            </div>
          )}
          {logs.map((log, i) => (
            <div key={i} style={getLogItemStyle(log)}>
              <span style={{ opacity: 0.5, marginRight: "8px" }}>
                [{i + 1}]
              </span>
              {log}
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
};

// --- [ 블랙 & 블루 세련된 스타일 설정 ] ---

const containerStyle: React.CSSProperties = {
  padding: "24px",
  backgroundColor: "#131722",
  display: "flex",
  flexDirection: "column",
  gap: "20px",
  borderBottom: "1px solid #2a2e39",
};

const controlBarStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-end",
};

const inputGroupStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "flex-end",
  gap: "20px",
};

const fieldGroup: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "8px",
};

const labelStyle: React.CSSProperties = {
  color: "#848e9c",
  fontSize: "0.7rem",
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.5px",
};

const innerSelectStyle: React.CSSProperties = {
  backgroundColor: "#1e222d",
  color: "#fff",
  border: "1px solid #363c4e",
  padding: "8px 12px",
  borderRadius: "6px",
  fontSize: "0.85rem",
  fontWeight: 600,
  outline: "none",
  cursor: "pointer",
  marginRight: "4px",
};

const inputStyle: React.CSSProperties = {
  backgroundColor: "#1e222d",
  color: "#fff",
  border: "1px solid #363c4e",
  padding: "8px 12px",
  borderRadius: "6px",
  width: "80px",
  fontSize: "0.85rem",
  fontWeight: 600,
  outline: "none",
};

// 버튼 기본 스타일
const baseBtn: React.CSSProperties = {
  border: "none",
  padding: "10px 20px",
  borderRadius: "6px",
  cursor: "pointer",
  fontSize: "0.85rem",
  fontWeight: 700,
  transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};

const runBtnStyle: React.CSSProperties = {
  ...baseBtn,
  backgroundColor: "#2962FF",
  color: "#fff",
  boxShadow: "0 4px 12px rgba(41, 98, 255, 0.3)",
};

const syncBtnStyle: React.CSSProperties = {
  ...baseBtn,
  backgroundColor: "#f6465d",
  color: "#fff",
  boxShadow: "0 4px 12px rgba(246, 70, 93, 0.2)",
};

const clearBtnStyle: React.CSSProperties = {
  ...baseBtn,
  backgroundColor: "#2b3139",
  color: "#d1d4dc",
  border: "1px solid rgba(255,255,255,0.05)",
};

const disabledBtnStyle: React.CSSProperties = {
  ...baseBtn,
  backgroundColor: "#1e222d",
  color: "#5d6673",
  cursor: "not-allowed",
  boxShadow: "none",
};

// 터미널 스타일
const terminalStyle: React.CSSProperties = {
  backgroundColor: "#000",
  borderRadius: "10px",
  border: "1px solid #2a2e39",
  overflow: "hidden",
  boxShadow: "inset 0 0 20px rgba(0,0,0,0.5)",
};

const terminalHeaderStyle: React.CSSProperties = {
  padding: "10px 16px",
  backgroundColor: "#1e222d",
  borderBottom: "1px solid #2a2e39",
  fontSize: "0.7rem",
  color: "#d1d4dc",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  letterSpacing: "1px",
};

const logAreaStyle: React.CSSProperties = {
  height: "220px",
  padding: "16px",
  overflowY: "auto",
  fontFamily: "'Fira Code', 'IBM Plex Mono', monospace",
  fontSize: "0.8rem",
  lineHeight: "1.6",
  backgroundColor: "#050505",
};

const pulseDot: React.CSSProperties = {
  width: "6px",
  height: "6px",
  backgroundColor: "#2962FF",
  borderRadius: "50%",
  boxShadow: "0 0 8px #2962FF",
};

const getLogItemStyle = (log: string): React.CSSProperties => {
  let color = "#d1d4dc";
  if (log.includes("TAKE_PROFIT")) color = "#26a69a";
  if (log.includes("STOP_LOSS")) color = "#ef5350";
  if (log.includes("[진행도]")) color = "#ffa726";
  if (log.includes("성공") || log.includes("완료")) color = "#2962FF";
  return { color, marginBottom: "6px", display: "flex" };
};
