/*
 * HOT AXLE MONITORING SYSTEM - Coach C1
 * I2C slave address 9
 * D2 = DS18B20 (4.7k pull-up to 5V)
 * A4 SDA, A5 SCL (NO pull-ups here, only at gateway)
 * GND shared with all Nanos
 *
 * onRequest() sends cached temp instantly — no blocking
 * loop() refreshes temp every 2s using millis()
 */
#include <Wire.h>
#include <OneWire.h>
#include <DallasTemperature.h>

#define ONE_WIRE_BUS 2
#define I2C_ADDR     9
#define COACH_ID     1

OneWire           oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

volatile float currentTemp = 25.0;
bool     convStarted       = false;
uint32_t convAt            = 0;
uint32_t lastRead          = 0;

void onRequest() {
  float   t = currentTemp;
  uint8_t b[4];
  memcpy(b, &t, 4);
  Wire.write((uint8_t)COACH_ID);
  Wire.write(b[0]);
  Wire.write(b[1]);
  Wire.write(b[2]);
  Wire.write(b[3]);
}

void setup() {
  // 1. Sensor init
  sensors.begin();
  sensors.setResolution(12);

  // 2. Blocking read at boot — valid temp before first I2C request
  sensors.setWaitForConversion(true);
  sensors.requestTemperatures();
  float t = sensors.getTempCByIndex(0);
  if (t != DEVICE_DISCONNECTED_C && t > -100.0) {
    noInterrupts();
    currentTemp = t;
    interrupts();
  }
  sensors.setWaitForConversion(false);
  lastRead = millis();

  // 3. I2C slave — start last
  Wire.begin(I2C_ADDR);
  Wire.onRequest(onRequest);
}

void loop() {
  uint32_t now = millis();

  if (!convStarted && now - lastRead >= 2000) {
    sensors.requestTemperatures();
    convAt      = now;
    convStarted = true;
  }

  if (convStarted && now - convAt >= 850) {
    float t = sensors.getTempCByIndex(0);
    if (t != DEVICE_DISCONNECTED_C && t > -100.0) {
      noInterrupts();
      currentTemp = t;
      interrupts();
    }
    lastRead    = now;
    convStarted = false;
  }
}
