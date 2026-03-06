import streamlit as st
import requests

SERVER = "https://mahajan234.pythonanywhere.com"

PINS = ["D0","D1","D2","D3","D4","D5","D6","D7","D8"]

st.set_page_config(page_title="ESP8266 Dashboard", layout="wide")

st.title("🏠 ESP8266 IoT Dashboard")

# GET STATUS
def get_status():
    try:
        r = requests.get(SERVER + "/api", timeout=5)
        return r.json()
    except:
        return None

data = get_status()

if data:
    online = data["online"]
    pins = data["pins"]
    rssi = data["rssi"]
    uptime = data["uptime"]
else:
    online = False
    pins = {p:"OFF" for p in PINS}
    rssi = 0
    uptime = 0

# STATUS
col1,col2,col3 = st.columns(3)

col1.metric("Device","🟢 ONLINE" if online else "🔴 OFFLINE")
col2.metric("WiFi RSSI",rssi)
col3.metric("Uptime",uptime)

st.divider()

st.subheader("Pin Control")

cols = st.columns(3)

for i,p in enumerate(PINS):

    with cols[i%3]:

        state = pins[p]=="ON"

        if st.toggle(p,value=state):

            requests.get(f"{SERVER}/set/{p}/ON")

        else:

            requests.get(f"{SERVER}/set/{p}/OFF")
