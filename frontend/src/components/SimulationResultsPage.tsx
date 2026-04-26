import React, { useEffect, useState } from "react";
import { analysisApi, StrategyRank } from "../api";

const SimulationResultsPage: React.FC = () => {
  const [rankings, setRankings] = useState<StrategyRank[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  // 1. 데이터 로드 함수
  const loadRankings = async () => {
    setLoading(true);
    try {
      const data = await analysisApi.getRanking();
      setRankings(data);
    } catch (error) {
      console.error("랭킹 데이터 로드 실패:", error);
    } finally {
      setLoading(false);
    }
  };

  // 2. 컴포넌트 마운트 시 데이터 로드
  useEffect(() => {
    loadRankings();
  }, []);

  return (
    <div style={pageContainerStyle}>
      <div style={headerContainerStyle}>
        <h3 style={titleStyle}>전략별 수익성 랭킹 (Best Configurations)</h3>
        <button
          onClick={loadRankings}
          disabled={loading}
          style={loading ? disabledBtnStyle : refreshBtnStyle}
        >
          {loading ? "데이터 갱신 중..." : "새로고침"}
        </button>
      </div>

      <div style={tableWrapperStyle}>
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>순위</th>
              <th style={thStyle}>모드</th>
              <th style={thStyle}>레버리지</th>
              <th style={thStyle}>익절/손절</th>
              <th style={thStyle}>총 거래</th>
              <th style={thStyle}>승률</th>
              <th style={thStyle}>불타기 합계</th>
              <th style={thStyle}>총 수익 (PNL)</th>
            </tr>
          </thead>
          <tbody>
            {rankings.length === 0 ? (
              <tr>
                <td colSpan={8} style={emptyTdStyle}>
                  {loading
                    ? "데이터를 불러오는 중입니다..."
                    : "데이터가 없습니다. 시뮬레이션을 먼저 실행해 주세요."}
                </td>
              </tr>
            ) : (
              rankings.map((rank, index) => (
                <tr key={index} style={index < 3 ? topRankRowStyle : rowStyle}>
                  <td style={tdStyle}>
                    {index === 0
                      ? "🥇"
                      : index === 1
                        ? "🥈"
                        : index === 2
                          ? "🥉"
                          : index + 1}
                  </td>
                  <td style={tdStyle}>
                    <span
                      style={
                        rank.position_mode === "HEDGE"
                          ? hedgeBadgeStyle
                          : oneWayBadgeStyle
                      }
                    >
                      {rank.position_mode}
                    </span>
                  </td>
                  <td style={tdStyle}>{rank.leverage}x</td>
                  <td style={tdStyle}>
                    <span style={{ color: "#26a69a" }}>
                      {(rank.tp_ratio * 100).toFixed(1)}%
                    </span>{" "}
                    /
                    <span style={{ color: "#ef5350" }}>
                      {" "}
                      {(rank.sl_ratio * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td style={tdStyle}>{rank.total_trades}</td>
                  <td style={tdStyle}>{rank.win_rate}%</td>
                  <td style={tdStyle}>{rank.total_pyramid_count}회</td>
                  <td
                    style={{
                      ...tdStyle,
                      color: rank.total_pnl >= 0 ? "#26a69a" : "#ef5350",
                      fontWeight: "bold",
                    }}
                  >
                    ${rank.total_pnl.toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

// --- [ 스타일 정의 ] ---
const pageContainerStyle: React.CSSProperties = {
  padding: "0 24px 24px 24px",
  backgroundColor: "#0b0e14",
  flex: 1,
};

const headerContainerStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  margin: "20px 0",
};

const titleStyle: React.CSSProperties = {
  color: "#d1d4dc",
  margin: 0,
  fontSize: "1.1rem",
};

const tableWrapperStyle: React.CSSProperties = {
  backgroundColor: "#131722",
  borderRadius: "8px",
  border: "1px solid #2a2e39",
  overflow: "hidden",
};

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: "0.85rem",
  color: "#d1d4dc",
};

const thStyle: React.CSSProperties = {
  backgroundColor: "#1e222d",
  padding: "12px 15px",
  textAlign: "left",
  borderBottom: "1px solid #2a2e39",
  color: "#848e9c",
  fontWeight: 600,
};

const tdStyle: React.CSSProperties = {
  padding: "12px 15px",
  borderBottom: "1px solid #2a2e39",
};

const rowStyle: React.CSSProperties = { transition: "background-color 0.2s" };
const topRankRowStyle: React.CSSProperties = {
  ...rowStyle,
  backgroundColor: "rgba(41, 98, 255, 0.05)",
};

const emptyTdStyle: React.CSSProperties = {
  padding: "40px",
  textAlign: "center",
  color: "#555",
};

const badgeStyle = {
  padding: "2px 6px",
  borderRadius: "4px",
  fontSize: "0.7rem",
  fontWeight: "bold",
};
const hedgeBadgeStyle = {
  ...badgeStyle,
  backgroundColor: "rgba(255, 167, 38, 0.1)",
  color: "#ffa726",
};
const oneWayBadgeStyle = {
  ...badgeStyle,
  backgroundColor: "rgba(41, 98, 255, 0.1)",
  color: "#2962FF",
};

const refreshBtnStyle = {
  backgroundColor: "#2962FF",
  color: "#fff",
  border: "none",
  padding: "8px 16px",
  borderRadius: "4px",
  cursor: "pointer",
  fontSize: "0.85rem",
};
const disabledBtnStyle = {
  ...refreshBtnStyle,
  backgroundColor: "#555",
  cursor: "not-allowed",
};

export default SimulationResultsPage;
