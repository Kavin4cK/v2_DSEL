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
 * Topology supported:
 *   C0-C1-C3-C4  or  C0-C1-C2-C3-C4
 *   (any missing coach returns ERROR, Pi skips it)
 */
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>

#define ONE_WIRE_BUS 2

OneWire           oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

// Hardcoded neighbours
const int ILEFT[]  = {-1, -1,  1,  2,  3};
const int IRIGHT[] = { 1,  2,  3,  4, -1};

String cmd           = "";
bool   handshakeDone = false;

bool readCoachTempI2C(uint8_t id, float &tempOut) {
  uint8_t addr = id + 8;

  for (uint8_t attempt = 0; attempt < 3; attempt++) {
    uint8_t got = Wire.requestFrom(addr, (uint8_t)5);
    if (got == 5) {
      uint8_t rid = Wire.read();
      uint8_t b[4];
      for (int i = 0; i < 4; i++) b[i] = Wire.read();

      float t;
      memcpy(&t, b, 4);

      if (rid == id && !isnan(t) && t >= -100.0 && t <= 200.0) {
        tempOut = t;
        return true;
      }
    }

    while (Wire.available()) Wire.read();
    delay(8);
  }

  return false;
}

void handleTemp(int id) {
  // C0 — own sensor
  if (id == 0) {
    sensors.requestTemperatures();
    float t = sensors.getTempCByIndex(0);
    if (t == DEVICE_DISCONNECTED_C || t < -100.0) {
      Serial.println(F("ERROR"));
    } else {
      Serial.print(F("TEMP,0,-1,1,"));
      Serial.println(t, 2);
    }
    Serial.flush();
    return;
  }

  // C1-C4 — I2C
  float t = 0.0;
  if (!readCoachTempI2C((uint8_t)id, t)) {
    Serial.println(F("ERROR"));
    Serial.flush();
    return;
  }

  Serial.print(F("TEMP,"));
  Serial.print(id);
  Serial.print(F(","));
  Serial.print(ILEFT[id]);
  Serial.print(F(","));
  Serial.print(IRIGHT[id]);
  Serial.print(F(","));
  Serial.println(t, 2);
  Serial.flush();
}

void setup() {
  Serial.begin(9600);
  Wire.begin();
  Wire.setClock(50000);
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
