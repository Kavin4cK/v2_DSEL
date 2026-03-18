/*
 * Regular Coach - Hot Axle Monitoring System (REVISED)
 * C1: COACH_ID = 1 (MSB=0, LSB=1)
 * C2: COACH_ID = 2 (MSB=1, LSB=0)
 * C3: COACH_ID = 3 (MSB=1, LSB=1)
 */

#include <OneWire.h>
#include <DallasTemperature.h>
#include <Wire.h>

// ===== COACH CONFIGURATION - CHANGE FOR EACH COACH =====
#define COACH_ID 1          // C1=1, C2=2, C3=3
#define COACH_ID_MSB 0      // C1=0, C2=1, C3=1
#define COACH_ID_LSB 1      // C1=1, C2=0, C3=1

// ===== PIN DEFINITIONS =====
#define ONE_WIRE_BUS 2
#define LED_PIN 13

#define BROADCAST_MSB 8
#define BROADCAST_LSB 7
#define RIGHT_MSB 10
#define RIGHT_LSB 11
#define LEFT_MSB 4
#define LEFT_LSB 5

#define CTRL_MSB A2
#define CTRL_LSB A3

// ===== GLOBAL VARIABLES =====
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

int leftCoachID = -1;
int rightCoachID = -1;
float currentTemp = 0.0;
volatile bool sendMap = false;
volatile bool sendTemp = false;

// ===== SETUP =====
void setup() {
  Wire.begin(COACH_ID + 8);
  Wire.onRequest(sendData);
  
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);
  
  sensors.begin();
  
  pinMode(BROADCAST_MSB, OUTPUT);
  pinMode(BROADCAST_LSB, OUTPUT);
  pinMode(LEFT_MSB, INPUT);
  pinMode(LEFT_LSB, INPUT);
  pinMode(RIGHT_MSB, INPUT);
  pinMode(RIGHT_LSB, INPUT);
  pinMode(CTRL_MSB, INPUT);
  pinMode(CTRL_LSB, INPUT);
  
  delay(200);
  
  performNeighborDiscovery();
  
  delay(3000);
}

// ===== NEIGHBOR DISCOVERY =====
void performNeighborDiscovery() {
  digitalWrite(BROADCAST_MSB, COACH_ID_MSB);
  digitalWrite(BROADCAST_LSB, COACH_ID_LSB);
  delay(300);
  
  leftCoachID = listenToCoach(LEFT_MSB, LEFT_LSB);
  rightCoachID = listenToCoach(RIGHT_MSB, RIGHT_LSB);
}

int listenToCoach(int msbPin, int lsbPin) {
  delay(50);
  int msb = digitalRead(msbPin);
  int lsb = digitalRead(lsbPin);
  
  if (msb == LOW && lsb == LOW) {
    return -1;
  }
  
  int id = (msb << 1) | lsb;
  return id;
}

// ===== MAIN LOOP =====
void loop() {
  int ctrlMSB = digitalRead(CTRL_MSB);
  int ctrlLSB = digitalRead(CTRL_LSB);
  int targetID = (ctrlMSB << 1) | ctrlLSB;
  
  if (targetID == COACH_ID) {
    // Update temperature
    sensors.requestTemperatures();
    currentTemp = sensors.getTempCByIndex(0);
    sendTemp = true;
  }
  
  delay(50);
}

// ===== I2C CALLBACK =====
void sendData() {
  // Send map data (6 bytes: left, current, right)
  byte left = (leftCoachID == -1) ? 255 : leftCoachID;
  byte right = (rightCoachID == -1) ? 255 : rightCoachID;
  
  Wire.write(left);
  Wire.write((byte)COACH_ID);
  Wire.write(right);
  
  if (sendTemp) {
    // Send temperature as 4 bytes (float)
    byte tempBytes[4];
    memcpy(tempBytes, &currentTemp, 4);
    for (int i = 0; i < 4; i++) {
      Wire.write(tempBytes[i]);
    }
    sendTemp = false;
  } else {
    // Padding for map-only request
    Wire.write(0);
    Wire.write(0);
    Wire.write(0);
    Wire.write(0);
  }
}