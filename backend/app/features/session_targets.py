"""Next civil-session targets with per-origin label end times."""

from datetime import datetime, timezone
import numpy as np
import pandas as pd
from app.sessions.engine import sessions


def next_window(asof):
    row = sessions(datetime.fromtimestamp(int(asof), timezone.utc), "UTC")["next"]
    return dict(
        name=row["name"],
        start=int(datetime.fromisoformat(row["start"]).timestamp()),
        end=int(datetime.fromisoformat(row["end"]).timestamp()),
    )


def session_targets(d):
    rows = []
    starts = d.time.to_numpy()
    ends = d.end_time.to_numpy()
    for i, r in d.iterrows():
        window = next_window(r.end_time)
        left = int(np.searchsorted(starts, window["start"]))
        right = int(np.searchsorted(ends, window["end"], side="right"))
        future = d.iloc[left:right]
        if (
            future.empty
            or int(future.time.iloc[0]) != window["start"]
            or int(future.end_time.iloc[-1]) != window["end"]
            or not (
                future.time.iloc[1:].to_numpy() == future.end_time.iloc[:-1].to_numpy()
            ).all()
        ):
            rows.append(
                dict.fromkeys(["class", "return", "high", "low", "volatility"], np.nan)
            )
            continue
        ret = float(future.close.iloc[-1] / r.close - 1)
        threshold = r.atr_ratio * 0.15
        rows.append(
            {
                "class": 2 if ret > threshold else (0 if ret < -threshold else 1),
                "return": ret,
                "high": float(future.high.max() / r.close - 1),
                "low": float(future.low.min() / r.close - 1),
                "volatility": float(future["return"].std(ddof=0)),
            }
        )
    return pd.DataFrame(rows, index=d.index)
