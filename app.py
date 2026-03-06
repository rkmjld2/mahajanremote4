from flask import Flask, request, jsonify
import time

app = Flask(__name__)

device_status = {
    "pins": {},
    "rssi": "",
    "uptime": "",
    "last_seen": 0
}

@app.route("/update", methods=["POST"])
def update():
    data = request.json

    device_status["pins"] = data.get("pins", {})
    device_status["rssi"] = data.get("rssi", "")
    device_status["uptime"] = data.get("uptime", "")
    device_status["last_seen"] = time.time()

    return jsonify({"status": "ok"})


@app.route("/status")
def status():

    # check last update
    if time.time() - device_status["last_seen"] > 20:
        online = False
    else:
        online = True

    return jsonify({
        "online": online,
        "pins": device_status["pins"],
        "rssi": device_status["rssi"],
        "uptime": device_status["uptime"]
    })


if __name__ == "__main__":
    app.run()
