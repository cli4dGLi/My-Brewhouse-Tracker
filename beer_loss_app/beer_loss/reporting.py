"""Reconciling measured extract within explicit reporting boundaries."""
from collections import defaultdict
from .domain import (TOD, BBT, LINES, TARGETS, extract, material_value, brew_values,
                     timestamp, batches, fills, key)

def outcome(stage, available, output, closing=0.0, reasons=None, details=None):
    reasons = list(dict.fromkeys(reasons or []))
    loss = available - output - closing if not reasons else None
    if reasons:
        status, rate = "Incomplete", None
    elif available == 0 and output == 0 and closing == 0:
        status, rate, loss = "No activity", None, None
    elif available <= 0:
        status, rate, loss = "Incomplete", None, None
        reasons.append("A positive measured input or opening stock is needed for a loss percentage.")
    else:
        rate = loss / available
        status = "Apparent gain" if loss < -0.01 else "Above target" if rate > TARGETS[stage] else "On target"
    return {"Stage": stage, "Available kg extract": available, "Output kg extract": output,
            "Closing kg extract": closing, "Loss kg extract": loss, "Loss %": rate,
            "Target %": TARGETS[stage], "Status": status, "Reasons": reasons, "Details": details or []}

def reconcile(rows, site, start, end):
    rows = [r for r in rows if r["site"] == site and not r.get("voided")]
    current = [r for r in rows if start <= timestamp(r["occurred_at"]) < end]
    brews = [r for r in current if r["kind"] == "brew"]
    movements = [r for r in current if r["kind"] == "transfer"]
    packs = [r for r in current if r["kind"] == "packaging"]
    result = {}
    bh_in = sum(brew_values(r["payload"])[0] for r in brews)
    bh_out = sum(brew_values(r["payload"])[1] for r in brews)
    result["Brewhouse"] = outcome("Brewhouse", bh_in, bh_out)
    received, sent = defaultdict(float), defaultdict(float)
    for r in brews:
        p = r["payload"]
        for a in p["allocations"]:
            received[a["tank"]] += extract(a["volume_hl"], p["plato"])
    transfer_in, transfer_out = 0.0, 0.0
    for r in movements:
        p = r["payload"]
        source = extract(p["sent_hl"], p["sent_plato"])
        destination = extract(p["received_hl"], p["received_plato"])
        sent[p["from_tank"]] += source
        received[p["to_tank"]] += destination
        transfer_in += source + (material_value(p["additive"]) if p.get("additive") else 0)
        transfer_out += destination
    result["Clarification / transfer"] = outcome("Clarification / transfer", transfer_in, transfer_out)
    for r in packs:
        p = r["payload"]
        sent[p["line"]] += extract(p["volume_hl"], p["plato"])
    stocks = [r for r in rows if r["kind"] == "stock"]
    exact = {(r["payload"]["tank"], timestamp(r["occurred_at"])): r["payload"] for r in stocks}
    for stage, tanks in (("Fermentation / storage", TOD), ("Bright beer tanks", BBT), ("Packaging", LINES)):
        available, out, closing, reasons, detail = 0.0, 0.0, 0.0, [], []
        for tank in tanks:
            historic = [r for r in stocks if r["payload"]["tank"] == tank and timestamp(r["occurred_at"]) <= start]
            last = max(historic, key=lambda r: timestamp(r["occurred_at"]))["payload"] if historic else None
            known_fill = any(p["tank"] == tank and p["status"] != "Closed" for p in fills(rows, site, start).values())
            opening, close = exact.get((tank, start)), exact.get((tank, end))
            active = (tank in received or tank in sent or known_fill or
                      (last is not None and last["volume_hl"] > 0) or
                      (close is not None and close["volume_hl"] > 0))
            if not active:
                continue
            if opening is None:
                reasons.append(f"{tank}: missing opening stock at {start:%d %b %Y %H:%M}.")
            if close is None:
                reasons.append(f"{tank}: missing closing stock at {end:%d %b %Y %H:%M}.")
            op = extract(opening["volume_hl"], opening.get("plato")) if opening else None
            cl = extract(close["volume_hl"], close.get("plato")) if close else None
            available += (op or 0) + received[tank]
            out += sent[tank]
            closing += cl or 0
            detail.append({"Vessel": tank, "Opening kg extract": op, "Received kg extract": received[tank],
                           "Sent kg extract": sent[tank], "Closing kg extract": cl,
                           "Loss kg extract": None if op is None or cl is None else op + received[tank] - sent[tank] - cl})
        result[stage] = outcome(stage, available, out, closing, reasons, detail)
    used = defaultdict(float)
    for r in brews:
        for m in r["payload"]["materials"]:
            used[key(m["batch_id"])] += m["quantity"]
    for r in movements:
        if r["payload"].get("additive"):
            m = r["payload"]["additive"]
            used[key(m["batch_id"])] += m["quantity"]
    receipts, destroyed = defaultdict(float), defaultdict(float)
    for r in current:
        if r["kind"] in ("receipt", "destruction"):
            bucket = receipts if r["kind"] == "receipt" else destroyed
            bucket[key(r["payload"]["batch_id"])] += r["payload"]["quantity"]
    counts = [r for r in rows if r["kind"] == "material_stock"]
    counts_exact = {(key(r["payload"]["batch_id"]), timestamp(r["occurred_at"])): r["payload"]["quantity"] for r in counts}
    available, output, closing, reasons, details = 0.0, 0.0, 0.0, [], []
    for bid, b in batches(rows, site, end).items():
        historic = [r for r in counts if key(r["payload"]["batch_id"]) == bid and timestamp(r["occurred_at"]) <= start]
        last = max(historic, key=lambda r: timestamp(r["occurred_at"]))["payload"]["quantity"] if historic else 0
        op, cl = counts_exact.get((bid, start)), counts_exact.get((bid, end))
        if not (bid in used or bid in receipts or bid in destroyed or last > 0 or (cl is not None and cl > 0)):
            continue
        if op is None:
            reasons.append(f"{b['batch_id']}: missing opening material count at {start:%d %b %Y %H:%M}.")
        if cl is None:
            reasons.append(f"{b['batch_id']}: missing closing material count at {end:%d %b %Y %H:%M}.")
        factor = b["kg_per_unit"] * b["yield"]
        available += ((op or 0) + receipts[bid]) * factor
        output += used[bid] * factor
        closing += (cl or 0) * factor
        loss = None if op is None or cl is None else (op + receipts[bid] - used[bid] - cl) * factor
        details.append({"Batch": b["batch_id"], "Material": b["material"], "Unit": b["unit"],
                        "Opening": op, "Receipts": receipts[bid], "Used": used[bid], "Closing": cl,
                        "Declared destruction": destroyed[bid], "Loss kg extract": loss})
    result["Warehouse"] = outcome("Warehouse", available, output, closing, reasons, details)
    return [result[stage] for stage in TARGETS]

def production(rows, site, start, end):
    selected = [r for r in rows if not r.get("voided") and r["site"] == site and start <= timestamp(r["occurred_at"]) < end]
    brews = [r for r in selected if r["kind"] == "brew"]
    return {"Brews": len(brews),
            "Wort hL": sum(r["payload"]["wort_hl"] for r in brews),
            "Packaged hL": sum(r["payload"]["volume_hl"] for r in selected if r["kind"] == "packaging"),
            "Completed transfers": sum(r["kind"] == "transfer" for r in selected)}
