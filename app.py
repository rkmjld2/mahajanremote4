import streamlit as st
import requests
import re
import json
import time

# CONFIGURATION - FROM SECRETS
ESP_IP = st.secrets["ESP_IP"]
STATUS_URL = f"http://{ESP_IP}/status"
PINS = ["D0","D1","D2","D3","D4","D5","D6","D7","D8"]

# Fix ESP's broken JSON (trailing comma)
def fix_json(raw):
    cleaned = re.sub(r',\s*}', '}', raw)
    cleaned = re.sub(r',\s*]', ']', cleaned)
    try:
        return json.loads(cleaned)
    except:
        return {"pins": {p: False for p in PINS}}

# Test ESP connection
@st.cache_data(ttl=10)
def test_esp():
    try:
        r = requests.get(STATUS_URL, timeout=5)
        return r.status_code == 200, fix_json(r.text) if r.status_code == 200 else None
    except:
        return False, None

st.set_page_config(page_title="ESP Remote Control", layout="wide")
st.title("🌐 ESP8266 REMOTE CONTROL")

# CONNECTION STATUS
connected, data = test_esp()
col1, col2 = st.columns([3,1])

with col1:
    status_color = "inverse" if connected else "gray"
    st.metric("ESP Status", f"{'🟢 ONLINE' if connected else '🔴 OFFLINE'}", 
              f"IP: {ESP_IP}", delta_color=status_color)

with col2:
    st.caption(f"Last ping: {time.strftime('%H:%M:%S')}")

# Pin states
if "pins" not in st.session_state:
    st.session_state.pins = {p: False for p in PINS}

if connected:
    pins_data = data.get("pins", {})
    st.session_state.pins = {k: bool(pins_data.get(k, False)) for k in PINS}

# LIVE PIN DISPLAY
st.subheader("📊 LIVE PIN STATUS")
cols = st.columns(3)
for i, pin in enumerate(PINS):
    state = st.session_state.pins[pin]
    cols[i%3].metric(pin, f"{'🟢 ON' if state else '🔴 OFF'}")

# PIN TOGGLES
st.subheader("🔧 MANUAL CONTROL")
toggle_cols = st.columns(3)
for i, pin in enumerate(PINS):
    with toggle_cols[i%3]:
        current = st.session_state.pins[pin]
        disabled = not connected
        
        new_state = st.checkbox(
            f"**{pin}**", 
            value=current,
            key=f"toggle_{pin}",
            disabled=disabled,
            help="Disabled when ESP offline"
        )
        
        if new_state != current and connected:
            state_str = "on" if new_state else "off"
            with st.spinner(f"Setting {pin}..."):
                try:
                    url = f"http://{ESP_IP}/set/{pin}/{state_str}"
                    r = requests.get(url, timeout=5)
                    
                    if r.status_code == 200:
                        st.session_state.pins[pin] = new_state
                        st.success(f"✅ {pin} → {'ON' if new_state else 'OFF'}")
                        time.sleep(0.5)
                        # Refresh status
                        connected, data = test_esp()
                        if connected:
                            pins_data = data.get("pins", {})
                            st.session_state.pins[pin] = bool(pins_data.get(pin, new_state))
                    else:
                        st.error(f"❌ {pin}: HTTP {r.status_code}")
                        st.session_state.pins[pin] = current
                except Exception as e:
                    st.error(f"❌ {pin}: Connection timeout")
                    st.session_state.pins[pin] = current
            
            st.rerun()

# SUMMARY METRICS
col1, col2, col3 = st.columns(3)
on_count = sum(1 for v in st.session_state.pins.values() if v)
col1.metric("🟢 ON", on_count)
col2.metric("🔴 OFF", 9-on_count)
col3.metric("📶 Connection", f"{'🟢 LIVE' if connected else '🔴 OFFLINE'}")

# CONTROLS
col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 REFRESH STATUS", type="secondary"):
        st.cache_data.clear()
        st.rerun()
with col2:
    if st.button("🧪 TEST CONNECTION"):
        connected, data = test_esp()
        if connected:
            st.balloons()
            st.success("✅ ESP RESPONDING!")
        else:
            st.error("🔴 NO RESPONSE")

st.markdown("---")
st.caption("""
**🌍 CLOUD READY** - Control ESP from anywhere!
- Powered by Streamlit Cloud
- ESP must be internet accessible (port forward/ngrok)
- Auto-detects ESP online/offline status
""")
