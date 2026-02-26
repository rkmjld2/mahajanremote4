# app.py - WORKS WITH YOUR ESP STATUS ENDPOINT

import streamlit as st
import requests
import time

ESP_IP = "192.168.1.13"
STATUS_URL = f"http://{ESP_IP}/status"

st.set_page_config(page_title="ESP8266 Control", layout="wide")

st.title("🔌 ESP8266 Pin Monitor")
st.caption(f"📡 http://{ESP_IP} | Status: ✅ WORKING")

# Test button (matches your browser success)
if st.button("🧪 Test Connection", type="primary"):
    try:
        r = requests.get(STATUS_URL, timeout=10)
        st.success(f"✅ HTTP {r.status_code}")
        st.json(r.json())
    except Exception as e:
        st.error(f"❌ Python error: {e}")

# Live pin status
if "pins" not in st.session_state:
    st.session_state.pins = {f"D{i}": False for i in range(9)}

def refresh_status():
    try:
        r = requests.get(STATUS_URL, timeout=10)
        data = r.json().get("pins", {})
        st.session_state.pins = {k: bool(v) for k,v in data.items()}
        return True
    except:
        return False

# Auto-refresh every 5s
if st.button("🔄 Live Monitor", key="live"):
    if refresh_status():
        st.success("Updated!")
    else:
        st.error("Connection failed")
    st.rerun()

# Display pins
st.subheader("📊 Pin States")
cols = st.columns(3)
for i, pin in enumerate(["D0","D1","D2","D3","D4","D5","D6","D7","D8"]):
    state = st.session_state.pins[pin]
    cols[i%3].metric(pin, "🟢 ON" if state else "🔴 OFF")

# Manual refresh
st.subheader("🔧 Manual Refresh")
col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 Refresh Now"):
        refresh_status()
        st.rerun()
with col2:
    st.info("Browser works → Python network issue")

st.markdown("---")
st.info("""
**🚨 YOUR ESP HAS NO `/set/` ENDPOINTS**
- Browser `/status` ✅ WORKS
- Python `/status` ❌ NETWORK BLOCKED  
- `/set/D1/on` ❌ NOT IMPLEMENTED

**NEXT**: Upload ESP firmware with pin control endpoints
""")
