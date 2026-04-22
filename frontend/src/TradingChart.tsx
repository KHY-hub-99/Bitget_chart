import React, { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createSeriesMarkers,
  LineStyle,
} from "lightweight-charts";

interface ChartDataProps {
  data: {
    candles: any[];
    volumes: any[];
    indicators: {
      kijun?: any[];
      bb_upper?: any[];
      bb_lower?: any[];
      rsi?: any[];
      macd_line?: any[];
      macd_sig?: any[];
      senkou_a?: any[]; // 백엔드 키값에 맞춰 snake_case로 수정
      senkou_b?: any[];
    };
    markers: any[];
  };
}

const TradingChart: React.FC<ChartDataProps> = ({ data }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const legendRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartContainerRef.current || !legendRef.current || !data) return;

    chartContainerRef.current.innerHTML = "";

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#131722" },
        textColor: "#d1d4dc",
        fontSize: 12,
      },
      localization: {
        locale: "ko-KR",
        timeFormatter: (time: number) => {
          const date = new Date(time * 1000);
          return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일 ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
        },
      },
      grid: {
        vertLines: { color: "rgba(42, 46, 57, 0.2)" },
        horzLines: { color: "rgba(42, 46, 57, 0.2)" },
      },
      width: chartContainerRef.current.clientWidth,
      height: 600,
      crosshair: { mode: CrosshairMode.Normal },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderVisible: false,
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
    });
    candleSeries.setData(data.candles);

    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: "#26a69a",
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });
    volumeSeries
      .priceScale()
      .applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
    volumeSeries.setData(
      data.volumes.map((vol, index) => ({
        ...vol,
        color:
          data.candles[index].close >= data.candles[index].open
            ? "rgba(38, 166, 154, 0.2)"
            : "rgba(239, 83, 80, 0.2)",
      })),
    );

    // 지표 렌더링 함수
    const addLine = (
      name: string,
      indicatorData: any,
      color: string,
      pane?: string,
    ) => {
      if (indicatorData && indicatorData.length > 0) {
        const series = chart.addSeries(LineSeries, {
          color,
          lineWidth: name === "Kijun" ? 2 : 1,
          priceScaleId: pane || "right",
        });
        series.setData(indicatorData.filter((i: any) => i.value !== null));
        return series;
      }
      return null;
    };

    // 🎯 1. Kijun 색상 변경 (주황색, 약간 투명하게)
    const kijunSeries = addLine(
      "Kijun",
      data.indicators?.kijun,
      "rgba(255, 152, 0, 0.9)",
    );

    // 🎯 2. 지표 누락 해결 (백엔드 키값인 snake_case로 호출)
    addLine("SenkouA", data.indicators?.senkou_a, "rgba(0, 150, 136, 0.3)");
    addLine("SenkouB", data.indicators?.senkou_b, "rgba(255, 82, 82, 0.3)");

    const rsiSeries = addLine("RSI", data.indicators?.rsi, "#9c27b0", "rsi");
    const macdSeries = addLine(
      "MACD",
      data.indicators?.macd_line,
      "#2962FF",
      "macd",
    );

    if (data.indicators?.rsi)
      chart
        .priceScale("rsi")
        .applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
    if (data.indicators?.macd_line)
      chart
        .priceScale("macd")
        .applyOptions({ scaleMargins: { top: 0.7, bottom: 0.1 } });

    // 마커 로직 (유지)
    if (data.markers && data.markers.length > 0) {
      const formattedMarkers = data.markers.map((marker) => {
        let shape: any = "circle";
        let color: string = "#d1d4dc";
        let position: any = marker.position || "aboveBar";
        const textTag = (marker.text || "").toUpperCase();

        if (textTag.includes("LONG")) {
          shape = "arrowUp";
          color = "#26a69a";
          position = "belowBar";
        } else if (textTag.includes("SHORT")) {
          shape = "arrowDown";
          color = "#ef5350";
          position = "aboveBar";
        } else if (textTag.includes("TOP")) {
          shape = "square";
          color = "#f23645";
          position = "aboveBar";
        } else if (textTag.includes("BOT")) {
          shape = "square";
          color = "#26a69a";
          position = "belowBar";
        }

        return { ...marker, shape, color, position, size: 2.5 };
      });
      createSeriesMarkers(candleSeries, formattedMarkers as any);
    }

    // 🎯 3. Legend 수치 추가 (RSI, Kijun 등)
    const updateLegend = (param: any) => {
      if (!legendRef.current) return;
      const candle =
        param.seriesData.get(candleSeries) ||
        data.candles[data.candles.length - 1];

      // 실시간 지표 값 가져오기
      const rsiVal = rsiSeries ? param.seriesData.get(rsiSeries) : null;
      const kijunVal = kijunSeries ? param.seriesData.get(kijunSeries) : null;
      const macdVal = macdSeries ? param.seriesData.get(macdSeries) : null;

      const d = new Date(candle.time * 1000);
      const dateStr = `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
      const color = candle.close >= candle.open ? "#26a69a" : "#ef5350";

      legendRef.current.innerHTML = `
        <div style="color: #eceff1; font-weight: bold; margin-bottom: 4px;">
            BTC/USDT <span style="font-size: 11px; font-weight: normal; color: #848e9c; margin-left: 8px;">${dateStr}</span>
        </div>
        <div style="font-size: 12px; margin-bottom: 4px;">
            <span style="color: #848e9c">O:</span> <span style="color: ${color}">${candle.open}</span>
            <span style="color: #848e9c; margin-left: 8px;">H:</span> <span style="color: ${color}">${candle.high}</span>
            <span style="color: #848e9c; margin-left: 8px;">L:</span> <span style="color: ${color}">${candle.low}</span>
            <span style="color: #848e9c; margin-left: 8px;">C:</span> <span style="color: ${color}">${candle.close}</span>
        </div>
        <div style="font-size: 11px; display: flex; gap: 10px; margin-top: 2px;">
            ${kijunVal ? `<span style="color: rgba(255, 152, 0, 1)">Kijun: ${kijunVal.value.toFixed(2)}</span>` : ""}
            ${rsiVal ? `<span style="color: #9c27b0">RSI: ${rsiVal.value.toFixed(2)}</span>` : ""}
            ${macdVal ? `<span style="color: #2962FF">MACD: ${macdVal.value.toFixed(2)}</span>` : ""}
        </div>`;
    };

    chart.subscribeCrosshairMove(updateLegend);
    updateLegend({ seriesData: new Map() });

    const handleResize = () =>
      chartContainerRef.current &&
      chart.applyOptions({ width: chartContainerRef.current.clientWidth });
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [data]);

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "600px",
        background: "#131722",
        borderRadius: "8px",
        overflow: "hidden",
      }}
    >
      <div
        ref={legendRef}
        style={{
          position: "absolute",
          top: 16,
          left: 16,
          zIndex: 10,
          pointerEvents: "none",
          fontFamily: "sans-serif",
        }}
      />
      <div ref={chartContainerRef} style={{ width: "100%", height: "100%" }} />
    </div>
  );
};

export default TradingChart;
