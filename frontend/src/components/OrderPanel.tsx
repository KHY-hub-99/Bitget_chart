import React, { useState, useMemo } from "react";

// BUG FIX: currentPosition 제거 (App.tsx에서 전달되지 않고 컴포넌트 내부에서도 미사용)
//          activePositions 추가 (App.tsx에서 전달되나 interface에 누락됐던 항목)
interface OrderPanelProps {
  currentPrice: number;
  placeMarketOrder: (
    side: "LONG" | "SHORT",
    leverage: number,
    margin: number,
    currentPrice: number,
    tp?: number,
    sl?: number,
  ) => Promise<void>;
  resetSimulation: () => Promise<void>;
  loading: boolean;
  activePositions: any[];
  availableBalance: number;
  changePositionMode: (mode: "ONE_WAY" | "HEDGE") => Promise<void>;
  positionMode: "ONE_WAY" | "HEDGE";
}

export const OrderPanel: React.FC<OrderPanelProps> = ({
  currentPrice,
  placeMarketOrder,
  resetSimulation,
  loading,
  availableBalance = 0,
  changePositionMode,
  positionMode,
}) => {
  const [leverage, setLeverage] = useState<number>(10);
  const [margin, setMargin] = useState<number | "">("");
  const [tpPrice, setTpPrice] = useState<number | "">("");
  const [slPrice, setSlPrice] = useState<number | "">("");

  const [showModal, setShowModal] = useState(false);
  const [side, setSide] = useState<"LONG" | "SHORT">("LONG");

  const size = useMemo(() => {
    if (!margin || !currentPrice) return 0;
    return (Number(margin) * leverage) / currentPrice;
  }, [margin, leverage, currentPrice]);

  const openConfirmModal = (selectedSide: "LONG" | "SHORT") => {
    if (!margin || Number(margin) <= 0) return alert("증거금을 입력해주세요.");
    if (Number(margin) > availableBalance) return alert("잔액이 부족합니다.");
    setSide(selectedSide);
    setShowModal(true);
  };

  const handleFinalConfirm = async () => {
    try {
      await placeMarketOrder(
        side,
        leverage,
        Number(margin),
        currentPrice,
        tpPrice ? Number(tpPrice) : undefined,
        slPrice ? Number(slPrice) : undefined,
      );
      setShowModal(false);
      setMargin("");
      setTpPrice("");
      setSlPrice("");
    } catch (error) {}
  };

  return (
    <div style={styles.container}>
      {/* 0. 포지션 모드 선택 탭 */}
      <div style={styles.modeTabContainer}>
        <button
          onClick={() => changePositionMode("ONE_WAY")}
          style={{
            ...styles.modeBtn,
            color: positionMode === "ONE_WAY" ? "#fcd535" : "#848e9c",
            borderBottom:
              positionMode === "ONE_WAY" ? "2px solid #fcd535" : "none",
          }}
        >
          One-Way
        </button>
        <button
          onClick={() => changePositionMode("HEDGE")}
          style={{
            ...styles.modeBtn,
            color: positionMode === "HEDGE" ? "#fcd535" : "#848e9c",
            borderBottom:
              positionMode === "HEDGE" ? "2px solid #fcd535" : "none",
          }}
        >
          Hedge (양방향)
        </button>
      </div>

      {/* 1. 지갑 정보 및 리셋 버튼 */}
      <div style={styles.walletInfo}>
        <div style={styles.flexBetween}>
          <span style={styles.label}>Available Balance</span>
          <button
            onClick={resetSimulation}
            style={styles.resetBtn}
            title="잔고를 10,000 USDT로 초기화합니다"
          >
            Reset
          </button>
        </div>
        <span style={styles.balanceText}>
          {(availableBalance ?? 0).toLocaleString(undefined, {
            minimumFractionDigits: 2,
          })}{" "}
          USDT
        </span>
      </div>

      {/* 2. 레버리지 설정 */}
      <div style={styles.section}>
        <div style={styles.flexBetween}>
          <label style={styles.label}>Leverage</label>
          <span style={styles.leverageValue}>{leverage}x</span>
        </div>
        <input
          type="range"
          min="1"
          max="125"
          value={leverage}
          onChange={(e) => setLeverage(Number(e.target.value))}
          style={styles.range}
        />
      </div>

      {/* 3. 증거금 입력 */}
      <div style={styles.section}>
        <label style={styles.label}>Margin (Isolated)</label>
        <div style={styles.inputWrapper}>
          <input
            type="number"
            placeholder="0.00"
            value={margin}
            onChange={(e) =>
              setMargin(e.target.value === "" ? "" : Number(e.target.value))
            }
            style={styles.mainInput}
          />
          <span style={styles.unit}>USDT</span>
        </div>
      </div>

      {/* 4. TP/SL 설정 */}
      <div style={styles.row}>
        <div style={{ flex: 1 }}>
          <label style={styles.smallLabel}>Take Profit</label>
          <input
            type="number"
            placeholder="TP Price"
            value={tpPrice}
            onChange={(e) =>
              setTpPrice(e.target.value === "" ? "" : Number(e.target.value))
            }
            style={styles.smallInput}
          />
        </div>
        <div style={{ flex: 1 }}>
          <label style={styles.smallLabel}>Stop Loss</label>
          <input
            type="number"
            placeholder="SL Price"
            value={slPrice}
            onChange={(e) =>
              setSlPrice(e.target.value === "" ? "" : Number(e.target.value))
            }
            style={styles.smallInput}
          />
        </div>
      </div>

      {/* 5. Long/Short 버튼 */}
      <div style={styles.btnRow}>
        <button
          onClick={() => openConfirmModal("LONG")}
          disabled={loading}
          style={{
            ...styles.actionBtn,
            backgroundColor: "#00b561",
            opacity: loading ? 0.5 : 1,
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading
            ? "..."
            : positionMode === "HEDGE"
              ? "Open Long"
              : "Buy / Long"}
        </button>
        <button
          onClick={() => openConfirmModal("SHORT")}
          disabled={loading}
          style={{
            ...styles.actionBtn,
            backgroundColor: "#eb4d4b",
            opacity: loading ? 0.5 : 1,
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading
            ? "..."
            : positionMode === "HEDGE"
              ? "Open Short"
              : "Sell / Short"}
        </button>
      </div>

      {/* 6. 최종 확인 모달 */}
      {showModal && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <h3
              style={{
                color: side === "LONG" ? "#00b561" : "#eb4d4b",
                marginBottom: "15px",
              }}
            >
              Confirm {side} Order ({positionMode})
            </h3>
            <div style={styles.confirmRow}>
              <span>Symbol:</span> <strong>BTCUSDT</strong>
            </div>
            <div style={styles.confirmRow}>
              <span>Side:</span>{" "}
              <strong
                style={{ color: side === "LONG" ? "#00b561" : "#eb4d4b" }}
              >
                {side}
              </strong>
            </div>
            <div style={styles.confirmRow}>
              <span>Leverage:</span> <strong>{leverage}x</strong>
            </div>
            <div style={styles.confirmRow}>
              <span>Margin:</span> <strong>{margin} USDT</strong>
            </div>
            <div style={styles.confirmRow}>
              <span>Entry Price:</span>{" "}
              <strong>{currentPrice.toLocaleString()}</strong>
            </div>
            <div style={styles.confirmRow}>
              <span>Qty:</span> <strong>{size.toFixed(4)} BTC</strong>
            </div>

            <div style={styles.modalBtnRow}>
              <button
                onClick={() => setShowModal(false)}
                style={styles.cancelBtn}
              >
                Cancel
              </button>
              <button
                onClick={handleFinalConfirm}
                style={styles.confirmBtn}
                disabled={loading}
              >
                {loading ? "Processing..." : "Confirm Order"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    height: "100%",
    overflowY: "auto",
    backgroundColor: "#131722",
    boxSizing: "border-box",
  },
  modeTabContainer: {
    display: "flex",
    gap: "15px",
    borderBottom: "1px solid #2a2e39",
    marginBottom: "4px",
  },
  modeBtn: {
    padding: "8px 0",
    background: "none",
    border: "none",
    fontSize: "12px",
    fontWeight: "bold",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  walletInfo: {
    padding: "10px",
    backgroundColor: "#1e222d",
    borderRadius: "4px",
    display: "flex",
    flexDirection: "column",
  },
  label: { fontSize: "12px", color: "#848e9c", marginBottom: "4px" },
  balanceText: { fontSize: "14px", fontWeight: "bold", color: "#d1d4dc" },
  resetBtn: {
    padding: "2px 8px",
    backgroundColor: "#2b3139",
    color: "#848e9c",
    border: "1px solid #474d57",
    borderRadius: "4px",
    fontSize: "10px",
    cursor: "pointer",
    transition: "all 0.2s",
  },
  section: { display: "flex", flexDirection: "column", gap: "8px" },
  flexBetween: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  leverageValue: { color: "#fcd535", fontWeight: "bold" },
  range: { accentColor: "#2962FF", cursor: "pointer", width: "100%" },
  inputWrapper: { position: "relative" },
  mainInput: {
    width: "100%",
    padding: "10px",
    backgroundColor: "#1e222d",
    border: "1px solid #2a2e39",
    color: "#fff",
    borderRadius: "4px",
    outline: "none",
    fontSize: "13px",
  },
  unit: {
    position: "absolute",
    right: "10px",
    top: "50%",
    transform: "translateY(-50%)",
    fontSize: "12px",
    color: "#5d6673",
  },
  row: { display: "flex", gap: "10px" },
  smallLabel: {
    fontSize: "11px",
    color: "#848e9c",
    marginBottom: "4px",
    display: "block",
  },
  smallInput: {
    width: "100%",
    padding: "8px",
    backgroundColor: "#1e222d",
    border: "1px solid #2a2e39",
    color: "#fff",
    borderRadius: "4px",
    fontSize: "12px",
  },
  btnRow: {
    display: "flex",
    gap: "10px",
    marginTop: "10px",
    paddingBottom: "10px",
  },
  actionBtn: {
    flex: 1,
    padding: "12px",
    border: "none",
    borderRadius: "4px",
    color: "#fff",
    fontWeight: "bold",
    cursor: "pointer",
    fontSize: "14px",
  },
  modalOverlay: {
    position: "fixed",
    top: 0,
    left: 0,
    width: "100vw",
    height: "100vh",
    backgroundColor: "rgba(0,0,0,0.8)",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 10000,
  },
  modalContent: {
    backgroundColor: "#1e222d",
    padding: "24px",
    borderRadius: "8px",
    width: "320px",
    border: "1px solid #2a2e39",
    boxShadow: "0 10px 25px rgba(0,0,0,0.5)",
  },
  confirmRow: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: "13px",
    marginBottom: "10px",
    color: "#848e9c",
  },
  modalBtnRow: { display: "flex", gap: "10px", marginTop: "20px" },
  cancelBtn: {
    flex: 1,
    padding: "12px",
    backgroundColor: "#2b3139",
    color: "#fff",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
  },
  confirmBtn: {
    flex: 1,
    padding: "12px",
    backgroundColor: "#2962FF",
    color: "#fff",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    fontWeight: "bold",
  },
};
