import React from "react";
// api.ts에서 정의한 타입을 가져옵니다 (경로 확인 필요)
import { SimulationStatus } from "../api";

interface PositionBoardProps {
  currentPrice: number;
  status: SimulationStatus | null; // 부모로부터 지갑 상태를 받음
  closeMarketPosition: () => Promise<void>; // 부모로부터 종료 함수를 받음
}

export const PositionBoard: React.FC<PositionBoardProps> = ({
  currentPrice,
  status,
  closeMarketPosition,
}) => {
  // ❌ 내부 useSimulation 호출 삭제 (부모에서 넘겨받은 Props 사용)

  if (!status)
    return (
      <div style={styles.container}>
        <div style={styles.empty}>지갑 정보를 불러오는 중...</div>
      </div>
    );

  const positions = Object.entries(status.positions);

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h3 style={{ margin: 0, fontSize: "16px" }}>포지션 현황 (Positions)</h3>
        <div style={styles.walletInfo}>
          <span>
            총 자산:{" "}
            <strong style={{ color: "#eaecef" }}>
              {(status.total_balance ?? 0).toLocaleString(undefined, {
                minimumFractionDigits: 2,
              })}{" "}
              USDT
            </strong>
          </span>
          <span style={{ margin: "0 10px", color: "#444" }}>|</span>
          <span>
            묶인 증거금:{" "}
            <strong style={{ color: "#ff9800" }}>
              {(status.frozen_margin ?? 0).toLocaleString(undefined, {
                minimumFractionDigits: 2,
              })}{" "}
              USDT
            </strong>
          </span>
        </div>
      </div>

      <table style={styles.table}>
        <thead>
          <tr style={styles.thRow}>
            <th style={styles.th}>계약 (Symbol)</th>
            <th style={styles.th}>수량 (Size)</th>
            <th style={styles.th}>진입 가격 (Entry)</th>
            <th style={styles.th}>시장 가격 (Mark)</th>
            <th style={styles.th}>강제 청산가 (Liq. Price)</th>
            <th style={styles.th}>격리 증거금 (Margin)</th>
            <th style={styles.th}>TP / SL</th>
            <th style={styles.th}>미실현 손익 (ROE%)</th>
            <th style={styles.th}>종료 (Close)</th>
          </tr>
        </thead>
        <tbody>
          {positions.length === 0 ? (
            <tr>
              <td colSpan={9} style={styles.empty}>
                현재 활성화된 포지션이 없습니다.
              </td>
            </tr>
          ) : (
            positions.map(([symbol, pos]) => {
              const isLong = pos.side === "LONG";
              const sideColor = isLong ? "#00b561" : "#ff4c4c";

              // ROE 및 PNL 계산
              const roe =
                (pos.unrealized_pnl / (pos.isolated_margin || 1)) * 100;
              const pnlColor = pos.unrealized_pnl >= 0 ? "#00b561" : "#ff4c4c";

              return (
                <tr key={symbol} style={styles.tdRow}>
                  <td style={styles.td}>
                    <span
                      style={{
                        color: sideColor,
                        fontWeight: "bold",
                        marginRight: "8px",
                      }}
                    >
                      {pos.side}
                    </span>
                    <span style={{ color: "#eaecef", fontWeight: "bold" }}>
                      {symbol}
                    </span>
                    <span style={styles.leverageBadge}>{pos.leverage}x</span>
                  </td>
                  <td style={styles.td}>{pos.size.toFixed(4)}</td>
                  <td style={styles.td}>
                    {pos.entry_price.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                    })}
                  </td>
                  <td style={styles.td}>
                    {currentPrice.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                    })}
                  </td>
                  <td
                    style={{
                      ...styles.td,
                      color: "#ff9800",
                      fontWeight: "bold",
                    }}
                  >
                    {pos.liquidation_price.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                    })}
                  </td>
                  <td style={styles.td}>{pos.isolated_margin.toFixed(2)}</td>
                  <td style={styles.td}>
                    {pos.take_profit ? pos.take_profit.toLocaleString() : "--"}{" "}
                    / {pos.stop_loss ? pos.stop_loss.toLocaleString() : "--"}
                  </td>
                  <td
                    style={{
                      ...styles.td,
                      color: pnlColor,
                      fontWeight: "bold",
                    }}
                  >
                    <div style={{ fontFamily: "'IBM Plex Mono', monospace" }}>
                      {pos.unrealized_pnl > 0 ? "+" : ""}
                      {pos.unrealized_pnl.toFixed(2)} USDT
                    </div>
                    <div style={{ fontSize: "11px", opacity: 0.8 }}>
                      ({roe > 0 ? "+" : ""}
                      {roe.toFixed(2)}%)
                    </div>
                  </td>
                  <td style={styles.td}>
                    <button
                      onClick={() => closeMarketPosition()}
                      style={styles.closeBtn}
                    >
                      Market Close
                    </button>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
};

// --- [스타일 설정은 기존과 동일] ---
const styles: { [key: string]: React.CSSProperties } = {
  container: {
    backgroundColor: "#1e2026",
    borderTop: "1px solid #2b3139",
    color: "#848e9c",
    padding: "16px 20px",
    height: "100%",
    boxSizing: "border-box",
    overflowY: "auto",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "16px",
    color: "#eaecef",
  },
  walletInfo: { fontSize: "14px" },
  table: { width: "100%", borderCollapse: "collapse", textAlign: "right" },
  thRow: { borderBottom: "1px solid #2b3139" },
  th: {
    padding: "12px 8px",
    fontSize: "12px",
    fontWeight: "normal",
    color: "#848e9c",
    textAlign: "right",
  },
  tdRow: {
    borderBottom: "1px solid #2b3139",
    transition: "background-color 0.2s",
  },
  td: { padding: "12px 8px", fontSize: "14px", color: "#eaecef" },
  leverageBadge: {
    backgroundColor: "#2b3139",
    color: "#fcd535",
    padding: "2px 6px",
    borderRadius: "4px",
    fontSize: "11px",
    marginLeft: "8px",
  },
  empty: { textAlign: "center", padding: "40px", color: "#848e9c" },
  closeBtn: {
    padding: "6px 10px",
    backgroundColor: "#2b3139",
    color: "#eaecef",
    border: "1px solid #474d57",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "12px",
    fontWeight: "bold",
  },
};
