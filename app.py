import streamlit as st
import requests

SERVER = "https://mahajan234.pythonanywhere.com"

st.set_page_config(
    page_title="ESP8266 IoT Dashboard",
    layout="wide"
)

st.title("🏠 ESP8266 Smart Control")

# -------------------------------
# Get device status
# -------------------------------
try:
    r = requests.get(SERVER + "/api", timeout=3)
    data = r.json()

    online = data["online"]
    pins = data["pins"]
    rssi = data["rssi"]
    uptime = data["uptime"]

except:
    st.error("Server not reachable")
    st.stop()

# -------------------------------
# Device status
# -------------------------------
if online:
    st.success("Device ONLINE")
else:
    st.error("Device OFFLINE")

st.write(f"📶 WiFi RSSI: {rssi}")
st.write(f"⏱ Uptime: {uptime}")

st.divider()

# -------------------------------
# Pin Controls
# -------------------------------
cols = st.columns(3)

pin_list = ["D1","D2","D3","D4","D5","D6","D7","D8"]

for i,pin in enumerate(pin_list):

    with cols[i % 3]:

        current_state = pins[pin] == "ON"

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

        if current_state:
            st.success("ON")
        else:
            st.info("OFF")

# -------------------------------
# Auto refresh
# -------------------------------
st.caption("Auto refresh every 3 seconds")

st.markdown(
"""
<script>
setTimeout(function(){
window.location.reload();
},3000);
</script>
""",
unsafe_allow_html=True
)
