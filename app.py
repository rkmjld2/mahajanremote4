import streamlit as st
import requests
import re
import json
import time
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage

# ─── CONFIG ───
ESP_IP = st.secrets["ESP_IP"]
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
STATUS_URL = f"http://{ESP_IP}/status"
PINS = ["D0","D1","D2","D3","D4","D5","D6","D7","D8"]

# Fix ESP JSON
def fix_json(raw):
    cleaned = re.sub(r',\s*}', '}', raw)
    cleaned = re.sub(r',\s*]', ']', cleaned)
    try:
        return json.loads(cleaned)
    except:
        return {"pins": {p: False for p in PINS}}

# Test connection
@st.cache_data(ttl=10)
def test_esp():
    try:
        r = requests.get(STATUS_URL, timeout=5)
        return r.status_code == 200, fix_json(r.text) if r.status_code == 200 else None
    except:
        return False, None

# ─── TOOLS ───
@tool
def set_pin(pin: str, state: str) -> str:
    """Control ESP pin D0-D8 (ON/OFF)"""
    if not test_esp()[0]:
        return "❌ ESP OFFLINE"
    try:
        url = f"http://{ESP_IP}/set/{pin}/{state}"
        r = requests.get(url, timeout=5)
        return f"✅ {pin} → {state.upper()} (HTTP {r.status_code})" if r.status_code == 200 else f"❌ HTTP {r.status_code}"
    except:
        return "❌ Connection failed"

@tool
def get_status() -> str:
    """Get all pin states"""
    connected, data = test_esp()
    if not connected:
        return "❌ ESP OFFLINE"
    pins = data.get("pins", {})
    return "\n".join([f"{p}: {'ON' if pins.get(p, False) else 'OFF'}" for p in PINS])

tools = [set_pin, get_status]

# ─── AI AGENT ───
llm = ChatGroq(groq_api_key=GROQ_API_KEY, model_name="llama-3.1-70b-versatile", temperature=0.1)
prompt = ChatPromptTemplate.from_messages([
    ("system", "ESP8266 controller. Pins: {pins}. Use tools precisely."),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad")
]).partial(pins=", ".join(PINS))

agent = create_react_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=False, handle_parsing_errors=True)

# ─── UI ───
st.set_page_config(page_title="ESP Remote", layout="wide")
st.title("🌐 ESP8266 REMOTE CONTROL")

# Status
connected, data = test_esp()
col1, col2 = st.columns([3,1])
with col1:
    status_emoji = "🟢 ONLINE" if connected else "🔴 OFFLINE"
    st.metric("ESP Status", status_emoji, f"IP: {ESP_IP}")
with col2:
    st.caption(f"Last ping: {time.strftime('%H:%M:%S')}")

if "pins" not in st.session_state:
    st.session_state.pins = {p: False for p in PINS}

if connected:
    pins_data = data.get("pins", {})
    st.session_state.pins = {k: bool(pins_data.get(k, False)) for k in PINS}

# Pin display
st.subheader("📊 LIVE PINS")
cols = st.columns(3)
for i, pin in enumerate(PINS):
    cols[i%3].metric(pin, "🟢 ON" if st.session_state.pins[pin] else "🔴 OFF")

# Manual controls
st.subheader("🔧 MANUAL CONTROL")
toggle_cols = st.columns(3)
for i, pin in enumerate(PINS):
    with toggle_cols[i%3]:
        disabled = not connected
        current = st.session_state.pins[pin]
        new_state = st.checkbox(pin, value=current, key=f"t_{pin}", disabled=disabled)
        
        if new_state != current and connected:
            state_str = "on" if new_state else "off"
            with st.spinner(f"Setting {pin}..."):
                try:
                    r = requests.get(f"http://{ESP_IP}/set/{pin}/{state_str}", timeout=5)
                    if r.status_code == 200:
                        st.session_state.pins[pin] = new_state
                        st.success(f"✅ {pin} = {'ON' if new_state else 'OFF'}")
                    else:
                        st.error(f"❌ {r.status_code}")
                except Exception as e:
                    st.error(f"❌ {str(e)[:50]}")
            st.rerun()

# AI Chat
tab2, tab3 = st.tabs(["🤖 AI Control", "ℹ️ Info"])
with tab2:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    for msg in st.session_state.messages:
        role = "assistant" if isinstance(msg, AIMessage) else "user"
        st.chat_message(role).markdown(msg.content)
    
    if prompt := st.chat_input("turn D1 on, status, etc...", disabled=not connected):
        st.session_state.messages.append(HumanMessage(content=prompt))
        st.chat_message("user").markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("AI thinking..."):
                try:
                    result = agent_executor.invoke({"input": prompt})
                    st.markdown(result["output"])
                    st.session_state.messages.append(AIMessage(content=result["output"]))
                except Exception as e:
                    st.error(f"AI Error: {str(e)}")

# Info
with tab3:
    st.info(f"""
    **🌐 CLOUD READY**
    • ESP IP: `{ESP_IP}`
    • Status: {'🟢 LIVE' if connected else '🔴 OFFLINE'}
    • Control: Manual + AI chat
    
    **🔧 Commands**
    • "turn D1 on"
    • "status" 
    • "all off"
    
    **⚡ Powered by**
    Groq + Streamlit Cloud
    """)

if st.button("🔄 REFRESH", type="secondary"):
    st.rerun()
