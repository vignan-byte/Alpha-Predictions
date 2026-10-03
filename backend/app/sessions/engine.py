from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo

SESSIONS = [
    ("Asian", "Asia/Tokyo", 9, 18),
    ("London", "Europe/London", 8, 17),
    ("New York", "America/New_York", 8, 17),
]


def sessions(now=None, display="Asia/Kolkata", df=None):
    now = now or datetime.now(timezone.utc)
    target = ZoneInfo(display)
    windows = []
    for name, tz, start, end in SESSIONS:
        zone = ZoneInfo(tz)
        local = now.astimezone(zone)
        for offset in (-1, 0, 1, 2, 3):
            day = local.date() + timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            a = datetime.combine(day, time(start), zone)
            b = datetime.combine(day, time(end), zone)
            if b > now:
                row = dict(
                    name=name,
                    start=a.astimezone(target).isoformat(),
                    end=b.astimezone(target).isoformat(),
                    active=a <= now < b,
                    seconds_remaining=int((b - now).total_seconds()),
                    starts_in=int((a - now).total_seconds()),
                    high=None,
                    low=None,
                    range=None,
                )
                if df is not None:
                    subset = df[
                        (df.time >= a.timestamp())
                        & (df.time < min(now.timestamp(), b.timestamp()))
                    ]
                    if not subset.empty:
                        row.update(
                            high=float(subset.high.max()),
                            low=float(subset.low.min()),
                            range=float(subset.high.max() - subset.low.min()),
                        )
                windows.append(row)
    current = [r for r in windows if r["active"]]
    upcoming = sorted(
        [r for r in windows if not r["active"]], key=lambda r: r["starts_in"]
    )
    return dict(
        current=current,
        next=upcoming[0] if upcoming else None,
        overlap=all(
            any(r["name"] == n for r in current) for n in ["London", "New York"]
        ),
        timezone=display,
        timestamp=now.astimezone(target).isoformat(),
        note="Weekday analytical session windows; holidays not modeled. Crypto trades continuously.",
    )


def historical_sessions(df, display="Asia/Kolkata"):
    """Session windows and extrema using only fully contained, closed input bars."""
    if df.empty:
        return []
    windows = []
    target = ZoneInfo(display)
    first = datetime.fromtimestamp(int(df.time.iloc[0]), timezone.utc)
    last = datetime.fromtimestamp(int(df.end_time.iloc[-1]), timezone.utc)
    for name, tz, h1, h2 in SESSIONS:
        zone = ZoneInfo(tz)
        day = first.astimezone(zone).date() - timedelta(days=1)
        finish = last.astimezone(zone).date()
        while day <= finish:
            if day.weekday() < 5:
                start = datetime.combine(day, time(h1), zone)
                end = datetime.combine(day, time(h2), zone)
                part = df[
                    (df.time >= start.timestamp())
                    & (df.end_time <= min(end.timestamp(), last.timestamp()))
                ]
                if not part.empty:
                    complete = (
                        int(part.time.iloc[0]) == int(start.timestamp())
                        and int(part.end_time.iloc[-1]) == int(end.timestamp())
                        and bool(
                            (
                                part.time.iloc[1:].to_numpy()
                                == part.end_time.iloc[:-1].to_numpy()
                            ).all()
                        )
                    )
                    windows.append(
                        dict(
                            name=name,
                            start=int(start.timestamp()),
                            end=int(end.timestamp()),
                            local_start=start.astimezone(target).isoformat(),
                            open=float(part.open.iloc[0]),
                            high=float(part.high.max()),
                            low=float(part.low.min()),
                            close=float(part.close.iloc[-1]),
                            range=float(part.high.max() - part.low.min()),
                            return_pct=float(
                                (part.close.iloc[-1] / part.open.iloc[0] - 1) * 100
                            ),
                            bars=len(part),
                            complete=complete,
                        )
                    )
            day += timedelta(days=1)
    # Explicit London/New York overlap windows for shading and statistics.
    for london in [w for w in windows if w["name"] == "London"]:
        for ny in [w for w in windows if w["name"] == "New York"]:
            a = max(london["start"], ny["start"])
            b = min(london["end"], ny["end"])
            if a < b:
                part = df[(df.time >= a) & (df.end_time <= b)]
                if len(part):
                    windows.append(
                        dict(
                            name="London/NY overlap",
                            start=a,
                            end=b,
                            local_start=datetime.fromtimestamp(a, timezone.utc)
                            .astimezone(target)
                            .isoformat(),
                            open=float(part.open.iloc[0]),
                            high=float(part.high.max()),
                            low=float(part.low.min()),
                            close=float(part.close.iloc[-1]),
                            range=float(part.high.max() - part.low.min()),
                            return_pct=float(
                                (part.close.iloc[-1] / part.open.iloc[0] - 1) * 100
                            ),
                            bars=len(part),
                            complete=bool(
                                int(part.time.iloc[0]) == a
                                and int(part.end_time.iloc[-1]) == b
                                and (
                                    part.time.iloc[1:].to_numpy()
                                    == part.end_time.iloc[:-1].to_numpy()
                                ).all()
                            ),
                        )
                    )
    return sorted(windows, key=lambda w: w["start"])[-150:]


def session_sweeps(df, windows):
    events = []
    for w in windows:
        if not w["complete"]:
            continue
        later = df[(df.time >= w["end"]) & (df.time < w["end"] + 43200)]
        for side, level, test in [
            (1, w["low"], (later.low < w["low"]) & (later.close > w["low"])),
            (-1, w["high"], (later.high > w["high"]) & (later.close < w["high"])),
        ]:
            match = later[test]
            if len(match):
                r = match.iloc[0]
                events.append(
                    dict(
                        time=int(r.time),
                        confirmed_at=int(r.end_time),
                        kind="Session low sweep" if side == 1 else "Session high sweep",
                        session=w["name"],
                        side=side,
                        level=level,
                    )
                )
    return sorted(events, key=lambda e: e["time"])
