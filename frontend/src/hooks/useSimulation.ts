import { useState, useEffect, useCallback } from "react";
import { simulationApi, SimulationStatus } from "../api";

export const useSimulation = (symbol: string = "BTC/USDT") => {
  const [status, setStatus] = useState<SimulationStatus | null>(null);
  const [loading, setLoading] = useState(false);

  // 1. 상태 새로고침 (지갑 잔고 및 포지션 정보 갱신)
  const refreshStatus = useCallback(async () => {
    try {
      const data = await simulationApi.getStatus();
      setStatus(data);
    } catch (error) {
      console.error("Failed to fetch simulation status", error);
    }
  }, []);

  // 2. 주문 실행 함수 (TP/SL 파라미터 추가)
  const placeMarketOrder = async (
    side: "LONG" | "SHORT",
    leverage: number,
    margin: number,
    currentPrice: number,
    takeProfit?: number, // 익절 옵션
    stopLoss?: number, // 손절 옵션
  ) => {
    setLoading(true);
    try {
      await simulationApi.placeOrder({
        symbol,
        side,
        leverage,
        margin,
        current_price: currentPrice,
        take_profit: takeProfit,
        stop_loss: stopLoss,
      });
      await refreshStatus(); // 주문 성공 시 즉시 지갑 상태 동기화
    } catch (error: any) {
      alert(error.response?.data?.detail || "주문 실패");
    } finally {
      setLoading(false);
    }
  };

  // 3. 틱(Tick) 업데이트 함수 (차트 재생 시 캔들이 움직일 때마다 호출)
  const checkTick = async (currentPrice: number) => {
    try {
      const result = await simulationApi.processTick(symbol, currentPrice);
      // 포지션이 청산되거나 익절/손절되어 상태(RUNNING -> 종료)가 바뀌었을 수 있으므로 갱신
      if (result.tick_result && result.tick_result.status !== "RUNNING") {
        await refreshStatus();
      }
      return result;
    } catch (error) {
      console.error("Tick processing failed", error);
    }
  };

  // 4. 시뮬레이션 초기화 (지갑 잔고 리셋)
  const resetSimulation = async () => {
    try {
      await simulationApi.reset();
      await refreshStatus();
      alert("시뮬레이션 지갑이 10,000 USDT로 초기화되었습니다.");
    } catch (error) {
      console.error("Reset failed", error);
    }
  };

  // 초기 로드 시 한 번 지갑 상태를 가져옵니다.
  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  return {
    status, // 현재 지갑 및 포지션 데이터
    loading, // 주문 처리 중 로딩 상태
    refreshStatus, // 수동 갱신 함수
    placeMarketOrder, // 주문 넣기 함수
    checkTick, // 틱 갱신 함수
    resetSimulation, // 초기화 함수
    currentPosition: status?.positions[symbol] || null, // 현재 이 코인의 포지션 여부
  };
};
