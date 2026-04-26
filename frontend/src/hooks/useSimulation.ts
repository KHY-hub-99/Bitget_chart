import { useState, useEffect, useCallback, useMemo } from "react";
import { simulationApi, SimulationStatus } from "../api";

export const useSimulation = (symbol: string) => {
  const [status, setStatus] = useState<SimulationStatus | null>(null);
  const [loading, setLoading] = useState(false);

  // 1. 상태 새로고침 (지갑 잔고 및 포지션 정보 갱신)
  const refreshStatus = useCallback(async () => {
    try {
      const data = await simulationApi.getStatus();
      setStatus(data);
    } catch (error) {
      console.error("지갑 상태를 가져오는데 실패했습니다.", error);
    }
  }, []);

  // 2. 주문 실행 함수
  const placeMarketOrder = async (
    side: "LONG" | "SHORT",
    leverage: number,
    margin: number,
    currentPrice: number,
    tp?: number,
    sl?: number,
  ) => {
    setLoading(true);
    try {
      await simulationApi.placeOrder({
        symbol,
        side,
        leverage,
        margin,
        current_price: currentPrice,
        take_profit: tp,
        stop_loss: sl,
      });
      await refreshStatus();
    } catch (error: any) {
      alert(error.response?.data?.detail || "주문 실패");
    } finally {
      setLoading(false);
    }
  };

  // 3. 포지션 시장가 종료 (Market Close)
  // targetKey가 없으면 현재 심볼의 모든 포지션을 닫는 대신, 명확한 키를 받도록 권장합니다.
  const closeMarketPosition = async (targetKey: string) => {
    if (!targetKey) return;
    setLoading(true);
    try {
      await simulationApi.closePosition(targetKey);
      await refreshStatus();
    } catch (error: any) {
      alert(error.response?.data?.detail || "포지션 종료 실패");
    } finally {
      setLoading(false);
    }
  };

  // 4. 실시간 가격 변동 체크 (청산/익절/손절 감시)
  const checkTick = useCallback(
    async (price: number) => {
      try {
        const result = await simulationApi.processTick(symbol, price);

        if (result.wallet) {
          setStatus(result.wallet);
        }

        if (result.tick_result && result.tick_result.status !== "RUNNING") {
          await refreshStatus();
        }

        return result;
      } catch (error) {
        console.error("Tick 업데이트 실패", error);
      }
    },
    [symbol, refreshStatus],
  );

  // 5. 시뮬레이션 초기화 (Reset)
  const resetSimulation = async () => {
    if (!window.confirm("지갑을 초기 상태(10,000 USDT)로 리셋하시겠습니까?"))
      return;
    try {
      await simulationApi.reset();
      await refreshStatus();
    } catch (error) {
      console.error("리셋 실패", error);
    }
  };

  // 6. 포지션 모드 변경
  const changePositionMode = async (mode: "ONE_WAY" | "HEDGE") => {
    try {
      // 포지션이 있으면 백엔드에서 에러를 뱉으므로 프론트에서 먼저 체크하면 좋습니다.
      if (status && Object.keys(status.positions).length > 0) {
        alert("활성화된 포지션이 있을 때는 모드를 변경할 수 없습니다.");
        return;
      }
      await simulationApi.setMode(mode);
      await refreshStatus();
      alert(
        `포지션 모드가 ${mode === "ONE_WAY" ? "단방향" : "양방향"}으로 변경되었습니다.`,
      );
    } catch (error: any) {
      alert(error.response?.data?.detail || "모드 변경 실패");
    }
  };

  // 초기 로드 시 실행
  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  // [수정 핵심] Hedge Mode 대응: 현재 심볼에 해당하는 모든 포지션 찾기
  // 차트에는 여러 선이 그어질 수 있도록 배열을 반환하는 activePositions를 추가합니다.
  const activePositions = useMemo(() => {
    if (!status || !status.positions) return [];

    // 정확한 매칭: 'BTCUSDT' 혹은 'BTCUSDT_LONG', 'BTCUSDT_SHORT'만 필터링
    return Object.entries(status.positions)
      .filter(([key]) => key === symbol || key.startsWith(`${symbol}_`))
      .map(([key, pos]) => ({ ...pos, positionKey: key }));
  }, [status, symbol]);

  // 기존 TradingChart와의 호환성을 위해 "가장 먼저 찾은 포지션" 하나도 유지
  const currentPosition = useMemo(() => {
    return activePositions.length > 0 ? activePositions[0] : null;
  }, [activePositions]);

  return {
    status,
    loading,
    placeMarketOrder,
    closeMarketPosition,
    checkTick,
    resetSimulation,
    changePositionMode,
    currentPosition, // 기존 호환용 (단수)
    activePositions, // Hedge 모드 대응용 (복수)
    refreshStatus,
  };
};
