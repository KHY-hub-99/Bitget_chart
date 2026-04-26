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
      await refreshStatus(); // 주문 성공 후 즉시 상태 동기화
    } catch (error: any) {
      alert(error.response?.data?.detail || "주문 실패");
    } finally {
      setLoading(false);
    }
  };

  // 3. 포지션 시장가 종료 (Market Close)
  const closeMarketPosition = async (targetKey: string = symbol) => {
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
  // 차트에서 새로운 가격이 들어올 때마다 App.tsx에서 이 함수를 호출해줘야 합니다.
  const checkTick = useCallback(
    async (price: number) => {
      try {
        const result = await simulationApi.processTick(symbol, price);

        // 백엔드에서 전달받은 최신 지갑(wallet) 정보를 상태에 반영
        // 이 순간 PositionBoard의 Mark Price와 PNL이 즉시 바뀝니다.
        if (result.wallet) {
          setStatus(result.wallet);
        }

        // 만약 청산이나 TP/SL로 포지션이 닫혔다면(RUNNING이 아니라면)
        // 전체 상태를 다시 한번 정밀하게 새로고침
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

  // 초기 로드 시 한 번 실행
  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  // 양방향 모드일 경우 키가 달라질 수 있으므로, 값(Object.values)을 뒤져서 심볼이 같은 포지션을 찾습니다.
  const currentPosition = useMemo(() => {
    if (!status) return null;
    return (
      Object.values(status.positions).find((p) => p.symbol === symbol) || null
    );
  }, [status, symbol]);

  return {
    status, // 전체 지갑 상태 (잔고 등)
    loading, // 주문/종료 처리 중 로딩
    placeMarketOrder, // 주문 함수
    closeMarketPosition, // 종료 함수
    checkTick, // 가격 변동 체크 함수
    resetSimulation, // 리셋 함수
    currentPosition, // 현재 활성화된 포지션 정보
    refreshStatus, // 수동 새로고침
  };
};
