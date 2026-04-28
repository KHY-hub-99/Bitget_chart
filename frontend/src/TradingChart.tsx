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
  createSeriesMarkers,
  IChartApi,
  IPriceLine,
} from "lightweight-charts";

// 🎯 [추가] App.tsx에서 변경된 카테고리에 맞춰 settings 타입 업데이트
interface ChartDataProps {
  data: {
    candles: any[];
    volumes: any[];
    indicators: { [key: string]: any[] };
    markers?: any[]; // 백엔드에서 생성해서 주는 마커 데이터 (선택)
  };
  settings: {
    ichimoku: boolean;
    whale: boolean;
    smc: boolean;
    bollinger: boolean;
    rsi: boolean;
    mfi: boolean;
    macd: boolean;
    signals: boolean; // 시그널 마커 토글
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
  const legendRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRefs = useRef<{ [key: string]: any }>({});
  const priceLinesRef = useRef<IPriceLine[]>([]);

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

  // --- [차트 초기화 useEffect] ---
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
          return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
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

    // 1. 메인 캔들
    s.candle = chart.addSeries(CandlestickSeries, {
      upColor: "#2ebd85",
      downColor: "#f6465d",
      borderVisible: false,
      wickUpColor: "#2ebd85",
      wickDownColor: "#f6465d",
    });

    // 🎯 [수정] 마커 플러그인 생성
    s.markersPlugin = createSeriesMarkers(s.candle);

    // 2. Whale 세력선 (시뮬전략.txt 반영)
    s.vwma224 = chart.addSeries(LineSeries, {
      color: "#ffffff", // 흰색 진한 선
      lineWidth: 3,
    });
    s.sma224 = chart.addSeries(LineSeries, {
      color: "#9e9e9e", // 회색 얇은 선
      lineWidth: 1,
    });

    // 3. SMC 구조 라인
    s.swingHighLevel = chart.addSeries(LineSeries, {
      color: "rgba(246, 70, 93, 0.8)", // 숏 기준선 (빨강)
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
    });
    s.swingLowLevel = chart.addSeries(LineSeries, {
      color: "rgba(41, 98, 255, 0.8)", // 롱 기준선 (파랑)
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
    });
    s.equilibrium = chart.addSeries(LineSeries, {
      color: "rgba(240, 185, 11, 0.8)", // 50% 익절 기준선 (노랑)
      lineWidth: 1,
      lineStyle: LineStyle.Dotted,
    });

    // 4. 일목균형표
    s.tenkan = chart.addSeries(LineSeries, { color: "#f0b90b", lineWidth: 1 });
    s.kijun = chart.addSeries(LineSeries, { color: "#ff9800", lineWidth: 2 });
    s.senkouA = chart.addSeries(LineSeries, {
      color: "rgba(46, 189, 133, 0.4)",
      lineWidth: 1,
    });
    s.senkouB = chart.addSeries(LineSeries, {
      color: "rgba(246, 70, 93, 0.4)",
      lineWidth: 1,
    });
    s.cloud = chart.addSeries(AreaSeries, {
      lineColor: "transparent",
      topColor: "rgba(46, 189, 133, 0.25)",
      bottomColor: "rgba(11, 14, 17, 0)",
      lineWidth: 0,
      priceLineVisible: false,
    });

    // 5. 볼린저 밴드
    s.bbUpper = chart.addSeries(LineSeries, {
      color: "rgba(33, 150, 243, 0.4)",
      lineStyle: LineStyle.Dashed,
      lineWidth: 1,
    });
    s.bbMid = chart.addSeries(LineSeries, {
      color: "rgba(158, 158, 158, 0.2)",
      lineStyle: LineStyle.Dotted,
      lineWidth: 1,
    });
    s.bbLower = chart.addSeries(LineSeries, {
      color: "rgba(33, 150, 243, 0.4)",
      lineStyle: LineStyle.Dashed,
      lineWidth: 1,
    });

    // 6. 하단 보조지표 (RSI, MFI, MACD, Volume)
    s.rsi = chart.addSeries(LineSeries, {
      color: "#9c27b0",
      lineWidth: 2,
      priceScaleId: "rsi_p",
    });
    s.mfi = chart.addSeries(LineSeries, {
      color: "#00bcd4",
      lineWidth: 2,
      priceScaleId: "rsi_p",
    });
    s.macdLine = chart.addSeries(LineSeries, {
      color: "#2962FF",
      lineWidth: 1.5,
      priceScaleId: "macd_p",
    });
    s.signalLine = chart.addSeries(LineSeries, {
      color: "#ff9800",
      lineWidth: 1.5,
      priceScaleId: "macd_p",
    });

    s.volume = chart.addSeries(HistogramSeries, {
      color: "rgba(146, 154, 165, 0.2)",
      priceFormat: { type: "volume" },
      priceScaleId: "vol_p",
    });

    // 7. 차트 스케일 조정
    chart.priceScale("right").applyOptions({
      autoScale: true,
      scaleMargins: { top: 0.1, bottom: 0.2 },
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

    // --- [레전드 (Tooltip) 로직] ---
    chart.subscribeCrosshairMove((param) => {
      if (!legendRef.current) return;
      const s = seriesRefs.current;
      const candle = param.seriesData.get(s.candle) as any;
      if (!candle || !param.time) return;

      const color = candle.close >= candle.open ? "#2ebd85" : "#f6465d";
      const formatVol = (val: number) => {
        if (val >= 1000000) return (val / 1000000).toFixed(2) + "M";
        if (val >= 1000) return (val / 1000).toFixed(2) + "K";
        return val.toFixed(1);
      };

      const vwmaV = param.seriesData.get(s.vwma224) as any;
      const rsiV = param.seriesData.get(s.rsi) as any;
      const eqV = param.seriesData.get(s.equilibrium) as any;
      const volV = param.seriesData.get(s.volume) as any;

      legendRef.current.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
          <span style="color: #fff; font-size: 14px; font-weight: 800; letter-spacing: -0.02em;">${symbolRef.current}</span>
        </div>
        <div style="display: flex; gap: 16px; margin-bottom: 14px; font-size: 13px;">
          <div style="display: flex; flex-direction: column;"><span style="color: #5d6673; font-size: 9px; font-weight: 700;">CLOSE</span><span style="color: ${color}; font-weight: 700;">${candle.close.toLocaleString()}</span></div>
          <div style="display: flex; flex-direction: column;"><span style="color: #5d6673; font-size: 9px; font-weight: 700;">VOL</span><span style="color: #e6e8ea;">${volV?.value !== undefined ? formatVol(volV.value) : "0.0"}</span></div>
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 6px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 12px;">
          ${settingsRef.current.whale && vwmaV?.value !== undefined ? `<div style="background: rgba(255, 255, 255, 0.08); padding: 4px 10px; border-radius: 4px;"><span style="color: #fff; font-size: 9px; font-weight: 900;">VWMA224</span> <span style="color: #fff; font-size: 11px;">${vwmaV.value.toFixed(1)}</span></div>` : ""}
          ${settingsRef.current.smc && eqV?.value !== undefined ? `<div style="background: rgba(240, 185, 11, 0.08); padding: 4px 10px; border-radius: 4px;"><span style="color: #f0b90b; font-size: 9px; font-weight: 900;">SMC EQ</span> <span style="color: #f0b90b; font-size: 11px;">${eqV.value.toFixed(1)}</span></div>` : ""}
          ${settingsRef.current.rsi && rsiV?.value !== undefined ? `<div style="background: rgba(156, 39, 176, 0.08); padding: 4px 10px; border-radius: 4px;"><span style="color: #9c27b0; font-size: 9px; font-weight: 900;">RSI</span> <span style="color: #9c27b0; font-size: 11px;">${rsiV.value.toFixed(2)}</span></div>` : ""}
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

  // --- [데이터 및 시그널 마커 렌더링 useEffect] ---
  useEffect(() => {
    if (!chartRef.current || !data) return;
    const s = seriesRefs.current;
    if (!s.candle) return;

    // 1. 캔들 및 거래량 세팅
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

    // 2. Standard CamelCase에 따른 지표 데이터 세팅
    if (data.indicators) {
      const ind = data.indicators;
      if (ind.vwma224) s.vwma224.setData(processData(ind.vwma224));
      if (ind.sma224) s.sma224.setData(processData(ind.sma224));

      if (ind.swingHighLevel)
        s.swingHighLevel.setData(processData(ind.swingHighLevel));
      if (ind.swingLowLevel)
        s.swingLowLevel.setData(processData(ind.swingLowLevel));
      if (ind.equilibrium) s.equilibrium.setData(processData(ind.equilibrium));

      if (ind.tenkan) s.tenkan.setData(processData(ind.tenkan));
      if (ind.kijun) s.kijun.setData(processData(ind.kijun));
      if (ind.senkouA) {
        const sa = processData(ind.senkouA);
        s.senkouA.setData(sa);
        s.cloud.setData(sa);
      }
      if (ind.senkouB) s.senkouB.setData(processData(ind.senkouB));

      if (ind.bbUpper) s.bbUpper.setData(processData(ind.bbUpper));
      if (ind.bbMid) s.bbMid.setData(processData(ind.bbMid));
      if (ind.bbLower) s.bbLower.setData(processData(ind.bbLower));

      if (ind.rsi) s.rsi.setData(processData(ind.rsi));
      if (ind.mfi) s.mfi.setData(processData(ind.mfi));
      if (ind.macdLine) s.macdLine.setData(processData(ind.macdLine));
      if (ind.signalLine) s.signalLine.setData(processData(ind.signalLine));
    }

    // 3. 🎯 시그널 자동 파싱 및 마커 생성 로직 (시뮬전략.txt 기반)
    if (s.markersPlugin && settings.signals) {
      let combinedMarkers: any[] = data.markers
        ? processData(data.markers, true)
        : [];

      // 백엔드에서 캔들 객체 내부에 플래그(1 or 0)를 넣어 보냈을 경우 이를 추적하여 마커 자동 생성
      finalCandles.forEach((c: any) => {
        // [Long 진입 규칙] SMC Strong Low 기반 파란 박스권 매수
        if (c.entrySmcLong === 1 || c.entrySmcLong === true) {
          combinedMarkers.push({
            time: c.time,
            position: "belowBar",
            color: "#2962FF",
            shape: "arrowUp",
            text: "Long Entry",
          });
        }
        // [Short 진입 규칙] SMC Strong High 기반 빨간 박스권 매도
        if (c.entrySmcShort === 1 || c.entrySmcShort === true) {
          combinedMarkers.push({
            time: c.time,
            position: "aboveBar",
            color: "#f6465d",
            shape: "arrowDown",
            text: "Short Entry",
          });
        }
        // [Short 익절] TOP (초록 다이아몬드 대체 -> 초록 화살표/마커)
        if (c.TOP === 1 || c.TOP === true) {
          combinedMarkers.push({
            time: c.time,
            position: "aboveBar",
            color: "#2ebd85",
            shape: "arrowDown",
            text: "TP (Short)",
          });
        }
        // [Long 익절] BOTTOM (빨간 다이아몬드 대체 -> 빨간 화살표/마커)
        if (c.BOTTOM === 1 || c.BOTTOM === true) {
          combinedMarkers.push({
            time: c.time,
            position: "belowBar",
            color: "#f6465d",
            shape: "arrowUp",
            text: "TP (Long)",
          });
        }
      });

      // 중복 제거 후 세팅
      const uniqueMarkers = Array.from(
        new Map(
          combinedMarkers.map((m) => [`${m.time}-${m.text}`, m]),
        ).values(),
      );
      s.markersPlugin.setMarkers(uniqueMarkers.sort((a, b) => a.time - b.time));
    } else if (s.markersPlugin) {
      s.markersPlugin.setMarkers([]); // 시그널 토글 OFF 시 초기화
    }

    // 4. 레이어 토글 가시성 적용
    Object.keys(settings).forEach((key) => {
      const isVisible = (settings as any)[key];
      if (key === "ichimoku") {
        ["tenkan", "kijun", "senkouA", "senkouB", "cloud"].forEach((k) =>
          s[k]?.applyOptions({ visible: isVisible }),
        );
      } else if (key === "whale") {
        ["vwma224", "sma224"].forEach((k) =>
          s[k]?.applyOptions({ visible: isVisible }),
        );
      } else if (key === "smc") {
        ["swingHighLevel", "swingLowLevel", "equilibrium"].forEach((k) =>
          s[k]?.applyOptions({ visible: isVisible }),
        );
      } else if (key === "bollinger") {
        ["bbUpper", "bbMid", "bbLower"].forEach((k) =>
          s[k]?.applyOptions({ visible: isVisible }),
        );
      } else if (key === "macd") {
        ["macdLine", "signalLine"].forEach((k) =>
          s[k]?.applyOptions({ visible: isVisible }),
        );
      } else if (s[key]) {
        s[key].applyOptions({ visible: isVisible });
      }
    });
  }, [data, settings]);

  // --- [포지션 Price Line 렌더링 useEffect] ---
  useEffect(() => {
    const s = seriesRefs.current;
    if (!s || !s.candle) return;

    priceLinesRef.current.forEach((line) => {
      s.candle.removePriceLine(line);
    });
    priceLinesRef.current = [];

    if (activePositions && activePositions.length > 0) {
      activePositions.forEach((pos) => {
        if (pos.entry_price <= 0) return;
        const isLong = pos.side === "LONG";
        const sideColor = isLong ? "#2ebd85" : "#f6465d";

        const entryLine = s.candle.createPriceLine({
          price: pos.entry_price,
          color: sideColor,
          lineWidth: 2,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: `${pos.side} ENTRY`,
        });
        priceLinesRef.current.push(entryLine);

        if (pos.liquidation_price > 0) {
          const liqLine = s.candle.createPriceLine({
            price: pos.liquidation_price,
            color: "#ff9800",
            lineWidth: 2,
            lineStyle: LineStyle.Solid,
            axisLabelVisible: true,
            title: `LIQ`,
          });
          priceLinesRef.current.push(liqLine);
        }
      });
    }
  }, [activePositions]);

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
