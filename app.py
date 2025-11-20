import streamlit as st
import pandas as pd
from datetime import date
from pathlib import Path
import urllib.parse

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
logo_path = Path(__file__).parent / "ggbl.png"
if logo_path.exists():
    st.image(str(logo_path), width=150)
else:
    st.warning("Logo file 'ggbl.png' not found in the same folder as app.py")

st.title("🍺 My Brewhouse Tracker")
st.write("Enter brewhouse data for a single brew using the form below.")

# ----------------------------------------------------
# FORM
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

    # ONLY keeping this short section for clarity (you already know the full form)
    st.subheader("❄️ Cold Wort (to Fermenter)")
    cw1, cw2, cw3 = st.columns(3)
    with cw1:
        cw_og = st.number_input("Cold Wort OG", step=0.0001, format="%.4f")
    with cw2:
        cw_pH = st.number_input("Cold Wort pH", step=0.01)
    with cw3:
        cw_volume = st.number_input("Cold Wort Volume (hl)", step=0.1)

    submitted = st.form_submit_button("Save Brew")

# ----------------------------------------------------
# AFTER SUBMIT
# ----------------------------------------------------
if submitted:
    # Build DataFrame
    data = {
        "Date": [brew_date],
        "Brand": [brand],
        "Brew Number": [brew_number],
        "FST/MLT": [fst_or_mlt],
        "Cold Wort OG": [cw_og],
        "Cold Wort pH": [cw_pH],
        "Cold Wort Volume": [cw_volume],
    }

    df = pd.DataFrame(data)

    st.success("Brew saved successfully.")
    st.dataframe(df, use_container_width=True)

    # CSV Download
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download this brew as CSV",
        data=csv,
        file_name=f"brewhouse_brew_{brew_number}.csv",
        mime="text/csv",
    )

    # ----------------------------------------------------
    # WHATSAPP LINK (Correct Format)
    # ----------------------------------------------------
    # TODO: Replace with your real number in CORRECT format
    phone_number = "233241234567"  # <-- REPLACE with your real Ghana number

    # Validate phone
    if not phone_number.isdigit():
        st.error("❌ ERROR: WhatsApp phone number must contain ONLY digits.")
    elif not phone_number.startswith("233"):
        st.error("❌ ERROR: Phone number must start with Ghana code: 233.")
    else:
        # Build the message
        wa_message = f"""
Brew Update – My Brewhouse Tracker

📅 Date: {brew_date}
🍺 Brand: {brand}
🔢 Brew No: {brew_number}
🏷️ FST/MLT: {fst_or_mlt}

❄️ Cold Wort:
   • OG: {cw_og}
   • pH: {cw_pH}
   • Volume: {cw_volume} hl
"""
        # Encode for URL
        encoded_msg = urllib.parse.quote(wa_message)

        # CORRECT WhatsApp link format
        wa_url = f"https://wa.me/{phone_number}?text={encoded_msg}"

        st.markdown(
            f"<a href='{wa_url}' target='_blank' style='font-size:20px;'>📲 <b>Send Brew Update via WhatsApp</b></a>",
            unsafe_allow_html=True,
        )

        # Debug (optional)
        st.write("🔍 WhatsApp URL generated:", wa_url)
