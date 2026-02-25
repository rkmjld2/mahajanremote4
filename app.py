import streamlit as st
import requests
import time
import threading
from datetime import datetime

from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from langchain.agents import create_react_agent, AgentExecutor

# ────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────
ESP_IP = "192.168.1.13"           # ← CHANGE THIS
STATUS_URL = f"http://{ESP_IP}/status"
SET_URL_TEMPLATE = f"http://{ESP_IP}/set/{{pin}}/{{state}}"

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") or ""
if not GROQ_API_KEY:
    st.error("GROQ_API_KEY not found. Add it to Streamlit secrets.")
    st.stop()

PINS = {
    "D0": {"gpio": "GPIO16", "note": "Wake/sleep – careful"},
    "D1": {"gpio": "GPIO5",  "note": "Safe"},
    "D2": {"gpio": "GPIO4",  "note": "Safe"},
    "D3": {"gpio": "GPIO0",  "note": "Boot HIGH – flash button"},
    "D4": {"gpio": "GPIO2",  "note": "Boot HIGH – LED often"},
    "D5": {"gpio": "GPIO14", "note": "Safe"},
    "D6": {"gpio": "GPIO12", "note": "Safe"},
    "D7": {"gpio": "GPIO13", "note": "Safe"},
    "D8": {"gpio": "GPIO15", "note": "Boot LOW"},
}

# ────────────────────────────────────────────────
# TOOLS
# ────────────────────────────────────────────────
@tool
def set_pin(pin: str, state: str) -> str:
    """Set pin like D1, D5 to 'on' or 'off'."""
    pin = pin.upper().strip()
    state = state.lower().strip()
    if pin not in PINS:
        return f"Invalid pin. Available: {', '.join(PINS.keys())}"
    if state not in ["on", "off"]:
        return "State must be 'on' or 'off'"
    try:
        url = SET_URL_TEMPLATE.format(pin=pin, state=state)
        r = requests.get(url, timeout=5)
        return f"{pin} → {state.upper()}" if r.status_code == 200 else f"ESP error: {r.text}"
    except Exception as e:
        return f"Connection failed: {str(e)}"


@tool
def get_all_pin_status() -> str:
    """Get current status of all pins."""
    try:
        r = requests.get(STATUS_URL, timeout=5)
        if r.status_code != 200:
            return f"HTTP error {r.status_code}"
        data = r.json().get("pins", {})
        return "\n".join(f"{p}: {'ON' if data.get(p, False) else 'OFF'}" for p in PINS)
    except Exception as e:
        return f"Status fetch failed: {str(e)}"


tools = [set_pin, get_all_pin_status]

# ────────────────────────────────────────────────
# LLM + ReAct Agent (classic & stable)
# ────────────────────────────────────────────────
llm = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model="llama-3.1-70b-versatile",
    temperature=0.3,
    max_tokens=600,
)

system_prompt_text = f"""You are a helpful ESP8266 assistant in Ludhiana, Punjab.
Time: {datetime.now().strftime("%Y-%m-%d %H:%M IST")}

Pins you control: {', '.join(PINS.keys())}.

Always use get_all_pin_status when asked about status.
Use set_pin only for clear on/off requests.
Be concise. Ask if unclear.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt_text),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

# Create classic ReAct agent
agent = create_react_agent(
    llm=llm,
    tools=tools,
    prompt=prompt,
)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=False,
    handle_parsing_errors=True,
    max_iterations=12,          # safety against loops
)

# ────────────────────────────────────────────────
# Streamlit App
# ────────────────────────────────────────────────
st.set_page_config(page_title="ESP8266 Groq Control", layout="wide")

tab1, tab2 = st.tabs(["Manual Control", "Chat (Natural Language)"])

# ── Manual Tab ──────────────────────────────────────────────────────
with tab1:
    st.title("ESP8266 Manual Control")
    st.caption(f"ESP IP: {ESP_IP}")

    conn_status = st.empty()

    # Init session state
    for p in PINS:
        if f"real_{p}" not in st.session_state:
            st.session_state[f"real_{p}"] = False

    def poll():
        while True:
            try:
                r = requests.get(STATUS_URL, timeout=4)
                if r.status_code == 200:
                    conn_status.success("Connected ✅")
                    data = r.json().get("pins", {})
                    for p in PINS:
                        st.session_state[f"real_{p}"] = bool(data.get(p, False))
                else:
                    conn_status.error("ESP error")
            except:
                conn_status.error("Not connected ⚠️")
            time.sleep(5)

    if "poller" not in st.session_state:
        st.session_state.poller = True
        threading.Thread(target=poll, daemon=True).start()

    st.subheader("Pin States")
    cols = st.columns(3)
    for i, (p, info) in enumerate(PINS.items()):
        val = st.session_state.get(f"real_{p}", False)
        cols[i % 3].metric(f"{p} ({info['gpio']})", "ON" if val else "OFF", help=info["note"])

    st.subheader("Toggle")
    ctrl_cols = st.columns(3)
    for i, (p, info) in enumerate(PINS.items()):
        with ctrl_cols[i % 3]:
            curr = st.session_state.get(f"real_{p}", False)
            tog = st.checkbox(p, value=curr, key=f"chk_{p}", help=info["note"])
            if tog != curr:
                s = "on" if tog else "off"
                try:
                    url = SET_URL_TEMPLATE.format(pin=p, state=s)
                    r = requests.get(url, timeout=5)
                    if r.status_code == 200:
                        st.session_state[f"real_{p}"] = tog
                        st.success(f"{p} → {s.upper()}")
                    else:
                        st.error("ESP failed")
                except Exception as e:
                    st.error(f"Error: {e}")
                st.rerun()

# ── Chat Tab ────────────────────────────────────────────────────────
with tab2:
    st.title("Natural Language Control")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        role = "assistant" if isinstance(msg, AIMessage) else "user"
        with st.chat_message(role):
            st.markdown(msg.content)

    if prompt := st.chat_input("e.g. turn D5 on, show status, all off"):
        st.session_state.messages.append(HumanMessage(content=prompt))
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    result = agent_executor.invoke({
                        "input": prompt,
                        "chat_history": st.session_state.messages[:-1],  # exclude current
                    })
                    reply = result["output"]
                    st.markdown(reply)
                    st.session_state.messages.append(AIMessage(content=reply))
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()
