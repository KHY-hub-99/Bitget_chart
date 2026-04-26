import React, { useEffect, useState } from "react";
import { analysisApi, StrategyRank } from "../api";

const SimulationResultsPage: React.FC = () => {
  const [rankings, setRankings] = useState<StrategyRank[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  // 필터 상태
  const [symbol, setSymbol] = useState<string>("ALL");
  const [timeframe, setTimeframe] = useState<string>("ALL");

  const loadRankings = async () => {
    setLoading(true);
    try {
      // 선택된 필터값을 API로 전달
      const data = await analysisApi.getRanking(symbol, timeframe);
      setRankings(data);
    } catch (error) {
      console.error("랭킹 데이터 로드 실패:", error);
    } finally {
      setLoading(false);
    }
  };

  // 필터가 변경될 때마다 데이터 다시 불러오기
  useEffect(() => {
    loadRankings();
  }, [symbol, timeframe]);

  return (
    <div style={pageContainerStyle}>
      {/* 1. 상단 헤더 및 필터 영역 */}
      <div style={headerCardStyle}>
        <div>
          <h2 style={titleStyle}>전략 성과 랭킹 보드</h2>
          <p style={subtitleStyle}>
            최적의 수익성과 안정성을 가진 파라미터 조합을 탐색합니다.
          </p>
        </div>

        <div style={controlsContainerStyle}>
          <div style={filterGroupStyle}>
            <span style={labelStyle}>Symbol</span>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              style={selectStyle}
            >
              <option value="ALL">전체 심볼</option>
              <option value="BTCUSDT">BTCUSDT</option>
              <option value="ETHUSDT">ETHUSDT</option>
            </select>
          </div>

          <div style={filterGroupStyle}>
            <span style={labelStyle}>Timeframe</span>
            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              style={selectStyle}
            >
              <option value="ALL">전체 시간</option>
              <option value="1m">1m</option>
              <option value="5m">5m</option>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
            </select>
          </div>

          <button
            onClick={loadRankings}
            disabled={loading}
            style={loading ? disabledBtnStyle : refreshBtnStyle}
          >
            {loading ? "데이터 갱신 중..." : "새로고침"}
          </button>
        </div>
      </div>

      {/* 2. 랭킹 테이블 영역 */}
      <div style={tableWrapperStyle}>
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>Rank</th>
              <th style={thStyle}>Mode / Lev</th>
              <th style={thStyle}>TP / SL Ratio</th>
              <th style={thStyle}>승/패 (청산)</th>
              <th style={thStyle}>승률</th>
              <th style={thStyle}>Avg MDD</th>
              <th style={thStyle}>Max Drawdown</th>
              <th style={{ ...thStyle, textAlign: "right" }}>Total PNL</th>
            </tr>
          </thead>
          <tbody>
            {rankings.length === 0 ? (
              <tr>
                <td colSpan={8} style={emptyTdStyle}>
                  {loading
                    ? "데이터를 분석 중입니다..."
                    : "조건에 맞는 시뮬레이션 데이터가 없습니다."}
                </td>
              </tr>
            ) : (
              rankings.map((rank, index) => {
                const winRate =
                  rank.total_trades > 0
                    ? ((rank.wins / rank.total_trades) * 100).toFixed(1)
                    : "0.0";

                return (
                  <tr
                    key={index}
                    style={index < 3 ? topRankRowStyle : rowStyle}
                  >
                    <td style={tdStyle}>
                      {index === 0
                        ? "🥇"
                        : index === 1
                          ? "🥈"
                          : index === 2
                            ? "🥉"
                            : `${index + 1}`}
                    </td>
                    <td style={tdStyle}>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                      >
                        <span
                          style={
                            rank.position_mode === "HEDGE"
                              ? hedgeBadgeStyle
                              : oneWayBadgeStyle
                          }
                        >
                          {rank.position_mode}
                        </span>
                        <span style={leverageStyle}>{rank.leverage}x</span>
                      </div>
                    </td>
                    <td style={tdStyle}>
                      <span style={{ color: "#26a69a", fontWeight: "bold" }}>
                        {(rank.tp_ratio * 100).toFixed(1)}%
                      </span>
                      <span style={{ color: "#848e9c", margin: "0 4px" }}>
                        /
                      </span>
                      <span style={{ color: "#ef5350", fontWeight: "bold" }}>
                        {(rank.sl_ratio * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td style={tdStyle}>
                      <span style={{ color: "#26a69a" }}>{rank.wins}</span> /
                      <span style={{ color: "#848e9c" }}> {rank.losses}</span>
                      {rank.liquidations > 0 && (
                        <span
                          style={{
                            color: "#ef5350",
                            fontSize: "0.75rem",
                            marginLeft: "4px",
                          }}
                        >
                          (청산 {rank.liquidations})
                        </span>
                      )}
                    </td>
                    <td style={tdStyle}>
                      <span
                        style={{
                          color: Number(winRate) >= 50 ? "#26a69a" : "#d1d4dc",
                        }}
                      >
                        {winRate}%
                      </span>
                    </td>
                    <td
                      style={{
                        ...tdStyle,
                        color: rank.avg_mdd_rate < -20 ? "#ef5350" : "#d1d4dc",
                      }}
                    >
                      {rank.avg_mdd_rate?.toFixed(2)}%
                    </td>
                    <td
                      style={{
                        ...tdStyle,
                        color: rank.max_drawdown < -50 ? "#ef5350" : "#ffa726",
                        fontWeight: "bold",
                      }}
                    >
                      {rank.max_drawdown?.toFixed(2)}%
                    </td>
                    <td
                      style={{
                        ...tdStyle,
                        textAlign: "right",
                        color: rank.total_pnl >= 0 ? "#26a69a" : "#ef5350",
                        fontWeight: "bold",
                        fontSize: "1rem",
                      }}
                    >
                      ${rank.total_pnl.toLocaleString()}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// --- [ 세련된 스타일 정의 ] ---
const pageContainerStyle: React.CSSProperties = {
  padding: "24px",
  backgroundColor: "#0b0e14",
  flex: 1,
  color: "#d1d4dc",
  minHeight: "100vh",
};

const headerCardStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  backgroundColor: "#131722",
  padding: "20px 24px",
  borderRadius: "12px",
  border: "1px solid #2a2e39",
  marginBottom: "24px",
  boxShadow: "0 4px 6px rgba(0, 0, 0, 0.3)",
};

const titleStyle: React.CSSProperties = {
  margin: 0,
  fontSize: "1.4rem",
  color: "#fff",
};
const subtitleStyle: React.CSSProperties = {
  margin: "6px 0 0 0",
  fontSize: "0.85rem",
  color: "#848e9c",
};

const controlsContainerStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "16px",
};

const filterGroupStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
  backgroundColor: "#1e222d",
  padding: "6px 12px",
  borderRadius: "8px",
  border: "1px solid #2a2e39",
};

const labelStyle: React.CSSProperties = {
  fontSize: "0.8rem",
  color: "#848e9c",
  fontWeight: "bold",
};

const selectStyle: React.CSSProperties = {
  backgroundColor: "transparent",
  color: "#fff",
  border: "none",
  outline: "none",
  cursor: "pointer",
  fontSize: "0.9rem",
  fontWeight: 600,
};

const tableWrapperStyle: React.CSSProperties = {
  backgroundColor: "#131722",
  borderRadius: "12px",
  border: "1px solid #2a2e39",
  overflow: "hidden",
  boxShadow: "0 4px 6px rgba(0, 0, 0, 0.3)",
};

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: "0.9rem",
};

const thStyle: React.CSSProperties = {
  backgroundColor: "#181a20",
  padding: "16px",
  textAlign: "left",
  borderBottom: "1px solid #2a2e39",
  color: "#848e9c",
  fontWeight: 600,
};

const tdStyle: React.CSSProperties = {
  padding: "16px",
  borderBottom: "1px solid #2a2e39",
  verticalAlign: "middle",
};

const rowStyle: React.CSSProperties = { transition: "background-color 0.2s" };
const topRankRowStyle: React.CSSProperties = {
  ...rowStyle,
  backgroundColor: "rgba(41, 98, 255, 0.08)", // 상위 랭크 하이라이트
};

const emptyTdStyle: React.CSSProperties = {
  padding: "60px",
  textAlign: "center",
  color: "#848e9c",
  fontSize: "1rem",
};

const badgeStyle: React.CSSProperties = {
  padding: "4px 8px",
  borderRadius: "6px",
  fontSize: "0.75rem",
  fontWeight: "bold",
  letterSpacing: "0.5px",
};

const hedgeBadgeStyle = {
  ...badgeStyle,
  backgroundColor: "rgba(255, 167, 38, 0.15)",
  color: "#ffa726",
  border: "1px solid rgba(255, 167, 38, 0.3)",
};
const oneWayBadgeStyle = {
  ...badgeStyle,
  backgroundColor: "rgba(41, 98, 255, 0.15)",
  color: "#2962FF",
  border: "1px solid rgba(41, 98, 255, 0.3)",
};

const leverageStyle: React.CSSProperties = {
  backgroundColor: "#2a2e39",
  padding: "4px 8px",
  borderRadius: "6px",
  fontSize: "0.75rem",
  fontWeight: "bold",
  color: "#d1d4dc",
};

const refreshBtnStyle: React.CSSProperties = {
  backgroundColor: "#2962FF",
  color: "#fff",
  border: "none",
  padding: "10px 20px",
  borderRadius: "8px",
  cursor: "pointer",
  fontSize: "0.9rem",
  fontWeight: "bold",
  transition: "background-color 0.2s",
};

const disabledBtnStyle = {
  ...refreshBtnStyle,
  backgroundColor: "#2a2e39",
  color: "#848e9c",
  cursor: "not-allowed",
};

export default SimulationResultsPage;
