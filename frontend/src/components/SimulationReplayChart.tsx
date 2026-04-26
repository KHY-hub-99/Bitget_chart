// frontend/src/components/SimulationReplayChart.tsx

import React, { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  SeriesMarker,
  Time,
  CandlestickSeries,
  createSeriesMarkers,
} from "lightweight-charts";

// --- [ 타입 정의 ] ---
export interface CandleData {
  time: Time;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface TradeMarker {
  time: Time;
  action: "BUY" | "SELL";
  price: number;
  reason: "ENTRY" | "TAKE_PROFIT" | "STOP_LOSS" | "LIQUIDATED" | "SWITCHED";
}

interface SimulationReplayChartProps {
  data: CandleData[];
  markers: TradeMarker[];
}

// --- [ 컴포넌트 ] ---
const SimulationReplayChart: React.FC<SimulationReplayChartProps> = ({
  data,
  markers,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // 1. 차트 인스턴스 생성 (다크 테마 및 퀀트 스타일)
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#131722" },
        textColor: "#d1d4dc",
      },
      grid: {
        vertLines: { color: "rgba(42, 46, 57, 0.5)" },
        horzLines: { color: "rgba(42, 46, 57, 0.5)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: "rgba(197, 203, 206, 0.8)",
      },
      timeScale: {
        borderColor: "rgba(197, 203, 206, 0.8)",
        timeVisible: true,
        secondsVisible: false,
      },
    });

    // 2. 캔들스틱 시리즈 추가
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderVisible: false,
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
    });

    // 데이터 세팅
    if (data.length > 0) {
      candlestickSeries.setData(data);
    }

    // 3. 매매 마커(화살표) 생성 로직
    if (markers.length > 0) {
      const chartMarkers: SeriesMarker<Time>[] = markers.map((m) => {
        const isBuy = m.action === "BUY";
        const isLiq = m.reason === "LIQUIDATED";

        // 청산은 해골이나 X표시, 일반 매매는 화살표
        return {
          time: m.time,
          position: isBuy ? "belowBar" : "aboveBar",
          color: isLiq ? "#ff9800" : isBuy ? "#2962FF" : "#E91E63",
          shape: isBuy ? "arrowUp" : "arrowDown",
          text: isLiq ? "💀 청산" : `${m.reason} @ ${m.price.toFixed(2)}`,
          size: 1,
        };
      });

      // 마커는 반드시 시간순으로 정렬되어야 에러가 나지 않습니다.
      chartMarkers.sort((a, b) => (a.time as number) - (b.time as number));
      createSeriesMarkers(candlestickSeries, chartMarkers);
    }

    chartRef.current = chart;

    // 4. 창 크기 변경 시 차트 리사이즈 핸들러
    const handleResize = () => {
      chart.applyOptions({ width: chartContainerRef.current?.clientWidth });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [data, markers]); // 데이터나 마커가 변경되면 차트를 다시 그립니다.

  return (
    <div
      ref={chartContainerRef}
      style={{
        width: "100%",
        height: "500px",
        borderRadius: "8px",
        overflow: "hidden",
      }}
    />
  );
};

export default SimulationReplayChart;
