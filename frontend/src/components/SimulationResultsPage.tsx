import React, { useEffect, useState } from "react";
import { analysisApi, StrategyRank } from "../api";
import SimulationReplayChart, {
  CandleData,
  TradeMarker,
} from "./SimulationReplayChart";

const SimulationResultsPage: React.FC = () => {
  const [rankings, setRankings] = useState<StrategyRank[]>([]);
  const [loading, setLoading] = useState<boolean>(false);

  // 필터 상태
  const [symbol, setSymbol] = useState<string>("ALL");
  const [timeframe, setTimeframe] = useState<string>("ALL");

  // 모달 및 차트 상태 관리
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [replayLoading, setReplayLoading] = useState<boolean>(false);
  const [replayData, setReplayData] = useState<CandleData[]>([]);
  const [replayMarkers, setReplayMarkers] = useState<TradeMarker[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<StrategyRank | null>(
    null,
  );

  const loadRankings = async () => {
    setLoading(true);
    try {
      const data = await analysisApi.getRanking(symbol, timeframe);
      setRankings(data);
    } catch (error) {
      console.error("랭킹 데이터 로드 실패:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRankings();
  }, [symbol, timeframe]);

  const handleRowClick = async (rank: StrategyRank) => {
    const targetSymbol = symbol === "ALL" ? "BTCUSDT" : symbol;
    const targetTimeframe = timeframe === "ALL" ? "15m" : timeframe;

    setSelectedStrategy(rank);
    setIsModalOpen(true);
    setReplayLoading(true);

    try {
      const response = await analysisApi.getSimulationReplay(
        targetSymbol,
        targetTimeframe,
        rank.position_mode,
        rank.leverage,
        rank.tp_ratio,
        rank.sl_ratio,
      );

      const rawData = response.data.candles || [];
      const formattedData = rawData.map((d: any) => ({
        ...d,
        time: d.time > 10000000000 ? Math.floor(d.time / 1000) : d.time,
      }));

      setReplayData(formattedData);
      setReplayMarkers(response.markers || []);
    } catch (error) {
      console.error("차트 복기 데이터 로드 실패:", error);
      alert("차트 데이터를 불러오는데 실패했습니다.");
      setIsModalOpen(false);
    } finally {
      setReplayLoading(false);
    }
  };

  return (
    <div style={pageContainerStyle}>
      {/* 1. 상단 헤더 및 필터 영역 */}
      <div style={headerCardStyle}>
        <div>
          <h2 style={titleStyle}>전략 성과 랭킹 보드</h2>
          <p style={subtitleStyle}>
            최적의 수익성과 안정성을 가진 파라미터 조합을 탐색합니다. (행 클릭
            시 상세 복기)
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
              <option value="ALL">ALL SYMBOLS</option>
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
              <option value="ALL">ALL TIMES</option>
              <option value="15m">15M</option>
              <option value="1h">1H</option>
              <option value="4h">4H</option>
              <option value="1d">1D</option>
              <option value="1w">1W</option>
            </select>
          </div>

          <button
            onClick={loadRankings}
            disabled={loading}
            style={loading ? disabledBtnStyle : refreshBtnStyle}
          >
            {loading ? "REFRESHING..." : "새로고침"}
          </button>
        </div>
      </div>

      {/* 2. 랭킹 테이블 영역 */}
      <div style={tableWrapperStyle}>
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>RANK</th>
              <th style={thStyle}>MODE / LEV</th>
              <th style={thStyle}>TP / SL RATIO</th>
              <th style={thStyle}>W/L (LIQ)</th>
              <th style={thStyle}>WIN RATE</th>
              <th style={thStyle}>AVG MDD</th>
              <th style={thStyle}>MAX DRAWDOWN</th>
              <th style={{ ...thStyle, textAlign: "right" }}>TOTAL PNL</th>
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
                    className="ranking-row"
                    style={index < 3 ? topRankRowStyle : rowStyle}
                    onClick={() => handleRowClick(rank)}
                  >
                    <td style={tdStyle}>
                      <span style={index < 3 ? medalStyle : rankNumStyle}>
                        {index === 0
                          ? "1st"
                          : index === 1
                            ? "2nd"
                            : index === 2
                              ? "3rd"
                              : index + 1}
                      </span>
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
                      <span style={{ color: "#26a69a", fontWeight: 700 }}>
                        {(rank.tp_ratio * 100).toFixed(1)}%
                      </span>
                      <span style={{ color: "#363c4e", margin: "0 6px" }}>
                        /
                      </span>
                      <span style={{ color: "#ef5350", fontWeight: 700 }}>
                        {(rank.sl_ratio * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td style={tdStyle}>
                      <span style={{ color: "#26a69a", fontWeight: 600 }}>
                        {rank.wins}
                      </span>
                      <span style={{ color: "#848e9c" }}> / {rank.losses}</span>
                      {rank.liquidations > 0 && (
                        <span style={liqBadgeStyle}>({rank.liquidations})</span>
                      )}
                    </td>
                    <td style={tdStyle}>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                      >
                        <div style={winRateTrack}>
                          <div
                            style={{ ...winRateBar, width: `${winRate}%` }}
                          ></div>
                        </div>
                        <span
                          style={{
                            color:
                              Number(winRate) >= 50 ? "#26a69a" : "#d1d4dc",
                            fontWeight: 700,
                            fontSize: "0.8rem",
                          }}
                        >
                          {winRate}%
                        </span>
                      </div>
                    </td>
                    <td
                      style={{
                        ...tdStyle,
                        color: rank.avg_mdd_rate < -10 ? "#ef5350" : "#d1d4dc",
                      }}
                    >
                      {rank.avg_mdd_rate?.toFixed(2)}%
                    </td>
                    <td
                      style={{ ...tdStyle, color: "#ffa726", fontWeight: 700 }}
                    >
                      {rank.max_drawdown?.toFixed(2)}%
                    </td>
                    <td
                      style={{
                        ...tdStyle,
                        textAlign: "right",
                        color: rank.total_pnl >= 0 ? "#26a69a" : "#ef5350",
                        fontWeight: 800,
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

      {/* 3. 차트 복기 모달 창 */}
      {isModalOpen && (
        <div style={modalOverlayStyle} onClick={() => setIsModalOpen(false)}>
          <div style={modalContentStyle} onClick={(e) => e.stopPropagation()}>
            <div style={modalHeaderStyle}>
              <div
                style={{ display: "flex", flexDirection: "column", gap: "4px" }}
              >
                <h3 style={{ margin: 0, color: "#fff", fontSize: "1.1rem" }}>
                  전략 복기 리플레이
                </h3>
                <span
                  style={{
                    color: "#2962FF",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                  }}
                >
                  CONFIG: {selectedStrategy?.position_mode} |{" "}
                  {selectedStrategy?.leverage}X | TP{" "}
                  {(selectedStrategy?.tp_ratio || 0) * 100}% | SL{" "}
                  {(selectedStrategy?.sl_ratio || 0) * 100}%
                </span>
              </div>
              <button
                style={closeBtnStyle}
                onClick={() => setIsModalOpen(false)}
              >
                ✕
              </button>
            </div>

            <div style={{ padding: "24px", backgroundColor: "#0b0e14" }}>
              {replayLoading ? (
                <div style={loaderContainerStyle}>
                  <div className="loading-spinner"></div>
                  <p style={{ marginTop: "15px" }}>
                    시뮬레이션 타점을 계산하는 중...
                  </p>
                </div>
              ) : (
                <SimulationReplayChart
                  data={replayData}
                  markers={replayMarkers}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// --- [ 세련된 블랙 & 블루 스타일 설정 ] ---

const pageContainerStyle: React.CSSProperties = {
  padding: "24px",
  backgroundColor: "#0b0e14",
  flex: 1,
  color: "#d1d4dc",
  minHeight: "100vh",
  fontFamily: "'Inter', sans-serif",
};

const headerCardStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  backgroundColor: "#131722",
  padding: "24px",
  borderRadius: "12px",
  border: "1px solid #2a2e39",
  marginBottom: "24px",
  boxShadow: "0 8px 24px rgba(0, 0, 0, 0.4)",
};

const titleStyle: React.CSSProperties = {
  margin: 0,
  fontSize: "1.3rem",
  color: "#fff",
  fontWeight: 800,
};
const subtitleStyle: React.CSSProperties = {
  margin: "6px 0 0 0",
  fontSize: "0.8rem",
  color: "#848e9c",
  fontWeight: 500,
};

const controlsContainerStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "12px",
};

const filterGroupStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "6px",
};

const labelStyle: React.CSSProperties = {
  fontSize: "0.65rem",
  color: "#2962FF",
  fontWeight: 800,
  textTransform: "uppercase",
  letterSpacing: "1px",
};

const selectStyle: React.CSSProperties = {
  backgroundColor: "#1e222d",
  color: "#fff",
  border: "1px solid #363c4e",
  padding: "8px 12px",
  borderRadius: "6px",
  outline: "none",
  cursor: "pointer",
  fontSize: "0.85rem",
  fontWeight: 600,
};

const tableWrapperStyle: React.CSSProperties = {
  backgroundColor: "#131722",
  borderRadius: "12px",
  border: "1px solid #2a2e39",
  overflow: "hidden",
  boxShadow: "0 10px 30px rgba(0, 0, 0, 0.5)",
};

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: "0.85rem",
};

const thStyle: React.CSSProperties = {
  backgroundColor: "#181a20",
  padding: "16px",
  textAlign: "left",
  borderBottom: "1px solid #2a2e39",
  color: "#848e9c",
  fontWeight: 700,
  fontSize: "0.75rem",
  letterSpacing: "1px",
};

const tdStyle: React.CSSProperties = {
  padding: "16px",
  borderBottom: "1px solid #2a2e39",
  verticalAlign: "middle",
};

const rowStyle: React.CSSProperties = {
  transition: "all 0.2s",
  cursor: "pointer",
};
const topRankRowStyle: React.CSSProperties = {
  ...rowStyle,
  backgroundColor: "rgba(41, 98, 255, 0.03)",
};

const medalStyle: React.CSSProperties = {
  color: "#2962FF",
  fontWeight: 900,
  fontSize: "0.9rem",
};
const rankNumStyle: React.CSSProperties = { color: "#5d6673", fontWeight: 700 };

const hedgeBadgeStyle: React.CSSProperties = {
  padding: "4px 8px",
  borderRadius: "4px",
  fontSize: "0.7rem",
  fontWeight: 800,
  backgroundColor: "rgba(255, 167, 38, 0.1)",
  color: "#ffa726",
  border: "1px solid rgba(255, 167, 38, 0.2)",
};
const oneWayBadgeStyle: React.CSSProperties = {
  padding: "4px 8px",
  borderRadius: "4px",
  fontSize: "0.7rem",
  fontWeight: 800,
  backgroundColor: "rgba(41, 98, 255, 0.1)",
  color: "#2962FF",
  border: "1px solid rgba(41, 98, 255, 0.2)",
};
const leverageStyle: React.CSSProperties = {
  backgroundColor: "#1e222d",
  padding: "4px 6px",
  borderRadius: "4px",
  fontSize: "0.7rem",
  fontWeight: 700,
  color: "#fff",
};
const liqBadgeStyle: React.CSSProperties = {
  color: "#ef5350",
  fontSize: "0.7rem",
  fontWeight: 700,
  marginLeft: "6px",
};

const winRateTrack: React.CSSProperties = {
  width: "60px",
  height: "4px",
  backgroundColor: "#1e222d",
  borderRadius: "2px",
  overflow: "hidden",
};
const winRateBar: React.CSSProperties = {
  height: "100%",
  backgroundColor: "#26a69a",
};

const refreshBtnStyle: React.CSSProperties = {
  backgroundColor: "#2962FF",
  color: "#fff",
  border: "none",
  padding: "10px 24px",
  borderRadius: "8px",
  cursor: "pointer",
  fontSize: "0.85rem",
  fontWeight: 800,
  transition: "all 0.2s",
  boxShadow: "0 4px 12px rgba(41, 98, 255, 0.3)",
  marginTop: "16px",
};

const disabledBtnStyle: React.CSSProperties = {
  ...refreshBtnStyle,
  backgroundColor: "#2b3139",
  color: "#5d6673",
  boxShadow: "none",
  cursor: "not-allowed",
};

const modalOverlayStyle: React.CSSProperties = {
  position: "fixed",
  top: 0,
  left: 0,
  width: "100%",
  height: "100%",
  backgroundColor: "rgba(0, 0, 0, 0.85)",
  display: "flex",
  justifyContent: "center",
  alignItems: "center",
  zIndex: 1000,
  backdropFilter: "blur(8px)",
};
const modalContentStyle: React.CSSProperties = {
  backgroundColor: "#131722",
  width: "95%",
  maxWidth: "1300px",
  borderRadius: "16px",
  border: "1px solid #2a2e39",
  boxShadow: "0 20px 60px rgba(0,0,0,0.8)",
  overflow: "hidden",
};
const modalHeaderStyle: React.CSSProperties = {
  padding: "20px 24px",
  borderBottom: "1px solid #2a2e39",
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  backgroundColor: "#181a20",
};
const closeBtnStyle: React.CSSProperties = {
  background: "none",
  border: "none",
  color: "#848e9c",
  fontSize: "1.5rem",
  cursor: "pointer",
};
const loaderContainerStyle: React.CSSProperties = {
  height: "500px",
  display: "flex",
  flexDirection: "column",
  justifyContent: "center",
  alignItems: "center",
  color: "#848e9c",
  fontWeight: 600,
};
const emptyTdStyle: React.CSSProperties = {
  padding: "80px",
  textAlign: "center",
  color: "#5d6673",
  fontSize: "1rem",
  fontWeight: 600,
};

export default SimulationResultsPage;
