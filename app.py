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
# CONFIG – CHANGE THIS
# ────────────────────────────────────────────────
ESP_IP = "192.168.1.13"           # your ESP IP
STATUS_URL = f"http://{ESP_IP}/status"
SET_URL_TEMPLATE = f"http://{ESP_IP}/set/{{pin}}/{{state}}"

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") or ""
if not GROQ_API_KEY:
    st.error("GROQ_API_KEY missing → add to Streamlit secrets")
    st.stop()

PINS = ["D0","D1","D2","D3","D4","D5","D6","D7","D8"]

# ────────────────────────────────────────────────
# TOOLS
# ────────────────────────────────────────────────
@tool
def set_pin(pin: str, state: str) -> str:
    """Set pin (D0-D8) to on or off."""
    pin = pin.upper()
    state = state.lower()
    if pin not in PINS:
        return f"Bad pin. Use: {', '.join(PINS)}"
    if state not in ["on", "off"]:
        return "State must be on/off"
    try:
        url = SET_URL_TEMPLATE.format(pin=pin, state=state)
        r = requests.get(url, timeout=5)
        return f"{pin} set to {state.upper()}" if r.ok else f"ESP failed: {r.text}"
    except Exception as e:
        return f"Conn error: {str(e)}"


@tool
def get_pin_status() -> str:
    """Get status of all pins."""
    try:
        r = requests.get(STATUS_URL, timeout=5)
        if not r.ok:
            return f"HTTP {r.status_code}"
        pins = r.json().get("pins", {})
        return "\n".join(f"{p}: {'ON' if pins.get(p, False) else 'OFF'}" for p in PINS)
    except Exception as e:
        return f"Status error: {str(e)}"


tools = [set_pin, get_pin_status]

# ────────────────────────────────────────────────
# LLM + Agent (classic ReAct – works in 0.2.x)
# ────────────────────────────────────────────────
llm = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model="llama-3.1-70b-versatile",
    temperature=0.3,
)

system_prompt = f"""ESP8266 assistant. Time: {datetime.now().strftime("%Y-%m-%d %H:%M IST")}

Pins: {', '.join(PINS)}

Use get_pin_status for status questions.
Use set_pin only for clear turn on/off commands.
Be short. Ask if unclear.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),
])

agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=False,
    handle_parsing_errors=True,
    max_iterations=10,
)

# ────────────────────────────────────────────────
# Streamlit UI (same as before – manual + chat)
# ────────────────────────────────────────────────
st.set_page_config(page_title="ESP8266 Control", layout="wide")

tab1, tab2 = st.tabs(["Manual", "Chat"])

with tab1:
    st.title("Manual Pin Control")
    conn = st.empty()

    if "states" not in st.session_state:
        st.session_state.states = {p: False for p in PINS}

    def poll():
        while True:
            try:
                r = requests.get(STATUS_URL, timeout=4)
                if r.ok:
                    conn.success("Connected")
                    data = r.json().get("pins", {})
                    for p in PINS:
                        st.session_state.states[p] = bool(data.get(p))
                else:
                    conn.error("ESP error")
            except:
                conn.error("Disconnected")
            time.sleep(5)

    if "poll_run" not in st.session_state:
        st.session_state.poll_run = True
        threading.Thread(target=poll, daemon=True).start()

    cols = st.columns(3)
    for i, p in enumerate(PINS):
        cols[i % 3].metric(p, "ON" if st.session_state.states[p] else "OFF")

    st.subheader("Toggle")
    tcols = st.columns(3)
    for i, p in enumerate(PINS):
        with tcols[i % 3]:
            curr = st.session_state.states[p]
            tog = st.checkbox(p, value=curr, key=f"chk_{p}")
            if tog != curr:
                s = "on" if tog else "off"
                try:
                    url = SET_URL_TEMPLATE.format(pin=p, state=s)
                    r = requests.get(url, timeout=5)
                    if r.ok:
                        st.session_state.states[p] = tog
                        st.success(f"{p} {s.upper()}")
                    else:
                        st.error("ESP no")
                except:
                    st.error("Conn fail")
                st.rerun()

with tab2:
    st.title("Natural Language")

    if "msgs" not in st.session_state:
        st.session_state.msgs = []

    for m in st.session_state.msgs:
        role = "assistant" if isinstance(m, AIMessage) else "user"
        with st.chat_message(role):
            st.write(m.content)

    if txt := st.chat_input("turn D5 on / status ..."):
        st.session_state.msgs.append(HumanMessage(content=txt))
        with st.chat_message("user"):
            st.write(txt)

        with st.spinner("..."):
            try:
                res = agent_executor.invoke({
                    "input": txt,
                    "chat_history": st.session_state.msgs[:-1]
                })
                reply = res["output"]
                st.chat_message("assistant").write(reply)
                st.session_state.msgs.append(AIMessage(content=reply))
            except Exception as e:
                st.error(f"Agent fail: {str(e)}")

    if st.button("Clear"):
        st.session_state.msgs = []
        st.rerun()
