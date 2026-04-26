import React, { useState, useMemo } from "react";
import { useSimulation } from "../hooks/useSimulation";

interface OrderPanelProps {
  currentPrice: number;
}

export const OrderPanel: React.FC<OrderPanelProps> = ({ currentPrice }) => {
  const { status, placeMarketOrder, loading, currentPosition } =
    useSimulation("BTCUSDT");

  // --- [상태 관리] ---
  const [leverage, setLeverage] = useState<number>(10);
  const [margin, setMargin] = useState<number | "">("");
  const [tpPrice, setTpPrice] = useState<number | "">("");
  const [slPrice, setSlPrice] = useState<number | "">("");

  // 최종 확인 모달 상태
  const [showModal, setShowModal] = useState(false);
  const [side, setSide] = useState<"LONG" | "SHORT">("LONG");

  const availableBalance = status ? status.available_balance : 0;

  // --- [계산 로직] ---
  const size = useMemo(() => {
    if (!margin || !currentPrice) return 0;
    return (Number(margin) * leverage) / currentPrice;
  }, [margin, leverage, currentPrice]);

  // --- [함수] ---
  const openConfirmModal = (selectedSide: "LONG" | "SHORT") => {
    if (!margin || Number(margin) <= 0) return alert("증거금을 입력해주세요.");
    setSide(selectedSide);
    setShowModal(true);
  };

  const handleFinalConfirm = async () => {
    await placeMarketOrder(
      side,
      leverage,
      Number(margin),
      currentPrice,
      tpPrice ? Number(tpPrice) : undefined,
      slPrice ? Number(slPrice) : undefined,
    );
    setShowModal(false); // 주문 후 모달 닫기
    setMargin("");
    setTpPrice("");
    setSlPrice(""); // 입력창 초기화
  };

  return (
    <div style={styles.container}>
      {/* 1. 지갑 정보 */}
      <div style={styles.walletInfo}>
        <span style={styles.label}>Available Balance</span>
        <span style={styles.balanceText}>
          {availableBalance.toLocaleString()} USDT
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
            onChange={(e) => setMargin(e.target.value)}
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
            placeholder="TP"
            value={tpPrice}
            onChange={(e) => setTpPrice(e.target.value)}
            style={styles.smallInput}
          />
        </div>
        <div style={{ flex: 1 }}>
          <label style={styles.smallLabel}>Stop Loss</label>
          <input
            type="number"
            placeholder="SL"
            value={slPrice}
            onChange={(e) => setSlPrice(e.target.value)}
            style={styles.smallInput}
          />
        </div>
      </div>

      {/* 5. Long/Short 버튼 (최종 확인 모달 트리거) */}
      <div style={styles.btnRow}>
        <button
          onClick={() => openConfirmModal("LONG")}
          disabled={!!currentPosition}
          style={{ ...styles.actionBtn, backgroundColor: "#00b561" }}
        >
          Buy / Long
        </button>
        <button
          onClick={() => openConfirmModal("SHORT")}
          disabled={!!currentPosition}
          style={{ ...styles.actionBtn, backgroundColor: "#eb4d4b" }}
        >
          Sell / Short
        </button>
      </div>

      {/* 6. 🛡️ 최종 확인 모달 (Confirmation Modal) */}
      {showModal && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <h3
              style={{
                color: side === "LONG" ? "#00b561" : "#eb4d4b",
                marginBottom: "15px",
              }}
            >
              Confirm {side} Order
            </h3>

            <div style={styles.confirmRow}>
              <span>Symbol:</span> <strong>BTC/USDT</strong>
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

// --- [스타일] ---
const styles: { [key: string]: React.CSSProperties } = {
  // 1. 전체 컨테이너 (잘림 방지 및 스크롤 최적화)
  container: {
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    height: "100%", // 부모 높이 꽉 채우기
    overflowY: "auto", // 내용 많으면 패널 내부에서 스크롤
    backgroundColor: "#131722",
    boxSizing: "border-box",
  },

  // 2. 헤더 (제목)
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    borderBottom: "1px solid #2b3139",
    paddingBottom: "10px",
    whiteSpace: "nowrap", // 제목 잘림 방지
  },

  // 3. 지갑 정보 박스
  walletInfo: {
    padding: "10px",
    backgroundColor: "#1e222d",
    borderRadius: "4px",
    display: "flex",
    flexDirection: "column",
  },
  label: { fontSize: "12px", color: "#848e9c", marginBottom: "4px" },
  balanceText: { fontSize: "14px", fontWeight: "bold", color: "#d1d4dc" },

  // 4. 섹션 (레버리지, 증거금 등 공통 섹션)
  section: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  flexBetween: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  leverageValue: { color: "#fcd535", fontWeight: "bold" },
  range: { accentColor: "#2962FF", cursor: "pointer", width: "100%" },

  // 5. 입력창 (Main Input)
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

  // 6. TP/SL 가로 배치 행
  row: {
    display: "flex",
    gap: "10px",
  },
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

  // 7. 하단 버튼 구역 (잘림 방지 고정 마진)
  btnRow: {
    display: "flex",
    gap: "10px",
    marginTop: "10px", // 내용물과 붙어있게 함
    paddingBottom: "10px", // 최하단 여유
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

  // 8. 🛡️ 최종 확인 모달 스타일
  modalOverlay: {
    position: "fixed",
    top: 0,
    left: 0,
    width: "100vw",
    height: "100vh",
    backgroundColor: "rgba(0,0,0,0.8)", // 배경을 조금 더 어둡게
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 10000, // 최상단 유지
  },
  modalContent: {
    backgroundColor: "#1e222d",
    padding: "24px",
    borderRadius: "8px",
    width: "320px", // 모바일/소형 모니터 고려
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
  modalBtnRow: {
    display: "flex",
    gap: "10px",
    marginTop: "20px",
  },
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
