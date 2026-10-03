"""Causal operational definitions, not a claim to a universal ICT interpretation."""

import numpy as np
import pandas as pd


def calculate(df, swing=3):
    d = df.copy()
    n = len(d)
    cols = [
        "bos",
        "choch",
        "mss",
        "sweep",
        "displacement",
        "fvg",
        "inverse_fvg",
        "order_block",
        "breaker",
        "mitigation",
        "inducement",
        "equal_high",
        "equal_low",
        "structure",
        "bias",
    ]
    out = {k: np.zeros(n) for k in cols}
    sh = np.full(n, np.nan)
    sl = sh.copy()
    premium = sh.copy()
    events = []
    zones = []
    high = None
    low = None
    prev_high = None
    prev_low = None
    bias = 0
    broken_h = None
    broken_l = None
    h = d.high.to_numpy()
    l = d.low.to_numpy()
    c = d.close.to_numpy()
    o = d.open.to_numpy()
    atr = (
        d.atr.to_numpy()
        if "atr" in d
        else (d.high - d.low).rolling(14).mean().to_numpy()
    )

    def event(i, kind, side, level):
        events.append(
            dict(
                time=int(d.time.iloc[i]),
                confirmed_at=(
                    int(d.end_time.iloc[i]) if "end_time" in d else int(d.time.iloc[i])
                ),
                kind=kind,
                side=side,
                level=float(level),
            )
        )

    for i in range(n):
        tol = atr[i] * 0.1 if np.isfinite(atr[i]) else (h[i] - l[i]) * 0.1
        p = i - swing
        if p >= swing:
            if h[p] > max(h[p - swing : p]) and h[p] >= max(h[p + 1 : i + 1]):
                prev_high = high
                high = h[p]
                if prev_high is not None:
                    out["structure"][i] = 1 if high > prev_high else -1
                    event(i, "HH" if high > prev_high else "LH", 1, high)
                    if abs(high - prev_high) <= tol:
                        out["equal_high"][i] = 1
                        event(i, "Equal highs", 1, high)
            if l[p] < min(l[p - swing : p]) and l[p] <= min(l[p + 1 : i + 1]):
                prev_low = low
                low = l[p]
                if prev_low is not None:
                    event(i, "HL" if low > prev_low else "LL", -1, low)
                    if abs(low - prev_low) <= tol:
                        out["equal_low"][i] = 1
                        event(i, "Equal lows", -1, low)
        sh[i] = high if high is not None else np.nan
        sl[i] = low if low is not None else np.nan
        if high is not None and low is not None and high > low:
            premium[i] = (c[i] - low) / (high - low)
        if np.isfinite(atr[i]) and abs(c[i] - o[i]) > 1.5 * atr[i]:
            out["displacement"][i] = np.sign(c[i] - o[i])
        if high is not None and h[i] > high and c[i] < high:
            out["sweep"][i] = -1
            event(i, "Buy-side sweep", -1, high)
        if low is not None and l[i] < low and c[i] > low:
            out["sweep"][i] = 1
            event(i, "Sell-side sweep", 1, low)
        side = (
            1
            if high is not None and c[i] > high and broken_h != high
            else (-1 if low is not None and c[i] < low and broken_l != low else 0)
        )
        if side:
            kind = "CHoCH" if bias and side != bias else "BOS"
            out[kind.lower()][i] = side
            if kind == "CHoCH" and out["displacement"][i] == side:
                out["mss"][i] = side
                event(i, "MSS", side, c[i])
            event(i, kind, side, high if side == 1 else low)
            bias = side
            if side == 1:
                broken_h = high
            else:
                broken_l = low
            for j in range(i - 1, max(-1, i - 11), -1):
                if (c[j] - o[j]) * side < 0:
                    zones.append(
                        dict(
                            kind="Order block",
                            side=side,
                            low=float(l[j]),
                            high=float(h[j]),
                            time=int(d.time.iloc[i]),
                            confirmed_at=(
                                int(d.end_time.iloc[i])
                                if "end_time" in d
                                else int(d.time.iloc[i])
                            ),
                            status="active",
                            created=i,
                        )
                    )
                    out["order_block"][i] = side
                    break
        if i >= 2:
            side = 1 if l[i] > h[i - 2] else (-1 if h[i] < l[i - 2] else 0)
            if side:
                bottom = h[i - 2] if side == 1 else h[i]
                top = l[i] if side == 1 else l[i - 2]
                zones.append(
                    dict(
                        kind="FVG",
                        side=side,
                        low=float(bottom),
                        high=float(top),
                        time=int(d.time.iloc[i]),
                        confirmed_at=(
                            int(d.end_time.iloc[i])
                            if "end_time" in d
                            else int(d.time.iloc[i])
                        ),
                        status="active",
                        created=i,
                    )
                )
                out["fvg"][i] = side
                event(i, "FVG", side, (bottom + top) / 2)
        for z in zones:
            if z["created"] == i or z["status"] != "active":
                continue
            invalid = (c[i] < z["low"]) if z["side"] == 1 else (c[i] > z["high"])
            if invalid:
                z["status"] = "invalidated"
                z["invalidated_at"] = (
                    int(d.end_time.iloc[i]) if "end_time" in d else int(d.time.iloc[i])
                )
                kind = "inverse_fvg" if z["kind"] == "FVG" else "breaker"
                out[kind][i] = -z["side"]
                event(i, kind, -z["side"], c[i])
                z["transition_kind"] = (
                    "Inverse FVG" if z["kind"] == "FVG" else "Breaker block"
                )
            elif (
                l[i] <= z["high"]
                and h[i] >= z["low"]
                and z["kind"] == "Order block"
                and not z.get("touched")
            ):
                z["touched"] = True
                z["mitigated_at"] = (
                    int(d.end_time.iloc[i]) if "end_time" in d else int(d.time.iloc[i])
                )
                out["mitigation"][i] = z["side"]
                event(i, "Mitigation", z["side"], c[i])
        out["bias"][i] = bias
        if out["displacement"][i]:
            event(i, "Displacement", int(out["displacement"][i]), c[i])
        if out["sweep"][i] and out["sweep"][i] == bias:
            out["inducement"][i] = bias
    for k, a in out.items():
        d[k] = a
    d["swing_high"] = sh
    d["swing_low"] = sl
    d["premium_discount"] = premium
    width = d.swing_high - d.swing_low
    d["ote_low"] = np.where(
        d.bias > 0, d.swing_high - 0.79 * width, d.swing_low + 0.62 * width
    )
    d["ote_high"] = np.where(
        d.bias > 0, d.swing_high - 0.62 * width, d.swing_low + 0.79 * width
    )
    d.loc[(width <= 0) | (d.bias == 0), ["ote_low", "ote_high"]] = np.nan
    last = d.iloc[-1] if len(d) else None
    if last is not None and np.isfinite(last.ote_low):
        zones.append(
            dict(
                kind="OTE",
                side=int(last.bias),
                low=float(last.ote_low),
                high=float(last.ote_high),
                time=int(last.time),
                status="active",
            )
        )
    for level, key, side in [
        ("Buy-side liquidity", "swing_high", -1),
        ("Sell-side liquidity", "swing_low", 1),
    ]:
        if last is not None and np.isfinite(last[key]) and np.isfinite(last.atr):
            zones.append(
                dict(
                    kind="Liquidity",
                    label=level,
                    side=side,
                    low=float(last[key] - 0.05 * last.atr),
                    high=float(last[key] + 0.05 * last.atr),
                    time=int(last.time),
                    status="active",
                )
            )
    return (
        d,
        events,
        [{k: v for k, v in z.items() if k != "created"} for z in zones[-80:]],
    )
