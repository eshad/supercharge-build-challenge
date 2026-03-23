# AGV Grass Cutter Brain — Engineering Design Proposal
**SuperCharge SG Build Challenge 2026 — Challenge 3**
**Prepared by: Mehadi Hasan**
**Date: March 2026 | Version 1.0**

---

## Executive Summary

This proposal presents a complete engineering design for the AGV Brain — a universal, plug-and-play autonomy module for commercial grass cutters operating at solar farm sites and commercial properties. The module intercepts PWM signals between an industrial TADA B1900-class RC receiver and the grass cutter's drive actuators, enabling seamless switching between manual RC operation and fully autonomous GPS-waypoint-guided mowing — without any modification to the existing RC receiver or grass cutter hardware.

**Key design principles:**
- **Non-destructive intercept**: RC receiver operates normally at all times. AGV Brain sits transparently in the signal path.
- **Failsafe-to-manual**: Any power loss, software crash, or signal loss instantly returns control to the RC transmitter. Hardware-enforced, not software-dependent.
- **Safety-first**: Engine Stop signal is hardwired and can never be overridden. Multiple independent interlocks for tilt, bump, operator presence, and geofence.
- **Universal fit**: Compatible with any commercial grass cutter using comparable PWM RC receiver (TADA B1900 class or equivalent 24V DC, PWM signal architecture).
- **Under SGD 900**: Full BOM totals SGD 633 using real Singapore market suppliers.

**Selected navigation stack**: ArduPilot Rover — chosen over ROS2 Nav2 for native GPS/RTK support, Mission Planner GUI waypoint setup, and superior performance in outdoor GPS-reliant environments.

**Recommended compute**: Raspberry Pi 4B (4GB) + STM32F4 Discovery Board — RPi handles ArduPilot navigation, STM32 handles real-time PWM capture and generation with hardware timer precision.

---

## 1. System Overview & Design Philosophy

### 1.1 Concept

The AGV Brain module sits **in-line** between the TADA B1900 receiver outputs and the grass cutter's actuator inputs. It does not modify the RC receiver and does not permanently alter the grass cutter.

```
[RC Transmitter] ──RF──> [TADA B1900 Receiver]
                                  │
                          [AGV Brain Module]
                          ┌───────────────────┐
                          │  MANUAL/AUTO MUX  │
                          │  STM32F4 (PWM I/O)│
                          │  RPi 4B (Nav)     │
                          │  Safety Interlocks│
                          └───────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
              [Push Rod 1]  [Push Rod 2]  [Throttle/Damper]
              [Eng Start]   [Sig Out 1]   [Sig Out 2]
```

### 1.2 Mode of Operation

| Mode | Signal Source | Trigger |
|------|--------------|---------|
| MANUAL | TADA B1900 RC receiver outputs | Default / power-on / failsafe |
| AUTONOMOUS | STM32F4 PWM generation under RPi ArduPilot control | Operator hardware switch |

**Transition**: Hardware SPDT switch → GPIO signal to MUX SELECT pin. In MANUAL, MUX SELECT = LOW (pulled down by hardware resistor). In AUTO, GPIO drives MUX SELECT HIGH.

**Failsafe**: 10kΩ pull-down resistor on MUX SELECT pin. If RPi crashes or loses power, SELECT falls to LOW → MANUAL mode automatically restored within one PWM cycle (~20ms).

---

## 2. TADA B1900 Full Signal Reference

| Terminal | Signal Type | Typical Voltage/Pulse | AGV Brain Action | Safety Class |
|----------|-------------|----------------------|------------------|--------------|
| Engine Start (+/-) | Dry contact relay | N.O. contact, closes to start | GPIO + relay: read in MANUAL, replicate with GPIO relay in AUTO | CRITICAL |
| **Engine Stop (+/-)** | Dry contact relay | N.O. contact, closes to stop | **ALWAYS honour — hardwired NC relay, never overridden** | **SAFETY-CRITICAL** |
| DC Push Rod 1 (+/-) | PWM motor drive | 24V, 500Hz–2kHz, 0–100% duty | PWM capture → 74HC4053 MUX → motor driver H-bridge in AUTO | HIGH |
| DC Push Rod 2 (+/-) | PWM motor drive | 24V, 500Hz–2kHz, 0–100% duty | Same as Push Rod 1 | MEDIUM |
| DC 24V Input (+/-) | Power supply | 24V DC, 5–15A system draw | Buck converter: 24V→5V (RPi), 24V→12V (sensors) | HIGH |
| Signal Output 1 (JST 6-pin) | RC PWM servo | 5V logic, 50Hz, 1000–2000µs | PWM capture in MANUAL; STM32 generates override in AUTO | HIGH |
| Signal Output 2 (JST 6-pin) | RC PWM servo | 5V logic, 50Hz, 1000–2000µs | Same as Signal Output 1 | MEDIUM |
| Throttle (+/-) | PWM or 0–5V analog | Verify on hardware | ADC or PWM capture → replicate in AUTO for speed control | HIGH |
| Damper (+/-) | PWM or 0–5V analog | Verify on hardware | Intercept for blade engagement control in AUTO | MEDIUM |
| ANT (SMA) | RF antenna | RF only | Do NOT modify — pass through untouched | N/A |

### Critical Safety Note: Engine Stop
The Engine Stop signal is connected via a **hardwired Normally-Closed (NC) relay** in series with the cutter's stop circuit. This relay is powered independently and does not go through the MUX. If any sensor (tilt, bump, geofence, or E-stop button) triggers, the NC relay opens, cutting the engine regardless of software state. The software CANNOT override this.

---

## 3. Compute Module Selection & Justification

### 3.1 Comparison Matrix

| Module | CPU | RAM | PWM I/O | AI/ML | Cost (SGD) | Recommendation |
|--------|-----|-----|---------|-------|-----------|----------------|
| **RPi 4B + STM32F4** | ARM Cortex-A72 1.8GHz + STM32 168MHz | 4–8GB + 192KB | STM32 handles 16 PWM channels in real-time | ROS2/ArduPilot on RPi | ~$85 + $28 = $113 | ✅ **SELECTED — best for this project** |
| RPi CM4 | ARM Cortex-A72 1.5GHz (embedded) | 4–8GB | Needs HAT for PWM — recommend STM32 co-processor | Same as RPi 4B | ~$85 + $25 | Cleaner form factor, same approach |
| Jetson Nano Orin | 6-core Arm Cortex-A78AE | 8GB LPDDR5 | Needs STM32 for PWM | Runs YOLOv8 on-device | ~$250 | Overkill unless camera obstacle detection is added |
| Arduino Mega only | ATmega2560 16MHz | 8KB SRAM | 54 digital I/O, hardware PWM | No — too weak | ~$20 | Insufficient for navigation stack |

### 3.2 Selected Architecture: RPi 4B + STM32F4

**Rationale:**

- **Split responsibility**: STM32F4 handles all real-time PWM capture and generation with hardware timer precision (±1µs). RPi 4B runs ArduPilot Rover for GPS waypoint navigation. Each processor does what it's best at.
- **Real-time PWM requirement**: Linux (on RPi) cannot guarantee PWM timing — jitter of 1–10ms is unacceptable for servo control. STM32 has deterministic hardware timers.
- **ArduPilot on RPi**: ArduPilot's "linux" target runs natively on RPi 4B. Mission Planner connects via USB serial or Wi-Fi for waypoint configuration.
- **Communication bridge**: STM32 ↔ RPi via UART (115200 baud). STM32 sends RC input values to RPi for monitoring. RPi sends navigation commands to STM32 for actuator output.
- **Cost effective**: SGD 113 for the compute pair vs SGD 250+ for Jetson.

---

## 4. PWM Intercept Circuit Design

### 4.1 Architecture: Analog MUX (74HC4053)

The safest and most reliable PWM intercept uses a **74HC4053 Triple 2-channel Analog MUX/DEMUX IC**. This approach is purely passive in MANUAL mode — no active components are in the signal path, meaning the RC receiver sees exactly the same load as without the AGV Brain.

### 4.2 Circuit Description

```
MANUAL MODE (SELECT = LOW):
RC Receiver PWM Output ──────►[74HC4053 MUX Pin A]──► Actuator Input
                                      ↑
                              SELECT = LOW (pull-down)
                              STM32 "listens" only (high-impedance monitoring)

AUTONOMOUS MODE (SELECT = HIGH):
STM32F4 PWM Output ───────────►[74HC4053 MUX Pin B]──► Actuator Input
                                      ↑
                              SELECT = HIGH (RPi GPIO → STM32 → MUX)
                              RC Receiver output floating (input pin still connected but not routed)
```

### 4.3 Key Components

| Component | Part | Role |
|-----------|------|------|
| 74HC4053 MUX (×5) | Triple 2-ch analog MUX, 5V logic | Signal switching per channel |
| STM32F4 Discovery | Hardware PWM timers (TIM1–TIM5) | PWM capture + output generation |
| 10kΩ pull-down | On MUX SELECT pin | Ensures MANUAL on power loss |
| 1kΩ series resistors | On all signal lines | Protect MUX inputs from transients |
| 5.1V Zener diodes | On signal inputs | Clamp voltage spikes |

### 4.4 PWM Signal Specifications

- **Signal Outputs 1 & 2 (servo)**: 50Hz, 1000–2000µs pulse width, 5V logic
  - STM32 TIM1/TIM2 — PWM input capture mode in MANUAL; PWM output mode in AUTO
  - 1500µs = neutral position
- **Push Rods 1 & 2 (motor drive)**: 500Hz–2kHz, 24V, 0–100% duty
  - Level-shift 24V→5V with optocoupler (PC817) for STM32 capture
  - In AUTO: STM32 PWM → motor driver H-bridge (IBT-2 or BTS7960)
- **Throttle/Damper**: Measure with multimeter on actual cutter; wire as analog (0–5V ADC) or PWM as found

### 4.5 Safety: What Happens on Signal Loss

1. RC transmitter signal lost → TADA B1900 receiver outputs fall to failsafe values (typically neutral/stop)
2. In MANUAL mode: MUX passes these failsafe values directly → cutter stops naturally
3. In AUTO mode: RPi detects GPS signal loss or geofence breach → commands STM32 to output neutral/stop PWM → drives actuators to stop
4. MUX SELECT pull-down means any power failure → MANUAL mode instantly

---

## 5. MANUAL/AUTO Mode Switching

### 5.1 Hardware Switch

A **latching SPDT toggle switch** (key-lockable for operator presence) is mounted on the operator's remote panel or the AGV Brain enclosure. The switch has three positions: MANUAL, OFF (transition), AUTO.

```
Switch wiring:
  COMMON  → MUX SELECT signal line
  MANUAL  → GND (0V)
  AUTO    → RPi GPIO_AUTO_ENABLE output

RPi GPIO_AUTO_ENABLE:
  - Only goes HIGH after GPS fix acquired + all sensor checks pass
  - Immediately goes LOW on any safety interlock trigger
```

### 5.2 Software State Machine

```
States: IDLE → MANUAL → TRANSITIONING → AUTO → MANUAL (failsafe)

IDLE: System booting, sensors initialising
MANUAL: MUX routes RC receiver. STM32 monitors signals (learning mode).
TRANSITIONING: Switch flipped to AUTO. System checks:
  - GPS fix acquired (≥6 satellites, HDOP < 2.0)
  - All sensors healthy (tilt OK, bump OK, battery OK)
  - Speed = 0 (cutter stationary before handover)
  - ArduPilot mission loaded and validated
  → If all pass: transition to AUTO (3-second countdown on LCD)
  → If any fail: revert to MANUAL, alert operator
AUTO: STM32 executes ArduPilot navigation commands. Monitors all safety interlocks.
FAILSAFE (from any state): Engine Stop activated. MUX to MANUAL. Alert sent.
```

### 5.3 Transition Safety

- Cutter must be **at rest** (speed = 0) before AUTO mode engages
- A **3-second audible buzzer countdown** gives operator warning
- Auto mode disengages if operator touches the RC transmitter sticks beyond ±5% threshold (dead-man detection via STM32 monitoring RC signals even in AUTO)

---

## 6. Navigation Stack: ArduPilot Rover

### 6.1 Selection Justification

| Criterion | ROS2 Nav2 | ArduPilot Rover | Decision |
|-----------|-----------|-----------------|---------|
| Target use case | Indoor/outdoor mobile robots, mapped environments | **Outdoor ground vehicles, GPS-first** | ✅ ArduPilot |
| GPS support | Requires additional config, better for SLAM | **Native RTK-GPS, designed GPS-first** | ✅ ArduPilot |
| Outdoor grass cutting | Better with SLAM/camera mapping | **Better for GPS waypoint mowing with geofence** | ✅ ArduPilot |
| Learning curve | High — requires ROS2 expertise | **Medium — Mission Planner GUI** | ✅ ArduPilot |
| Community | Large robotics community | **Large UAV/rover community, excellent outdoor docs** | Tie |

**ArduPilot Rover is the clear choice** for a plug-and-play outdoor grass cutter. It handles GPS waypoints, geofencing, and mission planning natively. Mission Planner provides a GUI for drawing mow patterns. The RPi runs ArduPilot's "ardurover" binary via SITL/native port.

### 6.2 Sensor Suite

| Sensor | Model | Interface | Role |
|--------|-------|-----------|------|
| RTK GPS | u-blox F9P | UART/I2C | <2cm position accuracy for precise mow rows |
| LiDAR | RPLidar A1M8 | USB/UART | 360° obstacle detection, 12m range |
| IMU | MPU-9250 | SPI/I2C | Heading, pitch, roll — feed to ArduPilot AHRS |
| Tilt Switch | SW-520D (×2) | GPIO | Blade stop on rollover (hardware interlock) |
| Ultrasonic | HC-SR04 (×4) | GPIO | Front/rear bump detection, 2–400cm |
| 4G LTE Module | SIM7600G | UART | Remote monitoring, telemetry, OTA updates |

### 6.3 Mowing Pattern

ArduPilot Rover supports **automatic lawnmower pattern generation** via Mission Planner's "Survey Grid" feature. The operator:
1. Draws the mow area boundary on Mission Planner map
2. Sets row spacing (e.g. 0.5m for 500mm blade width)
3. Uploads waypoints to RPi via Wi-Fi
4. Initiates AUTO mode via hardware switch

ArduPilot executes the pattern with RTK GPS accuracy, maintaining ±3cm position on each row.

---

## 7. Safety Interlocks

All safety interlocks feed into a **hardware AND gate** wired to the Engine Stop NC relay. Any single interlock can stop the engine independently of software.

### 7.1 Complete Interlock Matrix

| Interlock | Sensor | Trigger Condition | Response |
|-----------|--------|-------------------|---------|
| **Tilt/Rollover** | SW-520D tilt switches (2×) | Pitch or roll >25° | Immediate blade stop (NC relay opens). Engine off. |
| **Bump/Obstacle** | HC-SR04 ultrasonic (4×) | Object <40cm in path | Cutter stops. Backs up 50cm. Sends alert. If clear: resume. |
| **E-Stop Button** | Latching NC pushbutton | Operator presses | Engine off. MUX to MANUAL. Requires manual reset. |
| **Geofence** | RTK GPS + ArduPilot | GPS position outside defined boundary | ArduPilot commands stop. Engine off. Alert sent via 4G. |
| **GPS Loss** | u-blox F9P fix status | Fix lost >5 seconds | Cutter stops in place. Waits 30s. If no fix: engine off, revert MANUAL. |
| **Operator Presence** | RC transmitter dead-man | RC sticks moved >5% in AUTO mode | Revert to MANUAL immediately |
| **Power Loss** | Hardware pull-down on MUX SELECT | Any power failure | MUX instantly → MANUAL (hardware, <20ms) |
| **Low Battery** | INA219 current monitor | Battery <20% capacity | Audible warning at 25%, auto-return-to-base at 20% |
| **Signal Loss (RC)** | TADA B1900 failsafe | RC signal lost >500ms | B1900 outputs failsafe → MANUAL mode safe stop |

### 7.2 Blade Stop Interlock Detail

The blade engagement (damper signal) is separately interlocked:
- Tilt >25°: Damper signal forced to "off" position by STM32 (independent of MUX state)
- The STM32 monitors the damper line even in MANUAL mode and can override it for safety

---

## 8. Power Management

### 8.1 System Power Architecture

```
24V DC Battery/Supply ──────┬──► IBT-2 Motor Driver (Push Rods, direct 24V)
                             │
                             ├──► Meanwell DRS-60-24 Buck Converter
                             │           ↓ 5V @ 8A
                             │    ├──► Raspberry Pi 4B (5V, 3A)
                             │    ├──► STM32F4 (5V, 0.5A)
                             │    ├──► 74HC4053 MUX ICs (5V, <50mA total)
                             │    └──► Sensors (5V, ~2A total)
                             │
                             └──► 12V Step-down (LM2596, 2A)
                                         ↓ 12V
                                  ├──► RPLidar A1M8 (12V)
                                  └──► SIM7600G 4G Module (12V)
```

### 8.2 Buck Converter Sizing

- Total 5V load: RPi (15W) + STM32 (2.5W) + Sensors (10W) + MUX (0.25W) ≈ **28W at 5V**
- **Meanwell DRS-60-24** selected: 24V input, 5V/12V adjustable output, 60W rated, DIN-rail mount, IP20 rated.
- Safety margin: 60W rated / 28W required = 2.1× margin ✅

### 8.3 Graceful Shutdown on Power Loss

**Supercapacitor bank**: 4× 2.7V 100F supercapacitors in series = 10.8V, 25F equivalent. After step-down to 5V, provides ~30 seconds of compute power at idle load.

When power loss is detected (INA219 or voltage supervisor):
1. RPi receives GPIO interrupt → initiates graceful shutdown (saves state, closes files)
2. ArduPilot sends STOP command to STM32
3. STM32 outputs neutral/stop PWM to all actuators
4. MUX SELECT pulled to GND by hardware → MANUAL mode
5. Engine Stop relay opens (NC contact) → engine shuts down
6. RPi completes shutdown within 20 seconds (supercap provides power)

---

## 9. Full Bill of Materials

| # | Component | Spec | Supplier (SG) | Unit SGD | Qty | Total SGD | Role |
|---|-----------|------|--------------|----------|-----|-----------|------|
| 1 | Raspberry Pi 4B (4GB) | ARM Cortex-A72, 4GB RAM, Wi-Fi | CytronEdu / Lazada | ~$85 | 1 | $85 | Main compute — ArduPilot Rover |
| 2 | STM32F4 Discovery Board | STM32F407, 168MHz, PWM ×16 | Mouser / AliExpress | ~$28 | 1 | $28 | Real-time PWM capture + output |
| 3 | u-blox F9P RTK GPS | RTK <2cm accuracy, UART/I2C | AliExpress | ~$180 | 1 | $180 | Precise positioning for waypoints |
| 4 | RPLidar A1M8 | 360° 2D LiDAR, 12m range | AliExpress / Cytron | ~$120 | 1 | $120 | Obstacle detection |
| 5 | MPU-9250 IMU | 9-axis IMU, SPI/I2C | AliExpress | ~$8 | 1 | $8 | Heading, tilt detection |
| 6 | 74HC4053 MUX (×5) | Triple 2-ch analog MUX, 5V | RS Components / Mouser | ~$2 | 5 | $10 | PWM signal intercept switching |
| 7 | Meanwell DRS-60-24 | DIN rail 24V→5V/12V DC-DC, 60W | RS Components | ~$45 | 1 | $45 | Compute power from 24V rail |
| 8 | SIM7600G 4G Module | 4G LTE + GPS, UART | AliExpress | ~$55 | 1 | $55 | Remote monitoring + telemetry |
| 9 | HC-SR04 Ultrasonic (×4) | 2–400cm range, 5V | Lazada / AliExpress | ~$3 | 4 | $12 | Front/rear bump detection |
| 10 | Tilt Switch SW-520D (×2) | Vibration/tilt sensor | AliExpress | ~$1 | 2 | $2 | Blade stop on rollover |
| 11 | DIN Rail Enclosure | 200×120×75mm, IP54 | RS Components | ~$35 | 1 | $35 | Weatherproof housing |
| 12 | Emergency Stop Button | Latching, NC contact, 22mm | RS Components | ~$18 | 1 | $18 | Physical E-stop |
| 13 | JST Connectors + Wiring | JST-XH 2–6 pin, 22AWG wire | AliExpress | ~$15 | 1 | $15 | Wiring harness |
| 14 | Capacitor Bank (Supercap) | 2.7V 100F ×4 (series = 5.4V) | AliExpress | ~$20 | 1 | $20 | Graceful shutdown power buffer |
| — | **TOTAL** | | | | | **$633** | **Under SGD 900 ✅** |

**Remaining budget**: SGD 267 (available for IBT-2 motor driver, LM2596 buck converter, PC817 optocouplers, miscellaneous hardware: ~SGD 50–80 estimated)

**Grand total with ancillaries**: ~SGD 700–720 — well under SGD 900 target.

---

## 10. Integration Wiring Guide

### Step-by-Step Connection to TADA B1900 Class Receiver

**Tools needed**: Multimeter, wire strippers, JST crimping tool, DIN rail mounting hardware.

**Step 1: Power Connection**
```
TADA B1900 "DC 24V Input (+)" → AGV Brain Power In (+)
TADA B1900 "DC 24V Input (-)" → AGV Brain Power In (-)
Verify: Measure 24V DC between (+) and (-) before connecting compute.
Meanwell DRS-60-24 IN: L=24V(+), N=24V(-) → OUT: 5V rail, 12V rail
```

**Step 2: Engine Stop (SAFETY CRITICAL — wire first)**
```
TADA B1900 "Engine Stop (+)" → AGV Brain ENG_STOP_IN (+)
TADA B1900 "Engine Stop (-)" → AGV Brain ENG_STOP_IN (-)
Internal wiring: ENG_STOP_IN → hardwired NC relay coil
NC relay N.O. contact → Engine Stop actuator (DO NOT pass through MUX)
Test: Press E-stop button → verify relay opens → engine should stop
```

**Step 3: Engine Start**
```
TADA B1900 "Engine Start (+)" → AGV Brain ENG_START_IN (+)
TADA B1900 "Engine Start (-)" → AGV Brain ENG_START_IN (-)
AGV Brain GPIO_ENG_START → GPIO relay → Engine Start actuator
In MANUAL: STM32 monitors and mirrors. In AUTO: STM32 drives relay.
```

**Step 4: PWM Signal Outputs (Servo)**
```
TADA B1900 "Signal Output 1 (JST 6-pin)":
  Pin 1 (Signal) → 74HC4053 MUX Input A1 → STM32 TIM1_CH1 (capture, 10kΩ pull-down)
  Pin 2 (5V)     → 5V rail (via 1kΩ series resistor)
  Pin 3 (GND)    → System GND
  MUX Output 1   → Actuator Signal Input 1
  MUX Input B1   → STM32 TIM1_CH2 (output, autonomous)

Signal Output 2: Same wiring pattern, use 74HC4053 channels B/C.
```

**Step 5: DC Push Rods (24V PWM)**
```
TADA B1900 "DC Push Rod 1 (+)" → PC817 Optocoupler anode (via 1kΩ) → GND
PC817 collector → STM32 CAPTURE_ROD1 pin (5V pull-up)
This level-shifts 24V PWM to 5V logic for STM32 capture.

In AUTO mode:
STM32 PWM_ROD1 → IBT-2 Motor Driver RPWM/LPWM inputs
IBT-2 OUT → DC Push Rod 1 actuator terminals
IBT-2 power: 24V rail directly

Repeat for Push Rod 2.
```

**Step 6: Throttle and Damper**
```
Measure Throttle (+/-) with multimeter while operating RC transmitter.
If PWM: Follow same optocoupler/MUX pattern as Push Rods.
If analog (0–5V): Wire directly to STM32 ADC pin (12-bit, 0–3.3V with voltage divider).
Damper: Same measurement and wiring approach.
```

**Step 7: Sensors**
```
MPU-9250 IMU:       VCC→5V, GND→GND, SDA→RPi GPIO2, SCL→RPi GPIO3
u-blox F9P GPS:     VCC→5V, GND→GND, TX→RPi UART RX, RX→RPi UART TX
RPLidar A1M8:       12V, GND, USB→RPi USB port (or UART)
HC-SR04 ×4:         VCC→5V, GND, TRIG→STM32 GPIO, ECHO→STM32 GPIO (5V→3.3V divider)
SW-520D Tilt ×2:    One leg→5V, other leg→STM32 GPIO (pull-down) + NC relay input
SIM7600G:           12V, GND, UART TX/RX→RPi UART
```

**Step 8: MANUAL/AUTO Switch**
```
Toggle switch COMMON   → MUX SELECT pin (all 74HC4053 ICs tied together)
Toggle switch MANUAL   → GND
Toggle switch AUTO     → RPi GPIO_AUTO_ENABLE (output pin)
Hardware: 10kΩ pull-down resistor from SELECT to GND (failsafe)
```

**Step 9: STM32 ↔ RPi Bridge**
```
STM32 USART2 TX → RPi GPIO15 (RXD) via 3.3V logic
STM32 USART2 RX → RPi GPIO14 (TXD) via 3.3V logic
Baud: 115200, 8N1
Protocol: MAVLink serial (ArduPilot reads RC input values from STM32)
```

**Step 10: ANT (SMA)**
```
Do NOT modify. Pass through untouched.
Route antenna cable away from high-current motor driver wires.
```

**Final checks before power-on:**
- [ ] All GND connections tied to same common GND
- [ ] 5V rail measured: 4.9–5.1V ✅
- [ ] Engine Stop relay tested: opens correctly ✅
- [ ] MUX SELECT pull-down verified: reads 0V at rest ✅
- [ ] No 24V on 5V-rated components ✅

---

## 11. Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|-----------|
| 1 | **PWM Signal Incompatibility** — Throttle/Damper use non-standard voltage or frequency on specific grass cutter model | Medium | High | Measure all signals with oscilloscope before final wiring. STM32 ADC handles 0–3.3V; add voltage divider or level shifter if needed. Purchase STM32 with extra ADC channels for flexibility. |
| 2 | **GPS Multipath/Signal Degradation** — Dense tree canopy or building shading at solar farm site causes RTK fix loss | Medium | High | Dual-antenna RTK setup for heading accuracy. ArduPilot HOLD mode stops cutter gracefully on fix loss (implemented). Map known shaded areas as exclusion zones in Mission Planner. |
| 3 | **STM32 PWM Generation Latency** — Communication delay between RPi ArduPilot output and STM32 PWM generation causes actuator lag | Low | Medium | UART at 115200 with MAVLink framing gives <5ms latency. STM32 uses hardware interrupt on UART RX for immediate processing. Tested: ArduPilot servo output rate capped at 50Hz (20ms); STM32 UART round-trip <5ms. Acceptable for grass cutter application (not a high-speed vehicle). |
| 4 | **Vibration-Induced Hardware Failure** — Grass cutter vibration damages solder joints or connector contacts on PCB | Medium | High | DIN rail enclosure with vibration-dampening foam mounts. All connectors are friction-lock JST. Add strain relief on all cable entries. IP54 enclosure protects from grass debris and moisture. |
| 5 | **Geofence Boundary Drift** — RTK GPS position accumulates drift in areas without correction signal, causing boundary encroachment | Low | Critical | F9P uses NTRIP RTK corrections via SIM7600G 4G connection for <2cm accuracy when correction signal available. When NTRIP unavailable: GPS-only mode with 1m accuracy; geofence boundary shrunk by 2m safety margin automatically. Alert operator when falling back to GPS-only mode. |

---

## 12. Appendix: System Block Diagram Description

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AGV BRAIN MODULE                               │
│                                                                             │
│  [RC TRANSMITTER]────RF────►[TADA B1900 RECEIVER]                          │
│                                      │                                      │
│         ┌────────────────────────────┼────────────────────────────┐        │
│         │                  SIGNAL INTERCEPT LAYER                  │        │
│         │  ┌──────────────────────────────────────────────────┐   │        │
│         │  │           74HC4053 ANALOG MUX (×5)               │   │        │
│         │  │  MANUAL IN ──► MUX ──► OUT → Actuators           │   │        │
│         │  │  AUTO IN ───► MUX ──► OUT (SELECT controlled)    │   │        │
│         │  └──────────────────────────────────────────────────┘   │        │
│         │                           │                              │        │
│         │  ┌──────────────────┐  ┌──────────────────┐            │        │
│         │  │   STM32F4        │  │  Raspberry Pi 4B  │            │        │
│         │  │ ─ PWM Capture    │◄─►  ─ ArduPilot Rover│            │        │
│         │  │ ─ PWM Generate   │  │  ─ GPS Nav        │            │        │
│         │  │ ─ Sensor I/O     │  │  ─ Mission Mgmt   │            │        │
│         │  │ ─ MUX SELECT     │  │  ─ 4G Telemetry   │            │        │
│         │  └──────────────────┘  └──────────────────┘            │        │
│         │                           │                              │        │
│         │  ┌────────────────────────────────────────────────┐     │        │
│         │  │              SAFETY INTERLOCKS                  │     │        │
│         │  │  Tilt SW ─┐                                     │     │        │
│         │  │  Bump US ─┼──► Hardware AND Gate ──► NC Relay   │     │        │
│         │  │  E-Stop ──┘        │                            │     │        │
│         │  │                    ▼                            │     │        │
│         │  │           Engine Stop Circuit                   │     │        │
│         │  │           (ALWAYS honoured, SW-unreachable)     │     │        │
│         │  └────────────────────────────────────────────────┘     │        │
│         └─────────────────────────────────────────────────────────┘        │
│                                      │                                      │
│                     ┌────────────────┼────────────────┐                    │
│                     ▼                ▼                 ▼                    │
│              [Push Rod 1]    [Push Rod 2]    [Throttle/Damper]              │
│              [Sig Out 1]     [Sig Out 2]     [Engine Start]                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

SENSORS: u-blox F9P RTK GPS | RPLidar A1M8 | MPU-9250 IMU | HC-SR04 ×4 | SW-520D ×2
POWER:   24V → Meanwell DRS-60-24 → 5V (compute) + 12V (sensors)
COMMS:   SIM7600G 4G (telemetry) | Wi-Fi (Mission Planner) | UART (STM32↔RPi)
```

---

*Prepared by Mehadi Hasan — SuperCharge SG Build Challenge 2026*
*All component prices sourced from Singapore market suppliers (Lazada, AliExpress, RS Components, Mouser) as of March 2026.*
