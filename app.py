#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>

const char* ssid = "YOUR_WIFI";
const char* password = "YOUR_WIFI_PASS";

ESP8266WebServer server(80);
bool pins[9] = {0};

void setup() {
  Serial.begin(115200);
  
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) delay(500);
  Serial.println("IP: " + WiFi.localIP().toString());

  // STATUS endpoint (already works)
  server.on("/status", [](){
    String json = "{\"pins\":{";
    for(int i=0; i<9; i++) json += "\"D"+String(i)+"\":" + String(pins[i]) + ",";
    json += "}}";
    server.send(200, "application/json", json);
  });

  // ADD THESE PIN CONTROL ENDPOINTS
  server.on("/set/D0/on", [](){ pins[0]=1; server.send(200); });
  server.on("/set/D0/off", [](){ pins[0]=0; server.send(200); });
  server.on("/set/D1/on", [](){ pins[1]=1; server.send(200); });
  server.on("/set/D1/off", [](){ pins[1]=0; server.send(200); });
  // Repeat D2-D8...

  server.begin();
}

void loop() {
  server.handleClient();
}
