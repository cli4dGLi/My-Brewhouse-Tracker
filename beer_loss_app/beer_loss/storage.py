"""Saving records transactionally and retaining voided entries."""
from datetime import datetime, date, UTC
import hashlib
import json
import uuid
from sqlalchemy import (create_engine, MetaData, Table, Column, String, Text, Float,
                        DateTime, Date, Boolean, JSON, Index, select, update, func, text)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from .domain import validate, natural_key, production_date, shift_of, timestamp, key

metadata = MetaData()
records = Table("beer_loss_records", metadata,
    Column("id", String(36), primary_key=True),
    Column("request_key", String(36), nullable=False, unique=True),
    Column("natural_key", String(260), unique=True),
    Column("resource_key", String(120), unique=True),
    Column("kind", String(24), nullable=False),
    Column("site", String(32), nullable=False),
    Column("occurred_at", DateTime, nullable=False),
    Column("production_date", Date, nullable=False),
    Column("shift", String(16), nullable=False),
    Column("logged_by", String(120), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("voided", Boolean, nullable=False, default=False),
    Column("void_reason", Text),
    Column("voided_by", String(120)),
    Column("voided_at", DateTime),
)
Index("ix_beer_loss_site_time", records.c.site, records.c.occurred_at)

def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)

def make_engine(url, live=False):
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    parsed = make_url(url)
    if live and (parsed.get_backend_name() != "postgresql" or parsed.query.get("sslmode") not in ("require", "verify-ca", "verify-full")):
        raise ValueError("Live mode requires a PostgreSQL URL with sslmode=require or certificate verification.")
    options = {"pool_pre_ping": True}
    if parsed.get_backend_name() == "sqlite":
        options["connect_args"] = {"timeout": 30, "check_same_thread": False}
    else:
        options["connect_args"] = {"connect_timeout": 10}
    engine = create_engine(url, **options)
    metadata.create_all(engine)
    return engine

def _lock(conn):
    if conn.dialect.name == "postgresql":
        # Serialising short write transactions across app instances.
        conn.execute(text("SELECT pg_advisory_xact_lock(724133009416)"))
    elif conn.dialect.name == "sqlite":
        conn.exec_driver_sql("BEGIN IMMEDIATE")

def _load(conn, include_voided=False):
    stmt = select(records).order_by(records.c.occurred_at, records.c.created_at, records.c.id)
    if not include_voided:
        stmt = stmt.where(records.c.voided.is_(False))
    return [dict(row) for row in conn.execute(stmt).mappings()]

def load(engine, include_voided=False):
    with engine.connect() as conn:
        return _load(conn, include_voided)

def _resource_keys(conn):
    rows = [r for r in _load(conn) if r["kind"] == "fill"]
    latest = {}
    for r in rows:
        latest[(r["site"], key(r["payload"]["fill_id"]))] = r
    conn.execute(update(records).where(records.c.kind == "fill").values(resource_key=None))
    occupied = set()
    for r in latest.values():
        if r["payload"]["status"] != "Closed":
            resource = r["site"] + "|" + r["payload"]["tank"]
            if resource in occupied:
                raise ValueError("This correction would create two open fills in the same tank.")
            occupied.add(resource)
            conn.execute(update(records).where(records.c.id == r["id"]).values(resource_key=resource))

def _check_references(rows):
    previous = []
    for r in sorted(rows, key=lambda r: (timestamp(r["occurred_at"]), r["created_at"], r["id"])):
        validate(r, previous, check_clock=False)
        previous.append(r)

def save(engine, row, request_key=None):
    request_key = request_key or str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            _lock(conn)
            old = conn.execute(select(records.c.id).where(records.c.request_key == request_key)).scalar_one_or_none()
            if old:
                return old, False
            current = _load(conn)
            validate(row, current)
            when = timestamp(row["occurred_at"])
            values = {
                "id": str(uuid.uuid4()), "request_key": request_key, "natural_key": natural_key(row),
                "resource_key": None, "kind": row["kind"], "site": row["site"], "occurred_at": when,
                "production_date": production_date(when), "shift": shift_of(when),
                "logged_by": row["logged_by"].strip(), "payload": row["payload"],
                "created_at": utcnow(), "voided": False,
            }
            conn.execute(records.insert().values(**values))
            if row["kind"] == "fill":
                _resource_keys(conn)
            return values["id"], True
    except IntegrityError:
        raise ValueError("A record with this reference or stock boundary already exists. Check Records before submitting again.") from None

def void(engine, record_id, reviewer, reason):
    if not reviewer.strip() or not reason.strip():
        raise ValueError("A reviewer and reason are required.")
    with engine.begin() as conn:
        _lock(conn)
        current = _load(conn)
        target = next((r for r in current if r["id"] == record_id), None)
        if not target:
            raise ValueError("The record is missing or already voided.")
        remaining = [r for r in current if r["id"] != record_id]
        if target["kind"] in ("fill", "batch"):
            _check_references(remaining)
        conn.execute(update(records).where(records.c.id == record_id).values(
            voided=True, void_reason=reason.strip(), voided_by=reviewer.strip(),
            voided_at=utcnow(), natural_key=None, resource_key=None))
        if target["kind"] == "fill":
            _resource_keys(conn)

def export_backup(engine):
    result = {"format": "beer-loss-backup", "version": 1, "exported_at_utc": utcnow().isoformat(),
              "records": load(engine, include_voided=True)}
    return json.dumps(result, default=lambda x: x.isoformat() if isinstance(x, (datetime, date)) else str(x), indent=2)

def read_backup(content):
    obj = json.loads(content)
    if obj.get("format") != "beer-loss-backup" or obj.get("version") != 1 or not isinstance(obj.get("records"), list):
        raise ValueError("This is not a supported Beer Loss backup.")
    parsed = []
    for raw in obj["records"]:
        row = {c.name: raw.get(c.name) for c in records.columns}
        uuid.UUID(row["id"])
        uuid.UUID(row["request_key"])
        row["occurred_at"] = timestamp(row["occurred_at"])
        row["created_at"] = timestamp(row["created_at"])
        row["production_date"] = date.fromisoformat(row["production_date"])
        if row["production_date"] != production_date(row["occurred_at"]) or row["shift"] != shift_of(row["occurred_at"]):
            raise ValueError("The backup contains inconsistent production dates or shifts.")
        if not isinstance(row["voided"], bool):
            raise ValueError("Invalid void status.")
        if row["voided_at"]:
            row["voided_at"] = timestamp(row["voided_at"])
        if row["voided"] and not (row["void_reason"] and row["voided_by"] and row["voided_at"]):
            raise ValueError("A voided entry is missing its audit details.")
        row["natural_key"] = None if row["voided"] else natural_key(row)
        row["resource_key"] = None
        parsed.append(row)
    _check_references([r for r in parsed if not r["voided"]])
    return parsed

def restore_empty(engine, content):
    parsed = read_backup(content)
    with engine.begin() as conn:
        _lock(conn)
        if conn.execute(select(func.count()).select_from(records)).scalar_one():
            raise ValueError("Restoring is allowed only into an empty database. Existing history is never overwritten.")
        if parsed:
            conn.execute(records.insert(), parsed)
        _resource_keys(conn)
    return len(parsed)
