"""Validating events and preserving measurement assumptions."""
from datetime import date, datetime, time, timedelta
import math

SITES = ("Achimota", "Kaasi")
BRANDS = ("MG", "FES", "Gulder", "Star", "ABC", "Mother", "Castel")
TOD = tuple(f"FST{x}" for x in range(101, 113)) + tuple(f"MLT{x}" for x in range(301, 305))
BBT = tuple(f"BBT{x}" for x in range(101, 106)) + tuple(f"BBT{x}" for x in range(201, 204))
LINES = ("LINE-01", "LINE-02")
TANKS = TOD + BBT + LINES
SHIFTS = ("Morning", "Afternoon", "Night")
KINDS = ("brew", "transfer", "stock", "packaging", "fill", "batch", "receipt", "material_stock", "destruction")
MATERIALS = {
    "Sorghum": ("kg", 1.0, 0.72), "Pale malt": ("kg", 1.0, 0.78),
    "Sugar": ("kg", 1.0, 0.99), "Maize": ("kg", 1.0, 0.80),
    "MGFC": ("hL", 112.5, 0.65), "GFE": ("hL", 115.0, 0.65),
}
TARGETS = {"Warehouse": 0.015, "Brewhouse": 0.025, "Fermentation / storage": 0.03,
           "Clarification / transfer": 0.03, "Bright beer tanks": 0.03, "Packaging": 0.02}
PERIODS = ("Shift", "Day", "WTD", "MTD", "YTD")

def timestamp(value):
    result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if result.tzinfo is not None:
        raise ValueError("Entering event times in Ghana local time without a timezone suffix.")
    return result

def production_date(value):
    return (timestamp(value) - timedelta(hours=6)).date()

def shift_of(value):
    hour = timestamp(value).hour
    return "Morning" if 6 <= hour < 14 else "Afternoon" if 14 <= hour < 22 else "Night"

def boundaries(day, period, shift="Morning"):
    if isinstance(day, str):
        day = date.fromisoformat(day)
    base = datetime.combine(day, time(6))
    if period == "Shift":
        start = base + timedelta(hours=8 * SHIFTS.index(shift))
        return start, start + timedelta(hours=8)
    end = base + timedelta(days=1)
    if period == "Day":
        return base, end
    if period == "WTD":
        return base - timedelta(days=day.weekday()), end
    if period == "MTD":
        return base.replace(day=1), end
    if period == "YTD":
        return base.replace(month=1, day=1), end
    raise ValueError("Unknown reporting period.")

def number(value, label, minimum=0, maximum=None):
    if value is None or isinstance(value, bool):
        raise ValueError(f"{label} is required.")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number.") from None
    if not math.isfinite(result) or result < minimum or (maximum is not None and result > maximum):
        raise ValueError(f"{label} is outside its allowed range.")
    return result

def extract(volume, plato):
    try:
        volume = number(volume, "Volume")
        if volume == 0:
            return 0.0
        plato = number(plato, "Gravity", 0.01, 50)
        return volume * (0.9974 / (1 / plato - 0.00382) + 0.02)
    except ValueError:
        return None

def required(value, label):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 120:
        raise ValueError(f"{label} must contain between 1 and 120 characters.")
    return value.strip()

def key(value):
    return str(value).strip().casefold()

def batches(rows, site, at=None):
    return {key(r["payload"]["batch_id"]): r["payload"] for r in rows
            if not r.get("voided") and r["site"] == site and r["kind"] == "batch"
            and (at is None or timestamp(r["occurred_at"]) <= at)}

def fills(rows, site, at=None):
    result = {}
    candidates = sorted(rows, key=lambda r: (timestamp(r["occurred_at"]), str(r.get("created_at", "")), str(r.get("id", ""))))
    for r in candidates:
        if not r.get("voided") and r["site"] == site and r["kind"] == "fill" and (at is None or timestamp(r["occurred_at"]) <= at):
            result[key(r["payload"]["fill_id"])] = r["payload"]
    return result

def material_value(item):
    return number(item["quantity"], "Quantity") * number(item["kg_per_unit"], "Density", 0.0001) * number(item["yield"], "Extract yield", 0, 1)

def brew_values(payload):
    available = sum(material_value(item) for item in payload["materials"])
    out = extract(payload["wort_hl"], payload["plato"])
    return available, out, available - out

def natural_key(row):
    p, kind = row["payload"], row["kind"]
    if kind == "stock":
        identity = p["tank"] + "|" + timestamp(row["occurred_at"]).isoformat()
    elif kind == "material_stock":
        identity = key(p["batch_id"]) + "|" + timestamp(row["occurred_at"]).isoformat()
    elif kind == "fill":
        identity = key(p["fill_id"]) + "|" + timestamp(row["occurred_at"]).isoformat()
    else:
        identity = key(p.get("brew_id") or p.get("batch_id") if kind in ("brew", "batch") else p["reference"])
    return row["site"] + "|" + kind + "|" + identity

def validate(row, rows, check_clock=True):
    kind, site, p = row["kind"], row["site"], row["payload"]
    when = timestamp(row["occurred_at"])
    if kind not in KINDS or site not in SITES or not isinstance(p, dict):
        raise ValueError("Unknown event type or brewery.")
    required(row["logged_by"], "Entered by")
    if check_clock and when > datetime.utcnow() + timedelta(minutes=5):
        raise ValueError("The event time is in the future.")
    bs, fs = batches(rows, site, when), fills(rows, site, when)
    def batch(batch_id):
        value = bs.get(key(required(batch_id, "Batch ID")))
        if not value:
            raise ValueError(f"Registering material batch {batch_id} before recording its use is required.")
        return value
    def fill(fill_id, tank):
        value = fs.get(key(required(fill_id, "Fill ID")))
        if not value or value["tank"] != tank or value["status"] == "Closed":
            raise ValueError(f"{fill_id} is not an open fill in {tank} at this event time.")
        return value
    if kind == "batch":
        required(p["batch_id"], "Batch ID")
        if p["material"] not in MATERIALS:
            raise ValueError("Unknown material.")
        if p["unit"] != MATERIALS[p["material"]][0]:
            raise ValueError("Using kg for grist and sugar, and hL for concentrates is required.")
        number(p["kg_per_unit"], "Density", 0.0001)
        number(p["yield"], "Extract yield", 0.0001, 1)
        if key(p["batch_id"]) in bs:
            raise ValueError("This material batch already exists.")
    elif kind == "fill":
        required(p["fill_id"], "Fill ID")
        if p["tank"] not in TOD + BBT or p["brand"] not in BRANDS or p["status"] not in ("Open", "Hold", "Closed"):
            raise ValueError("Invalid tank, brand or fill status.")
        all_fills = fills(rows, site)
        old = all_fills.get(key(p["fill_id"]))
        if old and (old["tank"] != p["tank"] or old["brand"] != p["brand"] or old["status"] == "Closed"):
            raise ValueError("A fill keeps its tank and brand. A closed fill needs a new ID for the next campaign.")
        previous = [timestamp(r["occurred_at"]) for r in rows if r["site"] == site and r["kind"] == "fill" and key(r["payload"]["fill_id"]) == key(p["fill_id"])]
        if previous and when <= max(previous):
            raise ValueError("A status update must occur after the previous fill status.")
        if not old and p["status"] == "Closed":
            raise ValueError("Registering a fill before closing it is required.")
        for fid, value in all_fills.items():
            if fid != key(p["fill_id"]) and value["tank"] == p["tank"] and value["status"] != "Closed" and p["status"] != "Closed":
                raise ValueError("Another open fill is already using this tank.")
    elif kind == "brew":
        required(p["brew_id"], "Brew ID")
        if p["brand"] not in BRANDS or extract(p["wort_hl"], p["plato"]) is None or number(p["wort_hl"], "Wort volume") <= 0:
            raise ValueError("A brew needs a brand, positive wort volume and measured gravity.")
        if not p["materials"] or not p["allocations"]:
            raise ValueError("Material quantities and destination fills are required.")
        total = 0
        seen = set()
        for m in p["materials"]:
            b = batch(m["batch_id"])
            if key(m["batch_id"]) in seen:
                raise ValueError("Each material batch must appear once per brew.")
            seen.add(key(m["batch_id"]))
            for field in ("material", "unit", "kg_per_unit", "yield"):
                if m[field] != b[field]:
                    raise ValueError("Material factors must match the registered batch.")
            total += material_value(m)
        if total <= 0:
            raise ValueError("The brew needs a positive raw-material input.")
        allocated = 0
        for a in p["allocations"]:
            f = fill(a["fill_id"], a["tank"])
            if a["tank"] not in TOD or f["brand"] != p["brand"]:
                raise ValueError("The destination must be a fermentation/storage fill of the same brand.")
            allocated += number(a["volume_hl"], "Allocated volume", 0.01)
        if not math.isclose(allocated, p["wort_hl"], abs_tol=0.01):
            raise ValueError("Allocated volumes must equal the brew's wort volume.")
    elif kind == "transfer":
        required(p["reference"], "Movement reference")
        if p["from_tank"] not in TOD + BBT or p["to_tank"] not in TANKS or p["from_tank"] == p["to_tank"]:
            raise ValueError("Selecting different source and destination vessels is required.")
        fill(p["from_fill"], p["from_tank"])
        if p["to_tank"] not in LINES:
            fill(p["to_fill"], p["to_tank"])
        for prefix in ("sent", "received"):
            if extract(p[prefix + "_hl"], p[prefix + "_plato"]) is None or number(p[prefix + "_hl"], "Volume") <= 0:
                raise ValueError("Both sent and received volumes and gravities must be measured.")
        if p.get("additive"):
            m = p["additive"]
            b = batch(m["batch_id"])
            if b["material"] != "GFE":
                raise ValueError("The transfer additive must be a registered GFE batch.")
            for field in ("material", "unit", "kg_per_unit", "yield"):
                if m[field] != b[field]:
                    raise ValueError("Additive factors must match the registered batch.")
            material_value(m)
    elif kind == "stock":
        if p["tank"] not in TANKS or extract(p["volume_hl"], p.get("plato")) is None:
            raise ValueError("A stock count needs a registered vessel, volume and gravity. Zero stock may omit gravity.")
    elif kind == "packaging":
        required(p["reference"], "Packaging reference")
        if p["line"] not in LINES or p["brand"] not in BRANDS or extract(p["volume_hl"], p["plato"]) is None or number(p["volume_hl"], "Packaged volume") <= 0:
            raise ValueError("Entering actual packaged volume and gravity is required.")
    else:
        batch(p["batch_id"])
        number(p["quantity"], "Quantity")
        if kind != "material_stock":
            required(p["reference"], "Reference")
            if p["quantity"] <= 0:
                raise ValueError("A receipt or destruction must have a positive quantity.")
        if kind == "destruction":
            required(p["reason"], "Destruction reason")
