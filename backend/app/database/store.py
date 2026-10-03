import json
import time
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Text,
    Float,
    select,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import IntegrityError
from app.core.config import ROOT, settings
from app.core.utils import dumps

Base = declarative_base()
url = settings.database_url or "sqlite:///" + str(ROOT / "data" / "alpha.db")
engine = create_engine(
    url,
    connect_args=(
        {"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}
    ),
)
Session = sessionmaker(engine, expire_on_commit=False)


class Record(Base):
    __tablename__ = "records"
    id = Column(Integer, primary_key=True)
    kind = Column(String(40), index=True, nullable=False)
    key = Column(String(240), nullable=False)
    payload = Column(Text, nullable=False)
    updated = Column(Float, default=time.time)
    __table_args__ = (UniqueConstraint("kind", "key"),)


class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True)
    key = Column(String(240), unique=True, nullable=False)
    symbol = Column(String(30), index=True)
    source = Column(String(30), index=True)
    created = Column(Integer, index=True)
    due = Column(Integer, index=True)
    payload = Column(Text, nullable=False)
    result = Column(Text, nullable=True)


def init_db():
    # Versioned migration runner, independent of working directory.
    from alembic.config import Config
    from alembic import command

    cfg = Config(str(ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "backend" / "migrations"))
    command.upgrade(cfg, "head")


def put(kind, key, payload):
    try:
        with Session.begin() as s:
            item = s.scalar(
                select(Record).where(Record.kind == kind, Record.key == key)
            )
            if item:
                item.payload = dumps(payload)
                item.updated = time.time()
            else:
                s.add(Record(kind=kind, key=key, payload=dumps(payload)))
    except IntegrityError:
        # Concurrent first writers can race on the unique document identity.
        with Session.begin() as s:
            item = s.scalar(
                select(Record).where(Record.kind == kind, Record.key == key)
            )
            if item is None:
                raise
            item.payload = dumps(payload)
            item.updated = time.time()
    return payload


def get(kind, key, default=None):
    with Session() as s:
        r = s.scalar(select(Record).where(Record.kind == kind, Record.key == key))
        return json.loads(r.payload) if r else default


def records(kind):
    with Session() as s:
        return [
            dict(key=r.key, **json.loads(r.payload))
            for r in s.scalars(
                select(Record)
                .where(Record.kind == kind)
                .order_by(Record.updated.desc())
            )
        ]


def delete(kind, key):
    with Session.begin() as s:
        r = s.scalar(select(Record).where(Record.kind == kind, Record.key == key))
        if r:
            s.delete(r)


def save_prediction(p):
    key = f"{p['source']}:{p['symbol']}:{p['horizon']}:{p['asof']}:{p['model_version']}"
    try:
        with Session.begin() as s:
            existing = s.scalar(select(Prediction).where(Prediction.key == key))
            if existing:
                return json.loads(existing.payload)
            s.add(
                Prediction(
                    key=key,
                    symbol=p["symbol"],
                    source=p["source"],
                    created=p["asof"],
                    due=p["due"],
                    payload=dumps(p),
                )
            )
        return json.loads(dumps(p))
    except IntegrityError:
        # Chart, panel and background collector share an immutable forecast identity.
        with Session() as s:
            existing = s.scalar(select(Prediction).where(Prediction.key == key))
            if existing is None:
                raise
            return json.loads(existing.payload)


def history(symbol=None, source=None, limit=500):
    with Session() as s:
        query = select(Prediction).order_by(Prediction.created.desc()).limit(limit)
        if symbol:
            query = query.where(Prediction.symbol == symbol)
        if source:
            query = query.where(Prediction.source == source)
        return [
            dict(
                id=r.id,
                **json.loads(r.payload),
                result=json.loads(r.result) if r.result else None,
            )
            for r in s.scalars(query)
        ]
