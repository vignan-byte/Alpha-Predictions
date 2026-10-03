"""Virtual, unlevered, quote-currency paper accounts. Never imports broker order APIs."""

import json
import math
import time
import uuid
from contextlib import contextmanager
from sqlalchemy import Column, Integer, String, Text, Float, select, text
from sqlalchemy.orm import Session
from app.database.store import Base, engine
from app.core.utils import dumps


class PaperAccount(Base):
    __tablename__ = "paper_accounts"
    id = Column(String(80), primary_key=True)
    payload = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=0)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True)
    created = Column(Float, nullable=False)
    action = Column(String(80), nullable=False)
    payload = Column(Text, nullable=False)


def currency(symbol):
    return "USDT" if symbol.endswith("USDT") else symbol[-3:]


def initial(source, quote, balance=10000):
    return dict(
        source=source,
        currency=quote,
        initial_balance=balance,
        balance=balance,
        positions=[],
        orders=[],
        trades=[],
        equity_curve=[],
        peak=balance,
        max_drawdown=0.0,
        created=int(time.time()),
    )


@contextmanager
def transaction(source, quote):
    # One DB transaction owns an account book. SQLite IMMEDIATE and PostgreSQL advisory
    # locks also serialize creation of a previously absent account across processes.
    with engine.connect() as connection:
        if engine.dialect.name == "sqlite":
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        else:
            connection.begin()
            if engine.dialect.name == "postgresql":
                connection.execute(text("SELECT pg_advisory_xact_lock(740221)"))
        with Session(bind=connection, expire_on_commit=False) as s:
            try:
                key = f"{source}:{quote}"
                row = s.scalar(
                    select(PaperAccount).where(PaperAccount.id == key).with_for_update()
                )
                if row is None:
                    row = PaperAccount(
                        id=key, payload=dumps(initial(source, quote)), version=0
                    )
                    s.add(row)
                    s.flush()
                book = json.loads(row.payload)
                yield book, s
                row.payload = dumps(book)
                row.version += 1
                s.flush()
                connection.commit()
            except Exception:
                connection.rollback()
                raise


def audit(s, action, data):
    s.add(AuditEvent(created=time.time(), action=action, payload=dumps(data)))


def _finite(*values):
    if any(not math.isfinite(float(v)) for v in values):
        raise ValueError("Finite values required")


def _mark(book):
    floating = sum(
        p["side"] * (p["mark"] - p["entry"]) * p["units"] for p in book["positions"]
    )
    equity = book["balance"] + floating
    used = sum(p["margin"] for p in book["positions"])
    book["peak"] = max(book["peak"], equity)
    dd = (equity / book["peak"] - 1) * 100 if book["peak"] else 0
    book["max_drawdown"] = min(book["max_drawdown"], dd)
    stamp = int(time.time())
    point = dict(time=stamp, value=equity, drawdown=dd)
    if book["equity_curve"] and book["equity_curve"][-1]["time"] == stamp:
        book["equity_curve"][-1] = point
    else:
        book["equity_curve"].append(point)
    book["equity_curve"] = book["equity_curve"][-10000:]
    return dict(
        equity=equity,
        unrealized_pnl=floating,
        used_margin=used,
        available=max(0, book["balance"] - used),
        drawdown=dd,
    )


def snapshot(source, quote):
    with transaction(source, quote) as (book, s):
        stats = _mark(book)
        pnls = [t["net_pnl"] for t in book["trades"]]
        wins = [v for v in pnls if v > 0]
        losses = [v for v in pnls if v <= 0]
        now = time.time()
        for order in book["orders"]:
            if order["status"] == "preview" and order["expires"] < now:
                order["status"] = "expired"
        return dict(
            **book,
            **stats,
            realized_pnl=book["balance"] - book["initial_balance"],
            trade_count=len(pnls),
            wins=len(wins),
            losses=len(losses),
            win_rate=len(wins) / len(pnls) if pnls else None,
            profit_factor=sum(wins) / -sum(losses) if sum(losses) < 0 else None,
            expectancy=sum(pnls) / len(pnls) if pnls else None,
            execution="PAPER ONLY",
            order_types=["market"],
            note="No leverage. P&L/account currency equals instrument quote currency. Stops use observed quotes; offline missed touches are not reconstructed.",
        )


def configure(source, quote, balance):
    _finite(balance)
    if not 100 <= balance <= 1e9:
        raise ValueError("Starting balance must be 100–1,000,000,000")
    with transaction(source, quote) as (book, s):
        if book["positions"] or book["trades"]:
            raise ValueError(
                "Starting balance can only change before the first filled trade"
            )
        book.update(initial(source, quote, float(balance)))
        audit(
            s,
            "paper.configure",
            {"source": source, "currency": quote, "balance": balance},
        )
    return snapshot(source, quote)


def preview(
    source,
    symbol,
    price,
    quote_time,
    side,
    units,
    stop,
    target,
    fee_bps=5,
    slippage_bps=2,
    risk_pct=None,
):
    _finite(price, quote_time, stop, target, fee_bps, slippage_bps)
    if price <= 0 or time.time() - quote_time > 120:
        raise ValueError("Fresh positive market quote required")
    if side not in (1, -1):
        raise ValueError("Invalid side")
    if not 0 <= fee_bps <= 100 or not 0 <= slippage_bps <= 100:
        raise ValueError("Costs must be between 0 and 100 bps per side")
    entry = price * (1 + side * slippage_bps / 10000)
    if (
        stop <= 0
        or target <= 0
        or (entry - stop) * side <= 0
        or (target - entry) * side <= 0
    ):
        raise ValueError(
            "Stop and target must bracket the estimated entry in the chosen direction"
        )
    with transaction(source, currency(symbol)) as (book, s):
        stats = _mark(book)
        if risk_pct is not None:
            _finite(risk_pct)
            if not 0 < risk_pct <= 5:
                raise ValueError("Risk must be >0 and <=5%")
            units = (
                book["balance"]
                * risk_pct
                / 100
                / (abs(entry - stop) + entry * 2 * (fee_bps + slippage_bps) / 10000)
            )
        _finite(units)
        if units <= 0:
            raise ValueError("Quantity must be positive")
        margin = units * entry
        fee = margin * fee_bps / 10000
        if margin + fee > stats["available"]:
            raise ValueError(
                "Insufficient available virtual balance; reduce quantity or risk percentage"
            )
        order = dict(
            id=str(uuid.uuid4()),
            symbol=symbol,
            source=source,
            currency=currency(symbol),
            side=side,
            units=float(units),
            stop=float(stop),
            target=float(target),
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            estimated_entry=entry,
            estimated_fee=fee,
            estimated_risk=units * abs(entry - stop) + fee * 2,
            margin=margin,
            quote_time=quote_time,
            created=time.time(),
            expires=time.time() + 30,
            status="preview",
            max_price_drift_bps=50,
        )
        book["orders"].append(order)
        book["orders"] = book["orders"][-1000:]
        audit(
            s,
            "paper.preview",
            {"order_id": order["id"], "source": source, "symbol": symbol},
        )
        return dict(order)


def confirm(source, quote, order_id, price, quote_time):
    _finite(price, quote_time)
    with transaction(source, quote) as (book, s):
        order = next((o for o in book["orders"] if o["id"] == order_id), None)
        if not order:
            raise ValueError("Preview not found in this paper account")
        if order["status"] == "filled":
            return order  # idempotent confirmation
        if order["status"] != "preview" or time.time() > order["expires"]:
            raise ValueError("Preview expired; request a fresh preview")
        if price <= 0 or time.time() - quote_time > 120:
            raise ValueError("Fresh quote required to confirm")
        entry = price * (1 + order["side"] * order["slippage_bps"] / 10000)
        if (
            abs(entry / order["estimated_entry"] - 1) * 10000
            > order["max_price_drift_bps"]
        ):
            raise ValueError("Price moved beyond preview tolerance; preview again")
        side = order["side"]
        if (entry - order["stop"]) * side <= 0 or (order["target"] - entry) * side <= 0:
            raise ValueError("Market moved beyond stop/target; preview again")
        margin = entry * order["units"]
        fee = margin * order["fee_bps"] / 10000
        if margin + fee > _mark(book)["available"]:
            raise ValueError("Insufficient available virtual balance")
        p = dict(
            id=order_id,
            symbol=order["symbol"],
            side=side,
            units=order["units"],
            entry=entry,
            mark=price,
            mark_time=quote_time,
            stop=order["stop"],
            target=order["target"],
            fee_bps=order["fee_bps"],
            slippage_bps=order["slippage_bps"],
            entry_fee=fee,
            margin=margin,
            opened=time.time(),
            source=source,
        )
        book["balance"] -= fee
        book["positions"].append(p)
        order.update(status="filled", filled_at=time.time(), fill_price=entry)
        _mark(book)
        audit(
            s,
            "paper.fill",
            {
                "order_id": order_id,
                "source": source,
                "price": entry,
                "units": p["units"],
            },
        )
        return dict(order)


def _close(book, s, p, price, reason):
    exit_price = price * (1 - p["side"] * p["slippage_bps"] / 10000)
    fee = exit_price * p["units"] * p["fee_bps"] / 10000
    gross = p["side"] * (exit_price - p["entry"]) * p["units"]
    book["balance"] += gross - fee
    trade = dict(
        **p,
        exit=exit_price,
        closed=time.time(),
        reason=reason,
        exit_fee=fee,
        gross_pnl=gross,
        net_pnl=gross - fee - p["entry_fee"],
    )
    book["trades"].append(trade)
    book["positions"].remove(p)
    audit(
        s,
        "paper.close",
        {
            "position_id": p["id"],
            "source": book["source"],
            "reason": reason,
            "net_pnl": trade["net_pnl"],
        },
    )
    return trade


def close(source, quote, position_id, price, quote_time):
    _finite(price, quote_time)
    if price <= 0 or time.time() - quote_time > 120:
        raise ValueError("Fresh quote required to close")
    with transaction(source, quote) as (book, s):
        p = next((p for p in book["positions"] if p["id"] == position_id), None)
        if p is None:
            old = next((t for t in book["trades"] if t["id"] == position_id), None)
            if old:
                return old
            raise ValueError("Paper position not found")
        result = _close(book, s, p, price, "manual")
        _mark(book)
        return result


def mark(source, symbol, price, quote_time):
    _finite(price, quote_time)
    if price <= 0 or time.time() - quote_time > 120:
        return
    with transaction(source, currency(symbol)) as (book, s):
        for p in list(book["positions"]):
            if p["symbol"] != symbol or quote_time < p["mark_time"]:
                continue
            p["mark"] = price
            p["mark_time"] = quote_time
            stop = price <= p["stop"] if p["side"] == 1 else price >= p["stop"]
            target = price >= p["target"] if p["side"] == 1 else price <= p["target"]
            if stop or target:
                _close(book, s, p, price, "stop" if stop else "target")
        _mark(book)


def open_symbols():
    with Session(engine) as s:
        return list(
            {
                (p["source"], p["symbol"])
                for row in s.scalars(select(PaperAccount))
                for p in json.loads(row.payload)["positions"]
            }
        )


def order_lookup(source, quote, order_id):
    with transaction(source, quote) as (book, s):
        found = next((o for o in book["orders"] if o["id"] == order_id), None)
        if not found:
            raise ValueError("Paper order not found")
        return dict(found)
