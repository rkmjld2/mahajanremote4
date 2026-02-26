# app.py - READY TO TEST WITH YOUR ngrok URL
import streamlit as st
import requests
import re
import json
import time

# YOUR ngrok URL - DIRECTLY BUILT-IN
ESP_IP =  "5967-2401-4900-8910-8704-2148-89f0-1383-cfb6.ngrok-free.app"
STATUS_URL = f"http://{ESP_IP}/status"
PINS = ["D0","D1","D2","D3","D4","D5","D6","D7","D8"]

st.set_page_config(page_title="ESP Control", layout="wide")
st.title("🌐 ESP8266 REMOTE CONTROL")

st.success(f"🔗 Using ngrok: **{ESP_IP}**")
st.caption("✅ Keep ngrok running on PC | 🟢 Green = ESP LIVE")

# Fix ESP JSON (trailing comma bug)
def fix_json(raw):
    cleaned = re.sub(r',\s*}', '}', raw)
    cleaned = re.sub(r',\s*]', ']', cleaned)
    try:
        return json.loads(cleaned)
    except:
        return {"pins": {p: False for p in PINS}}

# Test ESP connection
@st.cache_data(ttl=5)
def test_esp():
    try:
        r = requests.get(STATUS_URL, timeout=10)
        return r.status_code == 200, fix_json(r.text) if r.status_code == 200 else None
    except:
        return False, None

# CONNECTION STATUS
connected, data = test_esp()
status_emoji = "🟢 LIVE" if connected else "🔴 OFFLINE"

col1, col2 = st.columns([3,1])
with col1:
    st.metric("ESP Status", status_emoji, f"ngrok: {ESP_IP}")
with col2:
    st.caption(f"Ping: {time.strftime('%H:%M:%S')}")

# Pin states
if "pins" not in st.session_state:
    st.session_state.pins = {p: False for p in PINS}

if connected:
    pins_data = data.get("pins", {})
    st.session_state.pins = {k: bool(pins_data.get(k, False)) for k in PINS}

# LIVE PIN DISPLAY
st.subheader("📊 LIVE PINS")
cols = st.columns(3)
for i, pin in enumerate(PINS):
    state = st.session_state.pins[pin]
    cols[i%3].metric(pin, "🟢 ON" if state else "🔴 OFF")

# PIN TOGGLES
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
            disabled=disabled,
            help="🟢 Green = Click to toggle"
        )
        
        if new_state != current and connected:
            state_str = "on" if new_state else "off"
            with st.spinner(f"Setting {pin}..."):
                try:
                    url = f"http://{ESP_IP}/set/{pin}/{state_str}"
                    r = requests.get(url, timeout=10)
                    
                    if r.status_code == 200:
                        st.session_state.pins[pin] = new_state
                        st.success(f"✅ {pin} → {'ON' if new_state else 'OFF'}")
                        time.sleep(0.5)
                        # Verify change
                        connected, data = test_esp()
                        if connected:
                            pins_data = data.get("pins", {})
                            st.session_state.pins[pin] = bool(pins_data.get(pin, new_state))
                    else:
                        st.error(f"❌ HTTP {r.status_code}")
                        st.session_state.pins[pin] = current
                except Exception as e:
                    st.error(f"❌ Connection error")
                    st.session_state.pins[pin] = current
            
            st.rerun()

# SUMMARY METRICS
col1, col2, col3 = st.columns(3)
on_count = sum(st.session_state.pins.values())
col1.metric("🟢 ON", on_count)
col2.metric("🔴 OFF", 9-on_count)
col3.metric("Status", status_emoji)

# CONTROL BUTTONS
col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 REFRESH STATUS", type="secondary"):
        st.cache_data.clear()
        st.rerun()
with col2:
    if st.button("🧪 TEST CONNECTION"):
        connected, _ = test_esp()
        if connected:
            st.success("✅ ESP ALIVE!")
            st.balloons()
        else:
            st.error("🔴 ngrok stopped?")

st.markdown("---")
st.info("""
**✅ STATUS GUIDE:**
🟢 LIVE = ESP + ngrok running → Toggle pins!
🔴 OFFLINE = Check:
1. ngrok running? (`ngrok http 192.168.1.13:80`)
2. ESP powered?
3. PC + ESP same WiFi?

**🌍 GLOBAL CONTROL:** Phone data → toggle D1 → ESP LED lights up anywhere!
""")


