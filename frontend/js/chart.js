/* ============================================================
   chart.js — Master Strategy Frontend
   Lightweight Charts v4 + FastAPI 백엔드 연동
   ============================================================ */

const API_BASE = "http://localhost:8000/api";

// ── 상태 ─────────────────────────────────────────────────────
const state = {
  symbol: "BTC/USDT:USDT",
  timeframe: "5m",
  days: 10,
  data: [],
};

// ── DOM refs ─────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const statusMsg = $("statusMsg");
const signalLog = $("signalLog");
const signalBadge = $("signalBadge");
const loadBtn = $("loadBtn");
const loadText = $("loadBtnText");
const loadSpinner = $("loadSpinner");

// ── 차트 공통 옵션 ───────────────────────────────────────────
const CHART_OPTS_BASE = {
  layout: {
    background: { color: "#080c10" },
    textColor: "#4a6070",
    fontFamily: "'Space Mono', monospace",
    fontSize: 10,
  },
  grid: {
    vertLines: { color: "#0f1a24" },
    horzLines: { color: "#0f1a24" },
  },
  crosshair: {
    vertLine: { color: "#1e2d3d", labelBackgroundColor: "#111820" },
    horzLine: { color: "#1e2d3d", labelBackgroundColor: "#111820" },
  },
  timeScale: {
    borderColor: "#1e2d3d",
    timeVisible: true,
    secondsVisible: false,
    rightOffset: 8,
  },
  rightPriceScale: { borderColor: "#1e2d3d" },
  handleScroll: true,
  handleScale: true,
};

// ── 차트 인스턴스 ─────────────────────────────────────────────
let charts = {};
let series = {};

function initCharts() {
  // 기존 차트 제거
  Object.values(charts).forEach((c) => c.remove());
  charts = {};
  series = {};

  // [1] 메인 캔들 차트
  const mainEl = $("mainChart");
  charts.main = LightweightCharts.createChart(mainEl, {
    ...CHART_OPTS_BASE,
    width: mainEl.clientWidth,
    height: mainEl.clientHeight,
  });

  series.candle = charts.main.addCandlestickSeries({
    upColor: "#26a69a",
    downColor: "#ef5350",
    borderUpColor: "#26a69a",
    borderDownColor: "#ef5350",
    wickUpColor: "#26a69a",
    wickDownColor: "#ef5350",
  });

  // 기준선 (Kijun)
  series.kijun = charts.main.addLineSeries({
    color: "#f5c518",
    lineWidth: 1.5,
    title: "Kijun",
    priceLineVisible: false,
    lastValueVisible: false,
  });

  // 선행스팬 A (구름 상단)
  series.senkouA = charts.main.addLineSeries({
    color: "rgba(38,166,154,0.5)",
    lineWidth: 1,
    title: "Senkou A",
    priceLineVisible: false,
    lastValueVisible: false,
  });

  // 선행스팬 B (구름 하단)
  series.senkouB = charts.main.addLineSeries({
    color: "rgba(239,83,80,0.5)",
    lineWidth: 1,
    title: "Senkou B",
    priceLineVisible: false,
    lastValueVisible: false,
  });

  // 볼린저 밴드
  series.bbUpper = charts.main.addLineSeries({
    color: "rgba(224,64,251,0.6)",
    lineWidth: 1,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  series.bbLower = charts.main.addLineSeries({
    color: "rgba(224,64,251,0.6)",
    lineWidth: 1,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    priceLineVisible: false,
    lastValueVisible: false,
  });
  series.bbMid = charts.main.addLineSeries({
    color: "rgba(224,64,251,0.25)",
    lineWidth: 1,
    priceLineVisible: false,
    lastValueVisible: false,
  });

  // 마커용 더미 시리즈 (신호 표시)
  series.signals = charts.main.addLineSeries({
    color: "transparent",
    lineWidth: 0,
    priceLineVisible: false,
    lastValueVisible: false,
  });

  // [2] RSI / MFI 차트
  const rsiEl = $("rsiChart");
  charts.rsi = LightweightCharts.createChart(rsiEl, {
    ...CHART_OPTS_BASE,
    width: rsiEl.clientWidth,
    height: rsiEl.clientHeight,
    rightPriceScale: {
      borderColor: "#1e2d3d",
      scaleMargins: { top: 0.05, bottom: 0.05 },
    },
  });

  series.rsi = charts.rsi.addLineSeries({
    color: "#00e5ff",
    lineWidth: 1.5,
    title: "RSI",
    priceLineVisible: false,
    lastValueVisible: true,
  });
  series.mfi = charts.rsi.addLineSeries({
    color: "#ff6d00",
    lineWidth: 1.5,
    title: "MFI",
    priceLineVisible: false,
    lastValueVisible: true,
  });

  // RSI 레퍼런스 라인 (30 / 70)
  series.rsi.createPriceLine({
    price: 70,
    color: "#1e2d3d",
    lineWidth: 1,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    axisLabelVisible: true,
    title: "70",
  });
  series.rsi.createPriceLine({
    price: 30,
    color: "#1e2d3d",
    lineWidth: 1,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    axisLabelVisible: true,
    title: "30",
  });

  // [3] 거래량 차트
  const volEl = $("volChart");
  charts.vol = LightweightCharts.createChart(volEl, {
    ...CHART_OPTS_BASE,
    width: volEl.clientWidth,
    height: volEl.clientHeight,
    rightPriceScale: {
      borderColor: "#1e2d3d",
      scaleMargins: { top: 0.1, bottom: 0 },
    },
  });

  series.vol = charts.vol.addHistogramSeries({
    color: "#26a69a",
    priceFormat: { type: "volume" },
    priceLineVisible: false,
    lastValueVisible: false,
  });

  // 크로스헤어 동기화
  syncCrosshairs();

  // 리사이즈 옵저버
  observeResize();
}

// ── 크로스헤어 동기화 ─────────────────────────────────────────
function syncCrosshairs() {
  const pairs = [
    ["main", "rsi"],
    ["main", "vol"],
    ["rsi", "vol"],
  ];

  const handlers = {};

  Object.keys(charts).forEach((key) => {
    handlers[key] = (param) => {
      if (!param.time) return;
      Object.entries(charts).forEach(([k, c]) => {
        if (k !== key)
          c.setCrosshairPosition(
            param.seriesData?.get(series.candle)?.close ?? 0,
            param.time,
            series[k === "rsi" ? "rsi" : k === "vol" ? "vol" : "candle"],
          );
      });
    };
    charts[key].subscribeCrosshairMove(handlers[key]);
  });
}

// ── 리사이즈 옵저버 ────────────────────────────────────────────
function observeResize() {
  const ro = new ResizeObserver(() => {
    ["mainChart", "rsiChart", "volChart"].forEach((id) => {
      const el = $(id);
      const key = id.replace("Chart", "");
      if (charts[key]) {
        charts[key].applyOptions({
          width: el.clientWidth,
          height: el.clientHeight,
        });
      }
    });
  });
  ["mainChart", "rsiChart", "volChart"].forEach((id) => ro.observe($(id)));
}

// ── 데이터 로드 ───────────────────────────────────────────────
async function loadData() {
  setLoading(true);
  setStatus("데이터 로딩 중...");

  const symbol = encodeURIComponent(state.symbol);
  const timeframe = state.timeframe;
  const days = state.days;
  const url = `${API_BASE}/chart?symbol=${symbol}&timeframe=${timeframe}&days=${days}`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    const raw = await res.json();

    if (!Array.isArray(raw) || raw.length === 0) {
      throw new Error("백엔드에서 빈 데이터가 반환되었습니다.");
    }

    state.data = raw;
    renderCharts(raw);
    setStatus(
      `✓ ${raw.length}개 캔들 로드 완료 — ${state.symbol} / ${state.timeframe}`,
    );
  } catch (err) {
    setStatus(`✗ 에러: ${err.message}`);
    showToast(err.message);
  } finally {
    setLoading(false);
  }
}

// ── 차트 렌더링 ───────────────────────────────────────────────
function renderCharts(data) {
  // ── 캔들 ──
  const candleData = data.map((d) => ({
    time: d.time,
    open: d.open,
    high: d.high,
    low: d.low,
    close: d.close,
  }));
  series.candle.setData(candleData);

  // ── Kijun ──
  series.kijun.setData(toLine(data, "kijun"));

  // ── 선행스팬 ──
  series.senkouA.setData(toLine(data, "senkou_a"));
  series.senkouB.setData(toLine(data, "senkou_b"));

  // ── 볼린저 밴드 ──
  series.bbUpper.setData(toLine(data, "BB_upper"));
  series.bbLower.setData(toLine(data, "BB_lower"));
  series.bbMid.setData(toLine(data, "BB_middle"));

  // ── 거래량 (상승/하락 색상 구분) ──
  const volData = data.map((d) => ({
    time: d.time,
    value: d.volume,
    color: d.close >= d.open ? "rgba(38,166,154,0.7)" : "rgba(239,83,80,0.7)",
  }));
  series.vol.setData(volData);

  // ── RSI / MFI ──
  series.rsi.setData(toLine(data, "RSI_14"));
  series.mfi.setData(toLine(data, "MFI_14"));

  // ── 신호 마커 ──
  renderMarkers(data);

  // ── 신호 로그 & 최신값 ──
  renderSignalLog(data);
  renderLatestValues(data);
  renderPriceDisplay(data);

  // 오른쪽으로 스크롤
  charts.main.timeScale().scrollToRealTime();
  charts.rsi.timeScale().scrollToRealTime();
  charts.vol.timeScale().scrollToRealTime();
}

// ── 헬퍼: 지표 라인 데이터 변환 ──────────────────────────────
function toLine(data, key) {
  return data
    .filter((d) => d[key] != null)
    .map((d) => ({ time: d.time, value: d[key] }));
}

// ── 신호 마커 ─────────────────────────────────────────────────
function renderMarkers(data) {
  const markers = [];

  data.forEach((d) => {
    if (d.MASTER_LONG) {
      markers.push({
        time: d.time,
        position: "belowBar",
        color: "#00e5ff",
        shape: "arrowUp",
        text: "LONG",
        size: 1.5,
      });
    }
    if (d.MASTER_SHORT) {
      markers.push({
        time: d.time,
        position: "aboveBar",
        color: "#ff6d00",
        shape: "arrowDown",
        text: "SHORT",
        size: 1.5,
      });
    }
    if (d.TOP_DETECTED) {
      markers.push({
        time: d.time,
        position: "aboveBar",
        color: "#ff1744",
        shape: "circle",
        text: "TOP",
        size: 1,
      });
    }
    if (d.BOTTOM_DETECTED) {
      markers.push({
        time: d.time,
        position: "belowBar",
        color: "#76ff03",
        shape: "circle",
        text: "BOT",
        size: 1,
      });
    }
  });

  // 시간 오름차순 정렬 (Lightweight Charts 요구사항)
  markers.sort((a, b) => a.time - b.time);
  series.candle.setMarkers(markers);
}

// ── 신호 로그 ─────────────────────────────────────────────────
function renderSignalLog(data) {
  const signals = [];

  data.forEach((d) => {
    if (d.MASTER_LONG)
      signals.push({
        type: "long",
        label: "▲ MASTER LONG",
        time: d.time,
        price: d.close,
      });
    if (d.MASTER_SHORT)
      signals.push({
        type: "short",
        label: "▼ MASTER SHORT",
        time: d.time,
        price: d.close,
      });
    if (d.TOP_DETECTED)
      signals.push({
        type: "top",
        label: "◆ TOP DETECTED",
        time: d.time,
        price: d.close,
      });
    if (d.BOTTOM_DETECTED)
      signals.push({
        type: "bot",
        label: "◆ BOT DETECTED",
        time: d.time,
        price: d.close,
      });
  });

  // 최신 신호를 위에 표시
  signals.reverse();

  if (signals.length === 0) {
    signalLog.innerHTML = '<div class="log-empty">이 기간에 신호 없음</div>';
    return;
  }

  signalLog.innerHTML = signals
    .slice(0, 30)
    .map(
      (s) => `
    <div class="log-entry ${s.type}">
      <span class="log-sig">${s.label}</span>
      <span class="log-time">${formatTime(s.time)}</span>
      <span class="log-price">${fmtPrice(s.price)}</span>
    </div>
  `,
    )
    .join("");

  // 배지 업데이트: 가장 최신 신호 표시
  const latest = signals[0];
  signalBadge.className = `signal-badge ${latest.type}`;
  signalBadge.textContent = latest.label;
  signalBadge.classList.remove("hidden");
}

// ── 최신값 ───────────────────────────────────────────────────
function renderLatestValues(data) {
  const last = data[data.length - 1];
  if (!last) return;

  $("valRsi").textContent = last.RSI_14 != null ? last.RSI_14.toFixed(2) : "—";
  $("valMfi").textContent = last.MFI_14 != null ? last.MFI_14.toFixed(2) : "—";
  $("valKijun").textContent = last.kijun != null ? fmtPrice(last.kijun) : "—";

  $("valRsi").style.color =
    last.RSI_14 > 70 ? "#ef5350" : last.RSI_14 < 30 ? "#26a69a" : "#e8edf3";

  // 구름 위치
  if (last.senkou_a != null && last.senkou_b != null) {
    const above = last.close > Math.max(last.senkou_a, last.senkou_b);
    const below = last.close < Math.min(last.senkou_a, last.senkou_b);
    $("valCloud").textContent = above
      ? "☁ 구름 위"
      : below
        ? "☁ 구름 아래"
        : "☁ 구름 안";
    $("valCloud").style.color = above
      ? "#26a69a"
      : below
        ? "#ef5350"
        : "#f5c518";
  }

  // MACD
  if (last.MACD_line != null && last.MACD_signal != null) {
    const bull = last.MACD_line > last.MACD_signal;
    $("valMacd").textContent = bull ? "▲ 정배열" : "▼ 역배열";
    $("valMacd").style.color = bull ? "#26a69a" : "#ef5350";
  }
}

// ── 헤더 가격 표시 ───────────────────────────────────────────
function renderPriceDisplay(data) {
  if (data.length < 2) return;
  const last = data[data.length - 1];
  const prev = data[data.length - 2];

  $("currentPrice").textContent = fmtPrice(last.close);

  const pct = ((last.close - prev.close) / prev.close) * 100;
  const el = $("priceChange");
  el.textContent = `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
  el.className = `price-change ${pct >= 0 ? "up" : "dn"}`;
}

// ── 유틸 ─────────────────────────────────────────────────────
function fmtPrice(v) {
  if (v == null) return "—";
  return v >= 1000
    ? v.toLocaleString("en-US", { maximumFractionDigits: 2 })
    : v.toFixed(4);
}

function formatTime(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function setStatus(msg) {
  statusMsg.textContent = msg;
}

function setLoading(on) {
  loadBtn.disabled = on;
  loadText.classList.toggle("hidden", on);
  loadSpinner.classList.toggle("hidden", !on);
}

function showToast(msg, type = "error") {
  const el = document.createElement("div");
  el.className = `toast ${type === "info" ? "info" : ""}`;
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 5000);
}

// ── 이벤트 바인딩 ─────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  // 차트 초기화
  initCharts();

  // 심볼 변경
  $("symbolSelect").addEventListener("change", (e) => {
    state.symbol = e.target.value;
  });

  // 타임프레임 버튼
  document.querySelectorAll(".tf-btn").forEach((btn) => {
    if (btn.dataset.active) btn.classList.add("active");

    btn.addEventListener("click", () => {
      document
        .querySelectorAll(".tf-btn")
        .forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.timeframe = btn.dataset.tf;
    });
  });

  // 기간 입력
  $("daysInput").addEventListener("change", (e) => {
    state.days = parseInt(e.target.value, 10) || 10;
  });

  // LOAD 버튼
  $("loadBtn").addEventListener("click", loadData);

  // 키보드 단축키: Enter
  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !loadBtn.disabled) loadData();
  });
});
