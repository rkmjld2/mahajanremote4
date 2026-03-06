from flask import Flask, render_template_string, request, jsonify
import time

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# -------------------------------
# PIN STATES
# -------------------------------

pins = {
"D0":"OFF","D1":"OFF","D2":"OFF","D3":"OFF","D4":"OFF",
"D5":"OFF","D6":"OFF","D7":"OFF","D8":"OFF"
}

last_seen = 0
wifi_rssi = 0
uptime = 0

# -------------------------------
# HTML DASHBOARD
# -------------------------------

HTML = '''

<!DOCTYPE html>
<html>

<head>

<title>ESP8266 ULTRA IoT Dashboard</title>

<meta name="viewport" content="width=device-width, initial-scale=1">

<style>

body{
font-family:Arial;
background:#0f2027;
background:linear-gradient(to right,#2c5364,#203a43,#0f2027);
color:white;
text-align:center;
}

h1{margin-top:20px}

.grid{
display:grid;
grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
gap:20px;
max-width:1000px;
margin:auto;
padding:20px;
}

.card{
background:#1b2a33;
padding:20px;
border-radius:12px;
box-shadow:0 0 15px black;
}

.switch{
position:relative;
display:inline-block;
width:60px;
height:34px;
}

.switch input{display:none}

.slider{
position:absolute;
cursor:pointer;
top:0;left:0;right:0;bottom:0;
background:#ccc;
transition:.4s;
border-radius:34px;
}

.slider:before{
position:absolute;
content:"";
height:26px;width:26px;
left:4px;bottom:4px;
background:white;
transition:.4s;
border-radius:50%;
}

input:checked + .slider{
background:#00c853
}

input:checked + .slider:before{
transform:translateX(26px)
}

.status{
font-size:22px;
margin-bottom:10px
}

.online{color:#00ff9c}
.offline{color:#ff4444}

.info{
margin-top:10px;
font-size:14px;
opacity:.8
}

</style>

<script>

function toggle(pin,state){

fetch("/set/"+pin+"/"+state)

}

function update(){

fetch("/api")
.then(r=>r.json())
.then(data=>{

document.getElementById("wifi").innerText=data.rssi
document.getElementById("uptime").innerText=data.uptime

for(const p in data.pins){

let sw=document.getElementById(p)
sw.checked=data.pins[p]=="ON"

}

let s=document.getElementById("status")

if(data.online){

s.innerHTML="ONLINE"
s.className="online"

}else{

s.innerHTML="OFFLINE"
s.className="offline"

}

})

}

setInterval(update,2000)

</script>

</head>

<body>

<h1>🏠 Smart Home IoT Dashboard</h1>

<div class="status">
Device Status :
<span id="status">Loading...</span>
</div>

<div class="info">
WiFi Signal : <span id="wifi">0</span> dBm |
Uptime : <span id="uptime">0</span> sec
</div>

<div class="grid">

{% for p in pins %}

<div class="card">

<h3>{{p}}</h3>

<label class="switch">

<input type="checkbox" id="{{p}}"
onchange="toggle('{{p}}',this.checked?'ON':'OFF')">

<span class="slider"></span>

</label>

</div>

{% endfor %}

</div>

</body>

</html>

'''

# -------------------------------
# WEB PAGE
# -------------------------------

@app.route("/")
def home():
    return render_template_string(HTML,pins=pins)

# -------------------------------
# SET PIN
# -------------------------------

@app.route("/set/<pin>/<state>")
def setpin(pin,state):

    global last_seen

    if pin in pins:
        pins[pin] = state

    last_seen = time.time()

    return "OK"

# -------------------------------
# API STATUS
# -------------------------------

@app.route("/api")
def api():

    online = (time.time() - last_seen) < 20

    return jsonify({
        "pins":pins,
        "online":online,
        "rssi":wifi_rssi,
        "uptime":uptime
    })

# -------------------------------
# ESP8266 REQUEST
# -------------------------------

@app.route("/get")
def get():

    global last_seen
    global wifi_rssi
    global uptime

    last_seen = time.time()

    wifi_rssi = request.args.get("rssi",0)
    uptime = request.args.get("uptime",0)

    return ",".join([f"{p}:{pins[p]}" for p in pins])

# -------------------------------
# MAIN
# -------------------------------

if __name__=="__main__":
    app.run()
