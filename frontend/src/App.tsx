import { useState, useEffect } from "react";
import {
  Activity,
  LayoutDashboard,
  ChartCandlestick,
  BrainCircuit,
  ScanLine,
  Layers,
  FlaskConical,
  BarChart3,
  History,
  Bell,
  Star,
  Settings,
  ArrowUpRight,
  Radio,
  PanelLeftClose,
} from "lucide-react";
import { api, useData, price, number, pct } from "./api";
import { MarketChart, EquityChart } from "./Chart";
import {
  CalendarPage,
  NewsPage,
  PaperPage,
  CorrelationsPage,
} from "./ResearchPages";
import { Notifications } from "./Notifications";
const NAV = [
  ["Dashboard", LayoutDashboard],
  ["Chart", ChartCandlestick],
  ["Predictions", BrainCircuit],
  ["Backtesting", FlaskConical],
  ["Prediction History", History],
] as const;

const HORIZONS = [
  ["5m", "5 minutes"],
  ["15m", "15 minutes"],
  ["30m", "30 minutes"],
  ["1h", "1 hour"],
];
export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="empty">{children}</div>;
}
function ErrorBox({ text }: { text: string }) {
  return text ? (
    <div role="alert" className="error">
      {text}
    </div>
  ) : null;
}
function Badge({
  children,
  tone = "muted",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={"badge " + tone}>{children}</span>;
}
function Card({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="card">
      <div className="card-head">
        <h3>{title}</h3>
        {action}
      </div>
      {children}
    </section>
  );
}
function Metric({
  label,
  value,
  sub,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {sub && <small>{sub}</small>}
    </div>
  );
}
function QuoteCard({
  symbol,
  selected,
  onClick,
}: {
  symbol: string;
  selected: boolean;
  onClick: () => void;
}) {
  const q = useData("/api/markets/" + symbol, 30000);
  return (
    <button
      className={"quote-card " + (selected ? "selected" : "")}
      onClick={onClick}
    >
      <div>
        <b>
          {symbol
            .replace("USDT", " / USDT")
            .replace(/^(EUR|GBP|AUD)USD$/, "$1 / USD")}
        </b>
        <Badge tone={q.data?.source === "demo" ? "amber" : "green"}>
          {q.data?.source === "demo" ? "DEMO" : q.data?.status || "…"}
        </Badge>
      </div>
      <strong>{q.data ? price(q.data.price) : "—"}</strong>
      <span className={q.data?.change >= 0 ? "positive" : "negative"}>
        {q.data
          ? number(q.data.change) + "%"
          : q.error
            ? "Feed unavailable"
            : "Connecting…"}
      </span>
      <small>24h change</small>
    </button>
  );
}
function PredictionPanel({
  symbol,
  horizon,
  setHorizon,
}: {
  symbol: string;
  horizon: string;
  setHorizon: (v: string) => void;
}) {
  const p = useData(`/api/predictions/${symbol}?horizon=${horizon}`, 60000);
  const d = p.data;
  return (
    <Card
      title="Prediction outlook"
      action={<Badge tone="purple">PROBABILISTIC</Badge>}
    >
      <div className="horizon-tabs">
        {HORIZONS.map(([v, t]) => (
          <button
            key={v}
            className={horizon === v ? "active" : ""}
            onClick={() => setHorizon(v)}
          >
            {t}
          </button>
        ))}
      </div>
      <ErrorBox text={p.error} />
      {p.loading ? (
        <Empty>Loading model outlook…</Empty>
      ) : (
        d && (
          <>
            <div className="prediction-top">
              <div>
                <span className="eyebrow">
                  {d.status === "prediction"
                    ? "MODEL DIRECTION"
                    : "MODEL AVAILABILITY"}
                </span>
                <h2
                  className={
                    d.signal_action === "LONG"
                      ? "positive"
                      : d.signal_action === "SHORT"
                        ? "negative"
                        : ""
                  }
                >
                  {d.signal_action || d.direction || "Awaiting validated model"}
                </h2>
                <p>
                  {d.reason ||
                    `As of ${new Date(d.asof * 1000).toLocaleString()} · ${d.source}`}
                </p>
              </div>
              <div className="prediction-confidence">
                <Metric
                  label="Signal probability"
                  value={d.probability != null ? pct(d.probability) : "—"}
                  sub="Calibrated on held-out data"
                />
                <Metric
                  label="Signal confidence"
                  value={d.signal_confidence || "LOW"}
                  sub={d.signal_action === "NO-TRADE" ? "No validated trading edge" : "Evidence strength"}
                />
              </div>
            </div>
            {d.signal_confidence === "LOW" && d.status === "prediction" && (
              <div className="confidence-warning">
                Weak edge: the model does not have enough validated separation for a strong directional signal.
              </div>
            )}
            {d.expected_high != null && (
              <div className="metrics">
                <Metric label="Entry" value={price(d.entry ?? d.reference_price)} />
                <Metric label="Stop loss" value={price(d.stop_loss)} />
                <Metric label="Take profit" value={price(d.take_profit)} />
                <Metric label="Risk / reward" value={d.risk_reward ? `${number(d.risk_reward, 2)}R` : "—"} />
                <Metric label="Expected return" value={pct(d.expected_return)} />
                <Metric label="Held-out samples" value={d.metrics?.samples} />
              </div>
            )}
            <p className="footnote">
              <b>{d.validation_status || "NO VALIDATED MODEL"}</b> · Data age:{" "}
              {number(d.data_age_seconds, 0)} seconds · Model:{" "}
              {d.model_version || "Unavailable"}
            </p>
            {d.supporting_factors && (
              <div className="scenario-grid">
                <div className="scenario">
                  <span className="positive">Supporting used features</span>
                  <p>{d.supporting_factors.join(" · ") || "None aligned"}</p>
                </div>
                <div className="scenario">
                  <span className="negative">Opposing used features</span>
                  <p>{d.opposing_factors.join(" · ") || "None opposed"}</p>
                </div>
              </div>
            )}
            {d.scenarios && (
              <div className="scenario-grid">
                {d.scenarios.map((s: any) => (
                  <div key={s.name} className="scenario">
                    <span
                      className={
                        s.name === "Bull"
                          ? "positive"
                          : s.name === "Bear"
                            ? "negative"
                            : "lavender"
                      }
                    >
                      {s.name} scenario <ArrowUpRight size={13} />
                    </span>
                    <b>
                      {price(s.low)} – {price(s.high)}
                    </b>
                    <p>{s.condition}</p>
                  </div>
                ))}
              </div>
            )}
            <div className="metrics">
              <Metric label="Volatility estimate" value={pct(d.volatility)} />
              <Metric label="Support" value={price(d.support)} />
              <Metric label="Resistance" value={price(d.resistance)} />
              <Metric label="Invalidation" value={price(d.invalidation)} />
            </div>
            <p className="footnote">
              Liquidity targets:{" "}
              {d.liquidity_targets?.map((v: number) => price(v)).join(" / ") ||
                "—"}{" "}
              · Range: {price(d.expected_low)} – {price(d.expected_high)} ·
              Prediction timestamp:{" "}
              {d.asof ? new Date(d.asof * 1000).toLocaleString() : "—"}
            </p>
            {d.explanation?.length > 0 && (
              <div className="factors">
                <span className="eyebrow">OBSERVED CONTEXT</span>
                {d.explanation.map((f: string) => (
                  <span key={f}>{f}</span>
                ))}
              </div>
            )}
          </>
        )
      )}
      <p className="footnote">
        Conditional scenarios are analytical levels, not calibrated intervals.
        Long-horizon models require substantially more historical data.
      </p>
    </Card>
  );
}

export default function App() {
  const [page, setPage] = useState("Dashboard"),
    [symbol, setSymbol] = useState("BTCUSDT"),
    [tf, setTf] = useState("5m"),
    [horizon, setHorizon] = useState("15m"),
    [layers, setLayers] = useState(["ema20", "ema50"]),
    [tick, setTick] = useState<number | null>(null),
    [stream, setStream] = useState("connecting"),
    [compact, setCompact] = useState(false);
  const health = useData("/health", 15000),
    assets = useData("/api/markets"),
    a = useData(`/api/analysis/${symbol}?timeframe=${tf}`, 60000),
    quote = useData("/api/markets/" + symbol, 30000),
    session = useData("/api/sessions", 60000),
    news = useData("/api/news", 300000),
    watch = useData("/api/watchlist");
  useEffect(() => {
    setTick(null);
    setStream("connecting");
  }, [symbol, tf]);
  const assetLabel =
    assets.data?.find((x: any) => x.symbol === symbol)?.name || symbol;
  const demo = health.data?.mode === "demo";
  const chartVisible = ["Dashboard", "Chart", "Live Markets"].includes(page);
  const toggle = (v: string) =>
    setLayers((l) => (l.includes(v) ? l.filter((x) => x !== v) : [...l, v]));
  return (
    <div className={"app " + (compact ? "compact" : "")}>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">α</div>
          <div>
            AlphaPredictors
            <span>
              AI MARKET TERMINAL <b>2.2</b>
            </span>
          </div>
        </div>
        <div className="workspace">
          <span className="workspace-icon">A</span>
          <div>
            Personal workspace<small>Analysis · Research</small>
          </div>
          <button
            className="icon-button"
            title="Collapse navigation"
            onClick={() => setCompact(!compact)}
          >
            <PanelLeftClose size={15} />
          </button>
        </div>
        <span className="nav-label">WORKSPACE</span>
        <nav>
          {NAV.map(([name, Icon]) => (
            <button
              key={name}
              className={page === name ? "active" : ""}
              onClick={() => setPage(name)}
            >
              <Icon size={17} />
              <span>{name}</span>

            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div>
            <span className="status-dot" />
            Local analysis engine
          </div>
          <p>
            Real execution off
            <br />
            Your keys stay on your device.
          </p>
          <a href="/docs" target="_blank" rel="noreferrer">
            API documentation ↗
          </a>
        </div>
      </aside>
      <main>
        <header>
          <div className="breadcrumb">
            Workspace <span>/</span> <b>{page}</b>
          </div>
          <div className="header-right">
            <span className="status-dot" />
            <span>
              {health.error ? "Backend offline" : "System operational"}
            </span>
            <span className="avatar">AP</span>
          </div>
        </header>
        <div className="content">
          <div className="page-title">
            <div>
              <span className="eyebrow">MARKET INTELLIGENCE</span>
              <h1>{page === "Dashboard" ? "Market overview" : page}</h1>
              <p>
                {page === "Dashboard"
                  ? "A clearer view of price, structure, and probability."
                  : "Explore the evidence behind your market analysis."}
              </p>
            </div>
            <Badge tone={demo ? "amber" : "green"}>
              {demo
                ? "DEMO MODE · SYNTHETIC DATA"
                : health.data
                  ? "LIVE DATA MODE"
                  : "CONNECTING"}
            </Badge>
          </div>
          <ErrorBox text={health.error} />
          <div className="top-controls">
            <label>
              Instrument{" "}
              <select
                aria-label="Instrument"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
              >
                {(assets.data || [{ symbol: "BTCUSDT", name: "BTC/USDT" }]).map(
                  (x: any) => (
                    <option key={x.symbol} value={x.symbol}>
                      {x.name}
                      {!x.available ? " (unavailable)" : ""}
                    </option>
                  ),
                )}
              </select>
            </label>
            <label>
              Timeframe{" "}
              <select
                aria-label="Timeframe"
                value={tf}
                onChange={(e) => setTf(e.target.value)}
              >
                {["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w", "1M"].map(
                  (t) => (
                    <option key={t}>{t}</option>
                  ),
                )}
              </select>
            </label>
            <span className="session-inline">
              <Radio size={14} />{" "}
              {session.data?.current?.map((s: any) => s.name).join(" + ") ||
                "Between sessions"}
              {session.data?.overlap && " · Overlap"}
            </span>
          </div>
          {["Dashboard", "Live Markets", "Watchlist"].includes(page) && (
            <div className="quote-grid">
              {(page === "Watchlist"
                ? watch.data?.symbols || []
                : ["BTCUSDT", "ETHUSDT", "SOLUSDT", "EURUSD"]
              ).map((s: string) => (
                <QuoteCard
                  key={s}
                  symbol={s}
                  selected={s === symbol}
                  onClick={() => {
                    setSymbol(s);
                    if (page === "Watchlist") setPage("Chart");
                  }}
                />
              ))}
            </div>
          )}
          {chartVisible && (
            <div className="terminal-grid">
              <section className="card chart-card">
                <div className="chart-title">
                  <div>
                    <h2>
                      {assetLabel}
                      <Badge
                        tone={
                          demo ? "amber" : stream === "live" ? "green" : "muted"
                        }
                      >
                        {demo ? "DEMO" : stream.toUpperCase()}
                      </Badge>
                    </h2>
                    <div className="live-price">
                      {price(tick ?? quote.data?.price)}
                      <span
                        className={
                          quote.data?.change >= 0 ? "positive" : "negative"
                        }
                      >
                        {number(quote.data?.change)}%
                      </span>
                    </div>
                  </div>
                  <div className="quote-meta">
                    <span>
                      24h High <b>{price(quote.data?.high)}</b>
                    </span>
                    <span>
                      24h Low <b>{price(quote.data?.low)}</b>
                    </span>
                    <span>
                      Volume <b>{number(quote.data?.volume, 0)}</b>
                    </span>
                  </div>
                </div>
                <div className="layer-bar">
                  {[
                    ["ema20", "EMA 20"],
                    ["ema50", "EMA 50"],
                    ["vwap", "VWAP"],
                    ["structure", "Structure"],
                    ["liquidity", "Liquidity"],
                    ["fvg", "FVG"],
                    ["forecast", "Forecast"],
                  ].map(([k, v]) => (
                    <button
                      className={layers.includes(k) ? "active" : ""}
                      onClick={() => toggle(k)}
                      key={k}
                    >
                      {v}
                    </button>
                  ))}
                </div>
                <MarketChart
                  symbol={symbol}
                  timeframe={tf}
                  analysis={a.data}
                  layers={layers}
                  horizon={horizon}
                  onTick={setTick}
                  onStatus={setStream}
                />
                <div className="chart-footer">
                  <span>
                    Source: {a.data?.source || "—"} · Indicators use closed
                    candles
                  </span>
                  <span>
                    Chart by{" "}
                    <a
                      href="https://www.tradingview.com/"
                      target="_blank"
                      rel="noreferrer"
                    >
                      TradingView
                    </a>
                  </span>
                </div>
                <ErrorBox text={a.error} />
              </section>
              <div className="right-rail">
                <Card title="Market state" action={<Activity size={15} />}>
                  <div className="state-regime">
                    {a.data?.indicators?.regime || "Awaiting data"}
                  </div>
                  <div className="key-value">
                    <span>Momentum · RSI 14</span>
                    <b>{number(a.data?.indicators?.rsi, 1)}</b>
                  </div>
                  <div className="key-value">
                    <span>ATR 14</span>
                    <b>{price(a.data?.indicators?.atr)}</b>
                  </div>
                  <div className="key-value">
                    <span>Structure</span>
                    <b>{a.data?.events?.at(-1)?.kind || "—"}</b>
                  </div>
                  <div className="key-value">
                    <span>Premium / discount</span>
                    <b>
                      {a.data?.indicators?.premium_discount == null
                        ? "—"
                        : a.data.indicators.premium_discount > 0.5
                          ? "Premium"
                          : "Discount"}
                    </b>
                  </div>
                  <div className="key-value">
                    <span>Bid / ask</span>
                    <b>
                      {price(quote.data?.bid)} / {price(quote.data?.ask)}
                    </b>
                  </div>
                </Card>
                <Card title="Session clock" action={<Badge>LOCAL</Badge>}>
                  <p className="small muted">{session.data?.timezone}</p>
                  {session.data?.current?.length ? (
                    session.data.current.map((s: any) => (
                      <div className="session-block" key={s.name}>
                        <span>
                          <i className="status-dot" />
                          {s.name}
                        </span>
                        <b>
                          {Math.floor(s.seconds_remaining / 3600)}h{" "}
                          {Math.floor((s.seconds_remaining % 3600) / 60)}m left
                        </b>
                      </div>
                    ))
                  ) : (
                    <p className="muted">No active weekday session</p>
                  )}
                  <div className="next-session">
                    <span className="eyebrow">UP NEXT</span>
                    <b>{session.data?.next?.name || "—"}</b>
                    <small>
                      {session.data?.next
                        ? new Date(session.data.next.start).toLocaleString()
                        : ""}
                    </small>
                  </div>
                </Card>
                <Card title="Research discipline">
                  <p className="small muted">
                    Predictions express uncertainty. Check sample size,
                    out-of-sample results, and transaction costs before drawing
                    conclusions.
                  </p>
                  <button
                    className="text-button"
                    onClick={() => setPage("Model Performance")}
                  >
                    Inspect model evidence <ArrowUpRight size={14} />
                  </button>
                </Card>
              </div>
            </div>
          )}
          {["Dashboard", "Predictions"].includes(page) && (
            <PredictionPanel
              symbol={symbol}
              horizon={horizon}
              setHorizon={setHorizon}
            />
          )}
          {page === "Dashboard" && (
            <div className="bottom-grid">
              <Card title="Upcoming events & headlines">
                <ErrorBox text={news.error} />
                {news.data?.items?.length ? (
                  news.data.items.slice(0, 3).map((n: any) => (
                    <a
                      className="headline"
                      key={n.url}
                      href={n.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {n.title}
                      <small>{n.source}</small>
                    </a>
                  ))
                ) : (
                  <Empty>
                    News feed unavailable
                    <br />
                    <small>
                      Configure a news provider to show verified headlines.
                    </small>
                  </Empty>
                )}
              </Card>
              <Card title="Engine status">
                <div className="key-value">
                  <span>Database</span>
                  <Badge tone="green">
                    {health.data?.database || "Connecting"}
                  </Badge>
                </div>
                <div className="key-value">
                  <span>Price stream</span>
                  <Badge tone={stream === "live" ? "green" : "amber"}>
                    {stream}
                  </Badge>
                </div>
                <div className="key-value">
                  <span>Model engine</span>
                  <span>{health.data?.ml_engine || "—"}</span>
                </div>
                <div className="key-value">
                  <span>Trading</span>
                  <span>Disabled by design</span>
                </div>
              </Card>
            </div>
          )}
          {page === "Market Scanner" && (
            <Scanner
              onSelect={(s) => {
                setSymbol(s);
                setPage("Chart");
              }}
              timeframe={tf}
            />
          )}
          {page === "ICT / SMC Analysis" && (
            <Structure data={a.data} error={a.error} />
          )}
          {page === "Backtesting" && (
            <Backtesting symbol={symbol} timeframe={tf} />
          )}
          {page === "Model Performance" && <Models symbol={symbol} />}
          {page === "Prediction History" && (
            <PredictionHistory symbol={symbol} />
          )}
          {page === "Alerts" && <Alerts symbol={symbol} />}
          <Notifications />
          {page === "Watchlist" && (
            <WatchlistEditor assets={assets.data || []} watch={watch} />
          )}
          {page === "Economic Calendar" && <CalendarPage />}
          {page === "News" && <NewsPage />}
          {page === "Correlations" && <CorrelationsPage />}
          {page === "Paper Trading" && <PaperPage symbol={symbol} />}
          {page === "Settings" && <SettingsPage />}
          <footer>
            AlphaPredictorsAI 2.1{" "}
            <span>
              Analysis only · Forecasts are estimates ·{" "}
              {demo
                ? "Demo results do not establish real-market performance"
                : "Provider coverage and data delays may vary"}
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}
function Scanner({
  onSelect,
  timeframe,
}: {
  onSelect: (s: string) => void;
  timeframe: string;
}) {
  const [market, setMarket] = useState("all"),
    [direction, setDirection] = useState("all"),
    [scanSignal, setScanSignal] = useState("all"),
    [minProbability, setMinProbability] = useState(0);
  const d = useData(
    `/api/scanner?market=${market}&timeframe=${timeframe}&direction=${direction}&signal=${scanSignal}&min_probability=${minProbability}`,
    60000,
  );
  return (
    <Card
      title="Market scanner"
      action={<button onClick={d.refresh}>Refresh</button>}
    >
      <div className="form-row">
        <select
          aria-label="Market filter"
          value={market}
          onChange={(e) => setMarket(e.target.value)}
        >
          <option value="all">All markets</option>
          <option value="crypto">Crypto</option>
          <option value="forex">Forex</option>
        </select>
        <select
          aria-label="Direction filter"
          value={direction}
          onChange={(e) => setDirection(e.target.value)}
        >
          {["all", "Bullish", "Bearish"].map((x) => (
            <option key={x}>{x}</option>
          ))}
        </select>
      </div>
      <div className="form-row">
        <label>
          Signal filter
          <select
            value={scanSignal}
            onChange={(e) => setScanSignal(e.target.value)}
          >
            {["all", "high_volatility", "sweep", "FVG", "BOS", "CHoCH"].map(
              (v) => (
                <option key={v}>{v}</option>
              ),
            )}
          </select>
        </label>
        <label>
          Minimum model probability
          <select
            value={minProbability}
            onChange={(e) => setMinProbability(+e.target.value)}
          >
            <option value={0}>Any / unavailable</option>
            <option value={0.6}>60%</option>
            <option value={0.7}>70%</option>
            <option value={0.8}>80%</option>
          </select>
        </label>
      </div>
      <ErrorBox text={d.error} />
      {d.loading ? (
        <Empty>Scanning instruments…</Empty>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {[
                  "Instrument",
                  "Price",
                  "Trend",
                  "RSI",
                  "Regime",
                  "Structure",
                  "Probability",
                  "Source",
                  "Change %",
                  "Volume",
                  "Volatility",
                  "FVG / sweep",
                  "Session",
                  "Event risk",
                ].map((x) => (
                  <th key={x}>{x}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {d.data?.map((r: any) => (
                <tr
                  key={r.symbol}
                  onClick={() => onSelect(r.symbol)}
                  className="clickable"
                >
                  <td>
                    <b>{r.symbol}</b>
                  </td>
                  {r.status === "ok" ? (
                    <>
                      <td>{price(r.price)}</td>
                      <td
                        className={
                          r.trend === "Bullish" ? "positive" : "negative"
                        }
                      >
                        {r.trend}
                      </td>
                      <td>{number(r.rsi, 1)}</td>
                      <td>{r.regime}</td>
                      <td>{r.structure}</td>
                      <td>{pct(r.probability)}</td>
                      <td>{r.source}</td>
                      <td>{number(r.change)}%</td>
                      <td>{number(r.volume, 0)}</td>
                      <td>{pct(r.volatility)}</td>
                      <td>
                        {r.fvg ? "FVG" : "—"} /{" "}
                        {r.liquidity_sweep ? "Sweep" : "—"}
                      </td>
                      <td>{r.session?.join(" + ") || "Between sessions"}</td>
                      <td>{r.event_risk}</td>
                    </>
                  ) : (
                    <td colSpan={13}>{r.message}</td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="footnote">
        Trend is an EMA rule. Probability appears only when a matching model is
        promoted.
      </p>
    </Card>
  );
}
function Structure({ data, error }: { data: any; error: string }) {
  return (
    <>
      <ErrorBox text={error} />
      <div className="bottom-grid">
        <Card title="Confirmed market structure">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Confirmation time</th>
                  <th>Signal</th>
                  <th>Level</th>
                </tr>
              </thead>
              <tbody>
                {data?.events
                  ?.slice(-30)
                  .reverse()
                  .map((e: any, i: number) => (
                    <tr key={i}>
                      <td>{new Date(e.time * 1000).toLocaleString()}</td>
                      <td className={e.side > 0 ? "positive" : "negative"}>
                        {e.kind}
                      </td>
                      <td>{price(e.level)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card title="Imbalances & order blocks">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Zone</th>
                  <th>Range</th>
                  <th>State</th>
                </tr>
              </thead>
              <tbody>
                {data?.zones
                  ?.slice(-25)
                  .reverse()
                  .map((z: any, i: number) => (
                    <tr key={i}>
                      <td>{z.kind}</td>
                      <td>
                        {price(z.low)} – {price(z.high)}
                      </td>
                      <td>
                        <Badge>{z.status}</Badge>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <p className="footnote">
            Swing points are confirmed three bars later. Signals are timestamped
            at confirmation; history is not backdated.
          </p>
        </Card>
      </div>
      <Card title="Historical session statistics">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {[
                  "Session",
                  "Local start",
                  "Open",
                  "High",
                  "Low",
                  "Range",
                  "Return %",
                  "Coverage",
                ].map((v) => (
                  <th key={v}>{v}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data?.session_history
                ?.slice(-12)
                .reverse()
                .map((r: any) => (
                  <tr key={r.name + r.start}>
                    <td>{r.name}</td>
                    <td>{r.local_start}</td>
                    <td>{price(r.open)}</td>
                    <td>{price(r.high)}</td>
                    <td>{price(r.low)}</td>
                    <td>{price(r.range)}</td>
                    <td>{number(r.return_pct)}</td>
                    <td>{r.complete ? "Complete" : "Partial"}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
function Backtesting({
  symbol,
  timeframe,
}: {
  symbol: string;
  timeframe: string;
}) {
  const [strategy, setStrategy] = useState("ema"),
    [cost, setCost] = useState(5),
    [slip, setSlip] = useState(2),
    [spread, setSpread] = useState(0),
    [sizing, setSizing] = useState("risk"),
    [fixedUnits, setFixedUnits] = useState(1),
    [rr, setRr] = useState(2),
    [risk, setRisk] = useState(1),
    [start, setStart] = useState(""),
    [end, setEnd] = useState(""),
    [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [drawdown, setDrawdown] = useState(false);
  async function run() {
    setBusy(true);
    setError("");
    try {
      setData(
        await api("/api/backtest", "POST", {
          symbol,
          timeframe,
          strategy,
          cost_bps: cost,
          slippage_bps: slip,
          spread_bps: spread,
          sizing,
          fixed_units: fixedUnits,
          risk_reward: rr,
          risk_pct: risk,
          bars: 1000,
          start: start ? Math.floor(new Date(start).getTime() / 1000) : null,
          end: end ? Math.floor(new Date(end).getTime() / 1000) : null,
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Card title="Backtesting lab" action={<Badge>RESEARCH</Badge>}>
        <p className="muted">
          Closed-candle signals. Next-open entries. Costs on both sides.
          Stop-first handling for ambiguous candles.
        </p>
        <div className="form-row">
          <label>
            Strategy
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
            >
              <option value="ema">EMA20 / EMA50 crossover</option>
              <option value="smc">Structure break</option>
              <option value="rsi">RSI mean reversion</option>
            </select>
          </label>
          <label>
            Cost · bps / side
            <input
              type="number"
              min="0"
              value={cost}
              onChange={(e) => setCost(+e.target.value)}
            />
          </label>
          <label>
            Slippage · bps / side
            <input
              type="number"
              min="0"
              value={slip}
              onChange={(e) => setSlip(+e.target.value)}
            />
          </label>
          <label>
            Spread · bps
            <input
              type="number"
              min="0"
              max="500"
              value={spread}
              onChange={(e) => setSpread(+e.target.value)}
            />
          </label>
          <label>
            Sizing
            <select value={sizing} onChange={(e) => setSizing(e.target.value)}>
              <option value="risk">Fixed risk %</option>
              <option value="fixed">Fixed units</option>
            </select>
          </label>
          <label>
            Fixed units
            <input
              type="number"
              min="0.000001"
              step="any"
              value={fixedUnits}
              onChange={(e) => setFixedUnits(+e.target.value)}
            />
          </label>
          <label>
            Reward / risk
            <input
              type="number"
              min="0.1"
              step="0.1"
              value={rr}
              onChange={(e) => setRr(+e.target.value)}
            />
          </label>
          <label>
            Risk % · no leverage
            <input
              type="number"
              min="0.1"
              max="5"
              step="0.1"
              value={risk}
              onChange={(e) => setRisk(+e.target.value)}
            />
          </label>
        </div>
        <div className="form-row">
          <label>
            Start (optional)
            <input
              type="datetime-local"
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </label>
          <label>
            End (optional)
            <input
              type="datetime-local"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </label>
          <button
            className="primary"
            onClick={() => void run()}
            disabled={busy}
          >
            {busy ? "Running simulation…" : "Run backtest"}
          </button>
        </div>
        <ErrorBox text={error} />
        <p className="footnote">
          Uses up to 1,000 bars before the chosen end. Returned dates show
          actual coverage. Strategy backtests are separate from ML forecast
          evaluation.
        </p>
      </Card>
      {data && (
        <Card
          title="Measured backtest results"
          action={
            <Badge tone={data.source === "demo" ? "amber" : "green"}>
              {data.source}
            </Badge>
          }
        >
          <div className="metrics">
            <Metric label="Trades" value={data.total_trades} />
            <Metric label="Win rate" value={pct(data.win_rate)} />
            <Metric label="Profit factor" value={number(data.profit_factor)} />
            <Metric label="Net return" value={number(data.net_return) + "%"} />
            <Metric
              label="Max drawdown"
              value={number(data.max_drawdown) + "%"}
            />
            <Metric label="Sharpe" value={number(data.sharpe)} />
            <Metric label="Sortino" value={number(data.sortino)} />
          </div>
          {data.chronological && (
            <details>
              <summary>Chronological evaluation windows</summary>
              <p className="footnote">{data.chronological.method}</p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Window</th>
                      <th>Trades</th>
                      <th>Win rate</th>
                      <th>Net return</th>
                      <th>Drawdown</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.chronological.segments.map((r: any) => (
                      <tr key={r.label}>
                        <td>{r.label}</td>
                        <td>{r.total_trades}</td>
                        <td>{pct(r.win_rate)}</td>
                        <td>{number(r.net_return)}%</td>
                        <td>{number(r.max_drawdown)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          )}
          <div className="horizon-tabs">
            <button
              className={!drawdown ? "active" : ""}
              onClick={() => setDrawdown(false)}
            >
              Equity curve
            </button>
            <button
              className={drawdown ? "active" : ""}
              onClick={() => setDrawdown(true)}
            >
              Drawdown
            </button>
          </div>
          <EquityChart
            data={data.equity.map((p: any) => ({
              time: p.time,
              value: drawdown ? p.drawdown : p.value,
            }))}
          />
          <div className="metrics">
            <Metric
              label="Expectancy / trade"
              value={number(data.expectancy)}
            />
            <Metric label="Average win" value={number(data.average_win)} />
            <Metric label="Average loss" value={number(data.average_loss)} />
            <Metric
              label="Max win / loss streak"
              value={`${data.consecutive_wins} / ${data.consecutive_losses}`}
            />
          </div>
          <p className="footnote">
            {data.bars} candles · {new Date(data.start * 1000).toLocaleString()}{" "}
            → {new Date(data.end * 1000).toLocaleString()}
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Entry</th>
                  <th>Side</th>
                  <th>Entry price</th>
                  <th>Exit price</th>
                  <th>Net P&L</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {data.trades.map((t: any, i: number) => (
                  <tr key={i}>
                    <td>{new Date(t.opened * 1000).toLocaleString()}</td>
                    <td>{t.side > 0 ? "Long" : "Short"}</td>
                    <td>{price(t.entry)}</td>
                    <td>{price(t.exit)}</td>
                    <td className={t.pnl >= 0 ? "positive" : "negative"}>
                      {number(t.pnl)}
                    </td>
                    <td>{t.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="form-row">
            {Object.entries(data.monthly).map(([m, v]) => (
              <Metric key={m} label={m + " P&L"} value={number(v as number)} />
            ))}
          </div>
        </Card>
      )}
      <RiskCalculator />
    </>
  );
}
function RiskCalculator() {
  const [equity, setEquity] = useState(10000),
    [risk, setRisk] = useState(1),
    [entry, setEntry] = useState(100),
    [stop, setStop] = useState(98);
  const distance = Math.abs(entry - stop);
  return (
    <Card title="Analytical position-size calculator">
      <div className="form-row">
        {[
          ["Account value", equity, setEquity],
          ["Risk %", risk, setRisk],
          ["Entry", entry, setEntry],
          ["Invalidation", stop, setStop],
        ].map(([label, value, set]: any) => (
          <label key={label}>
            {label}
            <input
              type="number"
              min="0"
              value={value}
              onChange={(e) => set(+e.target.value)}
            />
          </label>
        ))}
      </div>
      <div className="metrics">
        <Metric
          label="Maximum theoretical loss"
          value={number((equity * risk) / 100)}
        />
        <Metric
          label="Price-unit quantity"
          value={
            distance > 0
              ? number((equity * risk) / 100 / distance)
              : "Invalid stop"
          }
        />
        <Metric label="Stop distance" value={number(distance)} />
      </div>
      <p className="footnote">
        Same-currency price units only. Excludes contract multipliers, FX
        conversion, fees, gaps and slippage. This is not an order.
      </p>
    </Card>
  );
}
function Models({ symbol }: { symbol: string }) {
  const [horizon, setHorizon] = useState("15m"),
    [bars, setBars] = useState(3000),
    [job, setJob] = useState(""),
    [state, setState] = useState<any>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const models = useData("/api/models", 30000),
    perf = useData("/api/performance?symbol=" + symbol, 60000);
  useEffect(() => {
    if (!job) return;
    let active = true;
    const timer = setInterval(async () => {
      try {
        const data = await api("/api/jobs/" + job);
        if (!active) return;
        setState(data);
        if (["completed", "failed"].includes(data.status)) {
          clearInterval(timer);
          setBusy(false);
          models.refresh();
        }
      } catch (e) {
        if (active) {
          setError((e as Error).message);
          setBusy(false);
          clearInterval(timer);
        }
      }
    }, 2000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [job]);
  async function train() {
    setBusy(true);
    setError("");
    setState(null);
    try {
      const j = await api("/api/models/train", "POST", {
        symbol,
        horizon,
        history_bars: bars,
      });
      setJob(j.job_id);
      setState({ status: "queued" });
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  return (
    <>
      <Card title="Controlled model training">
        <p className="muted">
          Compare Logistic Regression and Random Forest. Calibrate on a separate
          period. Promote only if validation improves on the prior baseline and
          eligible incumbent.
        </p>
        <div className="form-row">
          <label>
            Prediction horizon
            <select
              value={horizon}
              onChange={(e) => setHorizon(e.target.value)}
            >
              {HORIZONS.map(([v, l]) => (
                <option value={v} key={v}>
                  {l}
                </option>
              ))}
            </select>
          </label>
          <label>
            Historical candles
            <input
              type="number"
              min="800"
              max="20000"
              value={bars}
              onChange={(e) => setBars(+e.target.value)}
            />
          </label>
          <button
            className="primary"
            disabled={busy}
            onClick={() => void train()}
          >
            {busy ? "Training in progress…" : "Train & validate model"}
          </button>
        </div>
        <ErrorBox text={error || state?.error || ""} />
        {state && (
          <div className="notice">
            Job: {state.status}
            {state.result && (
              <>
                {" "}
                · {state.result.promoted ? "Promoted" : "Research model only"}
                <p>{state.result.promotion_reason}</p>
              </>
            )}
          </div>
        )}
        <p className="footnote">
          No training accuracy is used for promotion. Demo models demonstrate
          software behavior only. Yearly horizons need many years of appropriate
          data. Next-session targets use hourly candles and a four-day embargo;
          select at least 10,000 history bars for sufficient disjoint evaluation
          samples.
        </p>
      </Card>
      <Card title="Forward prediction performance">
        <ErrorBox text={perf.error} />
        {perf.data?.metrics ? (
          <div className="metrics">
            <Metric
              label="Non-overlapping forecasts"
              value={perf.data.non_overlapping}
            />
            <Metric
              label="Directional accuracy"
              value={pct(perf.data.metrics.accuracy)}
            />
            <Metric
              label="Calibration error"
              value={pct(perf.data.metrics.calibration_error)}
            />
            <Metric
              label="Return MAE"
              value={pct(perf.data.metrics.mean_absolute_return_error)}
            />
          </div>
        ) : (
          <Empty>
            {perf.data?.status || "Loading…"}
            <br />
            <small>
              {perf.data?.non_overlapping || 0} settled non-overlapping
              predictions · Minimum 30 required
            </small>
          </Empty>
        )}
      </Card>
      <Card title="Model registry">
        <ErrorBox text={models.error} />
        {!models.data?.length ? (
          <Empty>
            No models trained yet. Start a controlled training run above.
          </Empty>
        ) : (
          models.data
            .filter((m: any) => m.symbol === symbol)
            .map((m: any) => (
              <details className="model-detail" key={m.version}>
                <summary>
                  <b>
                    {m.symbol} · {m.timeframe} × {m.horizon_bars}
                  </b>
                  <span>{m.model}</span>
                  <Badge tone={m.source === "demo" ? "amber" : "green"}>
                    {m.source}
                  </Badge>
                  <Badge>{m.promoted ? "VALIDATED" : "REJECTED"}</Badge>
                </summary>
                <div className="metrics">
                  <Metric
                    label="Held-out accuracy"
                    value={pct(m.test.accuracy)}
                  />
                  <Metric label="Held-out samples" value={m.test.samples} />
                  <Metric
                    label="Macro precision"
                    value={pct(m.test.precision)}
                  />
                  <Metric label="Macro recall" value={pct(m.test.recall)} />
                  <Metric label="Macro F1" value={number(m.test.f1, 3)} />
                  <Metric
                    label="ROC-AUC (OvR)"
                    value={number(m.test.roc_auc, 3)}
                  />
                  <Metric label="Brier score" value={number(m.test.brier, 3)} />
                  <Metric label="Log loss" value={number(m.test.log_loss, 3)} />
                  <Metric
                    label="Calibration error"
                    value={pct(m.test.calibration_error)}
                  />
                </div>
                {m.test.confusion_matrix && (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Actual / predicted</th>
                          {m.test.class_order.map((v: string) => (
                            <th key={v}>{v}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {m.test.confusion_matrix.map(
                          (row: number[], i: number) => (
                            <tr key={i}>
                              <th>{m.test.class_order[i]}</th>
                              {row.map((v, j) => (
                                <td key={j}>{v}</td>
                              ))}
                            </tr>
                          ),
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
                <p className="small muted">
                  Version {m.version} · Feature set {m.feature_version}
                </p>
                <pre>
                  {JSON.stringify(
                    {
                      validation: m.validation,
                      baseline: m.baseline_log_loss,
                      walk_forward: m.walk_forward,
                      partitions: m.partitions,
                      regression_mae: m.regression_mae,
                      test_by_regime: m.test_by_regime,
                      validation_feature_importance: m.feature_importance,
                    },
                    null,
                    2,
                  )}
                </pre>
              </details>
            ))
        )}
      </Card>
    </>
  );
}
function PredictionHistory({ symbol }: { symbol: string }) {
  const d = useData("/api/history?symbol=" + symbol, 30000);
  return (
    <Card
      title="Immutable prediction ledger"
      action={<button onClick={d.refresh}>Refresh</button>}
    >
      <ErrorBox text={d.error} />
      {!d.data?.length ? (
        <Empty>
          No model predictions recorded for {symbol}.<br />
          <small>
            Train a model that passes validation; future predictions will be
            stored automatically.
          </small>
        </Empty>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {[
                  "As of",
                  "Horizon",
                  "Direction",
                  "Probability",
                  "Estimated low – high",
                  "Outcome",
                  "Source",
                  "Model",
                ].map((x) => (
                  <th key={x}>{x}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {d.data.map((p: any) => (
                <tr key={p.id}>
                  <td>{new Date(p.asof * 1000).toLocaleString()}</td>
                  <td>{p.horizon}</td>
                  <td>{p.direction}</td>
                  <td>{pct(p.probability)}</td>
                  <td>
                    {price(p.expected_low)} – {price(p.expected_high)}
                  </td>
                  <td>
                    {p.result
                      ? `${p.result.actual_outcome} · ${p.result.correct ? "Correct" : "Incorrect"}`
                      : "Pending complete outcome data"}
                  </td>
                  <td>{p.source}</td>
                  <td>{p.model_version}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
function Alerts({ symbol }: { symbol: string }) {
  const d = useData("/api/alerts", 10000);
  const [kind, setKind] = useState("above"),
    [level, setLevel] = useState(""),
    [signal, setSignal] = useState("BOS"),
    [repeat, setRepeat] = useState(false),
    [cooldown, setCooldown] = useState(300),
    [delta, setDelta] = useState(0.1),
    [error, setError] = useState("");
  async function add() {
    setError("");
    try {
      await api("/api/alerts", "POST", {
        symbol,
        kind,
        level: Number(level),
        signal,
        repeat,
        cooldown_seconds: cooldown,
        delta,
      });
      d.refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function remove(key: string) {
    try {
      await api("/api/alerts/" + key, "DELETE");
      d.refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <Card title="Local market alerts">
      <p className="muted">
        Alerts are evaluated every minute while the backend runs. Repeating
        rules use cooldowns and transition de-duplication. Add the instrument to
        your watchlist to enable background monitoring.
      </p>
      <div className="form-row">
        <label>
          Condition
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="above">Price at / above</option>
            <option value="below">Price at / below</option>
            <option value="signal">Confirmed structure signal</option>
            <option value="direction">1H prediction direction change</option>
            <option value="probability">1H probability change</option>
            <option value="model">1H model validation change</option>
            <option value="session">Session open</option>
            <option value="calendar">
              High-impact event within 15 minutes
            </option>
          </select>
        </label>
        {kind === "signal" ? (
          <label>
            Signal
            <select value={signal} onChange={(e) => setSignal(e.target.value)}>
              {[
                "BOS",
                "CHoCH",
                "FVG",
                "Buy-side sweep",
                "Sell-side sweep",
                "MSS",
                "Session high sweep",
                "Session low sweep",
              ].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
        ) : ["above", "below"].includes(kind) ? (
          <label>
            Price
            <input
              type="number"
              min="0"
              value={level}
              onChange={(e) => setLevel(e.target.value)}
            />
          </label>
        ) : null}
        <label>
          <span>Repeat</span>
          <input
            type="checkbox"
            checked={repeat}
            onChange={(e) => setRepeat(e.target.checked)}
          />
        </label>
        <label>
          Cooldown (seconds)
          <input
            type="number"
            min="30"
            max="86400"
            value={cooldown}
            onChange={(e) => setCooldown(+e.target.value)}
          />
        </label>
        {kind === "probability" && (
          <label>
            Probability change (0–1)
            <input
              type="number"
              min="0.01"
              max="1"
              step="0.01"
              value={delta}
              onChange={(e) => setDelta(+e.target.value)}
            />
          </label>
        )}
        <button className="primary" onClick={() => void add()}>
          Create alert for {symbol}
        </button>
      </div>
      <p className="footnote">
        In-app, browser and sound delivery work while this workspace is open.
        Calendar alerts require a calendar key. NewsAPI does not supply reliable
        high-impact tagging; news-impact alerts and email/Telegram/Discord
        delivery are not enabled.
      </p>
      <ErrorBox text={error || d.error} />
      {!d.data?.length ? (
        <Empty>No alerts configured.</Empty>
      ) : (
        d.data.map((r: any) => (
          <div className="alert-row" key={r.key}>
            <Bell size={18} />
            <div>
              <b>{r.symbol}</b>
              <p>
                {r.kind === "signal"
                  ? r.signal
                  : ["above", "below"].includes(r.kind)
                    ? r.kind + " " + price(r.level)
                    : r.kind}{" "}
                · {r.source}
              </p>
            </div>
            <Badge tone={r.triggered ? "green" : "muted"}>
              {r.triggered ? "Triggered" : "Watching"}
            </Badge>
            <button onClick={() => void remove(r.key)}>Delete</button>
          </div>
        ))
      )}
    </Card>
  );
}
function WatchlistEditor({ assets, watch }: { assets: any[]; watch: any }) {
  const [error, setError] = useState("");
  async function toggle(s: string) {
    const list = watch.data?.symbols || [];
    try {
      await api("/api/watchlist", "PUT", {
        symbols: list.includes(s)
          ? list.filter((x: string) => x !== s)
          : [...list, s],
      });
      watch.refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <Card title="Manage your watchlist">
      <ErrorBox text={error || watch.error} />
      <div className="watch-grid">
        {assets.map((a) => (
          <button
            key={a.symbol}
            className={
              (watch.data?.symbols || []).includes(a.symbol) ? "selected" : ""
            }
            onClick={() => void toggle(a.symbol)}
          >
            <Star size={16} />
            <b>{a.name}</b>
            <span>{a.market}</span>
          </button>
        ))}
      </div>
    </Card>
  );
}
function SettingsPage() {
  const d = useData("/api/settings");
  const [tz, setTz] = useState("Asia/Kolkata"),
    [message, setMessage] = useState(""),
    [a, setA] = useState("BTCUSDT"),
    [b, setB] = useState("ETHUSDT"),
    [window, setWindow] = useState(50),
    [corr, setCorr] = useState<any>(null);
  async function save() {
    try {
      await api("/api/settings", "PUT", { timezone: tz });
      setMessage(
        "Display timezone saved. Session panels refresh within one minute.",
      );
    } catch (e) {
      setMessage((e as Error).message);
    }
  }
  async function correlate() {
    try {
      setCorr(await api(`/api/correlations?a=${a}&b=${b}&window=${window}`));
    } catch (e) {
      setCorr({ status: (e as Error).message });
    }
  }
  return (
    <>
      <Card title="Application settings">
        <div className="key-value">
          <span>Market mode</span>
          <Badge tone={d.data?.mock_mode ? "amber" : "green"}>
            {d.data?.mock_mode ? "DEMO" : "LIVE"}
          </Badge>
        </div>
        <div className="key-value">
          <span>Forex API</span>
          <span>
            {d.data?.forex_configured ? "Configured" : "Not configured"}
          </span>
        </div>
        <div className="key-value">
          <span>News API</span>
          <span>
            {d.data?.news_configured ? "Configured" : "Not configured"}
          </span>
        </div>
        <p className="muted">
          To connect real markets, set MOCK_MODE=false in backend/.env and
          restart the backend. Crypto uses public market data; forex requires a
          Twelve Data key and a plan supporting the requested feeds.
        </p>
        <div className="form-row">
          <label>
            Display timezone
            <select value={tz} onChange={(e) => setTz(e.target.value)}>
              {[
                "Asia/Kolkata",
                "UTC",
                "Europe/London",
                "America/New_York",
                "Asia/Tokyo",
              ].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </label>
          <button className="primary" onClick={() => void save()}>
            Save preferences
          </button>
        </div>
        {message && <div className="notice">{message}</div>}
        <p className="footnote">
          API keys are read by the backend only. No keys are returned to the
          browser.
        </p>
      </Card>
      <Card title="Rolling return correlations">
        <div className="form-row">
          <label>
            Instrument A
            <select value={a} onChange={(e) => setA(e.target.value)}>
              {["BTCUSDT", "ETHUSDT", "SOLUSDT", "EURUSD", "GBPUSD"].map(
                (x) => (
                  <option key={x}>{x}</option>
                ),
              )}
            </select>
          </label>
          <label>
            Instrument B
            <select value={b} onChange={(e) => setB(e.target.value)}>
              {["BTCUSDT", "ETHUSDT", "SOLUSDT", "EURUSD", "GBPUSD"].map(
                (x) => (
                  <option key={x}>{x}</option>
                ),
              )}
            </select>
          </label>
          <label>
            Hourly return window
            <select value={window} onChange={(e) => setWindow(+e.target.value)}>
              {[20, 50, 100, 200].map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </label>
          <button onClick={() => void correlate()}>Calculate</button>
        </div>
        {corr && (
          <div className="notice">
            {corr.status} · Correlation: {number(corr.value, 3)} ·{" "}
            {corr.samples || 0} aligned observations
          </div>
        )}
      </Card>
    </>
  );
}
