import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
import traceback
import json
import paho.mqtt.client as mqtt
from datetime import datetime
import time

# ==================================================
# ⚙ PAGE SETTINGS & CSS
# ==================================================
st.set_page_config(page_title="AQI Dashboard", layout="wide")

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
# 📡 MQTT CONFIG
# ==================================================
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "aqi/project/smvitm_bantakal"  

# ==================================================
# ☁ SUPABASE CONFIG
# ==================================================
try:
    SUPABASE_URL = st.secrets["general"]["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["general"]["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error(f"Supabase Init Error: {e}. Check secrets.toml")
    st.stop()

# ==================================================
# ⚡ MQTT CLIENT (THREAD-SAFE "MAILBOX" VERSION)
# ==================================================
# This Class holds the data safely. 
# The background thread updates this, and Streamlit reads it.

@st.cache_resource
class MQTTService:
    def __init__(self):
        # This variable is the "Mailbox"
        self.latest_data = {"aqi": 0, "temperature": 0, "humidity": 0, "mq135": 0}
        self.is_connected = False
        
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        try:
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start() # Starts the background thread
        except Exception as e:
            print(f"MQTT Connection Failed: {e}")

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.is_connected = True
            print(f"✅ Connected to MQTT! Listening to: {MQTT_TOPIC}")
            client.subscribe(MQTT_TOPIC)

    def on_message(self, client, userdata, msg):
        try:
            # Background thread ONLY updates this variable. 
            # It does NOT touch st.session_state directly (which causes the crash).
            payload = json.loads(msg.payload.decode())
            self.latest_data = payload
            print(f"📥 Received: {payload}") 
        except Exception as e:
            print(f"Error parsing MQTT: {e}")

# Initialize the Global MQTT Service
mqtt_service = MQTTService()

# ==================================================
# 📥 FETCH HISTORY (Supabase)
# ==================================================
def get_historical_data(limit=200):
    try:
        response = supabase.table("sensor_data").select("*").order("id", desc=True).limit(limit).execute()
        if hasattr(response, 'data') and response.data:
            return response.data
        return []
    except Exception:
        return []

# ==================================================
# 🧭 SIDEBAR
# ==================================================
choice = st.sidebar.radio("📌 Select View", ["Current Data (Live)", "Stored Data (History)", "Future AQI Forecasting"])

# ==================================================
# 🟢 LIVE MONITOR VIEW
# ==================================================
if "live_history" not in st.session_state:
    st.session_state["live_history"] = []

@st.fragment(run_every=1)
def show_live_monitor():
    # 1. Main Thread Reads from the "Mailbox" (mqtt_service.latest_data)
    data = mqtt_service.latest_data
    
    aqi = int(data.get("aqi", 0))
    temp = data.get("temperature", 0)
    hum = data.get("humidity", 0)
    mq135_val = data.get("mq135", 0)

    # 2. Update History Graph locally in the Main Thread
    # We do this here because ONLY the main thread is allowed to modify session_state
    current_time = datetime.now().strftime("%H:%M:%S")
    
    # Only append if we have valid data
    if aqi > 0 or mq135_val > 0:
        st.session_state["live_history"].append({
            "Timestamp": current_time,
            "aqi": aqi,
            "mq135": mq135_val
        })
    
    # Keep list short (last 50 seconds)
    if len(st.session_state["live_history"]) > 50:
        st.session_state["live_history"].pop(0)

    # 3. Color Logic
    if aqi <= 50: status, color = "Good", "#00e400"
    elif aqi <= 100: status, color = "Moderate", "#ffff00"
    elif aqi <= 150: status, color = "Poor", "#ff7e00"
    elif aqi <= 200: status, color = "Unhealthy", "#ff0000"
    elif aqi <= 300: status, color = "Very Unhealthy", "#8f3f97"
    else: status, color = "Hazardous", "#7e0023"

    st.title("🌍 Live AQI Monitoring")
    
    if not mqtt_service.is_connected:
        st.toast("🔌 Connecting to MQTT Broker...", icon="⚠️")

    # 4. Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("AQI", aqi)
    col2.metric("Temp (°C)", temp)
    col3.metric("Humidity (%)", hum)
    col4.metric("MQ135 (Raw)", mq135_val)

    # 5. Gauge
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
        <span>0</span><span>50</span><span>100</span><span>150</span><span>200</span><span>300</span><span>300+</span>
    </div>
    <div class="big-aqi-value" style="color:{color};">{aqi} AQI</div>
    """, unsafe_allow_html=True)

    # 6. Graph
    st.subheader("📈 Live Stream (Last 50 Seconds)")
    if st.session_state["live_history"]:
        df_live = pd.DataFrame(st.session_state["live_history"])
        fig = px.line(df_live, x="Timestamp", y=["aqi", "mq135"], markers=True)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Waiting for live data...")

# ==================================================
# 📁 STORED DATA VIEW
# ==================================================
def show_history():
    st.title("📊 Historical AQI Data (Hourly Averages)")
    if st.button("🔄 Refresh Data"): st.rerun()

    rows = get_historical_data(1000)
    if not rows:
        st.warning("No data in Supabase.")
        return

    df = pd.DataFrame(rows)
    df.rename(columns={"created_at": "Timestamp"}, inplace=True)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["Timestamp"])
    
    try:
        if df["Timestamp"].dt.tz is not None:
            df["Timestamp"] = df["Timestamp"].dt.tz_convert("Asia/Kolkata")
        else:
            df["Timestamp"] = df["Timestamp"].dt.tz_localize("UTC").dt.tz_convert("Asia/Kolkata")
    except: pass

    df_sorted = df.sort_values("Timestamp")
    st.subheader("📈 Long-Term Trends")
    fig = px.line(df_sorted, x="Timestamp", y=["aqi", "temperature", "humidity"])
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df_sorted.set_index("Timestamp"), use_container_width=True)

# ==================================================
# ROUTING
# ==================================================
if choice == "Current Data (Live)":
    show_live_monitor()
elif choice == "Stored Data (History)":
    show_history()
elif choice == "Future AQI Forecasting":
    st.title("🔮 Forecasting"); st.info("Coming soon...")
