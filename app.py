import streamlit as st
import requests
import re
import json
import time

# SECRETS
ESP_IP = st.secrets["ESP_IP"]
STATUS_URL = f"http://{ESP_IP}/status"
PINS = ["D0","D1","D2","D3","D4","D5","D6","D7","D8"]

def fix_json(raw):
    cleaned = re.sub(r',\s*}', '}', raw)
    cleaned = re.sub(r',\s*]', ']', cleaned)
    try:
        return json.loads(cleaned)
    except:
        return {"pins": {p: False for p in PINS}}

@st.cache_data(ttl=10)
def test_esp():
    try:
        r = requests.get(STATUS_URL, timeout=5)
        return r.status_code == 200, fix_json(r.text) if r.status_code == 200 else None
    except:
        return False, None

st.set_page_config(page_title="ESP Remote", layout="wide")
st.title("🌐 ESP8266 REMOTE CONTROL")

# STATUS BAR
connected, data = test_esp()
status_text = "🟢 ONLINE" if connected else "🔴 OFFLINE"

col1, col2 = st.columns([3,1])
with col1:
    st.metric("ESP Status", status_text, f"IP: {ESP_IP}")
with col2:
    st.caption(f"Ping: {time.strftime('%H:%M:%S')}")

# PIN STATES
if "pins" not in st.session_state:
    st.session_state.pins = {p: False for p in PINS}

if connected:
    pins_data = data.get("pins", {})
    st.session_state.pins = {k: bool(pins_data.get(k, False)) for k in PINS}

# LIVE PINS
st.subheader("📊 PIN STATUS")
cols = st.columns(3)
for i, pin in enumerate(PINS):
    state = st.session_state.pins[pin]
    cols[i%3].metric(pin, "🟢 ON" if state else "🔴 OFF")

# TOGGLES
st.subheader("🔧 CONTROL PINS")
toggle_cols = st.columns(3)
for i, pin in enumerate(PINS):
    with toggle_cols[i%3]:
        current = st.session_state.pins[pin]
        disabled = not connected
        
        new_state = st.checkbox(
            f"**{pin}**", 
            value=current,
            key=f"t_{pin}",
            disabled=disabled
        )
        
        if new_state != current and connected:
            state_str = "on" if new_state else "off"
            with st.spinner(f"{pin}..."):
                try:
                    url = f"http://{ESP_IP}/set/{pin}/{state_str}"
                    r = requests.get(url, timeout=5)
                    if r.status_code == 200:
                        st.session_state.pins[pin] = new_state
                        st.success(f"✅ {pin} = {'ON' if new_state else 'OFF'}")
                        time.sleep(0.5)
                        connected, data = test_esp()
                        if connected:
                            st.session_state.pins[pin] = bool(data["pins"].get(pin, new_state))
                    else:
                        st.error(f"❌ HTTP {r.status_code}")
                except:
                    st.error("❌ Timeout")
            st.rerun()

# SUMMARY
col1, col2, col3 = st.columns(3)
on_count = sum(st.session_state.pins.values())
col1.metric("🟢 ON", on_count)
col2.metric("🔴 OFF", 9-on_count)
col3.metric("Status", status_text)

# BUTTONS
col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 REFRESH"):
        st.cache_data.clear()
        st.rerun()
with col2:
    if st.button("🧪 PING"):
        if connected:
            st.balloons()
        else:
            st.error("🔴 OFFLINE")

st.markdown("---")
st.caption("🌍 Cloud control • Plug/unplug ESP → auto-detect")
