import { useEffect, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  ColorType,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import { api, useData } from "./api";
import { Zones, chartZones } from "./Zones";
export function MarketChart({
  symbol,
  timeframe,
  analysis,
  layers,
  horizon = "5m",
  onTick,
  onStatus,
}: {
  symbol: string;
  timeframe: string;
  analysis: any;
  layers: string[];
  horizon?: string;
  onTick: (p: number) => void;
  onStatus: (s: string) => void;
}) {
  const forecast = useData(
    `/api/predictions/${symbol}?horizon=${horizon}`,
    60000,
  );
  const zones = useRef<Zones | null>(null);
  const host = useRef<HTMLDivElement>(null),
    chart = useRef<IChartApi | null>(null),
    series = useRef<ISeriesApi<"Candlestick"> | null>(null),
    vol = useRef<ISeriesApi<"Histogram"> | null>(null),
    bars = useRef<any[]>([]),
    extras = useRef<any[]>([]),
    lines = useRef<any[]>([]),
    markers = useRef<any>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const callbacks = useRef({ onTick, onStatus });
  callbacks.current = { onTick, onStatus };
  useEffect(() => {
    if (!host.current) return;
    setLoading(true);
    setError("");
    bars.current = [];
    const c = createChart(host.current, {
      autoSize: true,
      localization: { locale: "en-US" },
      layout: {
        background: { type: ColorType.Solid, color: "#11151e" },
        textColor: "#8b95a9",
        attributionLogo: true,
      },
      grid: {
        vertLines: { color: "#1b202b" },
        horzLines: { color: "#1b202b" },
      },
      timeScale: { timeVisible: true, secondsVisible: false, rightOffset: 8 },
      rightPriceScale: { borderColor: "#252c39" },
      crosshair: { mode: 0 },
    });
    chart.current = c;
    series.current = c.addSeries(CandlestickSeries, {
      upColor: "#31c9a0",
      downColor: "#f07782",
      borderVisible: false,
      wickUpColor: "#31c9a0",
      wickDownColor: "#f07782",
      priceFormat: {
        type: "price",
        precision: symbol.includes("JPY")
          ? 3
          : symbol.endsWith("USD") || symbol === "XRPUSDT"
            ? 5
            : 2,
        minMove: symbol.includes("JPY")
          ? 0.001
          : symbol.endsWith("USD") || symbol === "XRPUSDT"
            ? 0.00001
            : 0.01,
      },
    });
    zones.current = new Zones();
    series.current.attachPrimitive(zones.current);
    vol.current = c.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
      lastValueVisible: false,
      priceLineVisible: false,
    });
    c.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.83, bottom: 0 },
    });
    series.current
      .priceScale()
      .applyOptions({ scaleMargins: { top: 0.08, bottom: 0.23 } });
    let disposed = false,
      socket: WebSocket | null = null,
      reconnect: ReturnType<typeof setTimeout> | undefined;
    let lastEvent = 0;
    function apply() {
      if (disposed || !series.current) return;
      zones.current?.setBars(bars.current);
      series.current.setData(
        bars.current.map((b) => ({
          time: b.time as Time,
          open: b.open,
          high: b.high,
          low: b.low,
          close: b.close,
        })),
      );
      vol.current?.setData(
        bars.current
          .filter((b) => b.volume != null)
          .map((b) => ({
            time: b.time as Time,
            value: b.volume,
            color: b.close >= b.open ? "#204e48" : "#51313c",
          })),
      );
    }
    async function load(initial = false) {
      try {
        const data = await api(
          `/api/candles/${symbol}?timeframe=${timeframe}&limit=500`,
        );
        if (disposed) return;
        const map = new Map(bars.current.map((b) => [b.time, b]));
        for (const b of data.candles) map.set(b.time, b);
        bars.current = [...map.values()].sort((a, b) => a.time - b.time);
        apply();
        if (initial) c.timeScale().fitContent();
        setError("");
        setLoading(false);
        callbacks.current.onTick(data.candles.at(-1).close);
      } catch (e) {
        if (!disposed) {
          setError((e as Error).message);
          setLoading(false);
          callbacks.current.onStatus("unavailable");
        }
      }
    }
    function connect() {
      if (disposed) return;
      callbacks.current.onStatus("connecting");
      socket = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/market/${symbol}?timeframe=${timeframe}`,
      );
      socket.onmessage = (event) => {
        if (disposed) return;
        const message = JSON.parse(event.data);
        lastEvent = Date.now();
        callbacks.current.onStatus(message.status || "live");
        if (message.type === "candle") {
          const b = message.candle;
          const last = bars.current.at(-1);
          if (!last) return;
          if (b.time < last.time) return;
          if (b.time === last.time) bars.current[bars.current.length - 1] = b;
          else bars.current.push(b);
          series.current?.update({
            time: b.time as Time,
            open: b.open,
            high: b.high,
            low: b.low,
            close: b.close,
          });
          if (b.volume != null)
            vol.current?.update({
              time: b.time as Time,
              value: b.volume,
              color: b.close >= b.open ? "#204e48" : "#51313c",
            });
          zones.current?.setBars(bars.current);
          callbacks.current.onTick(b.close);
        }
        if (message.type === "price") {
          callbacks.current.onTick(message.price);
          const b = bars.current.at(-1);
          if (
            b &&
            message.timestamp >= b.time &&
            message.timestamp < b.end_time
          ) {
            b.close = message.price;
            b.high = Math.max(b.high, message.price);
            b.low = Math.min(b.low, message.price);
            series.current?.update({
              time: b.time as Time,
              open: b.open,
              high: b.high,
              low: b.low,
              close: b.close,
            });
          }
        }
      };
      socket.onclose = () => {
        if (!disposed) {
          callbacks.current.onStatus("reconnecting");
          reconnect = setTimeout(connect, 3000);
        }
      };
      socket.onerror = () => callbacks.current.onStatus("disconnected");
    }
    void load(true).then(connect);
    const poll = setInterval(() => void load(), 45000),
      stale = setInterval(() => {
        if (lastEvent && Date.now() - lastEvent > 30000)
          callbacks.current.onStatus("stale");
      }, 10000);
    return () => {
      disposed = true;
      clearInterval(poll);
      clearInterval(stale);
      clearTimeout(reconnect);
      socket?.close();
      c.remove();
      chart.current = null;
      series.current = null;
      extras.current = [];
      lines.current = [];
      markers.current = null;
      zones.current = null;
    };
  }, [symbol, timeframe]);
  useEffect(() => {
    const c = chart.current,
      s = series.current;
    if (!c || !s) return;
    for (const e of extras.current) c.removeSeries(e);
    extras.current = [];
    for (const l of lines.current) s.removePriceLine(l);
    lines.current = [];
    markers.current?.detach();
    markers.current = null;
    const last = bars.current.at(-1);
    zones.current?.setBars(bars.current);
    zones.current?.setZones(
      chartZones(
        analysis,
        layers,
        last
          ? last.end_time + (last.end_time - last.time) * 8
          : Date.now() / 1000,
        forecast.data,
      ),
    );
    if (!analysis) return;
    const colors: Record<string, string> = {
      ema20: "#a8a5fa",
      ema50: "#e5bd74",
      vwap: "#68bbd8",
      bb_upper: "#647a9b",
      bb_lower: "#647a9b",
      supertrend: "#f5a962",
    };
    for (const [key, color] of Object.entries(colors)) {
      if (!layers.includes(key)) continue;
      const line = c.addSeries(LineSeries, {
        color,
        lineWidth: 1,
        lastValueVisible: false,
        priceLineVisible: false,
      });
      line.setData(analysis.overlays[key] || []);
      extras.current.push(line);
    }
    if (layers.includes("structure")) {
      const byTime = new Map<number, any>();
      for (const e of analysis.events || [])
        if (
          [
            "HH",
            "HL",
            "LH",
            "LL",
            "BOS",
            "CHoCH",
            "MSS",
            "Displacement",
            "Session high sweep",
            "Session low sweep",
          ].includes(e.kind)
        )
          byTime.set(e.time, {
            time: e.time,
            position: e.side > 0 ? "belowBar" : "aboveBar",
            color: e.side > 0 ? "#31c9a0" : "#f07782",
            shape: e.side > 0 ? "arrowUp" : "arrowDown",
            text: e.kind,
          });
      markers.current = createSeriesMarkers(
        s,
        [...byTime.values()].sort((a, b) => a.time - b.time),
      );
    }
    const levels: any[] = [];
    if (layers.includes("liquidity"))
      levels.push(
        ["Swing high", analysis.indicators.swing_high, "#d2a45d"],
        ["Swing low", analysis.indicators.swing_low, "#d2a45d"],
      );
    if (layers.includes("previous"))
      levels.push(
        ["Previous day high", analysis.indicators.previous_day_high, "#8a91b6"],
        ["Previous day low", analysis.indicators.previous_day_low, "#8a91b6"],
      );
    if (layers.includes("fib"))
      for (const r of ["0.382", "0.5", "0.618"])
        levels.push(["Fib " + r, analysis.indicators["fib_" + r], "#ad8f62"]);
    for (const [title, p, color] of levels)
      if (p != null)
        lines.current.push(
          s.createPriceLine({
            price: p,
            color,
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: true,
            title,
          }),
        );
  }, [analysis, layers, symbol, timeframe, loading, forecast.data]);
  async function older() {
    try {
      const before = bars.current[0]?.time;
      if (!before) return;
      const data = await api(
        `/api/candles/${symbol}?timeframe=${timeframe}&limit=500&before=${before}`,
      );
      const range = chart.current?.timeScale().getVisibleRange();
      const map = new Map(
        [...data.candles, ...bars.current].map((b) => [b.time, b]),
      );
      bars.current = [...map.values()].sort((a, b) => a.time - b.time);
      series.current?.setData(
        bars.current.map((b) => ({
          time: b.time as Time,
          open: b.open,
          high: b.high,
          low: b.low,
          close: b.close,
        })),
      );
      vol.current?.setData(
        bars.current
          .filter((b) => b.volume != null)
          .map((b) => ({
            time: b.time as Time,
            value: b.volume,
            color: b.close >= b.open ? "#204e48" : "#51313c",
          })),
      );
      zones.current?.setBars(bars.current);
      if (range) chart.current?.timeScale().setVisibleRange(range);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <>
      <div className="chart-actions">
        <button onClick={() => void older()}>← Load earlier candles</button>
        <span>Drag to pan · Scroll to zoom · Crosshair to inspect</span>
        <button onClick={() => chart.current?.timeScale().fitContent()}>
          Fit view
        </button>
      </div>
      <div className="chart-host" ref={host} />
      {loading && <div className="empty">Loading market candles…</div>}
      {error && <div className="error">{error}</div>}
    </>
  );
}
export function EquityChart({ data }: { data: any[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const c = createChart(ref.current, {
      autoSize: true,
      localization: { locale: "en-US" },
      layout: {
        background: { type: ColorType.Solid, color: "#11151e" },
        textColor: "#8792a7",
      },
      grid: {
        vertLines: { color: "#1b202b" },
        horzLines: { color: "#1b202b" },
      },
    });
    const s = c.addSeries(LineSeries, { color: "#a8a5fa", lineWidth: 2 });
    s.setData(data);
    c.timeScale().fitContent();
    return () => c.remove();
  }, [data]);
  return <div ref={ref} style={{ height: 220 }} />;
}
