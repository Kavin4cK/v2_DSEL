/*
 * Gateway Coach C0 - Hot Axle Monitoring System (REVISED)
 * Coach ID: 0 (MSB=0, LSB=0)
 * Role: Gateway between Raspberry Pi and train coaches
 */

#include <OneWire.h>
#include <DallasTemperature.h>
#include <Wire.h>

// ===== COACH CONFIGURATION =====
#define COACH_ID 0
#define COACH_ID_MSB 0
#define COACH_ID_LSB 0

// ===== PIN DEFINITIONS =====
#define ONE_WIRE_BUS 2
#define LED_PIN 13

// ID Broadcast/Listen Pins
#define BROADCAST_MSB 8
#define BROADCAST_LSB 7
#define RIGHT_MSB 10
#define RIGHT_LSB 11
#define LEFT_MSB 4
#define LEFT_LSB 5

// Control Signal Pins
#define CTRL_MSB A2
#define CTRL_LSB A3

// ===== GLOBAL VARIABLES =====
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

int leftCoachID = -1;
int rightCoachID = -1;
float currentTemp = 0.0;

// ===== SETUP =====
void setup() {
  Serial.begin(9600);
  while (!Serial) { ; }
  
  Wire.begin();
  
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);
  
  sensors.begin();
  
  // Setup pins
  pinMode(BROADCAST_MSB, OUTPUT);
  pinMode(BROADCAST_LSB, OUTPUT);
  pinMode(LEFT_MSB, INPUT);
  pinMode(LEFT_LSB, INPUT);
  pinMode(RIGHT_MSB, INPUT);
  pinMode(RIGHT_LSB, INPUT);
  pinMode(CTRL_MSB, OUTPUT);
  pinMode(CTRL_LSB, OUTPUT);
  
  digitalWrite(CTRL_MSB, LOW);
  digitalWrite(CTRL_LSB, LOW);
  
  delay(200);
  
  // Neighbor discovery
  performNeighborDiscovery();
  
  delay(3000);
  
  Serial.println("READY");
  Serial.flush();
}

// ===== NEIGHBOR DISCOVERY =====
void performNeighborDiscovery() {
  // Broadcast ID
  digitalWrite(BROADCAST_MSB, COACH_ID_MSB);
  digitalWrite(BROADCAST_LSB, COACH_ID_LSB);
  delay(300);
  
  // Listen to neighbors
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
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command.startsWith("MAP,")) {
      handleMapRequest(command);
    }
    else if (command.startsWith("TEMP,")) {
      handleTempRequest(command);
    }
  }
}

// ===== COMMAND HANDLERS =====
void handleMapRequest(String command) {
  int coachID = command.substring(4).toInt();
  
  if (coachID == COACH_ID) {
    // Send our map data
    Serial.print(leftCoachID);
    Serial.print(",");
    Serial.print(COACH_ID);
    Serial.print(",");
    Serial.println(rightCoachID);
    Serial.flush();
  } else {
    // Request from other coach via I2C
    int leftID, currentID, rightID;
    bool success = requestMapFromCoach(coachID, leftID, currentID, rightID);
    
    if (success) {
      Serial.print(leftID);
      Serial.print(",");
      Serial.print(currentID);
      Serial.print(",");
      Serial.println(rightID);
      Serial.flush();
    } else {
      Serial.println("ERROR");
      Serial.flush();
    }
  }
}

void handleTempRequest(String command) {
  int coachID = command.substring(5).toInt();
  
  if (coachID == COACH_ID) {
    // Get our temperature
    sensors.requestTemperatures();
    currentTemp = sensors.getTempCByIndex(0);
    
    Serial.print(leftCoachID);
    Serial.print(",");
    Serial.print(COACH_ID);
    Serial.print(",");
    Serial.print(rightCoachID);
    Serial.print(",");
    Serial.println(currentTemp, 2);
    Serial.flush();
  } else {
    // Request from other coach
    int leftID, currentID, rightID;
    float temp;
    bool success = requestTempFromCoach(coachID, leftID, currentID, rightID, temp);
    
    if (success) {
      Serial.print(leftID);
      Serial.print(",");
      Serial.print(currentID);
      Serial.print(",");
      Serial.print(rightID);
      Serial.print(",");
      Serial.println(temp, 2);
      Serial.flush();
    } else {
      Serial.println("ERROR");
      Serial.flush();
    }
  }
}

// ===== I2C COMMUNICATION =====
bool requestMapFromCoach(int coachID, int &leftID, int &currentID, int &rightID) {
  setControlSignals(coachID);
  delay(100);
  
  Wire.requestFrom(coachID + 8, 6);
  
  unsigned long startTime = millis();
  while (Wire.available() < 6 && (millis() - startTime < 500)) {
    delay(10);
  }
  
  if (Wire.available() >= 6) {
    leftID = Wire.read();
    if (leftID == 255) leftID = -1;
    
    currentID = Wire.read();
    
    rightID = Wire.read();
    if (rightID == 255) rightID = -1;
    
    // Clear remaining bytes
    while (Wire.available()) Wire.read();
    
    setControlSignals(-1);
    return true;
  }
  
  setControlSignals(-1);
  return false;
}

bool requestTempFromCoach(int coachID, int &leftID, int &currentID, int &rightID, float &temp) {
  setControlSignals(coachID);
  delay(100);
  
  Wire.requestFrom(coachID + 8, 10);
  
  unsigned long startTime = millis();
  while (Wire.available() < 10 && (millis() - startTime < 500)) {
    delay(10);
  }
  
  if (Wire.available() >= 10) {
    leftID = Wire.read();
    if (leftID == 255) leftID = -1;
    
    currentID = Wire.read();
    
    rightID = Wire.read();
    if (rightID == 255) rightID = -1;
    
    // Read temperature as bytes
    byte tempBytes[4];
    for (int i = 0; i < 4; i++) {
      tempBytes[i] = Wire.read();
    }
    memcpy(&temp, tempBytes, 4);
    
    // Clear remaining
    while (Wire.available()) Wire.read();
    
    setControlSignals(-1);
    return true;
  }
  
  setControlSignals(-1);
  return false;
}

void setControlSignals(int targetID) {
  if (targetID < 0) {
    digitalWrite(CTRL_MSB, LOW);
    digitalWrite(CTRL_LSB, LOW);
    return;
  }
  
  int msb = (targetID >> 1) & 0x01;
  int lsb = targetID & 0x01;
  
  digitalWrite(CTRL_MSB, msb);
  digitalWrite(CTRL_LSB, lsb);
}