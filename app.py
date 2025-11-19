import streamlit as st
import pandas as pd
from datetime import date

# ----------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------
st.set_page_config(
    page_title="My Brewhouse Tracker",
    page_icon="🍺",
    layout="wide"
)

# ----------------------------------------------------
# LOGO + TITLE
# ----------------------------------------------------
st.image(r"C:\Users\clifford.srekumah-gl\Downloads\ggbl.png", width=150)
st.title("🍺 My Brewhouse Tracker")
st.write("Enter brewhouse data for a single brew using the form below.")

# ----------------------------------------------------
# FORM SECTION
# ----------------------------------------------------
with st.form("brewhouse_entry"):
    st.subheader("🧾 Brew Identification")

    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        brew_date = st.date_input("Date", value=date.today())
    with col_b:
        brand = st.text_input("Brand")
    with col_c:
        brew_number = st.number_input("Brew Number", min_value=1, step=1)
    with col_d:
        fst_or_mlt = st.selectbox("FST or MLT", ["FST", "MLT", "Other"])

    st.markdown("---")
    st.subheader("🥣 Adjunct Cooker / PMV")

    col1, col2, col3 = st.columns(3)
    with col1:
        pmv_ca = st.number_input("PMV Calcium (mg/L)", step=0.01)
    with col2:
        pmv_pH = st.number_input("PMV pH", step=0.01)
    with col3:
        pmv_fan = st.number_input("PMV FAN", step=0.1)

    st.markdown("---")
    st.subheader("🥣 Mash Combination Vessel (MCV)")

    col4, col5, col6, col7, col8 = st.columns(5)
    with col4:
        mcv_ca_before = st.number_input("MCV Calcium (mg/L) – BEFORE", step=0.01)
    with col5:
        mcv_ca_after = st.number_input("MCV Calcium (mg/L) – AFTER", step=0.01)
    with col6:
        mcv_pH_before = st.number_input("MCV pH – BEFORE", step=0.01)
    with col7:
        mcv_pH_after = st.number_input("MCV pH – AFTER", step=0.01)
    with col8:
        mcv_fan = st.number_input("MCV FAN", step=0.1)

    st.markdown("---")
    st.subheader("🧱 Mash Filter – Strong Wort")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        mf_strong_gravity = st.number_input("Strong Wort Gravity", step=0.0001, format="%.4f")
    with c2:
        mf_strong_turb90 = st.number_input("Turbidity @90", step=0.1)
    with c3:
        mf_strong_pH = st.number_input("Strong Wort pH", step=0.01)
    with c4:
        mf_strong_vol = st.number_input("Strong Wort Volume (hl)", step=0.1)

    c5, c6, c7 = st.columns(3)
    with c5:
        mf_strong_colour = st.number_input("Strong Wort Colour", step=0.1)
    with c6:
        mf_strong_grav_before_comp = st.number_input("Gravity Before Compression", step=0.0001, format="%.4f")
    with c7:
        mf_strong_grav_after_comp = st.number_input("Gravity After Compression", step=0.0001, format="%.4f")

    st.markdown("---")
    st.subheader("🧱 Mash Filter – Weak Wort")

    w1, w2, w3, w4, w5 = st.columns(5)
    with w1:
        mf_weak_pH_1 = st.number_input("Weak Wort pH (1)", step=0.01)
    with w2:
        mf_weak_gravity = st.number_input("Weak Wort Gravity", step=0.0001, format="%.4f")
    with w3:
        mf_weak_pH_2 = st.number_input("Weak Wort pH (2)", step=0.01)
    with w4:
        mf_weak_colour = st.number_input("Weak Wort Colour", step=0.1)
    with w5:
        mf_weak_vol = st.number_input("Weak Wort Volume (hl)", step=0.1)

    st.markdown("---")
    st.subheader("🔥 Wort Kettle – Pre-Boil")

    pre1, pre2, pre3, pre4 = st.columns(4)
    with pre1:
        wok_pre_gravity = st.number_input("Pre-boil Gravity", step=0.0001, format="%.4f")
    with pre2:
        wok_pre_pH = st.number_input("Pre-boil pH", step=0.01)
    with pre3:
        wok_pre_colour = st.number_input("Pre-boil Colour", step=0.1)
    with pre4:
        wok_pre_vol = st.number_input("Pre-boil Volume (hl)", step=0.1)

    st.markdown("---")
    st.subheader("🔥 Wort Kettle – Post-Boil")

    post1, post2, post3, post4, post5 = st.columns(5)
    with post1:
        wok_post_grav_before_sugar = st.number_input("Gravity Before Sugar", step=0.0001, format="%.4f")
    with post2:
        wok_post_grav_after_sugar = st.number_input("Gravity After Sugar", step=0.0001, format="%.4f")
    with post3:
        wok_post_pH = st.number_input("Post-boil pH", step=0.01)
    with post4:
        wok_post_colour = st.number_input("Post-boil Colour", step=0.1)
    with post5:
        wok_post_trub = st.number_input("Trub Content", step=0.1)

    st.markdown("---")
    st.subheader("❄️ Cold Wort (to Fermenter)")

    cw1, cw2, cw3, cw4 = st.columns(4)
    with cw1:
        cw_fan = st.number_input("Cold Wort FAN", step=0.1)
    with cw2:
        cw_bitter = st.number_input("Bitterness (IBU)", step=0.1)
    with cw3:
        cw_ca = st.number_input("Cold Wort Calcium", step=0.01)
    with cw4:
        cw_colour = st.number_input("Cold Wort Colour", step=0.1)

    cw5, cw6, cw7, cw8 = st.columns(4)
    with cw5:
        cw_app_extract = st.number_input("Apparent Extract (°P)", step=0.01)
    with cw6:
        cw_og = st.number_input("Original Gravity", step=0.0001, format="%.4f")
    with cw7:
        cw_oxygen = st.number_input("Oxygen (ppm)", step=0.01)
    with cw8:
        cw_pH = st.number_input("Cold Wort pH", step=0.01)

    cw9, cw10, cw11 = st.columns(3)
    with cw9:
        cw_tpp = st.number_input("Total Polyphenol", step=0.1)
    with cw10:
        cw_so2 = st.number_input("SO₂", step=0.1)
    with cw11:
        cw_volume = st.number_input("Cold Wort Volume (hl)", step=0.1)

    submitted = st.form_submit_button("Save Brew")

# ----------------------------------------------------
# SAVE + DOWNLOAD
# ----------------------------------------------------
if submitted:
    data = {
        "Date": [brew_date],
        "Brand": [brand],
        "Brew Number": [brew_number],
        "FST/MLT": [fst_or_mlt],

        "PMV Calcium": [pmv_ca],
        "PMV pH": [pmv_pH],
        "PMV FAN": [pmv_fan],

        "MCV Ca BEFORE": [mcv_ca_before],
        "MCV Ca AFTER": [mcv_ca_after],
        "MCV pH BEFORE": [mcv_pH_before],
        "MCV pH AFTER": [mcv_pH_after],
        "MCV FAN": [mcv_fan],

        "MF Strong Gravity": [mf_strong_gravity],
        "MF Strong Turb@90": [mf_strong_turb90],
        "MF Strong pH": [mf_strong_pH],
        "MF Strong Volume": [mf_strong_vol],
        "MF Strong Colour": [mf_strong_colour],
        "MF Grav Before Comp": [mf_strong_grav_before_comp],
        "MF Grav After Comp": [mf_strong_grav_after_comp],

        "MF Weak pH 1": [mf_weak_pH_1],
        "MF Weak Gravity": [mf_weak_gravity],
        "MF Weak pH 2": [mf_weak_pH_2],
        "MF Weak Colour": [mf_weak_colour],
        "MF Weak Volume": [mf_weak_vol],

        "WOK Pre Gravity": [wok_pre_gravity],
        "WOK Pre pH": [wok_pre_pH],
        "WOK Pre Colour": [wok_pre_colour],
        "WOK Pre Volume": [wok_pre_vol],

        "WOK Grav Before Sugar": [wok_post_grav_before_sugar],
        "WOK Grav After Sugar": [wok_post_grav_after_sugar],
        "WOK Post pH": [wok_post_pH],
        "WOK Post Colour": [wok_post_colour],
        "WOK Trub Content": [wok_post_trub],

        "Cold Wort FAN": [cw_fan],
        "Cold Wort Bitterness": [cw_bitter],
        "Cold Wort Calcium": [cw_ca],
        "Cold Wort Colour": [cw_colour],
        "Cold Wort Apparent Extract": [cw_app_extract],
        "Cold Wort Original Gravity": [cw_og],
        "Cold Wort Oxygen": [cw_oxygen],
        "Cold Wort pH": [cw_pH],
        "Cold Wort Total Polyphenol": [cw_tpp],
        "Cold Wort SO₂": [cw_so2],
        "Cold Wort Volume": [cw_volume],
    }

    result_df = pd.DataFrame(data)

    st.success("Brew saved in session. You can download this row as CSV.")
    st.dataframe(result_df, use_container_width=True)

    csv = result_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download this brew as CSV",
        data=csv,
        file_name=f"brewhouse_brew_{brew_number}.csv",
        mime="text/csv",
    )
