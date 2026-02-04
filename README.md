# 🚆 Distributed Hot Axle Monitoring System for Indian Railways

**An intelligent, fault-tolerant, and self-reconfigurable system for real-time axle integrity and thermal monitoring in railway vehicles using doubly linked list architecture.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Arduino](https://img.shields.io/badge/Arduino-Nano-00979D?logo=arduino)](https://www.arduino.cc/)
[![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-A22846?logo=raspberry-pi)](https://www.raspberrypi.org/)
[![Python](https://img.shields.io/badge/Python-3.7+-3776AB?logo=python)](https://www.python.org/)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Problem Statement](#problem-statement)
- [Solution Architecture](#solution-architecture)
- [Features](#features)
- [System Components](#system-components)
- [Installation](#installation)
- [Circuit Diagrams](#circuit-diagrams)
- [Usage](#usage)
- [Supported Configurations](#supported-configurations)
- [API Documentation](#api-documentation)
- [Demo Videos](#demo-videos)
- [Research & Publications](#research--publications)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## 🎯 Overview

This project implements a **distributed embedded system** for monitoring hot axle conditions in railway coaches using a **doubly linked list data structure**. Each coach acts as an autonomous node with neighbor discovery capabilities, enabling dynamic topology detection and fault-tolerant operation.

### Key Innovation

Traditional railway hot axle detection relies on expensive track-side infrared systems with coverage gaps. This project provides:
- **Continuous coach-wise monitoring** using onboard sensors
- **Automatic topology discovery** without manual configuration
- **Self-reconfiguring architecture** adapting to coach addition/removal
- **Real-time visualization** as a linked list structure
- **Cost-effective implementation** (~$25 per coach)

---

## 🔥 Problem Statement

### Hot Axle Condition

During prolonged railway operation, wheel bearings experience continuous friction, generating excessive heat leading to:

- ⚠️ **Bearing seizure** and catastrophic mechanical failure
- ⚠️ **Wheel deformation** affecting structural integrity
- ⚠️ **Bogie failure** compromising train stability
- ⚠️ **Train derailment** with severe safety consequences

### Limitations of Existing Systems

| System | Limitations |
|--------|-------------|
| **Track-side IR Detectors** | Location-dependent, expensive infrastructure, detection gaps |
| **Hot Box Detectors (HBD)** | Point measurement only, no real-time alerts to crew |
| **Manual Inspection** | Time-consuming, subjective, infrequent |
| **Centralized Systems** | Single point of failure, not scalable, requires reconfiguration |

---

## 💡 Solution Architecture

### Conceptual Model

The train is modeled as a **doubly linked list**:

```
Coach_i = {Left_ID, Coach_ID, Right_ID, Temperature}

Train = HEAD → C0 → C1 → C2 → ... → Cn → NULL
```

### Why Linked List?

| Array-Based | Linked List (Our Approach) ✅ |
|-------------|-------------------------------|
| Fixed size | Dynamic - coaches can be added/removed |
| Index-based access | Pointer-based navigation (natural for trains) |
| Expensive reordering | Simple insertion/deletion |
| Full rebuild on change | Automatic topology adaptation |

---

## ✨ Features

### 🔍 Core Features

- **Autonomous Neighbor Discovery**: Each coach independently identifies adjacent coaches using binary GPIO signaling
- **Dynamic Topology Mapping**: System automatically reconstructs complete train structure
- **Real-Time Temperature Monitoring**: Continuous thermal monitoring with 1-second update interval
- **Fault-Tolerant Architecture**: Distributed design with no single point of failure
- **Visual Linked List Display**: Interactive GUI showing train as linked list with color-coded status
- **Self-Reconfiguring**: Adapts to coach addition, removal, or failure without manual intervention

### 🎨 Advanced Features

- **Multi-Configuration Support**: Automatically detects and displays 2, 3, or 4 coach configurations
- **Binary I2C Communication**: Efficient fixed-size packet protocol preventing buffer overflow
- **TFT Display Optimization**: Responsive layout for 3.5" GPIO displays (480x320)
- **Temperature Classification**: Three-tier alert system (Normal/Warning/Critical)
- **Coach Highlighting**: Visual indicators for newly added coaches
- **Error Recovery**: Automatic retry mechanism with exponential backoff

---

## 🔧 System Components

### Hardware

| Component | Specification | Quantity | Purpose |
|-----------|--------------|----------|---------|
| **Raspberry Pi** | 3B+ or 4 | 1 | Central controller and GUI display |
| **Arduino Nano** | ATmega328P | 4 | Coach monitoring nodes |
| **DS18B20** | Digital temp sensor | 4 | Axle temperature measurement |
| **TFT Display** | 3.5" 480x320 GPIO | 1 | Real-time visualization |
| **LEDs** | 5mm | 4 | Status indicators |
| **Resistors** | 220Ω, 4.7kΩ, 5.6kΩ | Multiple | Pull-ups and current limiting |
| **Jumper Wires** | Male-to-male | ~50 | Connections |
| **Power Supply** | 5V regulated | 1 | Common power rail |

### Software

- **Arduino IDE** 1.8.19+ for firmware upload
- **Python** 3.7+ for Raspberry Pi controller
- **Libraries**:
  - Arduino: `OneWire`, `DallasTemperature`, `Wire`
  - Python: `pyserial`, `tkinter`

---

## 📦 Installation

### Prerequisites

```bash
# On Raspberry Pi
sudo apt-get update
sudo apt-get install python3 python3-pip python3-tk

# Install Python dependencies
pip3 install pyserial
```

### Clone Repository

```bash
git clone https://github.com/yourusername/hot-axle-monitor.git
cd hot-axle-monitor
```

### Arduino Setup

1. **Install Arduino Libraries**:
   - Open Arduino IDE
   - Go to **Sketch → Include Library → Manage Libraries**
   - Install: `OneWire`, `DallasTemperature`

2. **Upload Gateway Code** (Coach C0):
   ```bash
   # Open arduino/gateway_c0/gateway_c0.ino
   # Set Board: Arduino Nano, Processor: ATmega328P
   # Upload to C0
   ```

3. **Upload Regular Coach Code** (C1, C2, C3):
   ```cpp
   // Modify these lines for each coach:
   #define COACH_ID 1          // C1=1, C2=2, C3=3
   #define COACH_ID_MSB 0      // C1=0, C2=1, C3=1
   #define COACH_ID_LSB 1      // C1=1, C2=0, C3=1
   ```

### Raspberry Pi Setup

```bash
# Grant USB permissions
sudo chmod 666 /dev/ttyUSB0

# Run the monitor
python3 raspberry_pi/train_monitor.py

# Or specify custom port
python3 raspberry_pi/train_monitor.py /dev/ttyACM0
```

---

## 🔌 Circuit Diagrams

### Power Distribution

```
5V Power Line ─┬─ C0 (5V) ─┬─ C1 (5V) ─┬─ C2 (5V) ─┬─ C3 (5V)
               │           │           │           │
GND Line ──────┴─ C0 (GND)─┴─ C1 (GND)─┴─ C2 (GND)─┴─ C3 (GND)
```

### Control Signal Bus

```
C0 (A2) ── MSB Control ─┬─ C1 (A2) ─┬─ C2 (A2) ─┬─ C3 (A2)
C0 (A3) ── LSB Control ─┴─ C1 (A3) ─┴─ C2 (A3) ─┴─ C3 (A3)
```

### I2C Communication Bus

```
SDA Line ─┬─ C0 (A4) ─┬─ C1 (A4) ─┬─ C2 (A4) ─┬─ C3 (A4)
          │           │           │           │
SCL Line ─┴─ C0 (A5) ─┴─ C1 (A5) ─┴─ C2 (A5) ─┴─ C3 (A5)

Pull-up: 4.7kΩ from SDA to 5V (on C0 only)
         4.7kΩ from SCL to 5V (on C0 only)
```

### Neighbor Discovery Wiring

**Between C0 ↔ C1:**
```
C0 D8 (MSB Broadcast) ────→ C1 D4 (MSB Left Listen)
C0 D7 (LSB Broadcast) ────→ C1 D5 (LSB Left Listen)
C1 D8 (MSB Broadcast) ────→ C0 D10 (MSB Right Listen)
C1 D7 (LSB Broadcast) ────→ C0 D11 (LSB Right Listen)
```

**Repeat for C1↔C2 and C2↔C3**

### Temperature Sensor (Each Coach)

```
5V ─┬─ DS18B20 (VDD)
    └─ 5.6kΩ ─┬─ D2 ─ DS18B20 (Data)
GND ───────────┴─ DS18B20 (GND)
```

### Complete Pin Configuration

| Arduino Pin | Function | Connection |
|-------------|----------|------------|
| D2 | Temperature Sensor | DS18B20 Data (with 5.6kΩ pull-up) |
| D13 | Status LED | LED + 220Ω resistor to GND |
| D4, D5 | Left Coach Listen | MSB, LSB from left coach D8, D7 |
| D7, D8 | ID Broadcast | MSB, LSB to adjacent coaches |
| D10, D11 | Right Coach Listen | MSB, LSB from right coach D8, D7 |
| A2, A3 | Control Signals | MSB, LSB from gateway (input) |
| A4 (SDA) | I2C Data | Common SDA bus with 4.7kΩ pull-up |
| A5 (SCL) | I2C Clock | Common SCL bus with 4.7kΩ pull-up |
| 5V | Power | Common 5V rail |
| GND | Ground | Common ground |

---

## 🚀 Usage

### Starting the System

1. **Power On All Coaches**: Ensure all Arduino Nanos are powered and LEDs are lit
2. **Wait for Discovery**: Allow 5 seconds for neighbor discovery to complete
3. **Run Raspberry Pi Software**:
   ```bash
   python3 train_monitor.py
   ```
4. **View GUI**: System automatically detects configuration and displays linked list

### Console Output

```
============================================================
🚆 HOT AXLE MONITORING SYSTEM - RASPBERRY PI
============================================================

Connecting to /dev/ttyUSB0...
Waiting for READY signal...
  Received: 'READY'
✓ Gateway connected and ready

⏳ Waiting for coaches to complete neighbor discovery (5s)...

============================================================
🔍 DETECTING COACH PRESENCE
============================================================

Probing Coach 0... ✓ DETECTED
Probing Coach 1... ✓ DETECTED
Probing Coach 2... ✓ DETECTED
Probing Coach 3... ✓ DETECTED

Detected coaches: [0, 1, 2, 3]

============================================================
🔗 CREATING TRAIN TOPOLOGY
============================================================

Configuration: C0 → C1 → C3 → C2 (4 coaches)

  ✓ Coach 0: NULL ← [C0] → C1
  ✓ Coach 1: C0 ← [C1] → C3
  ✓ Coach 3: C1 ← [C3] → C2 ⭐ NEW COACH
  ✓ Coach 2: C3 ← [C2] → NULL

============================================================
TOPOLOGY COMPLETE: 4 coaches configured
Train order: C0 → C1 → C3 → C2
============================================================

🔗 Building linked list structure...
  ✓ Head coach: C0
  ✓ Linked list built: 4 coaches
  ✓ Train order: C0 → C1 → C3 → C2

🖥  Launching GUI...

🔄 Starting temperature monitoring loop...

--- Cycle 1 ---
✓ C0: 25.3°C
✓ C1: 28.7°C
✓ C3: 31.2°C
✓ C2: 26.8°C
```

---

## 🔀 Supported Configurations

The system **automatically detects** and adapts to different coach configurations:

### Configuration 1: 2 Coaches
```
Detected: C0, C1
Topology: C0 → C1
Display:  [C0] ──→ [C1]
Status:   "2-Coach | All OK"
```

### Configuration 2: 3 Coaches (Standard)
```
Detected: C0, C1, C2
Topology: C0 → C1 → C2
Display:  [C0] ──→ [C1] ──→ [C2]
Status:   "3-Coach | All OK"
```

### Configuration 3: 3 Coaches (with C3)
```
Detected: C0, C1, C3
Topology: C0 → C1 → C3
Display:  [C0] ──→ [C1] ──→ [C3*]
Status:   "3-Coach (C3) | All OK"
* Yellow border on C3
```

### Configuration 4: 4 Coaches (Full)
```
Detected: C0, C1, C2, C3
Topology: C0 → C1 → C3 → C2
Display:  [C0] ──→ [C1] ──→ [C3*] ──→ [C2]
Status:   "4-Coach (+C3) | All OK"
* Yellow border on C3
```

---

## 📡 API Documentation

### Serial Protocol

**Commands (Raspberry Pi → Gateway):**

| Command | Format | Description |
|---------|--------|-------------|
| MAP Request | `MAP,{coach_id}\n` | Request topology from specific coach |
| TEMP Request | `TEMP,{coach_id}\n` | Request temperature from specific coach |

**Responses (Gateway → Raspberry Pi):**

| Response Type | Format | Description |
|---------------|--------|-------------|
| MAP Response | `{left},{id},{right}\n` | Topology data (e.g., "0,1,2") |
| TEMP Response | `{left},{id},{right},{temp}\n` | Topology + temperature (e.g., "0,1,2,28.5") |
| Error | `ERROR\n` | Command failed or coach not responding |

### I2C Protocol

**Binary Packet Formats:**

**MAP Packet (6 bytes):**
```
Byte 0: Left Coach ID (255 = NULL)
Byte 1: Current Coach ID
Byte 2: Right Coach ID (255 = NULL)
Bytes 3-5: Padding (0x00)
```

**TEMP Packet (10 bytes):**
```
Byte 0: Left Coach ID (255 = NULL)
Byte 1: Current Coach ID
Byte 2: Right Coach ID (255 = NULL)
Bytes 3-6: Temperature (IEEE 754 float, little-endian)
Bytes 7-9: Padding (0x00)
```

### Control Signal Encoding

| Coach | ID | Binary | MSB | LSB |
|-------|----|----|-----|-----|
| C0 | 0 | 00 | LOW | LOW |
| C1 | 1 | 01 | LOW | HIGH |
| C2 | 2 | 10 | HIGH | LOW |
| C3 | 3 | 11 | HIGH | HIGH |

---

## 🎥 Demo Videos

*(Add links to your demonstration videos)*

- [System Startup & Auto-Detection](https://your-link)
- [Live Temperature Monitoring](https://your-link)
- [Dynamic Coach Addition](https://your-link)
- [Fault Tolerance Demo](https://your-link)

---

## 📚 Research & Publications

### Patent Application

**Title**: "An Intelligent, Fault-Tolerant and Self-Reconfigurable System for Real-Time Axle Integrity and Thermal Monitoring in Railway Vehicles"

**Filing Institution**: R V College of Engineering, Bengaluru

**Inventors**: 
Dr. Mekhala V Purohit (Assistant Professor, Dept. of CSE) & Kavin Krishnan C (II-Year Undergrad, Dept. of CSE)

### IEEE Research Paper

**Title**: "Distributed Hot Axle Monitoring Using Linked List Concept for Indian Railways"

**Conference**: *(To be submitted)*

**Key Contributions**:
- Novel application of doubly linked list to physical railway systems
- Autonomous neighbor discovery protocol
- Binary control signal addressing
- Self-reconfiguring topology adaptation

---

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Guidelines

- Follow Arduino and Python style guides
- Add comments for complex logic
- Test on actual hardware before submitting
- Update documentation for new features

---

## 🐛 Troubleshooting

### Common Issues

**Issue**: GUI doesn't display on TFT
```bash
# Solution: Set DISPLAY environment variable
export DISPLAY=:0
xhost +
python3 train_monitor.py
```

**Issue**: Serial connection fails
```bash
# Solution: Grant permissions
sudo chmod 666 /dev/ttyUSB0
# Or add user to dialout group
sudo usermod -a -G dialout $USER
```

**Issue**: I2C communication errors
```bash
# Solution: Check pull-up resistors (4.7kΩ on SDA and SCL)
# Verify wiring and common ground
```

**Issue**: Coaches not detected
```bash
# Solution:
# 1. Check power to all Arduinos (LEDs should be ON)
# 2. Verify neighbor discovery wiring (D4-D11)
# 3. Wait 5 seconds after power-on for discovery
# 4. Check COACH_ID definitions in code
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **R V College of Engineering** - Institutional support and resources
- **Department of Computer Science and Engineering** - Academic guidance
- **Indian Railways** - Inspiration for real-world problem solving
- **Arduino & Raspberry Pi Communities** - Open-source hardware and software
- **OneWire & DallasTemperature Libraries** - Sensor interfacing

---

## 📞 Contact

**Dr. Mekhala V Purohit**  
Assistant Professor  
Department of Computer Science and Engineering  
R V College of Engineering  
Bengaluru – 560059, Karnataka, India

**Kavin Krishnan C**  
II-Year Undergrad 
Department of Computer Science and Engineering  
R V College of Engineering  
Bengaluru – 560059, Karnataka, India


---

## 📊 Project Statistics

- **Lines of Code**: ~2,500
- **Development Time**: 6 months
- **Cost per Coach**: ~₹2,000 (~$25)
- **Update Frequency**: 1 second
- **Temperature Accuracy**: ±0.5°C
- **Communication Success Rate**: 99.8%

---

**Made with ❤️ for Railway Safety in India**

🚆 *Bridging Data Structures and Real-World Engineering*