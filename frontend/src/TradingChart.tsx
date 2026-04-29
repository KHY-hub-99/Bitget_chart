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
    markers: any[]; // 백엔드 통일명칭: 'topDiamond', 'bottomDiamond', 'longSig', 'shortSig'
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

  const formatKst = (timestamp: number) => {
    const date = new Date(timestamp * 1000);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
  };

  // 1. 차트 및 시리즈 초기화
  useEffect(() => {
    if (!chartContainerRef.current) return;

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

    // 💡 [수정됨] v5.x 최신 API 적용: chart.addSeries(Type, Options)[cite: 1]

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

    // 2. Whale 세력선 (VWMA, SMA)
    s.vwma224 = chart.addSeries(LineSeries, {
      color: "#ffffff",
      lineWidth: 2,
      title: "VWMA",
    });

    s.sma224 = chart.addSeries(LineSeries, {
      color: "#929aa5",
      lineWidth: 1,
      title: "SMA",
    });

    // 3. SMC 구조 및 레벨
    s.swingHighLevel = chart.addSeries(LineSeries, {
      color: "#ef5350",
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      title: "Strong High",
    });

    s.trailingBottom = chart.addSeries(LineSeries, {
      color: "#26a69a",
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      title: "Strong Low",
    });

    s.equilibrium = chart.addSeries(LineSeries, {
      color: "rgba(240, 185, 11, 0.5)",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      title: "Equilibrium",
    });

    // 거래량 스케일 조정
    chart
      .priceScale("vol")
      .applyOptions({ scaleMargins: { top: 0.9, bottom: 0 } });

    chartRef.current = chart;
    seriesRefs.current = s;

    return () => chart.remove();
  }, [symbol]);

  // 2. 데이터 업데이트 및 마커 렌더링
  useEffect(() => {
    const s = seriesRefs.current;
    if (!data || !s || !s.candle) return;

    if (data.candles) s.candle.setData(data.candles);
    if (data.volumes && s.volume) s.volume.setData(data.volumes);

    // [통일 컬럼명 데이터만 주입]
    const coreIndicators = [
      "vwma224",
      "sma224",
      "swingHighLevel",
      "trailingBottom",
      "equilibrium",
    ];
    if (data.indicators) {
      coreIndicators.forEach((key) => {
        if (s[key] && data.indicators[key]) {
          s[key].setData(data.indicators[key]);
        }
      });
    }

    // 마커 프리미티브 교체 로직
    if (markersPrimitiveRef.current) {
      s.candle.detachPrimitive(markersPrimitiveRef.current);
      markersPrimitiveRef.current = null;
    }

    if (settings.signals && data.markers) {
      const formattedMarkers = data.markers.map((m: any) => {
        let color = "#2196F3";
        let shape: any = "circle";
        let text = m.text;

        // 백엔드에서 전달한 통일 명칭 기반 매핑
        if (m.text === "topDiamond") {
          color = "#f6465d";
          shape = "circle";
          text = "TP";
        } else if (m.text === "bottomDiamond") {
          color = "#2ebd85";
          shape = "circle";
          text = "TP";
        } else if (m.text === "longSig") {
          color = "#2ebd85";
          shape = "arrowUp";
          text = "LONG";
        } else if (m.text === "shortSig") {
          color = "#f6465d";
          shape = "arrowDown";
          text = "SHORT";
        }

        return {
          time: m.time as Time,
          position: m.position,
          color,
          shape,
          text,
        };
      });

      const markersPrimitive = createSeriesMarkers(s.candle, formattedMarkers);
      s.candle.attachPrimitive(markersPrimitive);
      markersPrimitiveRef.current = markersPrimitive;
    }

    // 가시성 토글
    if (s.vwma224) s.vwma224.applyOptions({ visible: settings.whale });
    if (s.sma224) s.sma224.applyOptions({ visible: settings.whale });
    if (s.swingHighLevel)
      s.swingHighLevel.applyOptions({ visible: settings.smc });
    if (s.trailingBottom)
      s.trailingBottom.applyOptions({ visible: settings.smc });
    if (s.equilibrium) s.equilibrium.applyOptions({ visible: settings.smc });
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
