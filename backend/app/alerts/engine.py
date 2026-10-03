"""Persistent, source-scoped alert transitions. External delivery is never implicit."""

import time
import uuid
from app.database import store


def evaluate(
    symbol,
    source,
    price,
    events,
    prediction=None,
    session_context=None,
    calendar_events=None,
):
    triggered = []
    now = int(time.time())
    for rule in store.records("alert_rules"):
        if (
            rule["symbol"] != symbol
            or rule["source"] != source
            or (rule.get("triggered") and not rule.get("repeat", False))
        ):
            continue
        kind = rule["kind"]
        previous = rule.get("observed")
        value = None
        event_id = None
        hit = False
        if kind in ("above", "below"):
            value = (
                price >= rule["level"] if kind == "above" else price <= rule["level"]
            )
            hit = value and previous is not True
        elif kind == "signal":
            candidates = [
                e
                for e in events
                if e["kind"] == rule["signal"]
                and e.get("confirmed_at", e["time"]) >= rule["created"]
            ]
            if candidates:
                e = candidates[-1]
                event_id = f"{e['kind']}:{e.get('confirmed_at',e['time'])}:{e.get('session','')}"
                hit = event_id != rule.get("last_event")
        elif kind in ("direction", "probability", "model") and prediction is not None:
            value = prediction.get(
                {
                    "direction": "direction",
                    "probability": "probability",
                    "model": "validation_status",
                }[kind]
            )
            if previous is not None and value is not None:
                hit = (
                    abs(value - previous) >= rule.get("delta", 0.1)
                    if kind == "probability"
                    else value != previous
                )
        elif kind == "session":
            current = (session_context or {}).get("current", [])
            event_id = "|".join(sorted(f"{s['name']}:{s['start']}" for s in current))
            # Only sessions opening since this rule was created are eligible.
            from datetime import datetime

            hit = (
                bool(current)
                and any(
                    datetime.fromisoformat(s["start"]).timestamp() >= rule["created"]
                    for s in current
                )
                and event_id != rule.get("last_event")
            )
        elif kind == "calendar":
            relevant = [
                e
                for e in calendar_events or []
                if e["impact"] == "high"
                and 0 <= e["timestamp"] - now <= 900
                and (e["currency"] in symbol or e["currency"] == "USD")
            ]
            if relevant:
                event_id = "|".join(sorted(e["id"] for e in relevant))
                hit = event_id != rule.get("last_event")
        rule["observed"] = value
        if hit and now - rule.get("triggered_at", 0) >= rule.get(
            "cooldown_seconds", 300
        ):
            rule.update(
                triggered=True,
                triggered_at=now,
                price=price,
                last_event=event_id,
                trigger_count=rule.get("trigger_count", 0) + 1,
            )
            notification = dict(
                id=str(uuid.uuid4()),
                rule_id=rule["key"],
                symbol=symbol,
                source=source,
                kind=kind,
                signal=rule.get("signal"),
                price=price,
                created=now,
            )
            store.put("notifications", notification["id"], notification)
            triggered.append(notification)
        store.put(
            "alert_rules", rule["key"], {k: v for k, v in rule.items() if k != "key"}
        )
    return triggered
