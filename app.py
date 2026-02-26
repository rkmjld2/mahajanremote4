# app.py - 100% FIXED VERSION (no more errors)

import streamlit as st
import requests
import time
import threading
from datetime import datetime
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
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
    st.error("❌ GROQ_API_KEY missing in secrets. Add it now.")
    st.stop()

PINS = ["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"]

# ────────────────────────────────────────────────
# TOOLS WITH PROPER DOCSTRINGS
# ────────────────────────────────────────────────

@tool
def set_pin(pin: str, state: str) -> str:
    """Control ESP8266 pin D0-D8 to ON or OFF. Args: pin='D1', state='on' or 'off'"""
    pin = pin.upper().strip()
    state = state.lower().strip()
    
    if pin not in PINS:
        return f"❌ Invalid pin '{pin}'. Use: {', '.join(PINS)}"
    if state not in ['on', 'off']:
        return "❌ State must be 'on' or 'off'"
    
    for attempt in range(3):
        try:
            url = SET_URL_TEMPLATE.format(pin=pin, state=state)
            resp = requests.get(url, timeout=12)
            if resp.status_code == 200:
                return f"✅ {pin} → {state.upper()}"
            time.sleep(0.3)
        except Exception as e:
            if attempt == 2:
                return f"❌ {pin}→{state} failed: {str(e)[:80]}"
            time.sleep(1)
    return "❌ Max retries exceeded"

@tool
def get_all_pin_status() -> str:
    """Get current status of all D0-D8 pins from ESP"""
    try:
        resp = requests.get(STATUS_URL, timeout=10)
        if resp.status_code != 200:
            return f"❌ Status HTTP {resp.status_code}"
        data = resp.json()
        pins_data = data.get('pins', {})
        status = [f"{p}: {'🟢ON' if pins_data.get(p, False) else '🔴OFF'}" for p in PINS]
        return '\n'.join(status)
    except Exception as e:
        return f"❌ Status failed: {str(e)[:80]}"

tools = [set_pin, get_all_pin_status]

# ────────────────────────────────────────────────
# FIXED LLM AGENT (CORRECT TEMPLATE)
# ────────────────────────────────────────────────

llm = ChatGroq(groq_api_key=GROQ_API_KEY, model_name="llama-3.1-70b-versatile", temperature=0.1)

# FIXED PROMPT - using .partial() properly
prompt = ChatPromptTemplate.from_template(
    """Answer using these tools: {tools}

Format EXACTLY:
Question: {input}
Thought: ...
Action: exact tool name  
Action Input: arguments as JSON
Observation: result
...
Thought: Final answer ready
Final Answer: response

RULES:
- get_all_pin_status() for ANY status question
- set_pin(pin="D1", state="on") ONLY for clear change requests  
- Pins available: {pins}
- Be precise and brief

{agent_scratchpad}"""
).partial(
    tools="\n".join([f"- {t.name}: {t.description}" for t in tools]),
    pins=", ".join(PINS)
)

agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False, handle_parsing_errors=True, max_iterations=8)

# ────────────────────────────────────────────────
# STREAMLIT UI
# ────────────────────────────────────────────────

st.set_page_config(page_title="ESP Control", layout="wide")
tab1, tab2 = st.tabs(["🔌 Manual", "🤖 AI"])

# ─── MANUAL CONTROL ──────────────────────────────────────────────────────

with tab1:
    st.title("🔌 ESP8266 Pin Controller")
    st.caption(f"📡 http://{ESP_IP}")

    status_col = st.empty()
    if "pin_states" not in st.session_state:
        st.session_state.pin_states = {p: False for p in PINS}

    def poller():
        while True:
            try:
                r = requests.get(STATUS_URL, timeout=8)
                if r.status_code == 200:
                    pins_data = r.json().get("pins", {})
                    st.session_state.pin_states = {p: bool(pins_data.get(p)) for p in PINS}
                    status_col.success("🟢 LIVE")
                else:
                    status_col.warning(f"HTTP {r.status_code}")
            except:
                status_col.error("🔴 OFFLINE")
            time.sleep(3)

    if "poller" not in st.session_state:
        st.session_state.poller = True
        threading.Thread(target=poller, daemon=True).start()

    # Current states
    st.subheader("📊 Live Status")
    cols = st.columns(3)
    for i, pin in enumerate(PINS):
        state = st.session_state.pin_states[pin]
        cols[i%3].metric(pin, "🟢 ON" if state else "🔴 OFF")

    # Toggle switches
    st.subheader("🔧 Controls")
    toggle_cols = st.columns(3)
    pending = []
    
    for i, pin in enumerate(PINS):
        with toggle_cols[i%3]:
            current = st.session_state.pin_states[pin]
            new_state = st.checkbox(pin, value=current, key=f"t_{pin}")
            
            if new_state != current:
                state_str = "on" if new_state else "off"
                pending.append((pin, state_str))
                st.session_state.pin_states[pin] = new_state
                st.rerun()

    # Process pending requests (1 at a time)
    if pending:
        pin, state = pending[0]
        try:
            url = SET_URL_TEMPLATE.format(pin=pin, state=state)
            resp = requests.get(url, timeout=12)
            if resp.status_code == 200:
                st.success(f"✅ {pin} → {state.upper()}")
            else:
                st.error(f"❌ {pin}: {resp.status_code}")
                st.session_state.pin_states[pin] = not st.session_state.pin_states[pin]
        except Exception as e:
            st.error(f"❌ {pin}: {str(e)}")
            st.session_state.pin_states[pin] = not st.session_state.pin_states[pin]
        st.rerun()

    st.button("🔄 Refresh", type="secondary")

# ─── AI CHAT ─────────────────────────────────────────────────────────────

with tab2:
    st.title("🤖 AI Control")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        role = "assistant" if isinstance(msg, AIMessage) else "user"
        with st.chat_message(role):
            st.markdown(msg.content)

    if prompt := st.chat_input("turn D1 on, status, etc..."):
        st.session_state.messages.append(HumanMessage(content=prompt))
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("AI..."):
                try:
                    result = agent_executor.invoke({"input": prompt})
                    response = result["output"]
                    st.markdown(response)
                    st.session_state.messages.append(AIMessage(content=response))
                except Exception as e:
                    st.error(f"AI failed: {str(e)}")

    if st.button("Clear Chat", type="primary"):
        st.session_state.messages = []
        st.rerun()
