import streamlit as st
import requests
import time

SERVER = "https://mahajan234.pythonanywhere.com"

st.set_page_config(page_title="ESP8266 IoT", layout="wide")

st.title("🏠 ESP8266 Remote Control")

# ---------- GET DATA ----------
def get_data():
    try:
        r = requests.get(SERVER+"/api", timeout=2)
        return r.json()
    except:
        return None

data = get_data()

# ---------- DEVICE STATUS ----------
if data:

    if data["online"]:
        st.success("Device ONLINE")
    else:
        st.error("Device OFFLINE")

    st.write("WiFi:", data["rssi"], "dBm")
    st.write("Uptime:", data["uptime"], "sec")

    pins = data["pins"]

else:
    st.error("Server not reachable")
    pins={}

# ---------- TOGGLE SWITCH GRID ----------
st.subheader("GPIO Control")

cols = st.columns(3)

i=0

for pin,state in pins.items():

    with cols[i%3]:

        toggle = st.toggle(pin, value=(state=="ON"), key=pin)

        if toggle != (state=="ON"):

            new_state="ON" if toggle else "OFF"

            try:
                requests.get(f"{SERVER}/set/{pin}/{new_state}")
            except:
                pass

            time.sleep(0.3)
            st.rerun()

    i+=1

# ---------- AUTO REFRESH ----------
time.sleep(3)
st.rerun()
