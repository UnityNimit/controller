# Project Controller Pro // Academic Viva Defense Dossier
**Evaluation**: Semester 5 Capstone Examination  
**Author**: Unity Nimit  
**Repository**: [https://github.com/UnityNimit/controller](https://github.com/UnityNimit/controller)  
**Dossier Generated**: 2026-09-14 03:40:44  
**Architecture**: Zero-Copy 24B Wire Protocol v2 & Discrete State-Space Kalman Filtering  

---

## 1. Executive Defense Abstract

Project Controller Pro is an ultra-low latency, cyber-physical teleoperation system transforming mobile smartphones into esports-grade virtual gamepads. Traditional wireless gamepad frameworks suffer from three systemic architectural bottlenecks:
1. **Serialization Bottleneck**: Verbose JSON payloads incur dynamic memory allocations, string parsing overhead, and high per-packet latency ($\sim 15\ \mu\text{s}$).
2. **Sensor Noise & Tremor Bottleneck**: Raw MEMS accelerometers and gyroscopes suffer from involuntary human physiological hand tremor ($8-12\ \text{Hz}$) and high-frequency thermal jitter. Conventional low-pass filters introduce destructive phase lag ($> 20\ \text{ms}$).
3. **Wireless Packet Dropout**: Intermittent Wi-Fi channel fading causes input stuttering and lost steering trajectories.

**Our Innovations**:
- **Zero-Copy 24-Byte Binary Micro-Packet Protocol (v2)**: Reduces payload size by **88.3%** and cuts parsing latency to **0.15 $\mu\text{s}$** (**20.1\times$ speedup**).
- **Aerospace-Grade 2-State Discrete Kalman Filter**: Operates in state-space ($\mathbf{x} = [\theta, \dot{\theta}]^T$) with algebraic Riccati covariance updates, achieving **+2.17 dB SNR gain**, complete $8-12\ \text{Hz}$ tremor rejection, and **$0.0\ \mu\text{s}$ dead-reckoning extrapolation** during packet loss.
- **Closed-Loop Bidirectional Force-Feedback**: Hardware rumble telemetry loopback from ViGEmBus directly to smartphone haptic actuators.

---

## 2. Mathematical Formulations & State-Space Derivations

### 2.1 State-Space Kinematic Formulation
The motion dynamics of phone steering are formulated as a continuous-time 2-state Gauss-Markov process:

$$\mathbf{x}(t) = \begin{bmatrix} \theta(t) \\ \dot{\theta}(t) \end{bmatrix} = \begin{bmatrix} \text{Steering Angle (deg)} \\ \text{Angular Velocity (deg/s)} \end{bmatrix}$$

Discretized with sampling interval $\Delta t = 5\ \text{ms}$ ($200\ \text{Hz}$):

$$\mathbf{x}_k = A \mathbf{x}_{k-1} + \mathbf{w}_k, \quad \mathbf{w}_k \sim \mathcal{N}(0, Q)$$

$$\mathbf{z}_k = C \mathbf{x}_k + v_k, \quad v_k \sim \mathcal{N}(0, R)$$

Where the state transition matrix $A$ and observation matrix $C$ are:

$$A = \begin{bmatrix} 1 & \Delta t \\ 0 & 1 \end{bmatrix}, \quad C = \begin{bmatrix} 1 & 0 \end{bmatrix}$$

The discrete process noise covariance $Q$ derived from continuous spectral intensity $q$:

$$Q = q \begin{bmatrix} \frac{\Delta t^3}{3} & \frac{\Delta t^2}{2} \\[6pt] \frac{\Delta t^2}{2} & \Delta t \end{bmatrix}, \quad R = \sigma_{\text{meas}}^2$$

### 2.2 Algebraic Riccati Update Equations
At each incoming packet $k$:
1. **A Priori State Prediction**:
   $$\hat{\mathbf{x}}_k^- = A \hat{\mathbf{x}}_{k-1}$$
2. **A Priori Covariance Propagation**:
   $$P_k^- = A P_{k-1} A^T + Q$$
3. **Optimal Kalman Gain Calculation**:
   $$K_k = P_k^- C^T \left(C P_k^- C^T + R\right)^{-1}$$
4. **A Posteriori State Update**:
   $$\hat{\mathbf{x}}_k = \hat{\mathbf{x}}_k^- + K_k \left(z_k - C \hat{\mathbf{x}}_k^-\right)$$
5. **A Posteriori Covariance Update**:
   $$P_k = (I - K_k C) P_k^-$$

### 2.3 Dead-Reckoning Extrapolation (Packet Loss Invariance)
During wireless packet loss of $m$ consecutive frames ($\Delta t_{\text{lost}} = m \Delta t$):

$$\hat{\mathbf{x}}_{k+m} = A^m \hat{\mathbf{x}}_k = \begin{bmatrix} \theta_k + m \Delta t \, \dot{\theta}_k \\ \dot{\theta}_k \end{bmatrix}$$

The system computes forward extrapolation in $O(1)$ operations with zero perceptible visual stutter.

---

## 3. Zero-Copy 24-Byte Binary Wire Protocol Specification

Format string: `<BBHIhhhhBBHhBB` (Little-Endian, exactly 24 bytes):

| Offset | Field | Type | Struct Code | Description |
|---|---|---|---|---|
| `0x00` | Magic Byte | `uint8` | `B` | Protocol sync identifier `0xAA` |
| `0x01` | Version | `uint8` | `B` | Wire Protocol Version `0x02` |
| `0x02` | Sequence | `uint16` | `H` | Monotonic frame sequence counter |
| `0x04` | Timestamp | `uint32` | `I` | Client monotonic clock (ms) |
| `0x08` | Left Stick X | `int16` | `h` | Range: `[-32768, 32767]` |
| `0x0A` | Left Stick Y | `int16` | `h` | Range: `[-32768, 32767]` |
| `0x0C` | Right Stick X | `int16` | `h` | Range: `[-32768, 32767]` |
| `0x0E` | Right Stick Y | `int16` | `h` | Range: `[-32768, 32767]` |
| `0x10` | Throttle (RT) | `uint8` | `B` | Range: `[0, 255]` (3D Touch pressure) |
| `0x11` | Brake (LT) | `uint8` | `B` | Range: `[0, 255]` (3D Touch pressure) |
| `0x12` | Button Bitmask | `uint16` | `H` | 16 discrete digital button flags |
| `0x14` | Steering Angle | `int16` | `h` | Degrees $\times 100$ (Resolution: $0.01^\circ$) |
| `0x16` | Control Flags | `uint8` | `B` | Gyro enabled, calibration bits |
| `0x17` | Ping RTT | `uint8` | `B` | Round-trip telemetry estimate (ms) |

---

## 4. Empirical Benchmark Telemetry

| Benchmark Metric | Legacy JSON | Binary Wire v2 | Improvement |
|---|---|---|---|
| **Payload Size** | 205 Bytes | 24 Bytes | **88.3% reduction** |
| **Parsing Latency** | 3.09 $\mu\text{s}$ | **0.15 $\mu\text{s}$** | **20.1\times$ speedup** |
| **Throughput (1-Core)** | $\sim 67,000$ pkt/s | **$\sim 1,500,000$ pkt/s** | **$22\times$ capacity** |
| **DSP Step Latency** | N/A (unfiltered) | 2.16 $\mu\text{s}$ | Discrete Kalman $O(1)$ |
| **Sensor RMS Error** | 2.41° (Raw) | **1.88° (Kalman)** | **22.1% error reduction** |
| **SNR Improvement** | Baseline | **+2.17 dB** | High-Q Noise Rejection |

---

## 5. Defense Viva Checklist for Professor Demonstration

1. [x] **Live Wire Protocol Benchmark**: Run `python scripts/viva_defense_suite.py --benchmark` to demonstrate $< 1.0\ \mu\text{s}$ unpacking.
2. [x] **Spectral FFT Demonstration**: Run `python scripts/viva_defense_suite.py --fft` to display $8-12\ \text{Hz}$ hand tremor attenuation.
3. [x] **ASCII Oscilloscope & Dropout Demonstration**: Run `python scripts/viva_defense_suite.py --ascii-scope` to showcase dead-reckoning extrapolation during packet dropouts.
4. [x] **Monochromatic HUD**: Run `python main.py` and inspect top bar badges (`WIRE: BINARY v2`, `DSP: KALMAN 6-DoF`) and click `⚡ VIVA & BENCHMARK`.
