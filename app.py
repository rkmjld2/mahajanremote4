import streamlit as st
import requests

SERVER = "https://mahajan234.pythonanywhere.com"

st.set_page_config(
    page_title="ESP8266 IoT Control",
    layout="wide"
)

st.title("🏠 ESP8266 Smart Switch Panel")

# ---------------------------
# Get device status
# ---------------------------
try:
    r = requests.get(SERVER + "/api", timeout=3)
    data = r.json()

    online = data["online"]
    pins = data["pins"]

except:
    st.error("Server not reachable")
    st.stop()

# ---------------------------
# Device status
# ---------------------------
if online:
    st.success("Device ONLINE")
else:
    st.error("Device OFFLINE")

st.divider()

# ---------------------------
# Pins (including D0)
# ---------------------------
pin_list = ["D0","D1","D2","D3","D4","D5","D6","D7","D8"]

cols = st.columns(3)

for i,pin in enumerate(pin_list):

    with cols[i % 3]:

        state = pins[pin] == "ON"

        toggle = st.toggle(pin, value=state)

        if toggle != state:

            new_state = "ON" if toggle else "OFF"

            try:
                requests.get(
                    f"{SERVER}/set/{pin}/{new_state}",
                    timeout=2
                )
            except:
                st.warning("Command failed")

# ---------------------------
# Auto refresh
# ---------------------------
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
