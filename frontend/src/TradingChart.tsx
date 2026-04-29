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
  const priceLinesRef = useRef<any[]>([]);

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

    // 1. 메인 캔들
    s.candle = chart.addSeries(CandlestickSeries, {
      upColor: "#2ebd85",
      downColor: "#f6465d",
      borderVisible: false,
      wickUpColor: "#2ebd85",
      wickDownColor: "#f6465d",
    });

    // 2. Whale 세력선 (흰색/회색)
    s.vwma224 = chart.addSeries(LineSeries, {
      color: "#ffffff", // 흰색 진한 선
      lineWidth: 2,
      title: "VWMA 224",
      priceLineVisible: false,
    });
    s.sma224 = chart.addSeries(LineSeries, {
      color: "#929aa5", // 회색 얇은 선
      lineWidth: 1,
      title: "SMA 224",
      priceLineVisible: false,
    });

    // 3. SMC 구조 (Strong High 빨강 / Trailing Bottom 초록)
    s.swingHighLevel = chart.addSeries(LineSeries, {
      color: "#ef5350", // Strong High (빨강)
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: true,
      title: "Strong High",
    });
    s.trailingBottom = chart.addSeries(LineSeries, {
      color: "#26a69a", // Trailing Bottom (초록)
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      priceLineVisible: true,
      title: "Strong Low",
    });
    s.equilibrium = chart.addSeries(LineSeries, {
      color: "rgba(240, 185, 11, 0.5)",
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
      title: "Equilibrium",
    });

    // 4. 보조 지표 (일단 로드는 수행)
    s.tenkan = chart.addSeries(LineSeries, { color: "#05f1ff", lineWidth: 1 });
    s.kijun = chart.addSeries(LineSeries, { color: "#ff3a3a", lineWidth: 1 });
    s.rsiVal = chart.addSeries(LineSeries, {
      color: "#9c27b0",
      lineWidth: 1,
      priceScaleId: "rsi",
    });

    chart
      .priceScale("rsi")
      .applyOptions({ scaleMargins: { top: 0.8, bottom: 0.05 } });

    chartRef.current = chart;
    seriesRefs.current = s;

    return () => chart.remove();
  }, [symbol]);

  const markersPrimitiveRef = useRef<any>(null);

  // --- [데이터 처리 및 마커 주입] ---
  useEffect(() => {
    const s = seriesRefs.current;
    if (!data || !s || !s.candle) return;

    // 1. 캔들 및 볼륨은 고정이므로 안전하게 세팅
    if (data.candles) s.candle.setData(data.candles);
    if (data.volumes && s.volume) s.volume.setData(data.volumes);

    // 2. 지표 데이터 세팅 (에러 발생 지점)
    if (data.indicators) {
      Object.entries(data.indicators).forEach(([key, values]) => {
        // [핵심 수정] s[key]가 존재하는지 반드시 확인 후 setData 호출
        if (s[key]) {
          try {
            s[key].setData(values || []);
          } catch (err) {
            console.error(`Error setting data for ${key}:`, err);
          }
        } else {
          // 이 로그가 찍힌다면 백엔드에서는 보내는데 프론트에서 addSeries를 안 한 것임
          console.warn(
            `시리즈 ${key}가 차트에 등록되지 않았습니다. addSeries를 확인하세요.`,
          );
        }
      });
    }

    // [3. v5.2 전용 마커 로직] - setMarkers 대신 createSeriesMarkers 사용
    // 기존에 붙어있던 마커 프리미티브가 있다면 먼저 떼어냄
    if (markersPrimitiveRef.current) {
      s.candle.detachPrimitive(markersPrimitiveRef.current);
      markersPrimitiveRef.current = null;
    }

    if (settings.signals && data.markers) {
      const formattedMarkers = data.markers.map((m: any) => {
        let color = "#2196F3"; // 기본
        let shape: any = "circle";
        let text = m.text;

        // 사용자의 전략 컬러 및 형태 매핑
        // TOP (빨간 다이아/원) - 롱 익절
        if (m.text === "TOP") {
          color = "#f6465d"; // 빨강
          shape = "circle";
          text = "TP";
        }
        // BOTTOM (초록 다이아/원) - 숏 익절
        else if (m.text === "BOTTOM") {
          color = "#2ebd85"; // 초록
          shape = "circle";
          text = "TP";
        }
        // 일반 진입 신호 처리
        else if (m.text.includes("LONG")) {
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

      // v5.2 방식: 프리미티브 생성 후 시리즈에 attach
      const markersPrimitive = createSeriesMarkers(s.candle, formattedMarkers);
      s.candle.attachPrimitive(markersPrimitive);

      // 다음에 업데이트할 때 제거하기 위해 ref에 저장
      markersPrimitiveRef.current = markersPrimitive;
    }

    // [4. 가시성 제어]
    s.vwma224.applyOptions({ visible: settings.whale });
    s.sma224.applyOptions({ visible: settings.whale });
    s.swingHighLevel.applyOptions({ visible: settings.smc });
    s.trailingBottom.applyOptions({ visible: settings.smc });
  }, [data, settings]);

  // --- [실시간 포지션 라인] ---
  useEffect(() => {
    const s = seriesRefs.current;
    if (!s.candle || !chartRef.current) return;

    // 기존 라인 제거
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
