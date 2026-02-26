# app.py - MANUAL ONLY (works with your ESP)

import streamlit as st
import requests
import time
import threading

ESP_IP = "192.168.1.13"
STATUS_URL = f"http://{ESP_IP}/status"

st.set_page_config(page_title="ESP8266 Manual", layout="wide")

st.title("🔌 ESP8266 Manual Control")
st.caption(f"📡 http://{ESP_IP}")

# Test connection first
if st.button("🧪 Test Connection"):
    try:
        r = requests.get(STATUS_URL, timeout=5)
        st.success(f"✅ Status OK: {r.status_code}")
        st.json(r.json())
    except Exception as e:
        st.error(f"❌ {e}")

# Pin states
if "pins" not in st.session_state:
    st.session_state.pins = {f"D{i}": False for i in range(9)}

cols = st.columns(3)
for i, pin in enumerate([f"D{i}" for i in range(9)]):
    cols[i%3].metric(pin, "ON" if st.session_state.pins[pin] else "OFF")

# Auto-refresh status
if st.button("🔄 Auto Refresh", key="auto"):
    try:
        r = requests.get(STATUS_URL, timeout=5)
        data = r.json().get("pins", {})
        for pin in st.session_state.pins:
            st.session_state.pins[pin] = bool(data.get(pin, False))
        st.success("Updated!")
        st.rerun()
    except Exception as e:
        st.error(f"Status failed: {e}")

st.info("❌ /set/ endpoints missing → Update ESP firmware with pin control sketch")
