# ESP8266 Remote Control Panel with Groq + LangChain

A modern web interface to control all digital pins (D0–D8) of an **ESP8266** (NodeMCU / Wemos D1 Mini style board) using:

- **Manual toggle switches** (real-time status polling)
- **Natural language commands** powered by **Groq** + **LangChain** agent (tool calling)

Supports local network control and can be made remotely accessible (e.g. via ngrok, Tailscale, port forwarding, Cloudflare Tunnel, etc.).

Current time reference: February 2025–2026 timeframe (project developed/tested around this period)

## Features

- Control 9 common ESP8266 pins: D0, D1, D2, D3, D4, D5, D6, D7, D8
- Real-time status polling (shows ON/OFF for each pin)
- Visual warnings for boot-sensitive pins (D3, D4, D8, etc.)
- Two control modes:
  - **Manual tab**: checkboxes for each pin
  - **Chat tab**: natural language interface ("turn D5 on", "status please", "all off", "kitchen light on" if renamed, etc.)
- Groq-powered LLM agent with tool calling (`set_pin`, `get_all_pin_status`)
- Thread-safe polling (non-blocking background updates)
- Error handling & connection status indicator

## Project Structure

```text
esp8266-groq-control/
├── app.py                  # Main Streamlit application
├── requirements.txt        # Python dependencies
├── .streamlit/
│   └── config.toml         # (optional) Streamlit configuration
└── README.md               # This file
