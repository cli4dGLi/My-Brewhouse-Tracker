"""Serving password-protected activity logs and measured beer-loss summaries."""
from datetime import datetime, timedelta, UTC
from pathlib import Path
import json
import tempfile
import uuid
import pandas as pd
import plotly.express as px
import streamlit as st
from beer_loss.domain import (SITES, BRANDS, TOD, BBT, LINES, TANKS, SHIFTS, KINDS,
                             MATERIALS, TARGETS, PERIODS, boundaries, production_date,
                             shift_of, batches, fills, timestamp, key)
from beer_loss import storage
from beer_loss.reporting import reconcile, production
from beer_loss.auth import require_login, password_matches, setting

st.set_page_config(page_title="Beer Loss | Operations", page_icon="🍺", layout="wide")
st.markdown("""
<style>
.block-container {max-width:1450px;padding-top:2rem}
div[data-testid="stMetric"] {background:#eef4ee;border:1px solid #d7e6d9;border-radius:12px;padding:16px}
h1,h2,h3 {letter-spacing:-.025em}
[data-testid="stSidebar"] {border-right:1px solid #d7e6d9}
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def shared_engine(url, live):
    return storage.make_engine(url, live=live)

def get_engine():
    mode = setting("APP_MODE", "live").strip().lower()
    if mode == "demo":
        if "demo_url" not in st.session_state:
            folder = tempfile.mkdtemp(prefix="beer-loss-demo-")
            st.session_state.demo_url = "sqlite:///" + str(Path(folder) / "demo.db")
        st.warning("Demonstration mode: these entries are temporary. Use the live database for production logs.")
        return shared_engine(st.session_state.demo_url, False), mode
    if mode != "live":
        st.error("APP_MODE must be live or demo.")
        st.stop()
    url = setting("DATABASE_URL")
    pin = setting("ADMIN_PIN")
    if not url or len(pin) < 12 or pin.startswith("REPLACE"):
        st.error("Awaiting live setup. Configure the PostgreSQL connection and a private administrator PIN in Streamlit settings.")
        st.stop()
    try:
        engine = shared_engine(url, True)
        return engine, mode
    except Exception:
        st.error("The live database is unavailable. No entries have been saved locally. Please contact the administrator.")
        st.stop()

def pin_access(name, label, demo=False):
    expected = setting(name)
    if demo or (name == "LOG_PIN" and not expected):
        return True
    provided = st.text_input(label, type="password", key="access_" + name)
    return bool(expected) and password_matches(provided, expected)

def csv_bytes(frame):
    safe = frame.copy()
    for col in safe.columns:
        safe[col] = safe[col].map(lambda v: "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v)
    return safe.to_csv(index=False).encode("utf-8-sig")

def rate(value):
    return "—" if value is None else f"{value:.2%}"

def save_entry(kind, payload, when, entered_by):
    payload["notes"] = st.session_state.get("entry_notes", "")
    token_key = "request_" + kind
    token = st.session_state.setdefault(token_key, str(uuid.uuid4()))
    try:
        record_id, created = storage.save(engine, {
            "kind": kind, "site": site, "occurred_at": when,
            "logged_by": entered_by, "payload": payload}, token)
        st.session_state[token_key] = str(uuid.uuid4())
        st.session_state.flash = f"Record saved: {record_id}" if created else f"This submission was already saved: {record_id}"
        st.rerun()
    except (ValueError, KeyError, TypeError) as exc:
        st.error(str(exc))
    except Exception:
        st.error("The database could not confirm this save. Keep the form open and retry; the same request will not be stored twice.")

require_login()
engine, mode = get_engine()
st.sidebar.markdown("## 🍺 Beer Loss")
st.sidebar.caption("Brewing operations")
site = st.sidebar.selectbox("Brewery", SITES)
page = st.sidebar.radio("Page", ("Dashboard", "Log activity", "Tank board", "Records", "Data checks", "Administration", "Guide"))
if st.sidebar.button("Refresh records", width="stretch"):
    st.rerun()
st.sidebar.caption("Ghana time · production day starts 06:00")
st.sidebar.caption("Saved live records have no automatic expiry.")
try:
    rows = storage.load(engine)
except Exception:
    st.error("The shared database cannot be reached. Refresh when the connection returns.")
    st.stop()
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

def filters():
    a, b, c = st.columns((2, 2, 2))
    now = datetime.now(UTC).replace(tzinfo=None)
    day = a.date_input("Production day", value=production_date(now), max_value=production_date(now))
    period = b.selectbox("Reporting period", PERIODS, index=2)
    shift = c.selectbox("Shift", SHIFTS, index=SHIFTS.index(shift_of(now)))
    start, end = boundaries(day, period, shift)
    st.caption(f"{site} · {period} · {start:%d %b %Y %H:%M} to {end:%d %b %Y %H:%M} (Ghana time)")
    if end > now:
        st.info("This period is still open. Final stock-dependent loss figures need the closing readings.")
    return day, period, shift, start, end

def show_details(report):
    for item in report:
        with st.expander(item["Stage"] + " · " + item["Status"]):
            for reason in item["Reasons"]:
                st.write("• " + reason)
            st.write({k: v for k, v in item.items() if k not in ("Details", "Reasons", "Stage")})
            if item["Details"]:
                st.dataframe(pd.DataFrame(item["Details"]), hide_index=True, width="stretch")

if page in ("Dashboard", "Data checks"):
    st.title("Operations dashboard" if page == "Dashboard" else "Data checks")
    day, period, shift, start, end = filters()
    report = reconcile(rows, site, start, end)
    if page == "Data checks":
        incomplete = [item for item in report if item["Status"] == "Incomplete"]
        if incomplete:
            st.warning(f"{len(incomplete)} stages need additional readings.")
        else:
            st.success("No missing inputs were identified for this reporting period.")
        show_details(report)
    else:
        stats = production(rows, site, start, end)
        bh = next(item for item in report if item["Stage"] == "Brewhouse")
        a, b, c, d = st.columns(4)
        a.metric("Brews", stats["Brews"])
        b.metric("Wort to tanks", f'{stats["Wort hL"]:,.1f} hL')
        c.metric("Finished packaged", f'{stats["Packaged hL"]:,.1f} hL')
        d.metric("Brewhouse loss", rate(bh["Loss %"]))
        st.subheader("Loss by reporting period")
        matrix = [{"Stage": stage} for stage in TARGETS]
        for p in PERIODS:
            lo, hi = boundaries(day, p, shift)
            for target, value in zip(matrix, reconcile(rows, site, lo, hi)):
                target[p] = rate(value["Loss %"]) if value["Loss %"] is not None else value["Status"]
        for target, value in zip(matrix, report):
            target["Selected loss kg extract"] = value["Loss kg extract"]
            target["Target"] = rate(value["Target %"])
            target["Selected status"] = value["Status"]
        frame = pd.DataFrame(matrix)
        st.dataframe(frame, hide_index=True, width="stretch")
        st.download_button("Download period summary", csv_bytes(frame), f"beer_loss_{site}_{day}_{period}.csv", "text/csv")
        left, right = st.columns((3, 2))
        trend = []
        for offset in range(27, -1, -1):
            dday = day - timedelta(days=offset)
            lo, hi = boundaries(dday, "Day")
            trend.append({"Date": dday, **production(rows, site, lo, hi)})
        with left:
            st.subheader("Production · last 28 days")
            fig = px.bar(pd.DataFrame(trend), x="Date", y=["Wort hL", "Packaged hL"],
                         barmode="group", color_discrete_sequence=["#16714B", "#D8A83E"])
            fig.update_layout(legend_title_text="", yaxis_title="Volume (hL)", margin=dict(l=0, r=0, t=10, b=0))
            st.plotly_chart(fig, width="stretch")
        with right:
            st.subheader("Measured stage losses")
            valid = [r for r in report if r["Loss kg extract"] is not None]
            if valid:
                fig = px.bar(pd.DataFrame(valid), y="Stage", x="Loss kg extract", orientation="h",
                             color_discrete_sequence=["#16714B"])
                fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("Charts will appear when the required measurements are complete.")
        st.subheader("Shift handover")
        handover = []
        for s in SHIFTS:
            lo, hi = boundaries(day, "Shift", s)
            r = reconcile(rows, site, lo, hi)
            handover.append({"Shift": s, **production(rows, site, lo, hi),
                             "Brewhouse loss": rate(next(x for x in r if x["Stage"] == "Brewhouse")["Loss %"])})
        st.dataframe(pd.DataFrame(handover), hide_index=True, width="stretch")
        st.subheader("Reconciliation details")
        show_details(report)

elif page == "Log activity":
    st.title("Log activity")
    if not pin_access("LOG_PIN", "Logging PIN", mode == "demo"):
        st.info("Enter the logging PIN to submit records.")
        st.stop()
    labels = {"Brew": "brew", "Completed transfer": "transfer", "Tank / line stock": "stock",
              "Packaged output": "packaging", "Tank fill / status": "fill", "Material batch": "batch",
              "Material receipt": "receipt", "Material stock count": "material_stock", "Material destruction": "destruction"}
    kind = labels[st.selectbox("Activity", tuple(labels))]
    now = datetime.now(UTC).replace(tzinfo=None, second=0, microsecond=0)
    a, b, c = st.columns(3)
    day = a.date_input("Event date", value=now.date(), max_value=now.date())
    clock = b.time_input("Event time", value=now.time(), step=60)
    entered_by = c.text_input("Entered by", max_chars=120)
    when = datetime.combine(day, clock)
    if kind in ("stock", "material_stock"):
        boundary = st.selectbox("Reading time", ("Entered event time", "Start of shift", "End of shift", "Start of production day", "End of production day"))
        if boundary != "Entered event time":
            stock_day = st.date_input("Stock production day", value=production_date(when))
            stock_shift = st.selectbox("Stock shift", SHIFTS)
            lo, hi = boundaries(stock_day, "Shift" if "shift" in boundary else "Day", stock_shift)
            when = lo if boundary.startswith("Start") else hi
    st.caption(f"Production day: {production_date(when)} · {shift_of(when)} shift · reading time {when:%d %b %Y %H:%M}")
    bs, fs = batches(rows, site, when), fills(rows, site, when)
    live_fills = {fid: p for fid, p in fs.items() if p["status"] != "Closed"}
    st.text_area("Notes", key="entry_notes", max_chars=2000)
    if kind == "batch":
        material = st.selectbox("Material", tuple(MATERIALS))
        unit, density, factor = MATERIALS[material]
        st.caption("Confirm batch factors against the material certificate before saving.")
        with st.form("batch_form"):
            bid = st.text_input("Batch ID", max_chars=120)
            den = st.number_input("kg per " + unit, min_value=0.0001, value=density, format="%.4f")
            ext = st.number_input("Extract yield (%)", min_value=0.01, max_value=100.0, value=factor * 100, format="%.2f")
            if st.form_submit_button("Save record"):
                save_entry(kind, {"batch_id": bid, "material": material, "unit": unit, "kg_per_unit": den, "yield": ext / 100}, when, entered_by)
    elif kind == "fill":
        with st.form("fill_form"):
            fid = st.text_input("Fill ID", max_chars=120)
            tank = st.selectbox("Tank", TOD + BBT)
            brand = st.selectbox("Brand", BRANDS)
            status = st.selectbox("Fill status", ("Open", "Hold", "Closed"))
            st.caption("Closing a fill does not replace a measured empty stock reading.")
            if st.form_submit_button("Save record"):
                save_entry(kind, {"fill_id": fid, "tank": tank, "brand": brand, "status": status}, when, entered_by)
    elif kind == "brew":
        available = {fid: p for fid, p in live_fills.items() if p["tank"] in TOD}
        if not bs or not available:
            st.info("First register the material batches and destination tank fill.")
            st.stop()
        with st.form("brew_form"):
            brew_id = st.text_input("Brew ID", max_chars=120)
            brand = st.selectbox("Brand", BRANDS)
            wort = st.number_input("Wort volume (hL)", min_value=0.0, step=0.1)
            plato = st.number_input("Wort gravity (°P)", min_value=0.01, max_value=50.0, value=18.0)
            st.markdown("**Material quantities by batch**")
            raw = pd.DataFrame([{"Batch": b["batch_id"], "Material": b["material"], "Unit": b["unit"], "Quantity": 0.0} for b in bs.values()])
            edited = st.data_editor(raw, disabled=["Batch", "Material", "Unit"], hide_index=True, width="stretch",
                                    column_config={"Quantity": st.column_config.NumberColumn(min_value=0.0, step=0.1)})
            one = st.selectbox("Destination fill", tuple(available), format_func=lambda k: available[k]["fill_id"] + " · " + available[k]["tank"])
            two = st.selectbox("Second fill (optional)", ("None",) + tuple(available), format_func=lambda k: k if k == "None" else available[k]["fill_id"] + " · " + available[k]["tank"])
            second = st.number_input("Volume to second fill (hL)", min_value=0.0, step=0.1)
            if st.form_submit_button("Save record"):
                materials = []
                for item in edited.to_dict("records"):
                    if item["Quantity"] > 0:
                        m = dict(bs[key(item["Batch"])])
                        m["quantity"] = item["Quantity"]
                        materials.append(m)
                allocations = [{"fill_id": available[one]["fill_id"], "tank": available[one]["tank"], "volume_hl": wort - (second if two != "None" else 0)}]
                if two != "None":
                    allocations.append({"fill_id": available[two]["fill_id"], "tank": available[two]["tank"], "volume_hl": second})
                save_entry(kind, dict(brew_id=brew_id, brand=brand, wort_hl=wort, plato=plato, materials=materials, allocations=allocations), when, entered_by)
    elif kind == "transfer":
        if not live_fills:
            st.info("Register the source and destination fills before logging a transfer.")
            st.stop()
        targets = list(live_fills) + list(LINES)
        gfe = {bid: b for bid, b in bs.items() if b["material"] == "GFE"}
        with st.form("transfer_form"):
            ref = st.text_input("Movement reference", max_chars=120)
            source = st.selectbox("From fill", tuple(live_fills), format_func=lambda k: live_fills[k]["fill_id"] + " · " + live_fills[k]["tank"])
            dest = st.selectbox("To fill or line", targets, format_func=lambda k: k if k in LINES else live_fills[k]["fill_id"] + " · " + live_fills[k]["tank"])
            a, b = st.columns(2)
            sent = a.number_input("Sent volume (hL)", min_value=0.0, step=0.1)
            sp = a.number_input("Sent gravity (°P)", min_value=0.01, max_value=50.0, value=18.0)
            got = b.number_input("Received volume (hL)", min_value=0.0, step=0.1)
            gp = b.number_input("Received gravity (°P)", min_value=0.01, max_value=50.0, value=18.0)
            dose = st.selectbox("GFE batch (optional)", ("None",) + tuple(gfe), format_func=lambda k: k if k == "None" else gfe[k]["batch_id"])
            quantity = st.number_input("GFE added (hL)", min_value=0.0, step=0.1)
            st.caption("Sent gravity is the base beer before dosing. Received gravity is the measured blended product.")
            if st.form_submit_button("Save record"):
                additive = None if dose == "None" else dict(gfe[dose], quantity=quantity)
                if dose == "None" and quantity > 0:
                    st.error("Choose the GFE batch for this dose.")
                else:
                    save_entry(kind, {"reference": ref, "from_fill": live_fills[source]["fill_id"],
                        "from_tank": live_fills[source]["tank"], "to_fill": "" if dest in LINES else live_fills[dest]["fill_id"],
                        "to_tank": dest if dest in LINES else live_fills[dest]["tank"], "sent_hl": sent, "sent_plato": sp,
                        "received_hl": got, "received_plato": gp, "additive": additive}, when, entered_by)
    elif kind == "stock":
        with st.form("stock_form"):
            tank = st.selectbox("Tank or line", TANKS)
            volume = st.number_input("Measured stock (hL)", min_value=0.0, step=0.1)
            plato = st.number_input("Stock gravity (°P)", min_value=0.0, max_value=50.0, value=18.0)
            if st.form_submit_button("Save record"):
                save_entry(kind, {"tank": tank, "volume_hl": volume, "plato": plato if volume else None}, when, entered_by)
    elif kind == "packaging":
        with st.form("packaging_form"):
            ref = st.text_input("Packaging reference", max_chars=120)
            line = st.selectbox("Packaging line", LINES)
            brand = st.selectbox("Brand", BRANDS)
            volume = st.number_input("Actual packaged volume (hL)", min_value=0.0, step=0.1)
            plato = st.number_input("Packaged gravity (°P)", min_value=0.01, max_value=50.0, value=12.0)
            if st.form_submit_button("Save record"):
                save_entry(kind, {"reference": ref, "line": line, "brand": brand, "volume_hl": volume, "plato": plato}, when, entered_by)
    else:
        if not bs:
            st.info("Register the material batch before entering quantities.")
            st.stop()
        bid = st.selectbox("Material batch", tuple(bs), format_func=lambda k: bs[k]["batch_id"] + " · " + bs[k]["material"])
        with st.form("material_quantity_form"):
            quantity = st.number_input("Quantity (" + bs[bid]["unit"] + ")", min_value=0.0, step=0.1)
            ref = st.text_input("Reference", max_chars=120) if kind != "material_stock" else ""
            reason = st.text_input("Destruction reason", max_chars=120) if kind == "destruction" else ""
            if st.form_submit_button("Save record"):
                save_entry(kind, {"batch_id": bs[bid]["batch_id"], "quantity": quantity, "reference": ref, "reason": reason}, when, entered_by)

elif page == "Tank board":
    st.title("Tank board")
    current = fills(rows, site)
    if current:
        st.dataframe(pd.DataFrame(current.values())[["fill_id", "tank", "brand", "status"]], hide_index=True, width="stretch")
    else:
        st.info("No tank fills have been registered.")
    st.caption("The latest fill status is shown. The inventory calculation uses measured stock readings.")

elif page == "Records":
    st.title("Saved records")
    chosen = st.multiselect("Activity types", KINDS, default=list(KINDS))
    selected = [r for r in rows if r["site"] == site and r["kind"] in chosen]
    if not selected:
        st.info("There are no saved records for this selection.")
    else:
        records_frame = pd.DataFrame([{"ID": r["id"], "Activity": r["kind"], "Event time": r["occurred_at"],
            "Production day": r["production_date"], "Shift": r["shift"], "Entered by": r["logged_by"],
            "Saved at UTC": r["created_at"], "Details": json.dumps(r["payload"], ensure_ascii=False)} for r in selected])
        st.dataframe(records_frame.sort_values("Event time", ascending=False), hide_index=True, width="stretch")
        st.download_button("Download records", csv_bytes(records_frame), "beer_loss_records.csv", "text/csv")

elif page == "Administration":
    st.title("Administration")
    if not pin_access("ADMIN_PIN", "Administrator PIN", mode == "demo"):
        st.info("Enter the administrator PIN to review corrections and backups.")
        st.stop()
    st.subheader("Complete history and backup")
    st.download_button("Download full backup", storage.export_backup(engine), "beer_loss_backup.json", "application/json")
    history = storage.load(engine, include_voided=True)
    st.caption(f"{len(history)} records retained, including {sum(r['voided'] for r in history)} voided entries. The backup covers both breweries.")
    with st.expander("Review retained audit history"):
        st.dataframe(pd.DataFrame([{"ID": r["id"], "Site": r["site"], "Activity": r["kind"],
            "Event time": r["occurred_at"], "Voided": r["voided"], "Reason": r["void_reason"],
            "Voided by": r["voided_by"], "Voided at UTC": r["voided_at"],
            "Original details": json.dumps(r["payload"])} for r in history]), hide_index=True, width="stretch")
    st.subheader("Void an incorrect record")
    selected = [r for r in rows if r["site"] == site]
    if selected:
        options = {r["id"]: r for r in selected}
        rid = st.selectbox("Record", tuple(options), format_func=lambda k: options[k]["kind"] + " · " + str(options[k]["occurred_at"]) + " · " + k[:8])
        st.json(options[rid]["payload"])
        with st.form("void_form"):
            reviewer = st.text_input("Reviewer name", max_chars=120)
            reason = st.text_area("Reason for correction", max_chars=2000)
            confirmed = st.checkbox("I confirm that this record is incorrect. Its original details will remain in the audit history.")
            if st.form_submit_button("Void record"):
                try:
                    if not confirmed:
                        raise ValueError("Confirm the correction before voiding this record.")
                    storage.void(engine, rid, reviewer, reason)
                    st.session_state.flash = "The record is voided and retained in the audit history. You can now enter a replacement."
                    st.rerun()
                except (ValueError, KeyError) as exc:
                    st.error(str(exc))
                except Exception:
                    st.error("The correction could not be saved. Refresh and check the record before retrying.")
    with st.expander("Restore a full backup into an empty database"):
        upload = st.file_uploader("Beer Loss backup", type=["json"])
        if upload:
            try:
                content = upload.getvalue().decode("utf-8")
                parsed = storage.read_backup(content)
                st.write(f"Backup contains {len(parsed)} records.")
                confirm = st.checkbox("Restore this complete history into the currently connected empty database.")
                if st.button("Restore backup", disabled=not confirm):
                    count = storage.restore_empty(engine, content)
                    st.session_state.flash = f"Restored {count} records."
                    st.rerun()
            except (ValueError, KeyError, TypeError, UnicodeError) as exc:
                st.error(str(exc))
            except Exception:
                st.error("The backup could not be restored. Existing records have not been overwritten.")

else:
    st.title("How to use Beer Loss")
    st.markdown((Path(__file__).parent / "docs" / "Guide.md").read_text(encoding="utf-8"))
