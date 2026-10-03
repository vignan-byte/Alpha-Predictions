import json
import time
from sqlalchemy import select
from app.database.store import Session, Prediction
from app.core.utils import dumps
from app.models.pipeline import metrics, LABELS
import numpy as np


def settle(df, symbol, source, tf):
    now = int(time.time())
    count = 0
    with Session.begin() as s:
        rows = s.scalars(
            select(Prediction).where(
                Prediction.symbol == symbol,
                Prediction.source == source,
                Prediction.due <= now,
                Prediction.result == None,
            )
        )
        for row in rows:
            p = json.loads(row.payload)
            if p["timeframe"] != tf:
                continue
            future = df[
                (df.time >= p.get("outcome_start", p["asof"]))
                & (df.end_time <= p["due"])
            ]
            if (
                len(future) != p["horizon_bars"]
                or int(future.iloc[-1].end_time) != p["due"]
                or int(future.iloc[0].time) != p.get("outcome_start", p["asof"])
            ):
                continue
            actual_return = float(future.close.iloc[-1] / p["reference_price"] - 1)
            threshold = p["neutral_threshold"]
            direction = (
                "Bullish"
                if actual_return > threshold
                else ("Bearish" if actual_return < -threshold else "Neutral")
            )
            result = dict(
                actual_high=float(future.high.max()),
                actual_low=float(future.low.min()),
                actual_return=actual_return,
                actual_outcome=direction,
                correct=direction == p.get("model_direction", p["direction"]),
                signal_action=p.get("signal_action", p["direction"]),
                absolute_return_error=abs(actual_return - p["expected_return"]),
            )
            row.result = dumps(result)
            count += 1
    return count


def performance(rows):
    settled = sorted([r for r in rows if r.get("result")], key=lambda r: r["asof"])
    disjoint = []
    ends = {}
    for r in settled:
        k = (r["symbol"], r["source"], r["horizon"])
        if r["asof"] >= ends.get(k, 0):
            disjoint.append(r)
            ends[k] = r["due"]
    if len(disjoint) < 30:
        return dict(
            status="Insufficient sample size",
            settled=len(settled),
            non_overlapping=len(disjoint),
            required=30,
            metrics=None,
        )
    y = np.array([LABELS.index(r["result"]["actual_outcome"]) for r in disjoint])
    probs = np.array([[r["probabilities"][l] for l in LABELS] for r in disjoint])
    return dict(
        status="measured",
        settled=len(settled),
        non_overlapping=len(disjoint),
        metrics=dict(
            **metrics(y, probs),
            mean_absolute_return_error=float(
                np.mean([r["result"]["absolute_return_error"] for r in disjoint])
            )
        ),
        note="Prediction metrics only. Profit factor and drawdown belong to a specified trading backtest.",
    )
