import streamlit as st
import requests
import re
import json
import time

# ─── DYNAMIC IP CONFIG ───
if "ESP_IP" not in st.session_state:
    st.session_state.ESP_IP = "192.168.1.13"  # Default

# MANUAL IP INPUT
st.title("🌐 ESP8266 REMOTE CONTROL")
col1, col2 = st.columns([2, 1])

with col1:
    new_ip = st.text_input(
        "ESP IP Address", 
        value=st.session_state.ESP_IP,
        help="Enter ESP IP (local or public/ngrok)"
    )
    
    if st.button("📡 SET IP & CONNECT", type="primary") and new_ip.strip():
        st.session_state.ESP_IP = new_ip.strip()
        st.cache_data.clear()
        st.rerun()

ESP_IP = st.session_state.ESP_IP
STATUS_URL = f"http://{ESP_IP}/status"
PINS = ["D0","D1","D2","D3","D4","D5","D6","D7","D8"]

# ─── JSON FIXER ───
def fix_json(raw):
    cleaned = re.sub(r',\s*}', '}', raw)
    cleaned = re.sub(r',\s*]', ']', cleaned)
    try:
        return json.loads(cleaned)
    except:
        return {"pins": {p: False for p in PINS}}

# ─── CONNECTION TEST ───
@st.cache_data(ttl=5)
def test_esp():
    try:
        r = requests.get(STATUS_URL, timeout=5)
        return r.status_code == 200, fix_json(r.text) if r.status_code == 200 else None
    except:
        return False, None

# ─── STATUS DISPLAY ───
connected, data = test_esp()
status_emoji = "🟢 LIVE" if connected else "🔴 OFFLINE"

st.subheader(f"📶 Status: **{status_emoji}** → `{ESP_IP}`")

if "pins" not in st.session_state:
    st.session_state.pins = {p: False for p in PINS}

if connected:
    pins_data = data.get("pins", {})
    st.session_state.pins = {k: bool(pins_data.get(k, False)) for k in PINS}

# ─── LIVE PINS ───
st.subheader("📊 PIN STATES")
cols = st.columns(3)
for i, pin in enumerate(PINS):
    state = st.session_state.pins[pin]
    cols[i%3].metric(pin, "🟢 ON" if state else "🔴 OFF")

# ─── PIN CONTROLS ───
st.subheader("🔧 PIN TOGGLES")
toggle_cols = st.columns(3)
for i, pin in enumerate(PINS):
    with toggle_cols[i%3]:
        current = st.session_state.pins[pin]
        disabled = not connected
        
        new_state = st.checkbox(
            f"**{pin}**", 
            value=current,
            key=f"t_{pin}_{ESP_IP}",  # Unique key per IP
            disabled=disabled,
            help="Toggle when 🟢 LIVE"
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
                        # Verify change
                        connected, data = test_esp()
                        if connected:
                            st.session_state.pins[pin] = bool(data["pins"].get(pin, new_state))
                    else:
                        st.error(f"❌ HTTP {r.status_code}")
                except Exception as e:
                    st.error(f"❌ Connection failed")
            st.rerun()

# ─── SUMMARY ───
col1, col2, col3 = st.columns(3)
on_count = sum(st.session_state.pins.values())
col1.metric("🟢 ON", on_count)
col2.metric("🔴 OFF", 9-on_count)
col3.metric("Status", status_emoji)

# ─── CONTROLS ───
col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 REFRESH"):
        st.cache_data.clear()
        st.rerun()
with col2:
    if st.button("🧪 PING ESP"):
        connected, _ = test_esp()
        if connected:
            st.success("✅ ESP ALIVE!")
            st.balloons()
        else:
            st.error("🔴 NO RESPONSE")

# ─── HELP ───
with st.expander("ℹ️ HELP - Common IPs"):
    st.markdown("""
    **Local Network:**
    ```
    192.168.1.13    (your ESP)
    192.168.0.x
    10.0.0.x
    ```
    
    **Remote Access:**
    ```
    ngrok: https://abc123.ngrok.io → abc123.ngrok.io
    Public IP: 203.0.113.50
    ```
    
    **Find ESP IP:**
    1. Router → Connected Devices
    2. Serial Monitor → "IP: xxx.xxx.xxx.xxx"
    3. `nmap -sn 192.168.1.0/24`
    """)

st.caption("👆 Enter ESP IP → Click **SET IP & CONNECT** → 🟢 GREEN = READY!")
