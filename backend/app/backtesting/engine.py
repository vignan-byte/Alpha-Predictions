import numpy as np
import pandas as pd
from app.features.engine import build


def run(
    df,
    strategy="ema",
    cost_bps=5,
    slippage_bps=2,
    risk_reward=2,
    stop_atr=2,
    risk_pct=1,
    spread_bps=0,
    sizing="risk",
    fixed_units=1,
    start_index=61,
    end_index=None,
):
    d, _, _ = build(df)
    if sizing not in ("risk", "fixed") or fixed_units <= 0 or spread_bps < 0:
        raise ValueError("Invalid sizing or spread")
    d = d.iloc[:end_index] if end_index is not None else d
    if len(d) < max(62, start_index + 1):
        raise ValueError("Insufficient bars in evaluation window")
    execution_bps = slippage_bps + spread_bps / 2
    trades = []
    equity = [
        dict(
            time=int(d.time.iloc[max(0, start_index - 1)]), value=10000.0, drawdown=0.0
        )
    ]
    capital = 10000.0
    peak = capital
    position = None
    if strategy not in ("ema", "smc", "rsi"):
        raise ValueError("Unknown strategy")
    for i in range(max(61, start_index), len(d)):
        bar = d.iloc[i]
        prev = d.iloc[i - 1]
        if position is None:
            if strategy == "ema":
                signal = (
                    1
                    if prev.ema20 > prev.ema50
                    and d.ema20.iloc[i - 2] <= d.ema50.iloc[i - 2]
                    else (
                        -1
                        if prev.ema20 < prev.ema50
                        and d.ema20.iloc[i - 2] >= d.ema50.iloc[i - 2]
                        else 0
                    )
                )
            elif strategy == "smc":
                signal = int(prev.bos or prev.choch)
            else:
                signal = 1 if prev.rsi < 30 else (-1 if prev.rsi > 70 else 0)
            if signal and np.isfinite(prev.atr) and prev.atr > 0:
                entry = bar.open * (1 + signal * execution_bps / 10000)
                dist = prev.atr * stop_atr
                units = min(
                    capital
                    * risk_pct
                    / 100
                    / (dist + entry * 2 * (cost_bps + execution_bps) / 10000),
                    capital / (entry * (1 + cost_bps / 10000)),
                )
                if sizing == "fixed":
                    units = min(fixed_units, capital / (entry * (1 + cost_bps / 10000)))
                position = dict(
                    side=signal,
                    entry=float(entry),
                    stop=float(entry - signal * dist),
                    target=float(entry + signal * dist * risk_reward),
                    units=units,
                    opened=int(bar.time),
                )
        if position:
            p = position
            side = p["side"]
            exit_price = None
            reason = ""
            # Gaps fill at open when worse than stop. Ambiguous stop/target bars use stop first.
            if (side == 1 and bar.open <= p["stop"]) or (
                side == -1 and bar.open >= p["stop"]
            ):
                exit_price = bar.open
                reason = "gap stop"
            elif (side == 1 and bar.low <= p["stop"]) or (
                side == -1 and bar.high >= p["stop"]
            ):
                exit_price = p["stop"]
                reason = "stop"
            elif (side == 1 and bar.high >= p["target"]) or (
                side == -1 and bar.low <= p["target"]
            ):
                exit_price = p["target"]
                reason = "target"
            elif i == len(d) - 1:
                exit_price = bar.close
                reason = "end of data"
            if exit_price is not None:
                exit_price *= 1 - side * execution_bps / 10000
                pnl = p["units"] * (
                    side * (exit_price - p["entry"])
                    - (p["entry"] + exit_price) * cost_bps / 10000
                )
                ret = pnl / capital
                capital += pnl
                trades.append(
                    dict(
                        **p,
                        closed=int(bar.end_time),
                        exit=float(exit_price),
                        pnl=float(pnl),
                        return_pct=float(ret * 100),
                        reason=reason,
                    )
                )
                position = None
        marked = capital
        if position:
            marked += position["units"] * (
                position["side"] * (bar.close - position["entry"])
                - (position["entry"] + bar.close) * cost_bps / 10000
            )
        peak = max(peak, marked)
        equity.append(
            dict(
                time=int(bar.end_time),
                value=float(marked),
                drawdown=float((marked / peak - 1) * 100),
            )
        )
        if capital <= 0:
            break
    pnl = np.array([t["pnl"] for t in trades])
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    daily = pd.DataFrame(equity)
    daily.index = pd.to_datetime(daily.time, unit="s", utc=True)
    daily_ret = daily.value.resample("1D").last().pct_change().dropna()
    sharpe = (
        float(daily_ret.mean() / daily_ret.std() * np.sqrt(365))
        if len(daily_ret) > 20 and daily_ret.std() > 0
        else None
    )
    monthly = {}
    by_session = {}
    streak_win = streak_loss = max_win = max_loss = 0
    for t in trades:
        month = pd.Timestamp(t["closed"], unit="s", tz="UTC").strftime("%Y-%m")
        monthly[month] = monthly.get(month, 0) + t["pnl"]
        hour = pd.Timestamp(t["opened"], unit="s", tz="UTC").hour
        session = (
            "UTC 00–08" if hour < 8 else ("UTC 08–16" if hour < 16 else "UTC 16–24")
        )
        by_session[session] = by_session.get(session, 0) + t["pnl"]
        streak_win = streak_win + 1 if t["pnl"] > 0 else 0
        streak_loss = streak_loss + 1 if t["pnl"] <= 0 else 0
        max_win = max(max_win, streak_win)
        max_loss = max(max_loss, streak_loss)
    return dict(
        total_trades=len(trades),
        wins=len(wins),
        losses=len(losses),
        sortino=(
            float(
                daily_ret.mean()
                / np.sqrt(np.mean(np.minimum(daily_ret, 0) ** 2))
                * np.sqrt(365)
            )
            if len(daily_ret) > 20 and np.any(daily_ret < 0)
            else None
        ),
        win_rate=float(len(wins) / len(pnl)) if len(pnl) else None,
        loss_rate=float(len(losses) / len(pnl)) if len(pnl) else None,
        profit_factor=float(wins.sum() / -losses.sum()) if losses.sum() < 0 else None,
        expectancy=float(pnl.mean()) if len(pnl) else None,
        net_return=(capital / 10000 - 1) * 100,
        max_drawdown=min(x["drawdown"] for x in equity),
        sharpe=sharpe,
        average_win=float(wins.mean()) if len(wins) else None,
        average_loss=float(losses.mean()) if len(losses) else None,
        consecutive_wins=max_win,
        consecutive_losses=max_loss,
        monthly=monthly,
        session_performance=by_session,
        equity=equity,
        trades=trades,
        assumptions=dict(
            cost_bps_per_side=cost_bps,
            slippage_bps_per_side=slippage_bps,
            execution="Next open; stop first on ambiguous bars; no leverage; one position; mark-to-market drawdown",
            risk_pct=risk_pct,
            spread_bps=spread_bps,
            sizing=sizing,
            fixed_units=fixed_units if sizing == "fixed" else None,
            annualization="365 days; Sharpe unavailable under 21 daily returns",
        ),
    )


def chronological_report(df, **kwargs):
    """Fixed, user-selected strategy; no fitting or optimization on any segment."""
    n = len(df)
    cut = int(n * 0.6)
    reports = []
    ranges = [("In sample", 61, cut), ("Out of sample", cut, n)]
    boundaries = np.linspace(cut, n, 4, dtype=int)
    ranges += [
        (f"Forward window {i+1}", int(boundaries[i]), int(boundaries[i + 1]))
        for i in range(3)
    ]
    for label, a, b in ranges:
        if b <= a:
            continue
        result = run(df, **kwargs, start_index=a, end_index=b)
        reports.append(
            dict(
                label=label,
                start=int(df.time.iloc[a]),
                end=int(df.end_time.iloc[b - 1]),
                bars=b - a,
                **{
                    k: result[k]
                    for k in [
                        "total_trades",
                        "wins",
                        "losses",
                        "win_rate",
                        "net_return",
                        "max_drawdown",
                        "profit_factor",
                        "expectancy",
                        "sharpe",
                        "sortino",
                    ]
                },
            )
        )
    return dict(
        method="Fixed strategy; 60% research / 40% holdout; three sequential holdout windows. Each segment resets capital and positions; historical features retain prior-bar warmup. No optimization or test-set tuning.",
        segments=reports,
    )
