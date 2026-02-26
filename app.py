# app.py - Fixed for Langchain + Python 3.13

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

# Global queue for toggle requests (thread-safe)
request_queue = []
queue_lock = threading.Lock()

# ────────────────────────────────────────────────
# FIXED TOOLS (proper docstrings)
# ────────────────────────────────────────────────

@tool
def set_pin(pin: str, state: str) -> str:
    """
    Control a single ESP8266 pin (D0-D8) to ON or OFF state.
    
    Args:
        pin (str): Pin name like 'D1' or 'D0'
        state (str): 'on' or 'off'
    
    Returns:
        str: Success message or error
    """
    pin = pin.upper().strip()
    state = state.lower().strip()
    
    if pin not in PINS:
        return f"❌ Invalid pin '{pin}'. Use: {', '.join(PINS)}"
    if state not in ['on', 'off']:
        return "❌ State must be 'on' or 'off'"
    
    # 3 retries with backoff
    for attempt in range(3):
        try:
            url = SET_URL_TEMPLATE.format(pin=pin, state=state)
            resp = requests.get(url, timeout=12, headers={'Connection': 'close'})
            if resp.status_code == 200:
                return f"✅ {pin} → {state.upper()}"
            elif resp.status_code == 404:
                return f"❌ Endpoint /set/{pin}/{state} not found (404). Check ESP firmware."
            time.sleep(0.3 * (attempt + 1))
        except Exception as e:
            if attempt == 2:
                return f"❌ {pin}→{state} failed: {str(e)[:80]}"
            time.sleep(1)
    return "❌ Max retries exceeded"

@tool
def get_all_pin_status() -> str:
    """
    Get current ON/OFF status of all pins D0-D8 from ESP.
    
    Returns:
        str: Formatted list like "D0: OFF\nD1: ON\n..."
    """
    try:
        resp = requests.get(STATUS_URL, timeout=10, headers={'Connection': 'close'})
        if resp.status_code != 200:
            return f"❌ Status HTTP {resp.status_code}"
        data = resp.json()
        pins_data = data.get('pins', {})
        status_lines = []
        for pin in PINS:
            is_on = pins_data.get(pin, False)
            status_lines.append(f"{pin}: {'🟢 ON' if is_on else '🔴 OFF'}")
        return '\n'.join(status_lines)
    except Exception as e:
        return f"❌ Status failed: {str(e)[:80]}"

tools = [set_pin, get_all_pin_status]

# ────────────────────────────────────────────────
# LLM AGENT (fixed prompt)
# ────────────────────────────────────────────────

llm = ChatGroq(
    groq_api_key=GROQ_API_KEY, 
    model_name="llama-3.1-70b-versatile",
    temperature=0.1,  # Lower for reliability
    max_tokens=800
)

prompt_template = """You control ESP8266 pins D0-D8. Be precise.

TOOLS: {tools}

Format EXACTLY:
Question: {input}
Thought: I should...
Action: exact tool name
Action Input: arguments as JSON
Observation: tool result
...
Thought: Got it
Final Answer: Clear response

Rules:
- ONLY use get_all_pin_status for status questions
- ONLY use set_pin for explicit "turn X on/off"
- Confirm changes: "D1 turned ON"
- If unclear: ask "Did you mean turn D1 ON?"
- Current pins: {pins_list}

{agent_scratchpad}""".format(
    tools="\n".join([f"- {t.name}: {t.description}" for t in tools]),
    pins_list=", ".join(PINS)
)

prompt = ChatPromptTemplate.from_template(prompt_template)

agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(
    agent=agent, 
    tools=tools, 
    verbose=False,
    handle_parsing_errors=True,
    max_iterations=8
)

# ────────────────────────────────────────────────
# STREAMLIT UI
# ────────────────────────────────────────────────

st.set_page_config(page_title="ESP Control", layout="wide")
tab1, tab2 = st.tabs(["🔌 Manual", "🤖 AI"])

with tab1:
    st.title("ESP8266 Pin Controller")
    st.caption(f"📡 Target: http://{ESP_IP}")

    # Connection monitor
    status_col = st.empty()
    
    # Session state init
    if "pin_states" not in st.session_state:
        st.session_state.pin_states = {p: False for p in PINS}
    if "last_update" not in st.session_state:
        st.session_state.last_update = 0

    def status_poller():
        while True:
            try:
                r = requests.get(STATUS_URL, timeout=8)
                if r.status_code == 200:
                    pins_data = r.json().get("pins", {})
                    st.session_state.pin_states = {p: bool(pins_data.get(p)) for p in PINS}
                    st.session_state.last_update = time.time()
                    status_col.success("🟢 LIVE - Connected")
                else:
                    status_col.warning(f"⚠️ HTTP {r.status_code}")
            except:
                status_col.error("🔴 No connection")
            time.sleep(2.5)

    if "poller_started" not in st.session_state:
        st.session_state.poller_started = True
        threading.Thread(target=status_poller, daemon=True).start()

    # Current status metrics
    st.subheader("📊 Live Status")
    cols = st.columns(3)
    for i, pin in enumerate(PINS):
        state = st.session_state.pin_states.get(pin, False)
        cols[i%3].metric(pin, "🟢 ON" if state else "🔴 OFF")

    # Toggle controls
    st.subheader("🔧 Toggle Pins")
    cols2 = st.columns(3)
    for i, pin in enumerate(PINS):
        with cols2[i%3]:
            current = st.session_state.pin_states[pin]
            target_on = st.checkbox(f"{pin}", value=current, key=f"cb_{pin}")
            
            if target_on != current:
                state_str = "on" if target_on else "off"
                with queue_lock:
                    request_queue.append((pin, state_str))
                # Optimistic update
                st.session_state.pin_states[pin] = target_on
                st.success(f"📤 {pin} → {state_str.upper()} queued")
                st.rerun()

    # Process queue safely
    if request_queue:
        with queue_lock:
            if request_queue:
                pin, state = request_queue.pop(0)
        try:
            url = SET_URL_TEMPLATE.format(pin=pin, state=state)
            r = requests.get(url, timeout=12)
            if r.status_code == 200:
                st.balloons()
            else:
                st.error(f"{pin} failed: {r.status_code}")
                st.session_state.pin_states[pin] = not st.session_state.pin_states[pin]
        except Exception as e:
            st.error(f"{pin}: {str(e)}")
            st.session_state.pin_states[pin] = not st.session_state.pin_states[pin]
        st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Force Refresh", type="secondary"):
            st.rerun()
    with col2:
        st.info(f"Queue: {len(request_queue)} | Last sync: {time.time() - st.session_state.last_update:.0f}s ago")

with tab2:
    st.title("🤖 Natural Language Control")
    
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Render chat
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if user_input := st.chat_input("Ask: 'turn D1 on' or 'what's the status?'"):
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("AI processing..."):
                try:
                    result = agent_executor.invoke({"input": user_input})
                    ai_reply = result["output"]
                    st.markdown(ai_reply)
                    st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})
                except Exception as e:
                    st.error(f"AI error: ```{str(e)}```")

    if st.button("🗑️ Clear Chat", type="primary"):
        st.session_state.chat_history = []
        st.rerun()
