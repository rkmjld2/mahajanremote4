# app.py - Complete corrected version

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
    st.error("GROQ_API_KEY not found. Please add it to Streamlit secrets.")
    st.stop()

PINS = ["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"]

# Request queue to prevent toggle spam
request_queue = []

# ────────────────────────────────────────────────
# TOOLS (improved with retries & timeout)
# ────────────────────────────────────────────────

@tool
def set_pin(pin: str, state: str) -> str:
    pin = pin.upper().strip()
    state = state.lower().strip()
    if pin not in PINS or state not in ["on", "off"]:
        return f"Invalid: pin={pin}, state={state}. Use D0-D8, on/off."
    
    for attempt in range(3):
        try:
            url = SET_URL_TEMPLATE.format(pin=pin, state=state)
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return f"✅ {pin} → {state.upper()}"
            time.sleep(0.5)
        except Exception as e:
            if attempt == 2:
                return f"❌ Failed {pin}→{state}: {str(e)[:100]}"
            time.sleep(1)
    return "Failed after retries"

@tool
def get_all_pin_status() -> str:
    try:
        r = requests.get(STATUS_URL, timeout=10)
        if r.status_code != 200:
            return f"Status error: {r.status_code}"
        data = r.json().get("pins", {})
        status = [f"{p}: {'ON' if data.get(p, False) else 'OFF'}" for p in PINS]
        return "\n".join(status)
    except Exception as e:
        return f"Status read failed: {str(e)}"

tools = [set_pin, get_all_pin_status]

# ────────────────────────────────────────────────
# LLM AGENT
# ────────────────────────────────────────────────

llm = ChatGroq(groq_api_key=GROQ_API_KEY, model_name="llama-3.1-70b-versatile", temperature=0.35, max_tokens=650)

react_prompt = ChatPromptTemplate.from_template(
    """Answer using tools. Format:
Question: {input}
Thought: ...
Action: [tool]
Action Input: ...
Observation: ...
...
Thought: Final answer
Final Answer: ...

Pins: {pins}. Time: {now}. Use get_all_pin_status for status, set_pin only for clear changes.
{agent_scratchpad}"""
).partial(pins=", ".join(PINS), now=datetime.now().strftime("%Y-%m-%d %H:%M IST"))

agent = create_react_agent(llm, tools, react_prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False, handle_parsing_errors=True, max_iterations=12)

# ────────────────────────────────────────────────
# STREAMLIT UI
# ────────────────────────────────────────────────

st.set_page_config(page_title="ESP8266 Control", layout="wide")
tab1, tab2 = st.tabs(["Manual", "AI Chat"])

# ─── TAB 1: Manual ──────────────────────────────────────────────────────

with tab1:
    st.title("🔌 ESP8266 Manual Control")
    st.caption(f"ESP IP: http://{ESP_IP} | Status: OK (per your test)")

    conn_status = st.empty()
    if "pin_states" not in st.session_state:
        st.session_state.pin_states = {p: False for p in PINS}

    def update_status():
        while True:
            try:
                r = requests.get(STATUS_URL, timeout=8)
                if r.status_code == 200:
                    pins_data = r.json().get("pins", {})
                    st.session_state.pin_states = {p: bool(pins_data.get(p, False)) for p in PINS}
                    conn_status.success("🟢 Connected")
                else:
                    conn_status.warning(f"Status: {r.status_code}")
            except:
                conn_status.error("🔴 Disconnected")
            time.sleep(3)

    if "polling" not in st.session_state:
        st.session_state.polling = True
        threading.Thread(target=update_status, daemon=True).start()

    # Current states
    st.subheader("📊 Current States")
    cols = st.columns(3)
    for i, pin in enumerate(PINS):
        state = st.session_state.pin_states[pin]
        cols[i % 3].metric(label=pin, value="ON" if state else "OFF")

    # Toggle controls with queuing
    st.subheader("🔄 Toggle Pins")
    toggle_cols = st.columns(3)
    for i, pin in enumerate(PINS):
        with toggle_cols[i % 3]:
            current = st.session_state.pin_states[pin]
            new_state = st.checkbox(pin, value=current, key=f"toggle_{pin}")
            if new_state != current:
                target_state = "on" if new_state else "off"
                # Queue request to avoid spam
                request_queue.append((pin, target_state))
                # Optimistic update
                st.session_state.pin_states[pin] = new_state
                st.rerun()

    # Process queue (1 per cycle)
    if request_queue:
        pin, state = request_queue.pop(0)
        try:
            url = SET_URL_TEMPLATE.format(pin=pin, state=state)
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                st.error(f"Toggle {pin} failed: {resp.status_code}")
                # Revert optimistic update
                st.session_state.pin_states[pin] = not st.session_state.pin_states[pin]
        except Exception as e:
            st.error(f"Toggle {pin}: {str(e)}")
            st.session_state.pin_states[pin] = not st.session_state.pin_states[pin]
        st.rerun()

    if st.button("🔄 Refresh Status", type="secondary"):
        st.rerun()

# ─── TAB 2: AI Chat ──────────────────────────────────────────────────────

with tab2:
    st.title("🤖 AI Pin Control")
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Chat history
    for msg in st.session_state.messages:
        role = "assistant" if isinstance(msg, AIMessage) else "user"
        st.chat_message(role).markdown(msg.content)

    # New message
    if prompt := st.chat_input("e.g., 'turn D1 on', 'status', 'all off'"):
        st.session_state.messages.append(HumanMessage(content=prompt))
        st.chat_message("user").markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("AI thinking..."):
                try:
                    result = agent_executor.invoke({"input": prompt})
                    response = result["output"]
                    st.markdown(response)
                    st.session_state.messages.append(AIMessage(content=response))
                except Exception as e:
                    st.error(f"AI failed: {str(e)}")

    if st.button("🗑️ Clear Chat", type="primary"):
        st.session_state.messages = []
        st.rerun()
