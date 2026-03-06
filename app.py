import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh

SERVER = "https://mahajan234.pythonanywhere.com"

st.set_page_config(page_title="ESP8266 IoT Dashboard", layout="wide")

st.title("🏠 ESP8266 Smart Home Control")

# auto refresh every 2 sec
st_autorefresh(interval=2000, key="datarefresh")

# -------------------------
# Fetch device data
# -------------------------

try:
    r = requests.get(SERVER + "/api", timeout=2)
    data = r.json()

    online = data["online"]
    pins = data["pins"]
    rssi = data["rssi"]
    uptime = data["uptime"]

except:
    st.error("Server not reachable")
    st.stop()

# -------------------------
# Device status section
# -------------------------

col1, col2, col3 = st.columns(3)

with col1:
    if online:
        st.success("Device ONLINE")
    else:
        st.error("Device OFFLINE")

with col2:
    st.metric("WiFi Signal", f"{rssi} dBm")

with col3:
    st.metric("Uptime", f"{uptime} sec")

st.divider()

# -------------------------
# Pin control grid
# -------------------------

pins_list = ["D0","D1","D2","D3","D4","D5","D6","D7","D8"]

cols = st.columns(3)

for i, pin in enumerate(pins_list):

    with cols[i % 3]:

        current_state = pins.get(pin) == "ON"

        toggle = st.toggle(pin, value=current_state)

        if toggle != current_state:

            new_state = "ON" if toggle else "OFF"

            try:
                requests.get(
                    f"{SERVER}/set/{pin}/{new_state}",
                    timeout=2
                )
            except:
                st.warning("Command failed")
