import React, { useEffect, useRef } from "react";
import {
  createChart,
  createSeriesMarkers,
  ColorType,
  CrosshairMode,
  LineStyle,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  IChartApi,
  ISeriesApi,
  Time,
} from "lightweight-charts";

interface ChartDataProps {
  data: {
    candles: any[];
    volumes: any[];
    indicators: { [key: string]: { time: number; value: number }[] };
    markers: any[];
  };
  settings: {
    whale: boolean;
    smc: boolean;
    signals: boolean;
  };
  symbol: string;
  activePositions?: any[];
}

const TradingChart: React.FC<ChartDataProps> = ({
  data,
  settings,
  symbol,
  activePositions,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRefs = useRef<{ [key: string]: ISeriesApi<any> }>({});
  const priceLinesRef = useRef<any[]>([]);
  const markersPrimitiveRef = useRef<any>(null);

  // 🕒 KST 포맷팅
  const formatKst = (timestamp: number) => {
    const date = new Date(timestamp * 1000);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
  };

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // [v5.2] 차트 초기화
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0b0e11" },
        textColor: "#d1d4dc",
      },
      grid: {
        vertLines: { color: "rgba(42, 46, 57, 0.05)" },
        horzLines: { color: "rgba(42, 46, 57, 0.05)" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      timeScale: {
        timeVisible: true,
        borderVisible: false,
        rightOffset: 20,
        barSpacing: 6,
      },
      localization: { timeFormatter: (t: number) => formatKst(t) },
      width: chartContainerRef.current.clientWidth,
      height: 650,
    });

    const s: { [key: string]: ISeriesApi<any> } = {};

    // 1. 메인 캔들 및 거래량
    s.candle = chart.addSeries(CandlestickSeries, {
      upColor: "#2ebd85",
      downColor: "#f6465d",
      borderVisible: false,
      wickUpColor: "#2ebd85",
      wickDownColor: "#f6465d",
    });

    s.volume = chart.addSeries(HistogramSeries, {
      color: "rgba(146, 154, 165, 0.2)",
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });

    // 2. Whale 세력선 (VWMA: 흰색 두껍게 / SMA: 회색 얇게)
    s.vwma224 = chart.addSeries(LineSeries, {
      color: "#ffffff",
      lineWidth: 2,
      title: "VWMA 224",
      priceLineVisible: false,
    });
    s.sma224 = chart.addSeries(LineSeries, {
      color: "#929aa5",
      lineWidth: 1,
      title: "SMA 224",
      priceLineVisible: false,
    });

    // 3. SMC 구조 (Strong High: 빨강 점선 / Trailing Bottom: 초록 점선)
    s.swingHighLevel = chart.addSeries(LineSeries, {
      color: "#ef5350",
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: true,
      title: "Strong High",
    });
    s.trailingBottom = chart.addSeries(LineSeries, {
      color: "#26a69a",
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: true,
      title: "Strong Low",
    });

    // 거래량 스케일 조정 (차트 하단 10% 영역)
    chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.9, bottom: 0 },
    });

    chartRef.current = chart;
    seriesRefs.current = s;

    return () => chart.remove();
  }, [symbol]);

  // --- [데이터 처리 및 마커 주입] ---
  useEffect(() => {
    const s = seriesRefs.current;
    if (!data || !s || !s.candle) return;

    // 1. 캔들 및 거래량 세팅
    if (data.candles) s.candle.setData(data.candles);
    if (data.volumes && s.volume) s.volume.setData(data.volumes);

    // 2. 핵심 지표 4개만 세팅 (방어 코드 포함)
    if (data.indicators) {
      const coreIndicators = [
        "vwma224",
        "sma224",
        "swingHighLevel",
        "trailingBottom",
      ];

      coreIndicators.forEach((key) => {
        if (s[key] && data.indicators[key]) {
          try {
            s[key].setData(data.indicators[key] || []);
          } catch (err) {
            console.error(`Error setting data for ${key}:`, err);
          }
        }
      });
    }

    // 3. [v5.2] 마커 세팅 (topDiamond, bottomDiamond 대응)
    if (markersPrimitiveRef.current) {
      s.candle.detachPrimitive(markersPrimitiveRef.current);
      markersPrimitiveRef.current = null;
    }

    if (settings.signals && data.markers) {
      const formattedMarkers = data.markers.map((m: any) => {
        let color = "#2196F3";
        let shape: any = "circle";
        let text = m.text;

        // TOP (빨간 원) - 롱 익절 / 숏 타점
        if (m.text === "TOP") {
          color = "#f6465d";
          shape = "circle";
          text = "TP";
        }
        // BOTTOM (초록 원) - 숏 익절 / 롱 타점
        else if (m.text === "BOTTOM") {
          color = "#2ebd85";
          shape = "circle";
          text = "TP";
        } else if (m.text.includes("LONG")) {
          color = "#2ebd85";
          shape = "arrowUp";
        } else if (m.text.includes("SHORT")) {
          color = "#f6465d";
          shape = "arrowDown";
        }

        return {
          time: m.time as Time,
          position: m.position,
          color: color,
          shape: shape,
          text: text,
        };
      });

      const markersPrimitive = createSeriesMarkers(s.candle, formattedMarkers);
      s.candle.attachPrimitive(markersPrimitive);
      markersPrimitiveRef.current = markersPrimitive;
    }

    // 4. 가시성 제어 (토글 설정 반영)
    if (s.vwma224) s.vwma224.applyOptions({ visible: settings.whale });
    if (s.sma224) s.sma224.applyOptions({ visible: settings.whale });
    if (s.swingHighLevel)
      s.swingHighLevel.applyOptions({ visible: settings.smc });
    if (s.trailingBottom)
      s.trailingBottom.applyOptions({ visible: settings.smc });
  }, [data, settings]);

  // --- [실시간 포지션 라인] ---
  useEffect(() => {
    const s = seriesRefs.current;
    if (!s.candle || !chartRef.current) return;

    priceLinesRef.current.forEach((l) => s.candle.removePriceLine(l));
    priceLinesRef.current = [];

    if (activePositions) {
      activePositions.forEach((pos) => {
        const entryPrice = pos.entry_price || pos.entryPrice;
        const slPrice = pos.stop_loss_price || pos.slPrice;

        if (entryPrice) {
          const entryLine = s.candle.createPriceLine({
            price: Number(entryPrice),
            color: pos.side === "LONG" ? "#2196F3" : "#f6465d",
            lineWidth: 2,
            lineStyle: LineStyle.Solid,
            axisLabelVisible: true,
            title: `ENTRY ${pos.side}`,
          });
          priceLinesRef.current.push(entryLine);
        }

        if (slPrice) {
          const slLine = s.candle.createPriceLine({
            price: Number(slPrice),
            color: "#ff9800",
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: "SL",
          });
          priceLinesRef.current.push(slLine);
        }
      });
    }
  }, [activePositions, symbol]);

  return (
    <div
      ref={chartContainerRef}
      style={{ width: "100%", height: "650px", position: "relative" }}
    />
  );
};

export default TradingChart;
