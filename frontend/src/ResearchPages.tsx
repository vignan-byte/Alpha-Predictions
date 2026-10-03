import { useState, useEffect, type ReactNode } from "react";
import { api, useData, price, number, pct } from "./api";
import { EquityChart } from "./Chart";
function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="card research-card">
      <div className="card-head">
        <h3>{title}</h3>
      </div>
      {children}
    </section>
  );
}
function ErrorMessage({ text }: { text?: string }) {
  return text ? (
    <div className="error" role="alert">
      {text}
    </div>
  ) : null;
}
function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
const date = (v: number) => new Date(v * 1000).toLocaleString();
export function AuthGate({ children }: { children: ReactNode }) {
  const auth = useData("/api/auth/status"),
    [token, setToken] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  if (auth.loading)
    return <div className="auth-shell">Connecting to AlphaPredictorsAI…</div>;
  if (auth.error)
    return (
      <div className="auth-shell">
        <ErrorMessage text={auth.error} />
        <button onClick={auth.refresh}>Reconnect</button>
      </div>
    );
  if (auth.data?.authenticated) return <>{children}</>;
  return (
    <div className="auth-shell">
      <form
        className="card"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            await api("/api/auth/login", "POST", { token });
            setToken("");
            auth.refresh();
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <span className="eyebrow">PRIVATE RESEARCH WORKSPACE</span>
        <h1>AlphaPredictorsAI</h1>
        <p>Enter the access token configured on your server.</p>
        <label>
          Access token
          <input
            autoComplete="current-password"
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            required
          />
        </label>
        <ErrorMessage text={error} />
        <button className="primary" disabled={busy}>
          {busy ? "Verifying…" : "Unlock workspace"}
        </button>
      </form>
    </div>
  );
}
export function CalendarPage() {
  const [impact, setImpact] = useState(""),
    [currency, setCurrency] = useState(""),
    [now, setNow] = useState(Date.now() / 1000);
  const d = useData(
    `/api/calendar?${new URLSearchParams({ ...(impact ? { impact } : {}), ...(currency ? { currency } : {}) })}`,
    60000,
  );
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <Panel title="Economic calendar">
      <div className="research-intro">
        <div>
          <span className="eyebrow">MACRO INTELLIGENCE</span>
          <h2>Events that move markets</h2>
          <p>
            Scheduled releases with provider attribution, reported values and
            local time.
          </p>
        </div>
        <span
          className={"badge " + (d.data?.status === "live" ? "green" : "amber")}
        >
          {d.data?.status?.toUpperCase() || "CONNECTING"}
        </span>
      </div>
      <div className="form-row">
        <select
          aria-label="Impact filter"
          value={impact}
          onChange={(e) => setImpact(e.target.value)}
        >
          <option value="">All impact levels</option>
          {["high", "medium", "low"].map((v) => (
            <option key={v}>{v}</option>
          ))}
        </select>
        <select
          aria-label="Currency filter"
          value={currency}
          onChange={(e) => setCurrency(e.target.value)}
        >
          <option value="">All currencies</option>
          {["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "CNY", "INR"].map(
            (v) => (
              <option key={v}>{v}</option>
            ),
          )}
        </select>
        <button onClick={d.refresh}>Refresh calendar</button>
        <span className="muted">
          {d.data?.source} · {d.data?.timezone}
        </span>
      </div>
      <ErrorMessage text={d.error || d.data?.message} />
      {d.loading ? (
        <div className="empty">Loading calendar…</div>
      ) : !d.data?.events?.length ? (
        <div className="empty">
          No provider events available for these filters.
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {[
                  "Release time",
                  "Event",
                  "Currency",
                  "Impact",
                  "Countdown / status",
                  "Forecast",
                  "Previous",
                  "Actual",
                  "Source",
                ].map((x) => (
                  <th key={x}>{x}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {d.data.events.map((e: any) => (
                <tr key={e.id}>
                  <td>
                    {e.local_time?.replace("T", " ")}
                    {e.tentative ? " · tentative" : ""}
                  </td>
                  <td>
                    <b>{e.name}</b>
                    <small className="block muted">{e.country}</small>
                  </td>
                  <td>{e.currency}</td>
                  <td>
                    <span
                      className={
                        "badge " + (e.impact === "high" ? "red" : "amber")
                      }
                    >
                      {e.impact}
                    </span>
                  </td>
                  <td>
                    {e.timestamp > now
                      ? `${Math.floor((e.timestamp - now) / 3600)}h ${Math.floor(((e.timestamp - now) % 3600) / 60)}m`
                      : e.status}
                  </td>
                  <td>{e.forecast ?? "—"}</td>
                  <td>{e.previous ?? "—"}</td>
                  <td>{e.actual ?? "—"}</td>
                  <td>
                    {e.source_url?.startsWith("https://") ? (
                      <a href={e.source_url} target="_blank" rel="noreferrer">
                        {e.source}
                      </a>
                    ) : (
                      e.source
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="footnote">
        Provider schedules can change. Missing forecasts and actuals remain
        blank. Headlines are shown separately under News.
      </p>
    </Panel>
  );
}
export function NewsPage() {
  const d = useData("/api/news", 300000);
  return (
    <Panel title="Market news">
      <div className="research-intro">
        <div>
          <span className="eyebrow">SOURCE-ATTRIBUTED HEADLINES</span>
          <h2>The market briefing</h2>
          <p>
            Original reporting, timestamps and links. No generated sentiment
            scores.
          </p>
        </div>
        <span className="badge amber">
          {d.data?.status?.toUpperCase() || "CONNECTING"}
        </span>
      </div>
      <ErrorMessage text={d.error || d.data?.message} />
      <div className="news-grid">
        {d.data?.items?.map((n: any) => (
          <article className="news-item" key={n.url}>
            <span className="eyebrow">{n.source}</span>
            <h3>
              <a
                href={/^https?:\/\//.test(n.url) ? n.url : undefined}
                target="_blank"
                rel="noreferrer"
              >
                {n.title}
              </a>
            </h3>
            <p>{new Date(n.published_at).toLocaleString()}</p>
            <span className="badge muted">
              {n.related_assets?.join(" · ") || "Macro / broad market"}
            </span>
          </article>
        ))}
      </div>
      {!d.data?.items?.length && (
        <div className="empty">
          No news feed available. Add NEWS_API_KEY on the server to connect
          NewsAPI.
        </div>
      )}
    </Panel>
  );
}
export function CorrelationsPage() {
  const [symbols, setSymbols] = useState("BTCUSDT,ETHUSDT,SOLUSDT"),
    [query, setQuery] = useState(symbols),
    [window, setWindow] = useState(50);
  const d = useData(
    `/api/correlations/matrix?symbols=${encodeURIComponent(query)}&window=${window}`,
  );
  return (
    <Panel title="Cross-market relationships">
      <div className="research-intro">
        <div>
          <span className="eyebrow">RELATIVE STRENGTH & CO-MOVEMENT</span>
          <h2>Correlation workspace</h2>
          <p>
            Aligned closing returns. A relationship describes the sample; it is
            not a trade recommendation.
          </p>
        </div>
      </div>
      <form
        className="form-row"
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(symbols.toUpperCase().replaceAll(" ", ""));
        }}
      >
        <label>
          Instruments
          <input
            aria-label="Correlation symbols"
            value={symbols}
            onChange={(e) => setSymbols(e.target.value)}
          />
        </label>
        <label>
          Window
          <select value={window} onChange={(e) => setWindow(+e.target.value)}>
            {[20, 50, 100, 200].map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        <button className="primary">Measure relationships</button>
      </form>
      <ErrorMessage text={d.error} />
      {Object.entries(d.data?.errors || {}).map(([key, v]) => (
        <ErrorMessage key={key} text={`${key}: ${v}`} />
      ))}
      {d.loading ? (
        <div className="empty">Aligning instrument history…</div>
      ) : (
        <>
          <div className="table-wrap">
            <table className="correlation-table">
              <thead>
                <tr>
                  <th>Pearson r</th>
                  {d.data?.symbols?.map((s: string) => (
                    <th key={s}>{s}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {d.data?.symbols?.map((a: string) => (
                  <tr key={a}>
                    <th>{a}</th>
                    {d.data.symbols.map((b: string) => {
                      const v = d.data.matrix[a][b];
                      return (
                        <td
                          key={b}
                          style={{
                            background:
                              v == null
                                ? "transparent"
                                : `rgba(${v >= 0 ? "49,201,160" : "240,119,130"},${Math.abs(v) * 0.24})`,
                          }}
                        >
                          {number(v, 3)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="news-grid">
            {d.data?.relationships?.map((r: any) => (
              <article className="news-item" key={r.a + r.b}>
                <h3>
                  {r.a} ↔ {r.b}
                </h3>
                <p>
                  {r.samples} paired returns · recent 20:{" "}
                  {number(r.recent_20, 3)}
                </p>
                <p>
                  {r.breakdown
                    ? "Correlation shift > 0.5"
                    : "No measured breakdown"}{" "}
                  · {r.smt}
                </p>
                <p>20-bar return difference: {pct(r.return_divergence)}</p>
              </article>
            ))}
          </div>
          <p className="footnote">{d.data?.definition}</p>
          <p className="footnote">
            Sources:{" "}
            {Object.entries(d.data?.sources || {})
              .map(([s, v]) => `${s}: ${v}`)
              .join(" · ")}
            . NASDAQ, S&P 500, gold, DXY and yields require an additional
            licensed data adapter and are unavailable in this release.
          </p>
        </>
      )}
    </Panel>
  );
}
type Position = {
  id: string;
  symbol: string;
  side: number;
  units: number;
  entry: number;
  mark: number;
  stop: number;
  target: number;
  net_pnl: number;
  exit: number;
  closed: number;
  reason: string;
  mark_time: number;
};
type Preview = {
  id: string;
  symbol: string;
  units: number;
  estimated_entry: number;
  estimated_fee: number;
  estimated_risk: number;
  margin: number;
  expires: number;
  side: number;
  stop: number;
  target: number;
};
export function PaperPage({ symbol }: { symbol: string }) {
  const account = useData(`/api/paper/account?symbol=${symbol}`, 5000),
    quote = useData(`/api/paper/quote/${symbol}`, 5000);
  const [side, setSide] = useState(1),
    [units, setUnits] = useState("0.01"),
    [risk, setRisk] = useState(""),
    [stop, setStop] = useState(""),
    [target, setTarget] = useState(""),
    [balance, setBalance] = useState("10000"),
    [preview, setPreview] = useState<Preview | null>(null),
    [closing, setClosing] = useState<Position | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState("");
  const a = account.data;
  useEffect(() => {
    setPreview(null);
    setClosing(null);
    setStop("");
    setTarget("");
    setError("");
    setNotice("");
  }, [symbol, side]);
  async function action(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      account.refresh();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Panel title="Paper execution desk">
        <div className="research-intro">
          <div>
            <span className="eyebrow">
              VIRTUAL CAPITAL · MANUAL CONFIRMATION
            </span>
            <h2>Review. Confirm. Track.</h2>
            <p>
              Market orders with explicit costs, bracket protection and a
              persistent fill ledger.
            </p>
          </div>
          <span className="badge amber">
            PAPER ONLY · {a?.source?.toUpperCase() || "CONNECTING"}
          </span>
        </div>
        <div className="metrics">
          <Stat
            label={`Equity · ${a?.currency || ""}`}
            value={number(a?.equity)}
          />
          <Stat label="Available balance" value={number(a?.available)} />
          <Stat label="Realized P&L" value={number(a?.realized_pnl)} />
          <Stat label="Unrealized P&L" value={number(a?.unrealized_pnl)} />
          <Stat label="Max drawdown" value={number(a?.max_drawdown) + "%"} />
        </div>
        <ErrorMessage text={error || account.error || quote.error} />
        {notice && (
          <div className="success" role="status">
            {notice}
          </div>
        )}
        <div className="paper-grid">
          <form
            className="order-form"
            onSubmit={(e) => {
              e.preventDefault();
              void action(async () => {
                const p = await api("/api/paper/preview", "POST", {
                  symbol,
                  side,
                  units: +units,
                  risk_pct: risk ? +risk : null,
                  stop: +stop,
                  target: +target,
                  fee_bps: 5,
                  slippage_bps: 2,
                });
                setPreview(p);
                setNotice(
                  "Preview ready. Review and explicitly confirm to place a virtual order.",
                );
              });
            }}
          >
            <h3>
              {symbol} <span className="muted">{price(quote.data?.price)}</span>
            </h3>
            <p className="small muted">
              Quote: {quote.data?.source} · {quote.data?.status} ·{" "}
              {quote.data?.timestamp ? date(quote.data.timestamp) : "—"}
            </p>
            <label>
              Direction
              <select
                aria-label="Paper direction"
                value={side}
                onChange={(e) => setSide(+e.target.value)}
              >
                <option value={1}>Long</option>
                <option value={-1}>Short</option>
              </select>
            </label>
            <div className="form-row">
              <label>
                Units
                <input
                  aria-label="Paper units"
                  type="number"
                  min="0.000001"
                  step="any"
                  value={units}
                  onChange={(e) => setUnits(e.target.value)}
                  required
                />
              </label>
              <label>
                Risk % (optional)
                <input
                  aria-label="Paper risk"
                  type="number"
                  min="0.01"
                  max="5"
                  step="0.01"
                  placeholder="Use fixed units"
                  value={risk}
                  onChange={(e) => setRisk(e.target.value)}
                />
              </label>
            </div>
            <div className="form-row">
              <label>
                Stop loss
                <input
                  aria-label="Paper stop"
                  type="number"
                  min="0.000001"
                  step="any"
                  value={stop}
                  onChange={(e) => setStop(e.target.value)}
                  required
                />
              </label>
              <label>
                Take profit
                <input
                  aria-label="Paper target"
                  type="number"
                  min="0.000001"
                  step="any"
                  value={target}
                  onChange={(e) => setTarget(e.target.value)}
                  required
                />
              </label>
            </div>
            <button
              type="button"
              onClick={() => {
                const p = quote.data?.price;
                if (p) {
                  setStop((p * (1 - side * 0.02)).toFixed(p < 10 ? 5 : 2));
                  setTarget((p * (1 + side * 0.04)).toFixed(p < 10 ? 5 : 2));
                }
              }}
            >
              Set 2% stop / 4% target
            </button>
            <p className="footnote">
              Fee 5 bps + adverse slippage 2 bps per side. Full notional
              collateral; no leverage. Risk sizing overrides units.
            </p>
            <button className="primary" disabled={busy || !quote.data}>
              Preview paper order
            </button>
          </form>
          <div className="paper-review">
            {preview ? (
              <>
                <span className="eyebrow">
                  ORDER PREVIEW · EXPIRES AFTER 30 SECONDS
                </span>
                <h3>
                  {preview.side === 1 ? "Long" : "Short"} {preview.symbol}
                </h3>
                <dl>
                  <dt>Quantity</dt>
                  <dd>{number(preview.units, 6)}</dd>
                  <dt>Estimated entry</dt>
                  <dd>{price(preview.estimated_entry)}</dd>
                  <dt>Stop / target</dt>
                  <dd>
                    {price(preview.stop)} / {price(preview.target)}
                  </dd>
                  <dt>Reserved collateral</dt>
                  <dd>
                    {number(preview.margin)} {a?.currency}
                  </dd>
                  <dt>Estimated entry fee</dt>
                  <dd>{number(preview.estimated_fee)}</dd>
                  <dt>Estimated stop loss incl. fees</dt>
                  <dd>{number(preview.estimated_risk)}</dd>
                  <dt>Expires</dt>
                  <dd>{date(preview.expires)}</dd>
                </dl>
                <p className="footnote">
                  Actual quote is checked again on confirmation. Price drift
                  above 50 bps rejects the preview. Stop losses can slip.
                </p>
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() =>
                    void action(async () => {
                      await api("/api/paper/confirm", "POST", {
                        symbol,
                        preview_id: preview.id,
                        confirm: true,
                      });
                      setPreview(null);
                      setNotice(
                        "Paper order filled. Position and costs are recorded below.",
                      );
                    })
                  }
                >
                  Confirm paper order
                </button>
                <button onClick={() => setPreview(null)}>
                  Dismiss preview
                </button>
              </>
            ) : (
              <>
                <span className="eyebrow">CONTROLLED EXECUTION</span>
                <h3>Your review comes first.</h3>
                <p>
                  Set the quantity and protective levels, then preview the
                  order. The prediction engine cannot place trades.
                </p>
                <p className="footnote">{a?.note}</p>
                {!a?.positions?.length && !a?.trades?.length && (
                  <div>
                    <label>
                      Starting virtual balance
                      <input
                        aria-label="Starting balance"
                        type="number"
                        min="100"
                        max="1000000000"
                        value={balance}
                        onChange={(e) => setBalance(e.target.value)}
                      />
                    </label>
                    <button
                      disabled={busy}
                      onClick={() =>
                        void action(async () => {
                          await api("/api/paper/account", "PUT", {
                            symbol,
                            balance: +balance,
                          });
                          setNotice("Starting virtual balance updated.");
                        })
                      }
                    >
                      Set starting balance
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </Panel>
      <Panel title="Open positions">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {[
                  "Instrument",
                  "Side",
                  "Units",
                  "Entry",
                  "Mark",
                  "Stop",
                  "Target",
                  "Quote time",
                  "Action",
                ].map((x) => (
                  <th key={x}>{x}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {a?.positions?.map((p: Position) => (
                <tr key={p.id}>
                  <td>{p.symbol}</td>
                  <td>{p.side === 1 ? "Long" : "Short"}</td>
                  <td>{number(p.units, 6)}</td>
                  <td>{price(p.entry)}</td>
                  <td>{price(p.mark)}</td>
                  <td>{price(p.stop)}</td>
                  <td>{price(p.target)}</td>
                  <td>{date(p.mark_time)}</td>
                  <td>
                    <button onClick={() => setClosing(p)}>
                      Close position
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!a?.positions?.length && (
          <div className="empty">No open paper positions.</div>
        )}
        {closing && (
          <div
            className="confirmation"
            role="dialog"
            aria-label="Confirm paper close"
          >
            <b>
              Close {closing.symbol} virtual position at the next fresh quote?
            </b>
            <button
              className="primary"
              disabled={busy}
              onClick={() =>
                void action(async () => {
                  await api(
                    `/api/paper/positions/${closing.id}/close`,
                    "POST",
                    { symbol: closing.symbol, confirm: true },
                  );
                  setClosing(null);
                  setNotice(
                    "Paper position closed. Realized performance updated.",
                  );
                })
              }
            >
              Confirm close
            </button>
            <button onClick={() => setClosing(null)}>Cancel</button>
          </div>
        )}
      </Panel>
      <Panel title="Paper performance">
        <div className="metrics">
          <Stat label="Closed trades" value={a?.trade_count ?? 0} />
          <Stat label="Win rate" value={pct(a?.win_rate)} />
          <Stat label="Profit factor" value={number(a?.profit_factor)} />
          <Stat label="Expectancy" value={number(a?.expectancy)} />
        </div>
        {a?.equity_curve?.length > 0 && (
          <EquityChart
            data={a.equity_curve.map((p: any) => ({
              time: p.time,
              value: p.value,
            }))}
          />
        )}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {[
                  "Closed",
                  "Instrument",
                  "Side",
                  "Entry",
                  "Exit",
                  "Net P&L",
                  "Reason",
                ].map((x) => (
                  <th key={x}>{x}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {a?.trades
                ?.slice()
                .reverse()
                .map((t: Position) => (
                  <tr key={t.id}>
                    <td>{date(t.closed)}</td>
                    <td>{t.symbol}</td>
                    <td>{t.side === 1 ? "Long" : "Short"}</td>
                    <td>{price(t.entry)}</td>
                    <td>{price(t.exit)}</td>
                    <td className={t.net_pnl >= 0 ? "positive" : "negative"}>
                      {number(t.net_pnl)}
                    </td>
                    <td>{t.reason}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <details>
          <summary>Order preview / fill ledger</summary>
          <div className="table-wrap">
            <table>
              <tbody>
                {a?.orders
                  ?.slice()
                  .reverse()
                  .map((o: any) => (
                    <tr key={o.id}>
                      <td>{date(o.created)}</td>
                      <td>{o.symbol}</td>
                      <td>{o.status}</td>
                      <td>{o.id}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </details>
      </Panel>
    </>
  );
}
