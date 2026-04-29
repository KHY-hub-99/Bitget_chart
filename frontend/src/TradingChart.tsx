import React, { useEffect, useRef, useState } from "react";
import {
  createChart,
  createSeriesMarkers,
  ColorType,
  CrosshairMode,
  LineStyle,
  LineType, // 계단형 선을 위해 추가
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  IChartApi,
  ISeriesApi,
  Time,
  MouseEventParams,
} from "lightweight-charts";

interface ChartDataProps {
  data: {
    candles: any[];
    volumes: any[];
    indicators: { [key: string]: { time: number; value: number }[] };
    markers: any[]; // 백엔드 통일명칭: 'topDiamond', 'bottomDiamond', 'longSig_Rule1', 'longSig_Rule2' 등
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

  // 범례(Legend) 상태 관리
  const [legendData, setLegendData] = useState({
    time: "",
    open: 0,
    high: 0,
    low: 0,
    close: 0,
    vol: 0,
    swingHigh: 0,
    trailingBottom: 0,
    sma224: 0,
    vwma224: 0,
  });

  // KST 시간 포맷터 (YYYY-MM-DD HH:mm)
  const formatKst = (timestamp: number) => {
    const date = new Date(timestamp * 1000);
    const options: Intl.DateTimeFormatOptions = {
      timeZone: "Asia/Seoul",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    };
    // 포맷: 2026-04-26 00:00
    return new Intl.DateTimeFormat("ko-KR", options)
      .format(date)
      .replace(/\. /g, "-")
      .replace(".", "");
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

    // 메인 캔들
    s.candle = chart.addSeries(CandlestickSeries, {
      upColor: "#2ebd85",
      downColor: "#f6465d",
      borderVisible: false,
      wickUpColor: "#2ebd85",
      wickDownColor: "#f6465d",
    });

    // 2. Whale 세력선 (VWMA, SMA)
    s.vwma224 = chart.addSeries(LineSeries, {
      color: "#ffffff",
      lineWidth: 2,
      title: "VWMA224",
    });

    s.sma224 = chart.addSeries(LineSeries, {
      color: "#929aa5", // 회색
      lineWidth: 2,
      title: "SMA224",
    });

    // 3. SMC 구조 및 레벨 (LineType.WithSteps 사용하여 영역의 경계선처럼 표현)
    s.swingHighLevel = chart.addSeries(LineSeries, {
      color: "rgba(246, 70, 93, 0.8)", // 빨간색 명확히 구분
      lineWidth: 3,
      lineType: LineType.WithSteps, // 계단식으로 표시하여 레벨 강조
      title: "Strong High",
    });

    s.trailingBottom = chart.addSeries(LineSeries, {
      color: "rgba(46, 189, 133, 0.8)", // 초록색 명확히 구분
      lineWidth: 3,
      lineType: LineType.WithSteps,
      title: "Strong Low",
    });

    s.equilibrium = chart.addSeries(LineSeries, {
      color: "rgba(240, 185, 11, 0.8)", // 노란색 명확히 구분
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      lineType: LineType.WithSteps,
      title: "Equilibrium",
    });

    // Crosshair 이동 이벤트 (범례 데이터 업데이트)
    chart.subscribeCrosshairMove((param: MouseEventParams) => {
      if (
        param.point === undefined ||
        !param.time ||
        param.point.x < 0 ||
        param.point.x > chartContainerRef.current!.clientWidth ||
        param.point.y < 0 ||
        param.point.y > 650
      ) {
        return;
      }

      const candleData: any = param.seriesData.get(s.candle);
      const smaData: any = param.seriesData.get(s.sma224);
      const vwmaData: any = param.seriesData.get(s.vwma224);
      const swingData: any = param.seriesData.get(s.swingHighLevel);
      const trailingData: any = param.seriesData.get(s.trailingBottom);

      if (candleData) {
        setLegendData({
          time: formatKst(param.time as number),
          open: candleData.open,
          high: candleData.high,
          low: candleData.low,
          close: candleData.close,
          vol: 0, // 거래량 시리즈 숨김 처리로 제거됨 (요청사항 반영)
          swingHigh: swingData?.value || 0,
          trailingBottom: trailingData?.value || 0,
          sma224: smaData?.value || 0,
          vwma224: vwmaData?.value || 0,
        });
      }
    });

    chartRef.current = chart;
    seriesRefs.current = s;

    return () => chart.remove();
  }, [symbol]);

  // 2. 데이터 업데이트 및 마커 렌더링
  useEffect(() => {
    const s = seriesRefs.current;
    if (!data || !s || !s.candle) return;

    if (data.candles) s.candle.setData(data.candles);

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

    if (markersPrimitiveRef.current) {
      s.candle.detachPrimitive(markersPrimitiveRef.current);
      markersPrimitiveRef.current = null;
    }

    if (settings.signals && data.markers) {
      const formattedMarkers = data.markers.map((m: any) => {
        let color = "";
        let shape: any = "circle";
        let text = "";

        // 룰 및 표식 판별
        if (m.text === "topDiamond") {
          color = "#f6465d"; // 빨간 사각
          shape = "square";
          text = ""; // 텍스트 표시 없음
        } else if (m.text === "bottomDiamond") {
          color = "#2ebd85"; // 초록 사각
          shape = "square";
          text = ""; // 텍스트 표시 없음
        } else if (m.text.includes("longSig")) {
          color = "#2ebd85";
          shape = "arrowUp";
          text = m.text.includes("Rule1") ? "SMA/VWMA" : "SMC";
        } else if (m.text.includes("shortSig")) {
          color = "#f6465d";
          shape = "arrowDown";
          text = m.text.includes("Rule1") ? "SMA/VWMA" : "SMC";
        }

        return {
          time: m.time as Time,
          position: m.position,
          color,
          shape,
          text,
          size: 1, // 마커 사이즈
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

  // --- [실시간 포지션 라인] (이전 코드 동일) ---
  useEffect(() => {
    /* ... (생략: 기존 activePositions 라인 그리기 로직 동일) ... */
  }, [activePositions, symbol]);

  return (
    <div style={{ position: "relative", width: "100%", height: "650px" }}>
      {/* 커스텀 HTML 범례 (Legend) */}
      <div
        style={{
          position: "absolute",
          top: 10,
          left: 15,
          zIndex: 10,
          color: "#d1d4dc",
          fontSize: "12px",
          fontFamily: "monospace",
          pointerEvents: "none", // 범례 위에서도 마우스 드래그가 되도록 설정
        }}
      >
        <div
          style={{ fontSize: "14px", fontWeight: "bold", marginBottom: "4px" }}
        >
          {symbol}
        </div>
        <div>{legendData.time}</div>
        <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
          <span>O: {legendData.open}</span>
          <span>H: {legendData.high}</span>
          <span>L: {legendData.low}</span>
          <span>C: {legendData.close}</span>
        </div>

        {settings.whale && (
          <div style={{ display: "flex", gap: "12px", marginTop: "4px" }}>
            <span style={{ color: "#929aa5" }}>
              SMA: {legendData.sma224.toFixed(2)}
            </span>
            <span style={{ color: "#ffffff" }}>
              VWMA: {legendData.vwma224.toFixed(2)}
            </span>
          </div>
        )}

        {settings.smc && (
          <div style={{ display: "flex", gap: "12px", marginTop: "4px" }}>
            <span style={{ color: "rgba(246, 70, 93, 0.8)" }}>
              Strong High: {legendData.swingHigh.toFixed(2)}
            </span>
            <span style={{ color: "rgba(46, 189, 133, 0.8)" }}>
              Strong Low: {legendData.trailingBottom.toFixed(2)}
            </span>
          </div>
        )}
      </div>

      {/* 차트 컨테이너 */}
      <div ref={chartContainerRef} style={{ width: "100%", height: "100%" }} />
    </div>
  );
};

export default TradingChart;
