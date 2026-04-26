import React, { useState, useEffect, useRef } from "react";
import { analysisApi } from "../api";

interface ReplayControlProps {
  symbol: string;
  timeframe: string;
}

export const ReplayControl: React.FC<ReplayControlProps> = ({
  symbol,
  timeframe,
}) => {
  const [logs, setLogs] = useState<string[]>([]);
  const [days, setDays] = useState<number>(365); // [수정] 기본값을 365로 변경
  const [isSimulating, setIsSimulating] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

  const logEndRef = useRef<HTMLDivElement>(null);
  const socketRef = useRef<WebSocket | null>(null);

  // 1. 실시간 로그 수신을 위한 웹소켓 연결
  useEffect(() => {
    let reconnectTimeout: number;

    const connectSocket = () => {
      const url = analysisApi.getLogSocketUrl();
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log("🟢 시뮬레이션 로그 소켓 연결 성공");
      };

      ws.onmessage = (event) => {
        setLogs((prev) => [...prev, event.data].slice(-100));
      };

      ws.onclose = () => {
        console.log("⚪ 로그 소켓 연결 종료 (재연결 시도 중...)");
        // 컴포넌트가 언마운트되지 않았다면 3초 후 재연결
        reconnectTimeout = window.setTimeout(connectSocket, 3000);
      };

      ws.onerror = (err) => {
        console.error("🔴 로그 소켓 에러:", err);
        ws.close();
      };

      socketRef.current = ws;
    };

    connectSocket();

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      socketRef.current?.close();
    };
  }, []);

  // 2. 새 로그 추가 시 자동 스크롤
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // 3. 전체 시뮬레이션 실행 (e.preventDefault 추가)
  const handleStartSimulation = async (e: React.MouseEvent) => {
    e.preventDefault(); // [추가] 브라우저 새로고침/이벤트 전파 방지
    if (isSimulating) return;

    setIsSimulating(true);
    setLogs((prev) => [...prev, `[${symbol}] 전체 시뮬레이션 요청 중...`]);

    try {
      await analysisApi.runFullSimulation(symbol, timeframe);
    } catch (error) {
      setLogs((prev) => [...prev, "시뮬레이션 실행 요청 실패"]);
    } finally {
      setIsSimulating(false);
    }
  };

  // 4. 과거 데이터 동기화 (e.preventDefault 추가)
  const handleSyncHistorical = async (e: React.MouseEvent) => {
    e.preventDefault(); // [추가]
    if (isSyncing) return;

    setIsSyncing(true);
    setLogs((prev) => [...prev, ` ${symbol} ${days}일치 데이터 수집 시작...`]);

    try {
      await analysisApi.syncHistoricalData(symbol, timeframe, days);
    } catch (error) {
      setLogs((prev) => [...prev, "데이터 동기화 요청 실패"]);
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
        <div style={inputGroupStyle}>
          <span style={labelStyle}>과거 데이터 (일):</span>
          <input
            type="number"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            style={inputStyle}
          />
          <button
            type="button" // [명시]
            onClick={handleSyncHistorical}
            disabled={isSyncing}
            style={isSyncing ? disabledBtnStyle : syncBtnStyle}
          >
            {isSyncing ? "수집 중..." : "데이터 저장"}
          </button>
        </div>

        <div style={{ display: "flex", gap: "10px" }}>
          <button
            type="button" // [명시]
            onClick={handleStartSimulation}
            disabled={isSimulating}
            style={isSimulating ? disabledBtnStyle : runBtnStyle}
          >
            {isSimulating ? "계산 중..." : "전체 시뮬레이션 실행"}
          </button>
          <button type="button" onClick={clearLogs} style={clearBtnStyle}>
            로그 지우기
          </button>
        </div>
      </div>

      <div style={terminalStyle}>
        <div style={terminalHeaderStyle}>
          <span>Real-time Strategy Optimizer Logs</span>
          <span style={{ color: "#848e9c" }}>
            {symbol} | {timeframe}
          </span>
        </div>
        <div style={logAreaStyle}>
          {logs.length === 0 && (
            <div style={{ color: "#555" }}>
              준비 완료. 버튼을 눌러 작업을 시작하세요.
            </div>
          )}
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

// --- 스타일 정의는 기존과 동일하게 유지 ---
const containerStyle: React.CSSProperties = {
  padding: "20px 24px",
  backgroundColor: "#131722",
  display: "flex",
  flexDirection: "column",
  gap: "15px",
};

const controlBarStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
};

const terminalStyle: React.CSSProperties = {
  backgroundColor: "#000",
  borderRadius: "8px",
  border: "1px solid #2a2e39",
  display: "flex",
  flexDirection: "column",
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
  height: "250px",
  padding: "15px",
  overflowY: "auto",
  fontFamily: "'Fira Code', 'Courier New', monospace",
  fontSize: "0.85rem",
  lineHeight: "1.5",
};

const getLogItemStyle = (log: string): React.CSSProperties => {
  let color = "#d1d4dc";
  if (log.includes("TAKE_PROFIT")) color = "#26a69a";
  if (log.includes("STOP_LOSS")) color = "#ef5350";
  if (log.includes("불타기")) color = "#ffa726";
  if (log.includes("[INFO]")) color = "#2962FF";
  if (log.includes("[진행도]")) color = "#ffa726"; // 진행도 로그 색상 추가
  return { color, marginBottom: "4px" };
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
