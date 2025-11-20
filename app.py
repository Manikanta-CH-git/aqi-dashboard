import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client

# ==================================================
# ☁ SUPABASE CONFIG (FROM secrets.toml)
# ==================================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==================================================
# ⚙ PAGE SETTINGS
# ==================================================
st.set_page_config(page_title="AQI Dashboard", layout="wide")

# ==================================================
# 🌈 GLOBAL CSS
# ==================================================
st.markdown("""
<style>
    .aqi-bar-container { display: flex; height: 45px; border-radius: 10px; overflow: hidden; margin-top: 10px; }
    .seg { flex: 1; text-align: center; font-weight: bold; padding-top: 12px; color: white; font-family: sans-serif; font-size: 14px; }

    .good { background: #00e400; }
    .moderate { background: #ffff00; color: black !important; }
    .poor { background: #ff7e00; }
    .unhealthy { background: #ff0000; }
    .veryunhealthy { background: #8f3f97; }
    .hazardous { background: #7e0023; }

    .ticks { width: 100%; display: flex; justify-content: space-between; margin-top: 4px; font-size: 12px; color: #aaa; }
    .big-aqi-value { font-size: 48px; font-weight: 800; text-align: center; margin-top: 15px; transition: color 0.5s ease; }
    .status-text { font-size: 24px; text-align: center; margin-bottom: 10px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==================================================
# 📥 FETCH LATEST DATA
# ==================================================
def get_latest_data(limit=200):
    try:
        response = (
            supabase.table("sensordata")
            .select("*")
            .order("id", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data
    except:
        return []

# ==================================================
# 🧭 SIDEBAR
# ==================================================
refresh_seconds = st.sidebar.slider("⏱ Auto Refresh (Seconds)", 2, 60, 5)
choice = st.sidebar.radio("📌 Select View", ["Current Data", "Stored Data", "Future Predictions"])

# ==================================================
# 🟢 LIVE MONITOR
# ==================================================
@st.fragment(run_every=refresh_seconds)
def show_live_monitor():

    rows = get_latest_data(50)
    if not rows:
        st.info("Waiting for data from device…")
        return

    df = pd.DataFrame(rows)
    df.rename(columns={"created_at": "Timestamp"}, inplace=True)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"]).dt.tz_convert("Asia/Kolkata")
    latest = df.iloc[0]

    aqi = int(latest["aqi"])
    temp = latest["temperature"]
    hum = latest["humidity"]

    # 🔵 AQI Status Logic (Correct according to your color bar)
    if aqi <= 50: 
        status, color = "Good", "#00e400"
    elif aqi <= 100: 
        status, color = "Moderate", "#ffff00"
    elif aqi <= 150: 
        status, color = "Poor", "#ff7e00"   # UPDATED NAME
    elif aqi <= 200: 
        status, color = "Unhealthy", "#ff0000"
    elif aqi <= 300: 
        status, color = "Very Unhealthy", "#8f3f97"
    else: 
        status, color = "Hazardous", "#7e0023"

    st.title("🌍 Live AQI Monitoring")

    col1, col2, col3 = st.columns(3)
    col1.metric("AQI", aqi)
    col2.metric("Temperature (°C)", temp)
    col3.metric("Humidity (%)", hum)

    st.caption(f"Last Updated: {latest['Timestamp'].strftime('%H:%M:%S')}")

    # 🌈 AQI BAR
    st.markdown(f"""
    <div class="status-text">Current Status: {status}</div>

    <div class="aqi-bar-container">
        <div class="seg good">Good</div>
        <div class="seg moderate">Moderate</div>
        <div class="seg poor">Poor</div>
        <div class="seg unhealthy">Unhealthy</div>
        <div class="seg veryunhealthy">Very Unhealthy</div>
        <div class="seg hazardous">Hazardous</div>
    </div>

    <div class="ticks">
        <span>0</span><span>50</span><span>100</span><span>150</span>
        <span>200</span><span>300</span><span>300+</span>
    </div>

    <div class="big-aqi-value" style="color:{color};">{aqi} AQI</div>
    """, unsafe_allow_html=True)

    st.subheader("📈 Live AQI Trend")
    df_sorted = df.sort_values("Timestamp")
    fig = px.line(df_sorted, x="Timestamp", y="aqi", markers=True)
    st.plotly_chart(fig, use_container_width=True)

# ==================================================
# 📁 STORED DATA PAGE
# ==================================================
def show_history():
    st.title("📊 Historical AQI Data")

    rows = get_latest_data(1000)
    if not rows:
        st.warning("No data available.")
        return

    df = pd.DataFrame(rows)
    df.rename(columns={"created_at": "Timestamp"}, inplace=True)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"]).dt.tz_convert("Asia/Kolkata")
    df_sorted = df.sort_values("Timestamp")

    st.subheader("📈 AQI, Temperature & Humidity Trends")
    fig = px.line(df_sorted, x="Timestamp", y=["aqi", "temperature", "humidity"])
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📄 Data Table")
    st.dataframe(df, use_container_width=True)

# ==================================================
# 🔮 FUTURE PREDICTION
# ==================================================
def show_future():
    st.title("🔮 Future AQI Predictions")
    st.info("Prediction model coming soon…")

# ==================================================
# ROUTING
# ==================================================
if choice == "Current Data":
    show_live_monitor()
elif choice == "Stored Data":
    show_history()
elif choice == "Future Predictions":
    show_future()
