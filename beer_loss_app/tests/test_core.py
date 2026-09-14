from copy import deepcopy
from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import uuid
import pytest
from beer_loss.domain import *
from beer_loss.reporting import reconcile, production
from beer_loss import storage

START = datetime(2026, 1, 5, 6)
END = START + timedelta(days=1)

def row(kind, payload, at=START, site="Achimota"):
    return {"kind": kind, "payload": payload, "occurred_at": at, "site": site, "logged_by": "Test operator"}

def packaging(reference="P1", site="Achimota"):
    return row("packaging", {"reference": reference, "line": "LINE-01", "brand": "MG",
                            "volume_hl": 94.0, "plato": 10.0}, START + timedelta(hours=3), site)

def chain(additive=False):
    sugar = {"batch_id": "S1", "material": "Sugar", "unit": "kg", "kg_per_unit": 1.0, "yield": 0.99}
    rows = [row("batch", sugar, START - timedelta(days=1)),
            row("fill", {"fill_id": "F1", "tank": "FST101", "brand": "MG", "status": "Open"}, START - timedelta(hours=1)),
            row("fill", {"fill_id": "B1", "tank": "BBT101", "brand": "MG", "status": "Open"}, START - timedelta(hours=1))]
    rows += [row("stock", {"tank": tank, "volume_hl": 0.0, "plato": None}, at)
             for at in (START, END) for tank in ("FST101", "BBT101", "LINE-01")]
    rows += [row("material_stock", {"batch_id": "S1", "quantity": q}, at)
             for at, q in ((START, 3000.0), (END, 1000.0))]
    rows.append(row("brew", {"brew_id": "Brew1", "brand": "MG", "wort_hl": 100.0, "plato": 10.0,
                            "materials": [dict(sugar, quantity=2000.0)],
                            "allocations": [{"fill_id": "F1", "tank": "FST101", "volume_hl": 100.0}]}, START + timedelta(hours=1)))
    dose = None
    if additive:
        gfe = {"batch_id": "G1", "material": "GFE", "unit": "hL", "kg_per_unit": 115.0, "yield": 0.65}
        rows.append(row("batch", gfe, START - timedelta(days=1)))
        rows += [row("material_stock", {"batch_id": "G1", "quantity": q}, at)
                 for at, q in ((START, 10.0), (END, 9.0))]
        dose = dict(gfe, quantity=1.0)
    rows.append(row("transfer", {"reference": "T1", "from_fill": "F1", "from_tank": "FST101",
        "to_fill": "B1", "to_tank": "BBT101", "sent_hl": 98.0, "sent_plato": 10.0,
        "received_hl": 97.0, "received_plato": 10.0, "additive": dose}, START + timedelta(hours=2)))
    rows.append(row("transfer", {"reference": "T2", "from_fill": "B1", "from_tank": "BBT101",
        "to_fill": "", "to_tank": "LINE-01", "sent_hl": 96.0, "sent_plato": 10.0,
        "received_hl": 95.0, "received_plato": 10.0, "additive": None}, START + timedelta(hours=3)))
    rows.append(packaging())
    return rows

def test_extract_units_and_missing_measurements():
    assert extract(100, 10) == pytest.approx(100 * (0.9974 / (0.1 - 0.00382) + 0.02))
    assert extract(0, None) == 0
    assert extract(100, None) is None
    assert extract(-1, 10) is None
    assert extract(float("nan"), 10) is None

def test_shift_and_calendar_boundaries():
    assert production_date(datetime(2026, 1, 6, 5, 59)) == date(2026, 1, 5)
    assert shift_of(datetime(2026, 1, 6, 5, 59)) == "Night"
    assert boundaries(date(2026, 1, 5), "Shift", "Night") == (datetime(2026, 1, 5, 22), datetime(2026, 1, 6, 6))
    assert boundaries(date(2026, 1, 1), "WTD")[0] == datetime(2025, 12, 29, 6)
    assert boundaries(date(2026, 3, 9), "MTD")[0] == datetime(2026, 3, 1, 6)
    assert boundaries(date(2026, 3, 9), "YTD")[0] == datetime(2026, 1, 1, 6)

@pytest.mark.parametrize("additive", [False, True])
def test_stage_mass_balance_without_double_counting(additive):
    report = reconcile(chain(additive), "Achimota", START, END)
    assert all(r["Status"] != "Incomplete" for r in report)
    assert sum(r["Loss kg extract"] or 0 for r in report) == pytest.approx(1980 + (74.75 if additive else 0) - extract(94, 10))
    r = {x["Stage"]: x for x in report}
    assert r["Fermentation / storage"]["Loss kg extract"] == pytest.approx(extract(2, 10))
    assert r["Bright beer tanks"]["Loss kg extract"] == pytest.approx(extract(1, 10))
    assert r["Packaging"]["Loss kg extract"] == pytest.approx(extract(1, 10))

def test_missing_stock_blocks_final_loss_and_zero_is_valid():
    rows = [r for r in chain() if not (r["kind"] == "stock" and r["payload"]["tank"] == "BBT101" and r["occurred_at"] == END)]
    result = {r["Stage"]: r for r in reconcile(rows, "Achimota", START, END)}
    assert result["Bright beer tanks"]["Status"] == "Incomplete"
    assert result["Bright beer tanks"]["Loss %"] is None
    assert result["Packaging"]["Status"] != "Incomplete"

def test_stale_stock_is_not_reused():
    rows = chain()
    next(r for r in rows if r["kind"] == "stock" and r["payload"]["tank"] == "BBT101" and r["occurred_at"] == START)["occurred_at"] -= timedelta(minutes=1)
    assert next(r for r in reconcile(rows, "Achimota", START, END) if r["Stage"] == "Bright beer tanks")["Status"] == "Incomplete"

def test_period_cutoff_sites_and_weighted_rates():
    rows = chain()
    extra = deepcopy(next(r for r in rows if r["kind"] == "brew"))
    extra["payload"]["brew_id"] = "Brew2"
    extra["payload"]["materials"][0]["quantity"] = 1000.0
    extra["occurred_at"] = END
    rows.append(extra)
    rows.append(packaging("Other", "Kaasi"))
    assert production(rows, "Achimota", START, END)["Brews"] == 1
    assert production(rows, "Achimota", START, END)["Packaged hL"] == 94
    bh = next(r for r in reconcile(rows, "Achimota", START, END + timedelta(days=1)) if r["Stage"] == "Brewhouse")
    assert bh["Loss %"] == pytest.approx((2970 - 2 * extract(100, 10)) / 2970)

def test_material_usage_is_date_limited_and_destruction_is_not_subtracted_twice():
    rows = chain()
    close = next(r for r in rows if r["kind"] == "material_stock" and r["occurred_at"] == END)
    close["payload"]["quantity"] = 900.0
    rows.append(row("destruction", {"batch_id": "S1", "quantity": 100.0, "reference": "D1", "reason": "Test damage"}, START + timedelta(hours=5)))
    future = deepcopy(next(r for r in rows if r["kind"] == "brew"))
    future["occurred_at"] = END + timedelta(hours=1)
    rows.append(future)
    rm = reconcile(rows, "Achimota", START, END)[0]
    assert rm["Loss kg extract"] == pytest.approx(99)
    assert rm["Details"][0]["Declared destruction"] == 100

@pytest.fixture
def engine(tmp_path):
    value = storage.make_engine("sqlite:///" + str(tmp_path / "records.db"))
    yield value
    value.dispose()

def test_saved_history_survives_new_connection(engine):
    rid, created = storage.save(engine, packaging())
    second = storage.make_engine(engine.url.render_as_string(hide_password=False))
    assert created and storage.load(second)[0]["id"] == rid
    second.dispose()

def test_concurrent_retries_are_saved_once(engine):
    request = str(uuid.uuid4())
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: storage.save(engine, packaging(), request), range(4)))
    assert sum(created for _, created in results) == 1
    assert len(storage.load(engine)) == 1

def test_void_retains_original_and_allows_replacement(engine):
    rid, _ = storage.save(engine, packaging())
    storage.void(engine, rid, "Reviewer", "Incorrect quantity")
    assert storage.load(engine) == []
    original = storage.load(engine, True)[0]
    assert original["payload"]["volume_hl"] == 94
    assert original["voided_by"] == "Reviewer" and original["void_reason"] == "Incorrect quantity"
    storage.save(engine, packaging())
    assert len(storage.load(engine, True)) == 2

def test_duplicate_business_reference_and_future_time_are_rejected(engine):
    storage.save(engine, packaging())
    with pytest.raises(ValueError):
        storage.save(engine, packaging())
    future = packaging("Future")
    future["occurred_at"] = datetime.utcnow() + timedelta(hours=1)
    with pytest.raises(ValueError, match="future"):
        storage.save(engine, future)

def test_backup_restore_keeps_active_and_voided_records(engine, tmp_path):
    rid, _ = storage.save(engine, packaging())
    storage.void(engine, rid, "Reviewer", "Correction")
    storage.save(engine, packaging())
    content = storage.export_backup(engine)
    target = storage.make_engine("sqlite:///" + str(tmp_path / "restored.db"))
    assert storage.restore_empty(target, content) == 2
    assert len(storage.load(target)) == 1
    assert len(storage.load(target, True)) == 2
    assert next(r for r in storage.load(target, True) if r["id"] == rid)["voided"]
    with pytest.raises(ValueError, match="empty"):
        storage.restore_empty(target, content)
    assert len(storage.load(target, True)) == 2
    target.dispose()

def test_fill_occupancy_and_reference_protection(engine):
    first = row("fill", {"fill_id": "F1", "tank": "FST101", "brand": "MG", "status": "Open"})
    rid, _ = storage.save(engine, first)
    second = row("fill", {"fill_id": "F2", "tank": "FST101", "brand": "MG", "status": "Open"}, START + timedelta(hours=1))
    with pytest.raises(ValueError, match="Another open fill"):
        storage.save(engine, second)
    close = row("fill", dict(first["payload"], status="Closed"), START + timedelta(minutes=30))
    closed_id, _ = storage.save(engine, close)
    storage.save(engine, second)
    with pytest.raises(ValueError):
        storage.void(engine, closed_id, "Reviewer", "Test correction")
    assert not next(r for r in storage.load(engine, True) if r["id"] == closed_id)["voided"]

def test_live_storage_refuses_local_sqlite():
    with pytest.raises(ValueError, match="PostgreSQL"):
        storage.make_engine("sqlite://", live=True)
