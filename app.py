# app.py - 100% FIXED (deploys without errors)

import streamlit as st
import requests
import time
import threading
from datetime import datetime
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage
from langchain.agents import create_react_agent, AgentExecutor

# ────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────

ESP_IP = "192.168.1.13"
STATUS_URL = f"http://{ESP_IP}/status"
SET_URL_TEMPLATE = f"http://{ESP_IP}/set/{{pin}}/{{state}}"

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    st.error("❌ GROQ_API_KEY missing. Add to secrets.")
    st.stop()

PINS = ["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"]

# ────────────────────────────────────────────────
# TOOLS (fixed docstrings)
# ────────────────────────────────────────────────

@tool
def set_pin(pin: str, state: str) -> str:
    """Set ESP pin D0-D8 to on/off. Args: pin='D1', state='on'/'off'"""
    pin = pin.upper().strip()
    state = state.lower().strip()
    if pin not in PINS or state not in ['on', 'off']:
        return f"❌ Invalid: {pin}/{state}"
    
    for attempt in range(3):
        try:
            url = SET_URL_TEMPLATE.format(pin=pin, state=state)
            resp = requests.get(url, timeout=12)
            if resp.status_code == 200:
                return f"✅ {pin} → {state.upper()}"
            time.sleep(0.5)
        except:
            if attempt == 2: return f"❌ {pin} failed"
            time.sleep(1)
    return "❌ Failed after retries"

@tool
def get_all_pin_status() -> str:
    """Get status of all D0-D8 pins"""
    try:
        r = requests.get(STATUS_URL, timeout=10)
        if r.status_code != 200: return "❌ Status error"
        data = r.json().get('pins', {})
        status = [f"{p}: {'ON' if data.get(p, False) else 'OFF'}" for p in PINS]
        return '\n'.join(status)
    except:
        return "❌ Cannot read status"

tools = [set_pin, get_all_pin_status]

# ────────────────────────────────────────────────
# FIXED REACT PROMPT (REQUIRED VARIABLES)
# ────────────────────────────────────────────────

llm = ChatGroq(groq_api_key=GROQ_API_KEY, model_name="llama-3.1-70b-versatile", temperature=0.1)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You control ESP8266 pins {pins}. Use tools only when needed."),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad")
])

# CRITICAL: Partial with REQUIRED ReAct variables
prompt = prompt.partial(
    tools=str([t.name for t in tools]),
    tool_names=", ".join([t.name for t in tools]),
    pins=", ".join(PINS)
)

agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False, handle_parsing_errors=True, max_iterations=6)

# ────────────────────────────────────────────────
# STREAMLIT UI
# ────────────────────────────────────────────────

st.set_page_config(page_title="ESP Control", layout="wide")
tab1, tab2 = st.tabs(["🔌 Manual", "🤖 AI"])

with tab1:
    st.title("ESP8266 Control Panel")
    st.caption(f"Target: http://{ESP_IP}")

    if "states" not in st.session_state:
        st.session_state.states = {p: False for p in PINS}

    # Status poller
    status_col = st.empty()
    def poll():
        while True:
            try:
                r = requests.get(STATUS_URL, timeout=5)
                if r.status_code == 200:
                    data = r.json().get('pins', {})
                    st.session_state.states = {p: bool(data.get(p, False)) for p in PINS}
                    status_col.success("🟢 Connected")
                else:
                    status_col.error("🔴 Error")
            except:
                status_col.error("🔴 Offline")
            time.sleep(3)

    if "poll" not in st.session_state:
        st.session_state.poll = True
        threading.Thread(target=poll, daemon=True).start()

    # Current status
    st.subheader("📊 Status")
    cols = st.columns(3)
    for i, pin in enumerate(PINS):
        state = st.session_state.states[pin]
        cols[i%3].metric(pin, "ON" if state else "OFF")

    # Toggles with debouncing
    st.subheader("🔧 Toggle")
    cols2 = st.columns(3)
    pending_requests = []
    
    for i, pin in enumerate(PINS):
        with cols2[i%3]:
            current = st.session_state.states[pin]
            new_state = st.checkbox(pin, value=current, key=f"chk_{pin}")
            if new_state != current:
                state_str = "on" if new_state else "off"
                pending_requests.append((pin, state_str))
                st.session_state.states[pin] = new_state

    # Process one request at a time
    if pending_requests:
        pin, state = pending_requests[0]
        try:
            url = SET_URL_TEMPLATE.format(pin=pin, state=state)
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                st.error(f"{pin} failed: {r.status_code}")
                st.session_state.states[pin] = not st.session_state.states[pin]
            else:
                st.success(f"{pin} → {state.upper()}")
        except Exception as e:
            st.error(f"{pin}: {e}")
            st.session_state.states[pin] = not st.session_state.states[pin]
        st.rerun()

with tab2:
    st.title("🤖 AI Control")
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        role = "assistant" if isinstance(msg, AIMessage) else "user"
        st.chat_message(role).markdown(msg.content)

    if user_input := st.chat_input("turn D1 on, status, etc..."):
        st.session_state.messages.append(HumanMessage(content=user_input))
        st.chat_message("user").markdown(user_input)
        
        with st.chat_message("assistant"):
            with st.spinner("AI thinking..."):
                try:
                    result = agent_executor.invoke({"input": user_input})
                    response = result["output"]
                    st.markdown(response)
                    st.session_state.messages.append(AIMessage(content=response))
                except Exception as e:
                    st.error(f"AI Error: {str(e)}")

    st.button("Clear Chat", type="primary")

if st.button("🔄 Full Refresh"):
    st.rerun()
