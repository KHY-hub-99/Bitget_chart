import React, { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  LineStyle,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  createSeriesMarkers,
  IChartApi,
  ISeriesApi,
  SeriesMarker,
  Time,
} from "lightweight-charts";

// --- [1. 타입 정의] ---
interface ChartDataProps {
  data: {
    candles: any[];
    volumes: any[];
    indicators: { [key: string]: { time: number; value: number }[] };
    markers: any[];
  };
  settings: {
    ichimoku: boolean;
    whale: boolean;
    smc: boolean;
    bollinger: boolean;
    rsi: boolean;
    mfi: boolean;
    macd: boolean;
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
  const markersPluginRef = useRef<any>(null);
  const priceLinesRef = useRef<any[]>([]);

  // 🕒 KST 포맷팅
  const formatKst = (timestamp: number) => {
    const date = new Date(timestamp * 1000);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
  };

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0b0e11" },
        textColor: "#929aa5",
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: "rgba(42, 46, 57, 0.1)" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      timeScale: { timeVisible: true, borderVisible: false, rightOffset: 100 },
      localization: { timeFormatter: (t: number) => formatKst(t) },
      width: chartContainerRef.current.clientWidth,
      height: 650,
    });

    const s: { [key: string]: ISeriesApi<any> } = {};

    s.candle = chart.addSeries(CandlestickSeries, {
      upColor: "#2ebd85",
      downColor: "#f6465d",
      borderVisible: false,
    });
    s.volume = chart.addSeries(HistogramSeries, {
      color: "rgba(146, 154, 165, 0.2)",
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });

    s.vwma224 = chart.addSeries(LineSeries, {
      color: "#ffffff",
      lineWidth: 3,
      title: "VWMA 224",
    });
    s.sma224 = chart.addSeries(LineSeries, {
      color: "#929aa5",
      lineWidth: 1,
      title: "SMA 224",
    });

    // 🚀 SMC 기준 변경: SwingHigh(상단), TrailingBottom(하단), Equilibrium(평균)
    s.swingHighLevel = chart.addSeries(LineSeries, {
      color: "#f6465d",
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
    });
    s.trailingBottom = chart.addSeries(LineSeries, {
      color: "#2ebd85",
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
    });
    s.equilibrium = chart.addSeries(LineSeries, {
      color: "#f0b90b",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
    });

    s.trailingTop = chart.addSeries(LineSeries, {
      color: "rgba(246, 70, 93, 0.4)",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
    });

    s.tenkan = chart.addSeries(LineSeries, {
      color: "#05f1ff",
      lineWidth: 1,
      title: "Tenkan",
    });
    s.kijun = chart.addSeries(LineSeries, {
      color: "#ff3a3a",
      lineWidth: 1,
      title: "Kijun",
    });
    s.senkouA = chart.addSeries(LineSeries, {
      color: "rgba(38, 166, 154, 0.4)",
      lineWidth: 1,
      title: "Senkou A",
    });
    s.senkouB = chart.addSeries(LineSeries, {
      color: "rgba(239, 83, 80, 0.4)",
      lineWidth: 1,
      title: "Senkou B",
    });

    s.rsi = chart.addSeries(LineSeries, {
      color: "#9c27b0",
      lineWidth: 1,
      priceScaleId: "rsi",
    });
    chart
      .priceScale("rsi")
      .applyOptions({ scaleMargins: { top: 0.75, bottom: 0.05 } });
    chart
      .priceScale("vol")
      .applyOptions({ scaleMargins: { top: 0.9, bottom: 0 } });

    chartRef.current = chart;
    seriesRefs.current = s;
    return () => chart.remove();
  }, [symbol]);

  // --- [데이터 및 로직 연산] ---
  useEffect(() => {
    const s = seriesRefs.current;
    if (!data || !s.candle) return;

    s.candle.setData(data.candles || []);
    s.volume.setData(data.volumes || []);

    if (data.indicators) {
      // 1. 일반 지표 주입 (equilibrium 및 기존 swingLowLevel 제외)
      Object.entries(data.indicators).forEach(([key, values]) => {
        if (
          key !== "equilibrium" &&
          key !== "swingLowLevel" &&
          s[key] &&
          values
        ) {
          s[key].setData(values);
        }
      });

      // 2. 🚀 새로운 Equilibrium 계산: (swingHighLevel + trailingBottom) / 2
      const highData = data.indicators.swingHighLevel || [];
      const bottomData = data.indicators.trailingBottom || [];

      if (highData.length > 0 && bottomData.length > 0) {
        // 시간(time)을 기준으로 맵핑하기 위해 Map 생성
        const bottomMap = new Map(bottomData.map((d) => [d.time, d.value]));

        const newEquilibrium = highData
          .filter((h) => bottomMap.has(h.time))
          .map((h) => ({
            time: h.time,
            value: (h.value + bottomMap.get(h.time)!) / 2, // 상단과 하단의 평균값 계산
          }));

        if (newEquilibrium.length > 0) {
          s.equilibrium.setData(newEquilibrium);
        }
      } else if (data.indicators.equilibrium) {
        // 백업용 기존 데이터
        s.equilibrium.setData(data.indicators.equilibrium);
      }
    }

    if (markersPluginRef.current) {
      try {
        s.candle.detachPrimitive(markersPluginRef.current);
      } catch (e) {}
    }
    if (settings.signals && data.markers) {
      const sorted = [...data.markers].sort((a, b) => a.time - b.time);
      markersPluginRef.current = createSeriesMarkers(
        s.candle,
        sorted.map((m) => ({
          ...m,
          shape: m.shape === "diamond" ? "square" : m.shape,
        })),
      );
    }

    // 가시성 제어 (불필요한 swingLowLevel은 토글에서 제거)
    s.vwma224.applyOptions({ visible: settings.whale });
    s.sma224.applyOptions({ visible: settings.whale });
    ["swingHighLevel", "trailingBottom", "equilibrium", "trailingTop"].forEach(
      (k) => {
        if (s[k]) s[k].applyOptions({ visible: settings.smc });
      },
    );
    ["tenkan", "kijun", "senkouA", "senkouB"].forEach((k) =>
      s[k]?.applyOptions({ visible: settings.ichimoku }),
    );
    s.rsi.applyOptions({ visible: settings.rsi });
  }, [data, settings]);

  // --- [실시간 포지션 및 Trailing 라벨] ---
  useEffect(() => {
    const s = seriesRefs.current;
    if (!s.candle || !data) return;

    priceLinesRef.current.forEach((l) => s.candle.removePriceLine(l));
    priceLinesRef.current = [];

    if (activePositions) {
      activePositions.forEach((pos) => {
        const entry = s.candle.createPriceLine({
          price: pos.entry_price || pos.entryPrice,
          color: pos.side === "LONG" ? "#2196F3" : "#f6465d",
          lineWidth: 2,
          title: `ENTRY (${pos.side})`,
          axisLabelVisible: true,
        });
        const sl = s.candle.createPriceLine({
          price: pos.stop_loss_price || pos.slPrice,
          color: "#ff9800",
          lineWidth: 2,
          lineStyle: LineStyle.Dashed,
          title: "SL (POS)",
          axisLabelVisible: true,
        });
        priceLinesRef.current.push(entry, sl);
      });
    }

    if (data.indicators) {
      // SMC 상단 (swingHighLevel 기준)
      if (data.indicators.swingHighLevel?.length > 0) {
        const lastTop =
          data.indicators.swingHighLevel[
            data.indicators.swingHighLevel.length - 1
          ];
        const topLine = s.candle.createPriceLine({
          price: lastTop.value,
          color: "#f6465d",
          lineWidth: 2,
          lineStyle: LineStyle.Dashed,
          title: "SMC High",
          axisLabelVisible: true,
        });
        priceLinesRef.current.push(topLine);
      }

      // SMC 하단 (trailingBottom 기준)
      if (data.indicators.trailingBottom?.length > 0) {
        const lastBottom =
          data.indicators.trailingBottom[
            data.indicators.trailingBottom.length - 1
          ];
        const bottomLine = s.candle.createPriceLine({
          price: lastBottom.value,
          color: "#2ebd85",
          lineWidth: 2,
          lineStyle: LineStyle.Dashed,
          title: "SMC Low (Trailing)",
          axisLabelVisible: true,
        });
        priceLinesRef.current.push(bottomLine);
      }
    }
  }, [activePositions, data, symbol]);

  return (
    <div
      ref={chartContainerRef}
      style={{ width: "100%", height: "650px", position: "relative" }}
    />
  );
};

export default TradingChart;
