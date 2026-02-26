# app.py

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

ESP_IP = "192.168.1.13"                     # ← change to your ESP IP
STATUS_URL    = f"http://{ESP_IP}/status"
SET_URL_TEMPLATE = f"http://{ESP_IP}/set/{{pin}}/{{state}}"

# Get API key from Streamlit secrets (recommended for cloud deployment)
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    st.error("GROQ_API_KEY not found. Please add it to Streamlit secrets.")
    st.stop()

# Pins we want to control (should match ESP firmware)
PINS = ["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"]

# ────────────────────────────────────────────────
# TOOLS the agent can use
# ────────────────────────────────────────────────

@tool
def set_pin(pin: str, state: str) -> str:
    """Set one pin (D0–D8) to on or off."""
    pin = pin.upper().strip()
    state = state.lower().strip()

    if pin not in PINS:
        return f"Invalid pin. Available pins: {', '.join(PINS)}"

    if state not in ["on", "off"]:
        return "State must be 'on' or 'off'"

    try:
        url = SET_URL_TEMPLATE.format(pin=pin, state=state)
        resp = requests.get(url, timeout=6)
        if resp.status_code == 200:
            return f"OK → {pin} set to {state.upper()}"
        else:
            return f"ESP returned error {resp.status_code}: {resp.text}"
    except Exception as e:
        return f"Connection failed: {str(e)}"


@tool
def get_all_pin_status() -> str:
    """Return current ON/OFF state of all pins."""
    try:
        r = requests.get(STATUS_URL, timeout=6)
        if r.status_code != 200:
            return f"HTTP error {r.status_code}"
        data = r.json()
        pins_dict = data.get("pins", {})
        lines = []
        for p in PINS:
            val = pins_dict.get(p, False)
            lines.append(f"{p}: {'ON' if val else 'OFF'}")
        return "\n".join(lines)
    except Exception as e:
        return f"Cannot read status → {str(e)}"


tools = [set_pin, get_all_pin_status]

# ────────────────────────────────────────────────
# LLM + ReAct Agent
# ────────────────────────────────────────────────
# ────────────────────────────────────────────────
# LLM + ReAct Agent (hard-coded prompt – no hub.pull)
# ────────────────────────────────────────────────

llm = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model_name="llama-3.1-70b-versatile",
    temperature=0.35,
    max_tokens=650,
)

# Hard-coded classic ReAct prompt (exact equivalent of hwchase17/react)
react_prompt_template = """Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Additional instructions for this ESP8266 controller:
You are a helpful ESP8266 pin controller assistant.
Current time: {now}
Available pins: {pins}

Rules:
• Use get_all_pin_status tool when user asks about current state / status
• Use set_pin only when user clearly wants to change a pin state (on/off)
• Be concise and polite
• If command is ambiguous → ask for clarification

Begin!

Question: {input}
{agent_scratchpad}"""

prompt = ChatPromptTemplate.from_template(
    react_prompt_template
).partial(
    now=datetime.now().strftime("%Y-%m-%d %H:%M IST"),
    pins=', '.join(PINS)
)

agent = create_react_agent(
    llm=llm,
    tools=tools,
    prompt=prompt
)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=False,
    handle_parsing_errors=True,
    max_iterations=12,
)

# ────────────────────────────────────────────────
# Streamlit UI
# ────────────────────────────────────────────────

st.set_page_config(page_title="ESP8266 Control", layout="wide")

tab1, tab2 = st.tabs(["Manual control", "Natural language"])

# ──── Manual tab ──────────────────────────────────────────────────────

with tab1:
    st.title("Manual ESP8266 Pin Control")
    st.caption(f"Target ESP → http://{ESP_IP}")

    conn_placeholder = st.empty()

    # Keep real pin states in session
    if "real_states" not in st.session_state:
        st.session_state.real_states = {p: False for p in PINS}

    def poll_status():
        while True:
            try:
                r = requests.get(STATUS_URL, timeout=5)
                if r.status_code == 200:
                    conn_placeholder.success("Connected")
                    pins_d = r.json().get("pins", {})
                    for p in PINS:
                        st.session_state.real_states[p] = bool(pins_d.get(p))
                else:
                    conn_placeholder.error(f"HTTP {r.status_code}")
            except:
                conn_placeholder.error("Not connected")
            time.sleep(4.5)

    if "poller_running" not in st.session_state:
        st.session_state.poller_running = True
        threading.Thread(target=poll_status, daemon=True).start()

    st.subheader("Current states")
    cols = st.columns(3)
    for i, pin in enumerate(PINS):
        state = st.session_state.real_states.get(pin, False)
        cols[i % 3].metric(pin, "ON" if state else "OFF")

    st.subheader("Toggle pins")
    tcols = st.columns(3)
    for i, pin in enumerate(PINS):
        with tcols[i % 3]:
            current = st.session_state.real_states.get(pin, False)
            new_val = st.checkbox(
                label=pin,
                value=current,
                key=f"chk_{pin}"
            )
            if new_val != current:
                target = "on" if new_val else "off"
                try:
                    url = SET_URL_TEMPLATE.format(pin=pin, state=target)
                    resp = requests.get(url, timeout=6)
                    if resp.status_code == 200:
                        st.session_state.real_states[pin] = new_val
                        st.success(f"{pin} → {target.upper()}")
                    else:
                        st.error("ESP did not accept command")
                except Exception as e:
                    st.error(f"Connection problem: {str(e)}")
                st.rerun()

# ──── Natural language tab ────────────────────────────────────────────

with tab2:
    st.title("Natural language control")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        role = "assistant" if isinstance(msg, AIMessage) else "user"
        avatar = "🤖" if role == "assistant" else None
        with st.chat_message(role, avatar=avatar):
            st.markdown(msg.content)

    if user_msg := st.chat_input("turn D5 on / show status / all off / ..."):
        st.session_state.messages.append(HumanMessage(content=user_msg))
        with st.chat_message("user"):
            st.markdown(user_msg)

        with st.spinner("Thinking..."):
            try:
                result = agent_executor.invoke({
                    "input": user_msg,
                    "chat_history": st.session_state.messages[:-1],
                })
                answer = result["output"]
                st.chat_message("assistant").markdown(answer)
                st.session_state.messages.append(AIMessage(content=answer))
            except Exception as ex:
                st.error(f"Agent execution failed\n\n{str(ex)}")

    if st.button("Clear conversation", type="primary"):
        st.session_state.messages = []
        st.rerun()



