import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh

SERVER = "https://mahajan234.pythonanywhere.com"

st.set_page_config(page_title="ESP8266 IoT Dashboard", layout="wide")

# Auto refresh every 5 seconds
st_autorefresh(interval=5000, key="refresh")

st.title("ESP8266 Remote Control Dashboard")

# Get device status
try:
    r = requests.get(SERVER + "/status", timeout=3)
    data = r.json()

    online = data["online"]
    pins = data["pins"]

except:
    online = False
    pins = {}

# Device status display
if online:
    st.success("Device ONLINE")
else:
    st.error("Device OFFLINE")

# Pins
pin_list = ["D0","D1","D2","D3","D4","D5","D6","D7","D8"]

cols = st.columns(3)

for i,p in enumerate(pin_list):

    with cols[i%3]:

        state = pins.get(p,"OFF")

        st.write("###",p)

        if st.button(f"{p} ON"):
            requests.get(f"{SERVER}/set/{p}/ON")

        if st.button(f"{p} OFF"):
            requests.get(f"{SERVER}/set/{p}/OFF")

        st.write("State:",state)
