import pandas as pd


def correlation(a, b, window):
    aligned = pd.merge(
        a[["time", "close"]], b[["time", "close"]], on="time", suffixes=("_a", "_b")
    ).sort_values("time")
    returns = aligned[["close_a", "close_b"]].pct_change().dropna().tail(window)
    if len(returns) < window:
        return {
            "status": "Insufficient sample size",
            "value": None,
            "samples": len(returns),
        }
    value = returns.close_a.corr(returns.close_b)
    return {
        "status": "measured",
        "value": float(value) if pd.notna(value) else None,
        "samples": len(returns),
        "method": "Pearson correlation of aligned close-to-close returns",
    }


def matrix(data, window):
    names = list(data)
    values = {}
    relationships = []
    for a in names:
        values[a] = {}
        for b in names:
            result = correlation(data[a], data[b], window)
            values[a][b] = result["value"]
            if names.index(a) >= names.index(b):
                continue
            aligned = pd.merge(
                data[a][["time", "close", "high", "low"]],
                data[b][["time", "close", "high", "low"]],
                on="time",
                suffixes=("_a", "_b"),
            ).sort_values("time")
            returns = aligned[["close_a", "close_b"]].pct_change().dropna()
            recent = returns.tail(20)
            previous = returns.iloc[-window - 20 : -20]
            prior = (
                previous.close_a.corr(previous.close_b) if len(previous) >= 20 else None
            )
            now = recent.close_a.corr(recent.close_b) if len(recent) >= 20 else None
            divergence = None
            smt = None
            if len(aligned) >= 21:
                x = aligned.iloc[-1]
                past = aligned.iloc[-21:-1]
                ra = float(x.close_a / past.close_a.iloc[0] - 1)
                rb = float(x.close_b / past.close_b.iloc[0] - 1)
                divergence = ra - rb
                ah = x.high_a > past.high_a.max()
                bh = x.high_b > past.high_b.max()
                al = x.low_a < past.low_a.min()
                bl = x.low_b < past.low_b.min()
                smt = (
                    "Non-confirming high"
                    if ah != bh
                    else ("Non-confirming low" if al != bl else "No divergence")
                )
            relationships.append(
                dict(
                    a=a,
                    b=b,
                    correlation=result["value"],
                    samples=result["samples"],
                    recent_20=now,
                    previous=prior,
                    breakdown=bool(
                        prior is not None and now is not None and abs(prior - now) > 0.5
                    ),
                    return_divergence=divergence,
                    smt=smt,
                )
            )
    return dict(
        symbols=names,
        matrix=values,
        relationships=relationships,
        window=window,
        definition="Pearson aligned returns; breakdown = |recent20 - preceding-window correlation| > .5. SMT = one instrument makes a 20-bar high/low and the other does not; descriptive only.",
    )
