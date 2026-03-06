import streamlit as st
import time

st.set_page_config(page_title="ESP8266 IoT Dashboard", layout="wide")

# --------------------------
# GLOBAL PIN STATES
# --------------------------

if "pins" not in st.session_state:
    st.session_state.pins={
        "D0":"OFF","D1":"OFF","D2":"OFF","D3":"OFF","D4":"OFF",
        "D5":"OFF","D6":"OFF","D7":"OFF","D8":"OFF"
    }

if "last_seen" not in st.session_state:
    st.session_state.last_seen=0

if "wifi_rssi" not in st.session_state:
    st.session_state.wifi_rssi=0

if "uptime" not in st.session_state:
    st.session_state.uptime=0


pins=st.session_state.pins

# --------------------------
# CHECK DEVICE ONLINE
# --------------------------

online=False
if time.time()-st.session_state.last_seen < 10:
    online=True

# --------------------------
# HEADER
# --------------------------

st.title("🏠 Smart Home IoT Dashboard")

col1,col2,col3=st.columns(3)

if online:
    col1.success("Device ONLINE")
else:
    col1.error("Device OFFLINE")

col2.metric("WiFi Signal", st.session_state.wifi_rssi)
col3.metric("Uptime", st.session_state.uptime)

st.divider()

# --------------------------
# PIN CONTROL GRID
# --------------------------

cols=st.columns(3)

i=0
for p in pins:

    with cols[i%3]:

        st.subheader(p)

        state=st.toggle(
            "Switch",
            value=(pins[p]=="ON"),
            key=p
        )

        pins[p]="ON" if state else "OFF"

    i+=1


# --------------------------
# COMMAND STRING FOR ESP8266
# --------------------------

cmd=",".join([f"{p}:{pins[p]}" for p in pins])

st.divider()

st.subheader("ESP8266 Command API")

st.code(cmd)

st.write("ESP8266 should fetch this command string from the Streamlit endpoint.")

# --------------------------
# DEVICE UPDATE SECTION
# --------------------------

st.divider()
st.subheader("Device Update")

rssi=st.number_input("WiFi RSSI",value=0)
uptime=st.number_input("Device Uptime",value=0)

if st.button("Update Device Status"):

    st.session_state.last_seen=time.time()
    st.session_state.wifi_rssi=rssi
    st.session_state.uptime=uptime

    st.success("Device Updated")
