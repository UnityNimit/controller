# Controller v1.1.0 to v2.0.0 Diagnostic Report: Mobile Fighting Game Input Optimization

## Executive Summary

During competitive playtesting of **Controller** with *Brawlhalla Mobile* and PC platform fighters, several critical control anomalies were identified:
1. **70% to 90% Missed Combo Inputs**: Rapid combination attacks, jump-cancels, and quick button actuations failed to register in the game engine.
2. **Stick Drift**: The virtual controller exhibited uncommanded directional creep and residual post-flick drift even after releasing the on-screen joystick.
3. **Hyper-Sensitive / "Too Fast" Analog Joystick**: Directional movement snapped abruptly from neutral to 100% full tilt with minimal thumb travel, and horizontal movements frequently misfired as unintended vertical/diagonal attacks.

This report provides the exhaustive technical diagnosis, mathematical root cause analysis, and the architectural blueprint implemented in `version2` to achieve tournament-grade responsiveness.

---

## 1. Root Cause Analysis: 70%–90% Missed Combo Inputs

```mermaid
sequenceDiagram
    participant Phone as Mobile Touch Digitizer
    participant WiFi as Local Wi-Fi (A-MPDU Burst)
    participant Server as Server AsyncIO Loop
    participant MCU as 1000 Hz Virtual MCU Latch
    participant Driver as ViGEmBus Kernel (XInput)
    participant Game as PC Game Engine (60 FPS Poll)

    Note over Game: Frame 1 Poll (XInputGetState) -> Button X = 0
    Phone->>WiFi: Quick Combo Tap: Button X Pressed (t = 0ms)
    Phone->>WiFi: Quick Combo Tap: Button X Released (t = 15ms)
    Note over WiFi: 802.11 TCP Micro-Burst Arrival
    WiFi->>Server: Packet 1 (X=1) and Packet 2 (X=0) arrive in single read
    Server->>MCU: Iteration 1: latch['X'] = True (t = 16.00ms)
    Server->>MCU: Iteration 2: latch['X'] = False (t = 16.03ms)
    Note over MCU: Button was True for 0.03ms! Overwritten before 1ms tick!
    MCU->>Driver: No actuation sent (or held for <= 1ms)
    Note over Game: Frame 2 Poll (XInputGetState at t = 16.66ms) -> Button X = 0!
    Note over Game: Result: INPUT COMPLETELY MISSED (0% detection)
```

### A. The XInput State Snapshot Architecture
Unlike Windows desktop keyboard (`WM_KEYDOWN`) or mouse events, the DirectX `XInput` subsystem operates strictly via **state polling** (`XInputGetState()`). 
* There is **no operating-system event queue** for controller button presses.
* A game running at 60 frames per second queries controller state once every **16.66 milliseconds** (or once every 8.33 ms at 120 FPS).
* If a virtual controller presses a button and releases it between two successive calls to `XInputGetState()`, the game engine never detects the button press.

### B. Microsecond Latch Overwriting in `mcu_dispatch.py`
In competitive mobile play, a rapid attack tap lasts between 15 ms and 30 ms. Over local Wi-Fi, 802.11 frame aggregation causes these two packets (`down` and `up`) to arrive at the PC host in the same network socket buffer.
* In `gateway/server.py`, the loop processed both packets within **0.03 milliseconds** (30 microseconds).
* The atomic latch dictionary in `gateway/mcu_dispatch.py` was updated to `True` and immediately overwritten back to `False`.
* Because the Virtual MCU thread executes once every **1.0 millisecond** (1000 Hz), the button was reset before the MCU thread even woke up.
* Even when the MCU thread captured the press for a single 1.0 ms tick, the mathematical probability of a 60 Hz game polling during that exact 1.0 ms window is:
  $$\text{Detection Probability} = \frac{1.0\text{ ms}}{16.66\text{ ms}} \approx 6.0\%$$
  $$\text{Miss Rate} = 100\% - 6.0\% = 94.0\%$$
  This directly produced the reported **70% to 90% input drop rate** during rapid combos.

### C. Wi-Fi Coalescing Discard Bug in `gateway/server.py`
Lines 382–390 of `gateway/server.py` contained an optimization that discarded binary packets if the next message in the WebSocket deque shared the same button bitmask (`ws_msgs[0][18:20] == message[18:20]`). This logic inadvertently dropped intermediate analog stick coordinates and fast tap states during burst arrivals.

### D. Touch Digitizer Edge Cancellation in `client/js/cockpit.js`
In `handleButtonPointerMove`, if a player's thumb slid by even 1 pixel outside a button's 52px circle, `_getButtonAtPoint()` returned `null` and instantly cleared the button state. During aggressive gameplay, thumb contact patch deformation caused buttons to deactivate prematurely in the middle of attacks.

---

## 2. Root Cause Analysis: Stick Drift

```mermaid
flowchart LR
    subgraph DriftCauses ["Stick Drift Root Causes"]
        Dither["1. 1000 Hz Sub-Perceptual Dither (mcu_dispatch.py)<br/>Alternates sx between 0 and 1 every millisecond"]
        Kalman["2. Kalman Predictive Extrapolation (predictive_interpolator.py)<br/>High velocity flick projects forward into deadband bypass"]
        Snapback["3. 22ms Artificial Snapback Delay (cockpit.js)<br/>Holds 50% and 15% deflection across 3 setTimeout ticks"]
        Floating["4. Floating Joystick Origin Drift (cockpit.js)<br/>Anchor relocates on every touch, destroying muscle memory"]
    end

    DriftCauses --> Manifestation["Game Manifestation: Character Creeps, Turnaround Fails, Menus Scroll"]
```

1. **Sub-Perceptual 1000 Hz Dither**: `gateway/mcu_dispatch.py` forced `sx = 1` on alternating ticks when neutral (`sx == 0 and sy == 0`) to force `dwPacketNumber` updates. In fighting games with zero deadband, this registered as an active directional tilt.
2. **Kalman Predictive Over-Extrapolation**: `gateway/predictive_interpolator.py` projected position forward using velocity:
   $$\text{extrapolated} = \text{position} + (\text{velocity} \times dt \times \text{decay})$$
   Following rapid flicks, velocity exceeded 800 units/sec, bypassing deadband snapping and projecting non-zero coordinates for multiple frames after the finger lifted.
3. **Artificial 22ms Snapback Timeouts**: `client/js/cockpit.js` delayed zero-reset using three stepped timeouts (6 ms at 50%, 14 ms at 15%, 22 ms at 0%). At 60 FPS (16.66 ms/frame), the virtual stick remained deflected for more than an entire game frame after thumb release.
4. **Floating Origin Shift**: Re-centering the joystick anchor to wherever the thumb landed shifted the spatial zero-point on every touch, causing players to perceive continuous physical drift.

---

## 3. Root Cause Analysis: Joystick Hyper-Sensitivity ("Too Fast")

1. **40px Physical Radius**: 40 CSS pixels on high-DPI displays corresponds to only ~7.5 mm of thumb travel. Reaching 100% deflection (32,767) in 7.5 mm eliminated all progressive modulation between walking and running.
2. **2-Pixel Deadzone (5%)**: 5% of 40px is 2.0 pixels. Natural human thumb tremor on capacitive glass ranges from 3 to 6 pixels, preventing the stick from ever remaining at true neutral while touched.
3. **Absence of Cardinal Gating**: In platform fighters, 95% of inputs are strictly cardinal (Left, Right, Up, Down). Without directional snapping ($\pm 18^\circ$), pushing horizontally at a slight angle (e.g., $15^\circ$) outputs `stick_y = 8,480` (26% deflection), which games interpret as an unintended diagonal attack or jump.

---

## 4. Architectural Solutions Implemented in `version2`

### A. Frame-Paced Minimum Button Hold Latching (Input Buffer)
* Implemented a **30 ms minimum hold latch** in `VirtualMcuDispatcher`.
* When any digital button (A, B, X, Y, LB, RB, LT, RT, D-Pad, etc.) transitions from `False` to `True`, the MCU holds the hardware state active for at least **30 milliseconds** (1.8 frames at 60 Hz) before permitting release.
* Guaranteed detection: At 60 FPS, every button actuation spans at least two polling cycles ($100\%$ detection rate).

### B. Wi-Fi Burst Frame Merging
* Removed the message discard bug in `gateway/server.py`.
* All packets are processed sequentially. If multiple packets arrive in a single network burst, button bitmasks are merged via bitwise OR (`|=`) so that no intermediate tap or release can be lost.

### C. Touch Hysteresis & Slop Tolerances
* Updated `client/js/cockpit.js` so that active button presses remain bound to their originating pointer even if the thumb drifts up to 1.8x the button radius, unless explicitly sliding into an adjacent button.

### D. Zero-Drift Calibration & Instant Neutral Snap
* Removed the alternating `sx = 1` dither in `mcu_dispatch.py`.
* Removed the 3-step artificial spring snapback timeouts in `cockpit.js`. Thumb release transmits an authoritative neutral report immediately.
* Updated `predictive_interpolator.py` to immediately zero out velocity and acceleration upon receiving a neutral packet.

### E. Ergonomic Stick Scaling & Cardinal Gating
* Increased default base joystick radius from 40px to **75px** (~16 mm physical travel).
* Increased deadzone from 5% (2px) to **10%** (7.5px) to eliminate resting tremor jitter.
* Implemented **Cardinal Directional Gating** ($\pm 18^\circ$ snapping along Left, Right, Up, and Down axes).
* Supported fixed joystick mode to lock anchor coordinates and preserve spatial muscle memory.
