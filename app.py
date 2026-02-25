import streamlit as st
import requests
import time
import threading
from datetime import datetime

from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

# ────────────────────────────────────────────────
# CONFIG – CHANGE THESE
# ────────────────────────────────────────────────
ESP_IP = "192.168.1.13"           # ← your ESP8266 IP here
STATUS_URL = f"http://{ESP_IP}/status"
SET_URL_TEMPLATE = f"http://{ESP_IP}/set/{{pin}}/{{state}}"

# Get Groq API key (Streamlit secrets preferred)
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") or ""
if not GROQ_API_KEY:
    st.error("GROQ_API_KEY not found. Add it to Streamlit secrets or environment variables.")
    st.stop()

# Pin definitions (must match ESP firmware)
PINS = {
    "D0": {"gpio": "GPIO16", "note": "Wake/sleep – use carefully"},
    "D1": {"gpio": "GPIO5",  "note": "Safe general purpose"},
    "D2": {"gpio": "GPIO4",  "note": "Safe general purpose"},
    "D3": {"gpio": "GPIO0",  "note": "Boot HIGH – flash button"},
    "D4": {"gpio": "GPIO2",  "note": "Boot HIGH – often built-in LED"},
    "D5": {"gpio": "GPIO14", "note": "Safe – SPI CLK"},
    "D6": {"gpio": "GPIO12", "note": "Safe – SPI MISO"},
    "D7": {"gpio": "GPIO13", "note": "Safe – SPI MOSI"},
    "D8": {"gpio": "GPIO15", "note": "Boot LOW – pulled down"},
}

# ────────────────────────────────────────────────
# TOOLS
# ────────────────────────────────────────────────
@tool
def set_pin(pin: str, state: str) -> str:
    """Set ESP8266 pin to ON or OFF. Pin like D1, D5. State = 'on' or 'off'."""
    pin = pin.upper().strip()
    state = state.lower().strip()

    if pin not in PINS:
        return f"Error: Unknown pin '{pin}'. Available: {', '.join(PINS.keys())}"

    if state not in ["on", "off"]:
        return "Error: state must be 'on' or 'off'"

    try:
        url = SET_URL_TEMPLATE.format(pin=pin, state=state)
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return f"Success: {pin} set to {state.upper()}"
        else:
            return f"ESP error: {resp.text} (HTTP {resp.status_code})"
    except Exception as e:
        return f"Connection failed: {str(e)}"


@tool
def get_all_pin_status() -> str:
    """Get current ON/OFF status of all ESP8266 pins."""
    try:
        r = requests.get(STATUS_URL, timeout=5)
        if r.status_code != 200:
            return f"Error: HTTP {r.status_code}"
        data = r.json()
        pins_data = data.get("pins", {})
        lines = [f"{p}: {'ON' if pins_data.get(p, False) else 'OFF'}" for p in PINS]
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to fetch status: {str(e)}"


tools = [set_pin, get_all_pin_status]

# ────────────────────────────────────────────────
# LLM & Agent (fixed – no state_modifier)
# ────────────────────────────────────────────────
llm = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model="llama-3.1-70b-versatile",
    temperature=0.3,
    max_tokens=600,
)

# System prompt as messages_modifier (string or list of messages)
system_prompt = f"""You are a helpful ESP8266 smart home assistant running in Ludhiana, Punjab.
Current date/time: {datetime.now().strftime("%Y-%m-%d %H:%M IST")}

You control these pins: {', '.join(PINS.keys())}.

Rules:
- Use get_all_pin_status to check current states when asked about status.
- Use set_pin only when the user clearly wants to change a pin (turn on/off/set).
- Be concise and friendly.
- If command is unclear, ask for clarification.
- Never assume pin states — always check with tool if needed.
"""

from langgraph.prebuilt import create_react_agent

agent_executor = create_react_agent(
    model=llm,
    tools=tools,
    messages_modifier=system_prompt,   # ← this is the correct parameter
    # checkpointer=...   # optional if you want persistence later
)

# ────────────────────────────────────────────────
# Streamlit UI
# ────────────────────────────────────────────────
st.set_page_config(page_title="ESP8266 Groq Control", layout="wide")

tab1, tab2 = st.tabs(["Manual Pin Control", "Natural Language (Groq)"])

# ── Tab 1: Manual ───────────────────────────────────────────────────
with tab1:
    st.title("ESP8266 Manual Control")
    st.caption(f"Connected to ESP at: {ESP_IP}")

    conn_indicator = st.empty()

    for pin in PINS:
        if f"real_{pin}" not in st.session_state:
            st.session_state[f"real_{pin}"] = False

    def poll_esp_status():
        while True:
            try:
                r = requests.get(STATUS_URL, timeout=4)
                if r.status_code == 200:
                    conn_indicator.success("ESP8266 Connected ✅")
                    pins_data = r.json().get("pins", {})
                    for pin in PINS:
                        st.session_state[f"real_{pin}"] = bool(pins_data.get(pin, False))
                else:
                    conn_indicator.error(f"ESP error: HTTP {r.status_code}")
            except:
                conn_indicator.error("ESP Not Connected ⚠️")
            time.sleep(5)

    if "poller_started" not in st.session_state:
        st.session_state.poller_started = True
        threading.Thread(target=poll_esp_status, daemon=True).start()

    st.subheader("Current Pin States")
    cols = st.columns(3)
    for i, (pin, info) in enumerate(PINS.items()):
        state = st.session_state.get(f"real_{pin}", False)
        cols[i % 3].metric(
            label=f"{pin} ({info['gpio']})",
            value="ON" if state else "OFF",
            help=info["note"]
        )

    st.subheader("Toggle Pins")
    ctrl_cols = st.columns(3)
    for i, (pin, info) in enumerate(PINS.items()):
        col = ctrl_cols[i % 3]
        with col:
            current = st.session_state.get(f"real_{pin}", False)
            toggled = st.checkbox(
                label=pin,
                value=current,
                key=f"toggle_{pin}",
                help=info["note"]
            )
            if toggled != current:
                new_state = "on" if toggled else "off"
                try:
                    url = SET_URL_TEMPLATE.format(pin=pin, state=new_state)
                    resp = requests.get(url, timeout=5)
                    if resp.status_code == 200:
                        st.session_state[f"real_{pin}"] = toggled
                        st.success(f"{pin} → {new_state.upper()}")
                    else:
                        st.error("ESP rejected command")
                except Exception as e:
                    st.error(f"Failed to send: {e}")
                st.rerun()

# ── Tab 2: Groq Chat ────────────────────────────────────────────────
with tab2:
    st.title("Control ESP8266 with Natural Language")

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    for message in st.session_state.chat_messages:
        role = "assistant" if isinstance(message, AIMessage) else "user"
        with st.chat_message(role):
            st.markdown(message.content)

    if user_input := st.chat_input("e.g. turn D5 on, status of D1, all off..."):
        st.session_state.chat_messages.append(HumanMessage(content=user_input))
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = agent_executor.invoke(
                        {"messages": st.session_state.chat_messages}
                    )
                    ai_reply = response["messages"][-1].content
                    st.markdown(ai_reply)
                    st.session_state.chat_messages.append(AIMessage(content=ai_reply))
                except Exception as e:
                    st.error(f"Agent error: {str(e)}")

    if st.button("Clear Conversation"):
        st.session_state.chat_messages = []
        st.rerun()
