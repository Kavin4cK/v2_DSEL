/*
 * HOT AXLE MONITORING SYSTEM - Gateway C0
 * Pure I2C for all coaches
 *
 * A4 SDA, A5 SCL  (4.7k pull-ups to 5V HERE ONLY)
 * D2 = own DS18B20 (4.7k pull-up to 5V)
 * USB = Pi
 *
 * I2C addresses: C1=9  C2=10  C3=11  C4=12
 *
 * Pi sends  : TEMP,<id>
 * Reply OK  : TEMP,<id>,<left>,<right>,<temp>
 * Reply fail: ERROR
 * Boot      : READY (sent every second until Pi connects)
 *
 * Topology reporting:
 *   left/right neighbors are resolved dynamically from detected coaches.
 *   Missing coach queries return ERROR and Pi skips them.
 */
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>

#define ONE_WIRE_BUS 2

OneWire           oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

bool isCoachPresent(int id) {
  if (id == 0) return true;
  if (id < 1 || id > 4) return false;

  uint8_t addr = id + 8;
  uint8_t got  = Wire.requestFrom(addr, (uint8_t)1);
  if (got < 1) {
    while (Wire.available()) Wire.read();
    return false;
  }

  uint8_t rid = Wire.read();
  while (Wire.available()) Wire.read();
  return rid == (uint8_t)id;
}

void resolveNeighbors(int id, int &left, int &right) {
  left = -1;
  right = -1;

  for (int i = id - 1; i >= 0; i--) {
    if (isCoachPresent(i)) {
      left = i;
      break;
    }
  }

  for (int i = id + 1; i <= 4; i++) {
    if (isCoachPresent(i)) {
      right = i;
      break;
    }
  }
}

String cmd           = "";
bool   handshakeDone = false;

void handleTemp(int id) {
  int left  = -1;
  int right = -1;
  resolveNeighbors(id, left, right);

  // C0 — own sensor
  if (id == 0) {
    sensors.requestTemperatures();
    float t = sensors.getTempCByIndex(0);
    if (t == DEVICE_DISCONNECTED_C || t < -100.0) {
      Serial.println(F("ERROR"));
    } else {
      Serial.print(F("TEMP,0,"));
      Serial.print(left);
      Serial.print(F(","));
      Serial.print(right);
      Serial.print(F(","));
      Serial.println(t, 2);
    }
    Serial.flush();
    return;
  }

  // C1-C4 — I2C
  uint8_t addr = id + 8;
  uint8_t got  = Wire.requestFrom(addr, (uint8_t)5);

  if (got < 5) {
    while (Wire.available()) Wire.read();
    Serial.println(F("ERROR"));
    Serial.flush();
    return;
  }

  uint8_t rid = Wire.read();
  uint8_t b[4];
  for (int i = 0; i < 4; i++) b[i] = Wire.read();
  float t;
  memcpy(&t, b, 4);

  if (rid != (uint8_t)id || isnan(t) || t < -100.0 || t > 200.0) {
    Serial.println(F("ERROR"));
    Serial.flush();
    return;
  }

  Serial.print(F("TEMP,"));
  Serial.print(id);
  Serial.print(F(","));
  Serial.print(left);
  Serial.print(F(","));
  Serial.print(right);
  Serial.print(F(","));
  Serial.println(t, 2);
  Serial.flush();
}

void setup() {
  Serial.begin(9600);
  Wire.begin();
  Wire.setClock(100000);
  sensors.begin();
  sensors.setResolution(12);
  delay(2000);
}

void loop() {
  if (!handshakeDone) {
    Serial.println(F("READY"));
    Serial.flush();
    delay(1000);
  }

  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r' || c == '\n') {
      cmd.trim();
      if (cmd.length() > 0) {
        handshakeDone = true;
        if (cmd.startsWith(F("TEMP,"))) {
          int id = cmd.substring(5).toInt();
          if (id >= 0 && id <= 4) handleTemp(id);
        }
      }
      cmd = "";
    } else {
      cmd += c;
    }
  }
}
