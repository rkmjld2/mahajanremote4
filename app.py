# app.py - Corrected version

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
    st.error("GROQ_API_KEY not found. Please add it to Streamlit secrets.")
    st.stop()

PINS = ["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"]

# ────────────────────────────────────────────────
# TOOLS (with improved timeouts and retries)
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

    # Retry logic with longer timeout
    for attempt in range(3):
        try:
            url = SET_URL_TEMPLATE.format(pin=pin, state=state)
            resp = requests.get(url, timeout=10)  # Increased timeout
            if resp.status_code == 200:
                return f"OK → {pin} set to {state.upper()}"
            else:
                time.sleep(0.5)  # Brief delay before retry
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
            else:
                return f"Connection failed after 3 tries: {str(e)}"
    return "Failed after retries"

@tool
def get_all_pin_status() -> str:
    """Return current ON/OFF state of all pins."""
    try:
        r = requests.get(STATUS_URL, timeout=10)
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
# LLM + ReAct Agent (unchanged)
# ────────────────────────────────────────────────

llm = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model_name="llama-3.1-70b-versatile",
    temperature=0.35,
    max_tokens=650,
)

react_prompt_template = """Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the taking the action
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

prompt
