import streamlit as st
import requests
import time

SERVER = "https://mahajan234.pythonanywhere.com"

st.set_page_config(page_title="ESP8266 IoT Dashboard", layout="wide")

st.title("🏠 ESP8266 Smart Home Dashboard")

# ---------- GET DATA FROM SERVER ----------
def get_data():
    try:
        r = requests.get(SERVER+"/api", timeout=3)
        return r.json()
    except:
        return None

data = get_data()

# ---------- DEVICE STATUS ----------
if data:

    if data["online"]:
        st.success("Device Status : ONLINE")
    else:
        st.error("Device Status : OFFLINE")

    st.write("WiFi Signal:", data["rssi"])
    st.write("Uptime:", data["uptime"], "sec")

    pins = data["pins"]

else:
    st.error("Server Not Reachable")
    pins = {
    "D0":"OFF","D1":"OFF","D2":"OFF","D3":"OFF","D4":"OFF",
    "D5":"OFF","D6":"OFF","D7":"OFF","D8":"OFF"
    }

# ---------- PIN CONTROL ----------
st.subheader("GPIO Control")

cols = st.columns(3)

i = 0

for pin,state in pins.items():

    with cols[i%3]:

        st.markdown(f"### {pin}")

        if state=="ON":
            st.success("ON")
        else:
            st.warning("OFF")

        if st.button(f"Toggle {pin}", key=pin):

            new_state = "OFF" if state=="ON" else "ON"

            try:
                requests.get(f"{SERVER}/set/{pin}/{new_state}")
            except:
                pass

            time.sleep(1)
            st.rerun()

    i+=1


# ---------- AUTO REFRESH ----------
time.sleep(5)
st.rerun()
