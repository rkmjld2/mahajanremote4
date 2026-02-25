import streamlit as st
import requests
import time
import threading
from datetime import datetime

from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage

# ────────────────────────────────────────────────
# CONFIG – CHANGE THESE
# ────────────────────────────────────────────────
ESP_IP = "192.168.1.13"           # your ESP8266 IP
STATUS_URL = f"http://{ESP_IP}/status"
SET_URL_TEMPLATE = f"http://{ESP_IP}/set/{{pin}}/{{state}}"

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    st.error("GROQ_API_KEY not found. Add it to Streamlit secrets or environment variables.")
    st.stop()

# Pin definitions (same as ESP firmware)
PINS = {
    "D0": {"gpio": "GPIO16", "note": "Wake/sleep"},
    "D1": {"gpio": "GPIO5",  "note": "Safe"},
    "D2": {"gpio": "GPIO4",  "note": "Safe"},
    "D3": {"gpio": "GPIO0",  "note": "Boot HIGH / Flash"},
    "D4": {"gpio": "GPIO2",  "note": "Boot HIGH / LED"},
    "D5": {"gpio": "GPIO14", "note": "Safe"},
    "D6": {"gpio": "GPIO12", "note": "Safe"},
    "D7": {"gpio": "GPIO13", "note": "Safe"},
    "D8": {"gpio": "GPIO15", "note": "Boot LOW"},
}

# ────────────────────────────────────────────────
# TOOLS – these are what the LLM can call
# ────────────────────────────────────────────────
@tool
def set_pin(pin: str, state: str) -> str:
    """Set a specific ESP8266 pin to ON or OFF. Pin must be like 'D1', 'D5'. State must be 'on' or 'off'."""
    pin = pin.upper().strip()
    state = state.lower().strip()

    if pin not in PINS:
        return f"Error: Unknown pin {pin}. Available: {', '.join(PINS.keys())}"

    if state not in ["on", "off"]:
        return "Error: state must be 'on' or 'off'"

    try:
        url = SET_URL_TEMPLATE.format(pin=pin, state=state)
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200:
            return f"Success: {pin} set to {state.upper()}"
        else:
            return f"Error from ESP: {resp.text} (code {resp.status_code})"
    except Exception as e:
        return f"Connection failed: {str(e)}"

@tool
def get_all_pin_status() -> str:
    """Get current ON/OFF status of all ESP8266 pins."""
    try:
        r = requests.get(STATUS_URL, timeout=4)
        if r.status_code != 200:
            return f"Error: status code {r.status_code}"
        data = r.json()
        pins = data.get("pins", {})
        lines = []
        for p in PINS:
            val = pins.get(p, False)
            lines.append(f"{p}: {'ON' if val else 'OFF'}")
        return "\n".join(lines)
    except Exception as e:
        return f"Failed to get status: {str(e)}"

tools = [set_pin, get_all_pin_status]

# ────────────────────────────────────────────────
# LLM + Agent setup
# ────────────────────────────────────────────────
llm = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model="llama-3.1-70b-versatile",   # or "mixtral-8x7b-32768", "gemma2-9b-it" etc.
    temperature=0.4,
    max_tokens=512,
)

system_prompt = f"""You are a helpful ESP8266 smart home assistant.
You control pins: {', '.join(PINS.keys())}.

Use tools to:
- Get current status → get_all_pin_status
- Change pin state → set_pin (only call when user clearly wants to change something)

Be concise. If user asks status → use tool. If unclear → ask for clarification.
Current time: {datetime.now().strftime("%Y-%m-%d %H:%M IST")}
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=False,          # change to True for debugging
    handle_parsing_errors=True,
)

# ────────────────────────────────────────────────
# Streamlit UI
# ────────────────────────────────────────────────
st.set_page_config(page_title="ESP8266 Groq Control", layout="wide")

tab1, tab2 = st.tabs(["📟 Manual Control", "🗣️ Natural Language (Groq + LangChain)"])

# ── Tab 1: Manual (same as before, slightly cleaned) ────────────────
with tab1:
    st.title("ESP8266 Manual Pin Control")
    st.caption(f"ESP at: http://{ESP_IP}")

    conn_status = st.empty()
    status_cols = st.columns(3)

    # Poll function
    def poll_esp():
        while True:
            try:
                r = requests.get(STATUS_URL, timeout=3)
                if r.status_code == 200:
                    conn_status.success("Connected ✅")
                    pins_data = r.json().get("pins", {})
                    for lbl, info in PINS.items():
                        val = pins_data.get(lbl, False)
                        st.session_state[f"real_{lbl}"] = val
                else:
                    conn_status.error("ESP returned error")
            except:
                conn_status.error("Not connected ⚠️")
            time.sleep(5)

    if "poller_running" not in st.session_state:
        st.session_state.poller_running = True
        threading.Thread(target=poll_esp, daemon=True).start()

    # Show statuses
    for i, (lbl, info) in enumerate(PINS.items()):
        real_state = st.session_state.get(f"real_{lbl}", False)
        col = status_cols[i % 3]
        col.metric(f"{lbl} ({info['gpio']})", "ON" if real_state else "OFF", help=info["note"])

    # Controls
    st.subheader("Toggle Pins")
    ctrl_cols = st.columns(3)
    for i, (lbl, info) in enumerate(PINS.items()):
        col = ctrl_cols[i % 3]
        with col:
            curr = st.session_state.get(f"real_{lbl}", False)
            tog = st.checkbox(lbl, value=curr, key=f"chk_{lbl}", help=info["note"])
            if tog != curr:
                state_str = "on" if tog else "off"
                try:
                    url = SET_URL_TEMPLATE.format(pin=lbl, state=state_str)
                    r = requests.get(url, timeout=4)
                    if r.status_code == 200:
                        st.session_state[f"real_{lbl}"] = tog
                        st.success(f"{lbl} → {state_str.upper()}")
                    else:
                        st.error("ESP failed")
                        st.rerun()
                except:
                    st.error("Connection failed")
                    st.rerun()

# ── Tab 2: Natural Language Chat ───────────────────────────────────
with tab2:
    st.title("Talk to your ESP8266 (Groq Agent)")

    # Chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        role = "assistant" if isinstance(msg, AIMessage) else "user"
        with st.chat_message(role):
            st.markdown(msg.content)

    # Input
    if prompt := st.chat_input("e.g. turn D5 on, status of D1 and D2, all off..."):
        st.session_state.messages.append(HumanMessage(content=prompt))
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = agent_executor.invoke({
                        "input": prompt,
                        "chat_history": st.session_state.messages,
                    })
                    answer = response["output"]
                    st.markdown(answer)
                    st.session_state.messages.append(AIMessage(content=answer))
                except Exception as e:
                    st.error(f"Agent error: {str(e)}")

    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()
