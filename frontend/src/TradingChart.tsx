import React, { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createSeriesMarkers,
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
      senkouA?: any[]; // 구름대 상단 추가
      senkouB?: any[]; // 구름대 하단 추가
    };
    markers: any[];
  };
}

const TradingChart: React.FC<ChartDataProps> = ({ data }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const legendRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartContainerRef.current || !legendRef.current || !data) return;

    // React 18 StrictMode 중복 렌더링 방지
    chartContainerRef.current.innerHTML = "";

    // 1. 차트 생성 및 지역화 설정
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#131722" },
        textColor: "#d1d4dc",
      },
      localization: {
        locale: "ko-KR",
        dateFormat: "yyyy년 MM월 dd일",
        timeFormatter: (time: number) => {
          const date = new Date(time * 1000);
          const y = date.getFullYear();
          const m = date.getMonth() + 1;
          const d = date.getDate();
          const hh = String(date.getHours()).padStart(2, "0");
          const mm = String(date.getMinutes()).padStart(2, "0");
          return `${y}년 ${m}월 ${d}일 ${hh}:${mm}`;
        },
      },
      grid: {
        vertLines: { color: "rgba(42, 46, 57, 0.3)" },
        horzLines: { color: "rgba(42, 46, 57, 0.3)" },
      },
      width: chartContainerRef.current.clientWidth,
      height: 600,
      crosshair: { mode: CrosshairMode.Normal },
    });

    // 2. 캔들스틱 시리즈
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderVisible: false,
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
    });
    candleSeries.setData(data.candles);

    // 3. 거래량 시리즈
    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: "#26a69a",
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });
    volumeSeries
      .priceScale()
      .applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    volumeSeries.setData(
      data.volumes.map((vol, index) => ({
        ...vol,
        color:
          data.candles[index].close >= data.candles[index].open
            ? "rgba(38, 166, 154, 0.5)"
            : "rgba(239, 83, 80, 0.5)",
      })),
    );

    // 4. 지표 레이어 설정 (방어적 코딩 적용)

    // --- 기준선 (Kijun): 빨간색 두께 2 ---
    let kijunSeries: any = null;
    if (data.indicators?.kijun) {
      kijunSeries = chart.addSeries(LineSeries, {
        color: "#f23645",
        lineWidth: 2,
        title: "기준선",
      });
      kijunSeries.setData(
        data.indicators.kijun.filter((i: any) => i.value !== null),
      );
    }

    // --- 구름대 (Senkou A/B): 색칠 대신 투명한 선으로 ---
    if (data.indicators?.senkouA) {
      const sA = chart.addSeries(LineSeries, {
        color: "rgba(76, 175, 80, 0.3)",
        lineWidth: 1,
      });
      sA.setData(data.indicators.senkouA.filter((i: any) => i.value !== null));
    }
    if (data.indicators?.senkouB) {
      const sB = chart.addSeries(LineSeries, {
        color: "rgba(255, 82, 82, 0.3)",
        lineWidth: 1,
      });
      sB.setData(data.indicators.senkouB.filter((i: any) => i.value !== null));
    }

    // --- RSI: 보라색, 하단 축 ---
    let rsiSeries: any = null;
    if (data.indicators?.rsi) {
      rsiSeries = chart.addSeries(LineSeries, {
        color: "#9c27b0",
        lineWidth: 1.5,
        priceScaleId: "rsi",
      });
      rsiSeries.setData(
        data.indicators.rsi.filter((i: any) => i.value !== null),
      );
      chart
        .priceScale("rsi")
        .applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
    }

    // 🎯 5. 마커 시각화 (색상 및 모양 강제 지정 로직 강화)
    if (data.markers && data.markers.length > 0) {
      const formattedMarkers = data.markers.map((marker) => {
        let shape: any = "circle";
        let color: string = "#ffffff"; // 찾지 못했을 때 기본값 (하얀색)
        let position: any = marker.position || "aboveBar";

        // 🔍 텍스트를 대문자로 변환하여 비교 (BOT, Bottom, BOTTOM 모두 잡기 위함)
        const textTag = (marker.text || "").toUpperCase();

        if (textTag.includes("LONG")) {
          shape = "arrowUp";
          color = "#089981"; // 초록색
          position = "belowBar";
        } else if (textTag.includes("SHORT")) {
          shape = "arrowDown";
          color = "#f23645"; // 빨간색
          position = "aboveBar";
        } else if (textTag.includes("TOP")) {
          shape = "square";
          color = "#f23645"; // 빨간색 네모
          position = "aboveBar";
        } else if (textTag.includes("BOT")) {
          // 🎯 "BOTTOM"이나 "BOT"이 포함되어 있으면 무조건 초록색 네모!
          shape = "square";
          color = "#089981"; // 초록색 네모
          position = "belowBar";
        }

        return {
          time: marker.time,
          position,
          shape,
          color,
          text: marker.text, // 글자는 원래대로 표시
          size: 2.5,
        };
      });
      createSeriesMarkers(candleSeries, formattedMarkers as any, {
        autoScale: true,
      });
    }

    // 6. 실시간 범례(Legend) 로직 (날짜 에러 수정 및 지표 추가)
    const updateLegend = (param: any) => {
      if (!legendRef.current) return;

      const candle =
        param.seriesData.get(candleSeries) ||
        data.candles[data.candles.length - 1];
      const rsiVal = rsiSeries ? param.seriesData.get(rsiSeries) : null;
      const kijunVal = kijunSeries ? param.seriesData.get(kijunSeries) : null;

      const d = new Date(candle.time * 1000);
      const year = d.getFullYear();
      const month = d.getMonth() + 1;
      const date = d.getDate();
      const hours = String(d.getHours()).padStart(2, "0");
      const minutes = String(d.getMinutes()).padStart(2, "0");

      // 🎯 dateStr 참조 에러 수정 완료
      const dateStr = `${year}년 ${month}월 ${date}일 ${hours}:${minutes}`;
      const color = candle.close >= candle.open ? "#26a69a" : "#ef5350";

      legendRef.current.innerHTML = `
        <div style="font-size: 13px; line-height: 1.6;">
            <div style="color: #848e9c; font-size: 11px; margin-bottom: 2px;">${dateStr}</div>
            <b style="color: #d1d4dc">BTC/USDT</b> 
            <span style="color: ${color}">O:${candle.open} H:${candle.high} L:${candle.low} C:${candle.close}</span>
            ${kijunVal ? `<br/><span style="color: #f23645">Kijun: ${kijunVal.value.toFixed(2)}</span>` : ""}
            ${rsiVal ? `<br/><span style="color: #9c27b0">RSI(14): ${rsiVal.value.toFixed(2)}</span>` : ""}
        </div>
      `;
    };

    chart.subscribeCrosshairMove(updateLegend);
    updateLegend({ seriesData: new Map() }); // 초기값 표시

    const handleResize = () => {
      if (chartContainerRef.current)
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
    };
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
      }}
    >
      <div
        ref={legendRef}
        style={{
          position: "absolute",
          top: 12,
          left: 12,
          zIndex: 10,
          pointerEvents: "none",
          fontFamily: "sans-serif",
          color: "#d1d4dc",
        }}
      />
      <div ref={chartContainerRef} style={{ width: "100%", height: "100%" }} />
    </div>
  );
};

export default TradingChart;
