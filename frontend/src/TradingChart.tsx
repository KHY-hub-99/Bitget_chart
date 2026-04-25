import React, { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  AreaSeries,
  LineStyle,
  createSeriesMarkers, // 🎯 [V5 핵심] 마커 플러그인 임포트!
  IChartApi,
  ISeriesApi,
} from "lightweight-charts";

interface ChartDataProps {
  data: {
    candles: any[];
    volumes: any[];
    indicators: { [key: string]: any[] };
    markers: any[];
  };
  settings: {
    kijun: boolean;
    ichimoku: boolean;
    bollinger: boolean;
    rsi: boolean;
    macd: boolean;
  };
  symbol: string;
}

const TradingChart: React.FC<ChartDataProps> = ({ data, settings, symbol }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const legendRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRefs = useRef<{ [key: string]: any }>({}); // 타입 유연성을 위해 any 처리

  const settingsRef = useRef(settings);
  const symbolRef = useRef(symbol);

  useEffect(() => {
    settingsRef.current = settings;
  }, [settings]);

  useEffect(() => {
    symbolRef.current = symbol;
  }, [symbol]);

  const processData = (items: any[], isCandle = false) => {
    if (!items || !Array.isArray(items)) return [];
    const uniqueMap = new Map();

    items.forEach((item) => {
      if (!item || !item.time) return;

      if (!isCandle) {
        // 0 이하(음수)를 허용하도록 수정
        if (
          item.value === null ||
          item.value === undefined ||
          isNaN(item.value)
        ) {
          return;
        }
      }
      uniqueMap.set(item.time, item);
    });

    return Array.from(uniqueMap.values()).sort((a, b) => a.time - b.time);
  };

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0b0e11" },
        textColor: "#929aa5",
        fontSize: 12,
        fontFamily: "'Inter', sans-serif",
      },
      localization: {
        locale: "ko-KR",
        timeFormatter: (timestamp: number) => {
          const d = new Date(timestamp * 1000);
          return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
        },
      },
      grid: {
        vertLines: { color: "rgba(42, 46, 57, 0.03)" },
        horzLines: { color: "rgba(42, 46, 57, 0.03)" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { labelBackgroundColor: "#2962FF" },
        horzLine: { labelBackgroundColor: "#2962FF" },
      },
      timeScale: {
        borderColor: "rgba(197, 203, 206, 0.2)",
        timeVisible: true,
        secondsVisible: false,
        barSpacing: 12,
        rightOffset: 30,
        shiftVisibleRangeOnNewBar: true,
      },
      width: chartContainerRef.current.clientWidth,
      height: 650,
    });

    const s: any = {};

    // 🎯 [V5 핵심] 최신 통합 API 방식으로 복귀 (addSeries 사용)
    s.candle = chart.addSeries(CandlestickSeries, {
      upColor: "#2ebd85",
      downColor: "#f6465d",
      borderVisible: false,
      wickUpColor: "#2ebd85",
      wickDownColor: "#f6465d",
    });

    // 🎯 [V5 핵심] 마커 플러그인을 생성하여 s 객체에 저장해 둡니다.
    s.markersPlugin = createSeriesMarkers(s.candle);

    s.kijun = chart.addSeries(LineSeries, { color: "#f0b90b", lineWidth: 2 });
    s.senkou_a = chart.addSeries(LineSeries, {
      color: "rgba(46, 189, 133, 0.4)",
      lineWidth: 1,
    });
    s.senkou_b = chart.addSeries(LineSeries, {
      color: "rgba(246, 70, 93, 0.4)",
      lineWidth: 1,
    });
    s.cloud = chart.addSeries(AreaSeries, {
      lineColor: "transparent",
      topColor: "rgba(46, 189, 133, 0.25)",
      bottomColor: "rgba(11, 14, 17, 0)",
      lineWidth: 0,
      priceLineVisible: false,
      baseValue: { type: "price", price: 0 },
    });

    s.bb_upper = chart.addSeries(LineSeries, {
      color: "rgba(33, 150, 243, 0.4)",
      lineStyle: LineStyle.Dashed,
      lineWidth: 1,
    });
    s.bb_middle = chart.addSeries(LineSeries, {
      color: "rgba(158, 158, 158, 0.2)",
      lineStyle: LineStyle.Dotted,
      lineWidth: 1,
    });
    s.bb_lower = chart.addSeries(LineSeries, {
      color: "rgba(33, 150, 243, 0.4)",
      lineStyle: LineStyle.Dashed,
      lineWidth: 1,
    });

    s.rsi = chart.addSeries(LineSeries, {
      color: "#9c27b0",
      lineWidth: 2,
      priceScaleId: "rsi_p",
    });
    s.macd = chart.addSeries(LineSeries, {
      color: "#2962FF",
      lineWidth: 1.5,
      priceScaleId: "macd_p",
    });
    s.volume = chart.addSeries(HistogramSeries, {
      color: "rgba(146, 154, 165, 0.2)",
      priceFormat: { type: "volume" },
      priceScaleId: "vol_p",
    });

    chart.priceScale("right").applyOptions({
      autoScale: true, // 자동 스케일 활성화 [cite: 796]
      scaleMargins: {
        top: 0.1, // 상단 10% 여백 [cite: 801]
        bottom: 0.2, // 하단 20% 여백 (지표 레이어를 위해) [cite: 801]
      },
    });
    chart
      .priceScale("rsi_p")
      .applyOptions({ scaleMargins: { top: 0.65, bottom: 0.2 } });
    chart
      .priceScale("macd_p")
      .applyOptions({ scaleMargins: { top: 0.82, bottom: 0.08 } });
    chart
      .priceScale("vol_p")
      .applyOptions({ scaleMargins: { top: 0.93, bottom: 0 } });

    seriesRefs.current = s;
    chartRef.current = chart;

    chart.subscribeCrosshairMove((param) => {
      if (!legendRef.current) return;
      const s = seriesRefs.current;
      const candle = param.seriesData.get(s.candle) as any;
      if (!candle || !param.time) return;

      const color = candle.close >= candle.open ? "#2ebd85" : "#f6465d";

      const kijunV = param.seriesData.get(s.kijun) as any;
      const rsiV = param.seriesData.get(s.rsi) as any;
      const macdV = param.seriesData.get(s.macd) as any;
      const bbuV = param.seriesData.get(s.bb_upper) as any;
      const bblV = param.seriesData.get(s.bb_lower) as any;
      const volV = param.seriesData.get(s.volume) as any;

      const numStyle = `font-family: 'IBM Plex Mono', monospace; font-variant-numeric: tabular-nums; letter-spacing: -0.5px;`;
      const f = (val: number) =>
        val.toLocaleString(undefined, {
          minimumFractionDigits: 1,
          maximumFractionDigits: 1,
        });
      const formatVol = (val: number) => {
        if (val >= 1000000) return (val / 1000000).toFixed(2) + "M";
        if (val >= 1000) return (val / 1000).toFixed(2) + "K";
        return val.toFixed(1);
      };

      const formattedSymbol = symbolRef.current.replace("USDT", " / USDT");

      // 🎯 [해결] 옵셔널 체이닝(?.)과 !== undefined를 통해 .value 참조 전 완벽한 방어벽 구축
      legendRef.current.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
          <span style="color: #fff; font-size: 14px; font-weight: 800; letter-spacing: -0.02em;">${formattedSymbol}</span>
          <span style="font-size: 10px; color: #5d6673; font-weight: 500; ${numStyle}">${new Date((param.time as number) * 1000).toLocaleString()}</span>
        </div>
        
        <div style="display: flex; gap: 16px; margin-bottom: 14px; font-size: 13px;">
          <div style="display: flex; flex-direction: column;"><span style="color: #5d6673; font-size: 9px; font-weight: 700; margin-bottom: 2px;">OPEN</span><span style="color: #e6e8ea; ${numStyle}">${f(candle.open)}</span></div>
          <div style="display: flex; flex-direction: column;"><span style="color: #5d6673; font-size: 9px; font-weight: 700; margin-bottom: 2px;">HIGH</span><span style="color: #e6e8ea; ${numStyle}">${f(candle.high)}</span></div>
          <div style="display: flex; flex-direction: column;"><span style="color: #5d6673; font-size: 9px; font-weight: 700; margin-bottom: 2px;">LOW</span><span style="color: #e6e8ea; ${numStyle}">${f(candle.low)}</span></div>
          <div style="display: flex; flex-direction: column;"><span style="color: #5d6673; font-size: 9px; font-weight: 700; margin-bottom: 2px;">CLOSE</span><span style="color: ${color}; font-weight: 700; ${numStyle}">${f(candle.close)}</span></div>
          <div style="display: flex; flex-direction: column;"><span style="color: #5d6673; font-size: 9px; font-weight: 700; margin-bottom: 2px;">VOL</span><span style="color: #e6e8ea; ${numStyle}">${volV?.value !== undefined ? formatVol(volV.value) : "0.0"}</span></div>
        </div>

        <div style="display: flex; flex-wrap: wrap; gap: 6px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 12px;">
          ${settingsRef.current.kijun && kijunV?.value !== undefined ? `<div style="background: rgba(240, 185, 11, 0.08); padding: 4px 10px; border-radius: 4px; display: flex; align-items: center; gap: 8px;"><span style="color: #f0b90b; font-size: 9px; font-weight: 900;">KIJUN</span><span style="color: #f0b90b; font-size: 11px; font-weight: 500; ${numStyle}">${f(kijunV.value)}</span></div>` : ""}
          ${settingsRef.current.bollinger && bbuV?.value !== undefined && bblV?.value !== undefined ? `<div style="background: rgba(33, 150, 243, 0.08); padding: 4px 10px; border-radius: 4px; display: flex; align-items: center; gap: 8px;"><span style="color: #2196f3; font-size: 9px; font-weight: 900;">BB</span><span style="color: #2196f3; font-size: 11px; font-weight: 500; ${numStyle}">${bbuV.value.toFixed(0)} - ${bblV.value.toFixed(0)}</span></div>` : ""}
          ${settingsRef.current.rsi && rsiV?.value !== undefined ? `<div style="background: rgba(156, 39, 176, 0.08); padding: 4px 10px; border-radius: 4px; display: flex; align-items: center; gap: 8px;"><span style="color: #9c27b0; font-size: 9px; font-weight: 900;">RSI</span><span style="color: #9c27b0; font-size: 11px; font-weight: 500; ${numStyle}">${rsiV.value.toFixed(2)}</span></div>` : ""}
          ${settingsRef.current.macd && macdV?.value !== undefined ? `<div style="background: rgba(41, 98, 255, 0.08); padding: 4px 10px; border-radius: 4px; display: flex; align-items: center; gap: 8px;"><span style="color: #2962FF; font-size: 9px; font-weight: 900;">MACD</span><span style="color: #2962FF; font-size: 11px; font-weight: 500; ${numStyle}">${macdV.value.toFixed(2)}</span></div>` : ""}
        </div>
      `;
    });

    const handleResize = () =>
      chart.applyOptions({ width: chartContainerRef.current!.clientWidth });
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (!chartRef.current || !data) return;
    const s = seriesRefs.current;

    const finalCandles = processData(data.candles, true);
    s.candle.setData(finalCandles);

    const finalVols = processData(data.volumes);
    s.volume.setData(
      finalVols.map((v) => {
        const c = finalCandles.find((cand) => cand.time === v.time);
        return {
          ...v,
          color:
            c && c.close >= c.open
              ? "rgba(46, 189, 133, 0.25)"
              : "rgba(246, 70, 93, 0.25)",
        };
      }),
    );

    if (data.indicators?.kijun)
      s.kijun.setData(processData(data.indicators.kijun));
    if (data.indicators?.senkou_a) {
      const sa = processData(data.indicators.senkou_a);
      s.senkou_a.setData(sa);
      s.cloud.setData(sa);
    }
    if (data.indicators?.senkou_b)
      s.senkou_b.setData(processData(data.indicators.senkou_b));
    if (data.indicators?.bb_upper)
      s.bb_upper.setData(processData(data.indicators.bb_upper));
    if (data.indicators?.bb_middle)
      s.bb_middle.setData(processData(data.indicators.bb_middle));
    if (data.indicators?.bb_lower)
      s.bb_lower.setData(processData(data.indicators.bb_lower));
    if (data.indicators?.rsi) s.rsi.setData(processData(data.indicators.rsi));
    if (data.indicators?.macd_line)
      s.macd.setData(processData(data.indicators.macd_line));

    // 🎯 [V5 핵심] 마커 플러그인을 통한 마커 세팅!
    if (s.markersPlugin && data.markers) {
      const markerData = processData(data.markers, true);
      s.markersPlugin.setMarkers(markerData);
    }

    Object.keys(settings).forEach((key) => {
      if (key === "ichimoku") {
        ["senkou_a", "senkou_b", "cloud"].forEach((k) =>
          s[k]?.applyOptions({ visible: settings.ichimoku }),
        );
      } else if (key === "bollinger") {
        ["bb_upper", "bb_middle", "bb_lower"].forEach((k) =>
          s[k]?.applyOptions({ visible: settings.bollinger }),
        );
      } else if (s[key]) {
        s[key].applyOptions({ visible: (settings as any)[key] });
      }
    });
  }, [data, settings]);

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "650px",
        background: "#0b0e11",
        borderRadius: "16px",
        overflow: "hidden",
        border: "1px solid #1e222d",
      }}
    >
      <div
        ref={legendRef}
        style={{
          position: "absolute",
          top: 20,
          left: 20,
          zIndex: 10,
          pointerEvents: "none",
          fontFamily: "'Inter', sans-serif",
          background: "rgba(11, 14, 17, 0.85)",
          backdropFilter: "blur(12px)",
          padding: "18px",
          borderRadius: "14px",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          boxShadow: "0 12px 48px rgba(0, 0, 0, 0.5)",
          minWidth: "320px",
        }}
      />
      <div ref={chartContainerRef} style={{ width: "100%", height: "100%" }} />
    </div>
  );
};

export default TradingChart;
