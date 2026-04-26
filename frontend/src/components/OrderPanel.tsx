import React, { useState, useEffect, useMemo } from "react";
import { useSimulation } from "../hooks/useSimulation";

interface OrderPanelProps {
  currentPrice: number;
}

export const OrderPanel: React.FC<OrderPanelProps> = ({ currentPrice }) => {
  const { status, placeMarketOrder, loading, currentPosition } =
    useSimulation("BTCUSDT");

  // 1. 모델 기반 설정 옵션들
  const [leverage, setLeverage] = useState<number>(10); // leverage: 1 ~ 125
  const [margin, setMargin] = useState<number | "">(""); // isolated_margin
  const [orderType, setOrderType] = useState<"Market" | "Limit">("Market");
  const [limitPrice, setLimitPrice] = useState<number | "">(""); // 지정가용

  // TP/SL 옵션 (Optional Decimal)
  const [tpPrice, setTpPrice] = useState<number | "">("");
  const [slPrice, setSlPrice] = useState<number | "">("");

  const availableBalance = status ? status.available_balance : 0;

  // 2. 모델의 size(수량) 계산 로직 미리보기
  const calculatedSize = useMemo(() => {
    const price =
      orderType === "Limit" && limitPrice ? Number(limitPrice) : currentPrice;
    if (!margin || !price) return 0;
    return (Number(margin) * leverage) / price;
  }, [margin, leverage, currentPrice, orderType, limitPrice]);

  // 3. 주문 실행 (모든 옵션 패키징)
  const handleOrder = async (side: "LONG" | "SHORT") => {
    const entryPrice =
      orderType === "Limit" ? Number(limitPrice) : currentPrice;

    if (!margin || Number(margin) <= 0) return alert("증거금을 입력하세요.");
    if (orderType === "Limit" && !limitPrice)
      return alert("지정가를 입력하세요.");

    await placeMarketOrder(
      side,
      leverage,
      Number(margin),
      entryPrice,
      tpPrice ? Number(tpPrice) : undefined,
      slPrice ? Number(slPrice) : undefined,
    );
  };

  return (
    <div className="order-panel" style={styles.container}>
      {/* 지갑 상태 (Wallet Model 연동) */}
      <div style={styles.walletBox}>
        <div style={styles.flexBetween}>
          <span style={styles.label}>사용 가능 잔액</span>
          <span style={styles.value}>
            {availableBalance.toLocaleString()} USDT
          </span>
        </div>
      </div>

      {/* 주문 유형 선택 */}
      <div style={styles.tabGroup}>
        <button
          onClick={() => setOrderType("Market")}
          style={orderType === "Market" ? styles.activeTab : styles.tab}
        >
          시장가
        </button>
        <button
          onClick={() => setOrderType("Limit")}
          style={orderType === "Limit" ? styles.activeTab : styles.tab}
        >
          지정가
        </button>
      </div>

      {/* 레버리지 설정 (leverage 옵션) */}
      <div style={styles.inputGroup}>
        <div style={styles.flexBetween}>
          <label style={styles.label}>레버리지</label>
          <input
            type="number"
            min="1"
            max="125"
            value={leverage}
            onChange={(e) => setLeverage(Number(e.target.value))}
            style={styles.numInput}
          />
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

      {/* 지정가 입력 (Limit 선택 시) */}
      {orderType === "Limit" && (
        <div style={styles.inputGroup}>
          <label style={styles.label}>지정가 (Entry Price)</label>
          <input
            type="number"
            placeholder="0.00"
            value={limitPrice}
            onChange={(e) => setLimitPrice(e.target.value)}
            style={styles.mainInput}
          />
        </div>
      )}

      {/* 격리 증거금 입력 (isolated_margin 옵션) */}
      <div style={styles.inputGroup}>
        <label style={styles.label}>격리 증거금 (Margin)</label>
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

      {/* 익절/손절 (take_profit_price, stop_loss_price 옵션) */}
      <div style={styles.tpslContainer}>
        <div style={styles.inputHalf}>
          <label style={styles.smallLabel}>익절 (TP)</label>
          <input
            type="number"
            placeholder="익절가"
            value={tpPrice}
            onChange={(e) => setTpPrice(e.target.value)}
            style={styles.smallInput}
          />
        </div>
        <div style={styles.inputHalf}>
          <label style={styles.smallLabel}>손절 (SL)</label>
          <input
            type="number"
            placeholder="손절가"
            value={slPrice}
            onChange={(e) => setSlPrice(e.target.value)}
            style={styles.smallInput}
          />
        </div>
      </div>

      {/* 결과 미리보기 (size 옵션 반영) */}
      <div style={styles.summary}>
        <div style={styles.flexBetween}>
          <span>주문 수량</span>
          <span className="tabular-nums">{calculatedSize.toFixed(4)} BTC</span>
        </div>
      </div>

      {/* 주문 버튼 (PositionSide 옵션) */}
      <div style={styles.btnRow}>
        <button
          onClick={() => handleOrder("LONG")}
          disabled={loading || !!currentPosition}
          style={{ ...styles.orderBtn, backgroundColor: "#00b561" }}
        >
          Long / Buy
        </button>
        <button
          onClick={() => handleOrder("SHORT")}
          disabled={loading || !!currentPosition}
          style={{ ...styles.orderBtn, backgroundColor: "#eb4d4b" }}
        >
          Short / Sell
        </button>
      </div>
    </div>
  );
};

// 스타일 가이드 (Bitget 다크모드 스타일링)
const styles: { [key: string]: React.CSSProperties } = {
  container: {
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: "20px",
    height: "100%",
    backgroundColor: "#131722",
  },
  walletBox: {
    padding: "10px",
    backgroundColor: "#1e222d",
    borderRadius: "4px",
  },
  label: { fontSize: "12px", color: "#848e9c" },
  value: { fontSize: "13px", fontWeight: "bold", color: "#d1d4dc" },
  tabGroup: {
    display: "flex",
    gap: "2px",
    backgroundColor: "#1e222d",
    padding: "2px",
    borderRadius: "4px",
  },
  tab: {
    flex: 1,
    padding: "6px",
    border: "none",
    backgroundColor: "transparent",
    color: "#848e9c",
    cursor: "pointer",
    fontSize: "12px",
  },
  activeTab: {
    flex: 1,
    padding: "6px",
    border: "none",
    backgroundColor: "#2b3139",
    color: "#fff",
    borderRadius: "4px",
    fontSize: "12px",
    fontWeight: "bold",
  },
  inputGroup: { display: "flex", flexDirection: "column", gap: "8px" },
  mainInput: {
    width: "100%",
    padding: "10px",
    backgroundColor: "#1e222d",
    border: "1px solid #2a2e39",
    color: "#fff",
    borderRadius: "4px",
    outline: "none",
  },
  numInput: {
    width: "50px",
    textAlign: "right",
    backgroundColor: "transparent",
    border: "none",
    color: "#fcd535",
    fontWeight: "bold",
    outline: "none",
  },
  range: { accentColor: "#2962FF", cursor: "pointer" },
  tpslContainer: { display: "flex", gap: "10px" },
  inputHalf: { flex: 1, display: "flex", flexDirection: "column", gap: "5px" },
  smallLabel: { fontSize: "11px", color: "#848e9c" },
  smallInput: {
    width: "100%",
    padding: "8px",
    backgroundColor: "#1e222d",
    border: "1px solid #2a2e39",
    color: "#fff",
    borderRadius: "4px",
    fontSize: "12px",
    outline: "none",
  },
  summary: {
    fontSize: "12px",
    color: "#848e9c",
    borderTop: "1px solid #2a2e39",
    paddingTop: "10px",
  },
  flexBetween: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  inputWrapper: { position: "relative" },
  unit: {
    position: "absolute",
    right: "10px",
    top: "50%",
    transform: "translateY(-50%)",
    fontSize: "12px",
    color: "#5d6673",
  },
  btnRow: { display: "flex", gap: "10px", marginTop: "auto" },
  orderBtn: {
    flex: 1,
    padding: "12px",
    border: "none",
    borderRadius: "4px",
    color: "#fff",
    fontWeight: "bold",
    cursor: "pointer",
    fontSize: "14px",
  },
};
