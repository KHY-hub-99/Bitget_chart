import React, { useEffect, useState } from "react";
import { analysisApi, StrategyRank } from "../api";

const SimulationResultsPage: React.FC = () => {
  const [rankings, setRankings] = useState<StrategyRank[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  // 필터 상태 추가
  const [symbol, setSymbol] = useState<string>("BTCUSDT");
  const [timeframe, setTimeframe] = useState<string>("15m");

  const loadRankings = async () => {
    setLoading(true);
    try {
      // 백엔드 API가 파라미터를 지원하도록 수정되었다면 전달,
      // 아니라면 전체를 가져와서 프론트에서 필터링 가능
      const data = await analysisApi.getRanking();
      setRankings(data);
    } catch (error) {
      console.error("랭킹 데이터 로드 실패:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRankings();
  }, []);

  return (
    <div style={pageContainerStyle}>
      <div style={headerContainerStyle}>
        <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
          <h3 style={titleStyle}>전략 성과 랭킹</h3>

          {/* 심볼/타임프레임 선택기 추가 */}
          <div style={filterGroupStyle}>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              style={selectStyle}
            >
              <option value="BTCUSDT">BTCUSDT</option>
              <option value="ETHUSDT">ETHUSDT</option>
            </select>
            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              style={selectStyle}
            >
              <option value="1m">1m</option>
              <option value="5m">5m</option>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
            </select>
          </div>
        </div>

        <button
          onClick={loadRankings}
          disabled={loading}
          style={loading ? disabledBtnStyle : refreshBtnStyle}
        >
          {loading ? "갱신 중..." : "새로고침"}
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
              <th style={thStyle}>거래수</th>
              <th style={thStyle}>청산/스위칭</th> {/* 추가 */}
              <th style={thStyle}>평균 MDD</th> {/* 추가 */}
              <th style={thStyle}>최대 MDD</th> {/* 추가 */}
              <th style={thStyle}>총 수익 (Net)</th>
            </tr>
          </thead>
          <tbody>
            {rankings.length === 0 ? (
              <tr>
                <td colSpan={9} style={emptyTdStyle}>
                  데이터가 없습니다.
                </td>
              </tr>
            ) : (
              rankings.map((rank, index) => (
                <tr key={index} style={index < 3 ? topRankRowStyle : rowStyle}>
                  <td style={tdStyle}>
                    {index < 3 ? ["🥇", "🥈", "🥉"][index] : index + 1}
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

                  {/* 청산 및 스위칭 횟수 표시 */}
                  <td style={tdStyle}>
                    <span style={{ color: "#ef5350" }}>
                      {rank.liquidations}
                    </span>{" "}
                    / {rank.switches}
                  </td>

                  {/* MDD 지표 표시: 리스크 시각화 */}
                  <td
                    style={{
                      ...tdStyle,
                      color: rank.avg_mdd_rate < -20 ? "#ef5350" : "#d1d4dc",
                    }}
                  >
                    {rank.avg_mdd_rate.toFixed(2)}%
                  </td>
                  <td
                    style={{
                      ...tdStyle,
                      color: rank.max_drawdown < -50 ? "#ef5350" : "#ffa726",
                      fontWeight: "bold",
                    }}
                  >
                    {rank.max_drawdown.toFixed(2)}%
                  </td>

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

// --- 추가된 스타일 ---
const filterGroupStyle = {
  display: "flex",
  gap: "8px",
  backgroundColor: "#1e222d",
  padding: "4px",
  borderRadius: "6px",
};

const selectStyle = {
  backgroundColor: "#2a2e39",
  color: "#fff",
  border: "none",
  padding: "4px 8px",
  borderRadius: "4px",
  fontSize: "0.8rem",
  outline: "none",
  cursor: "pointer",
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
