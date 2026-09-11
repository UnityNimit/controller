/**
 * Project Controller - Edge Node Client Engine
 * Integrates WebSockets, Motion Sensors, Multi-Touch Zones, Haptics & HUD.
 */

import { SecurityClient } from "./security_client.js";
import { HapticEngine, ShiftToneSynthesizer } from "./haptics.js";
import { CockpitHUD } from "./hud.js";

class CockpitController {
  constructor() {
    this.security = new SecurityClient();
    this.haptics = new HapticEngine();
    this.synth = new ShiftToneSynthesizer();
    this.hud = null;

    // Network State
    this.ws = null;
    this.seq = 0;
    this.connected = false;
    this.playerSlot = 1;
    this.playerColor = "#00ffcc";

    // Sensor State
    this.rawAngle = 0.0;
    this.accel = { x: 0.0, y: 0.0, z: 9.8 };

    // Input Control States
    this.throttle = 0.0;
    this.brake = 0.0;
    this.buttons = {
      SHIFT_UP: false,
      SHIFT_DOWN: false,
      HANDBRAKE: false,
      HIGH_BEAM: false
    };

    // Diagnostics
    this.rtt = 0;
    this.packetRate = 0;
    this.packetsSent = 0;
    this.lastRateTime = performance.now();

    this._initDom();
    this._initTouchControls();
  }

  _initDom() {
    const canvas = document.getElementById("hud-canvas");
    this.hud = new CockpitHUD(canvas);

    this.dom = {
      statusIndicator: document.getElementById("status-dot"),
      statusText: document.getElementById("link-status"),
      rttText: document.getElementById("rtt-val"),
      hzText: document.getElementById("hz-val"),
      slotText: document.getElementById("slot-val"),
      brakeFill: document.getElementById("brake-fill"),
      brakeVal: document.getElementById("brake-pct"),
      throttleFill: document.getElementById("throttle-fill"),
      throttleVal: document.getElementById("throttle-pct"),
      engageModal: document.getElementById("engage-modal"),
      engageBtn: document.getElementById("engage-btn"),
      calibrateBtn: document.getElementById("calibrate-btn"),
      fullscreenBtn: document.getElementById("fullscreen-btn")
    };

    this.dom.engageBtn.addEventListener("click", () => this.engageCockpit());
    this.dom.calibrateBtn.addEventListener("click", () => this.calibrateZero());
    if (this.dom.fullscreenBtn) {
      this.dom.fullscreenBtn.addEventListener("click", () => this.toggleFullscreen());
    }
  }

  toggleFullscreen() {
    const el = document.documentElement;
    try {
      if (!document.fullscreenElement && !document.webkitFullscreenElement) {
        if (el.requestFullscreen) {
          el.requestFullscreen().catch(() => {});
        } else if (el.webkitRequestFullscreen) {
          el.webkitRequestFullscreen();
        } else if (el.webkitRequestFullScreen) {
          el.webkitRequestFullScreen();
        } else if (el.mozRequestFullScreen) {
          el.mozRequestFullScreen();
        } else if (el.msRequestFullscreen) {
          el.msRequestFullscreen();
        }
      } else {
        if (document.exitFullscreen) {
          document.exitFullscreen().catch(() => {});
        } else if (document.webkitExitFullscreen) {
          document.webkitExitFullscreen();
        }
      }
    } catch (e) {
      console.debug("Fullscreen error", e);
    }
    window.scrollTo(0, 1);
  }

  async engageCockpit() {
    // 1. Enter Fullscreen Mode
    this.toggleFullscreen();

    // 2. Initialize Web Audio Context
    this.synth.initAudio();

    // 3. Request Motion Sensor Permissions (required by iOS Safari)
    if (typeof DeviceOrientationEvent !== "undefined" && typeof DeviceOrientationEvent.requestPermission === "function") {
      try {
        const perm = await DeviceOrientationEvent.requestPermission();
        if (perm !== "granted") {
          console.warn("DeviceOrientation permission denied");
        }
      } catch (err) {
        console.warn("DeviceOrientation permission error:", err);
      }
    }

    // 3. Request Wake Lock to prevent screen dimming
    try {
      if ("wakeLock" in navigator) {
        await navigator.wakeLock.request("screen");
      }
    } catch (err) {
      console.debug("WakeLock unavailable", err);
    }

    // 4. Attach Motion Listeners
    this._attachMotionSensors();

    // 5. Hide Modal & Connect WebSocket
    this.dom.engageModal.style.display = "none";
    this.connectWebSocket();

    // 6. Start Render & Transmission Loops
    this._startLoops();
  }

  _attachMotionSensors() {
    // Orientation: Steering from wrist tilt
    window.addEventListener("deviceorientation", (e) => {
      // In landscape: beta represents tilt left/right
      // Check screen orientation
      const orientation = window.orientation || (screen.orientation ? screen.orientation.angle : 0);
      let angle = 0;
      if (orientation === 90) {
        angle = -e.beta;
      } else if (orientation === -90) {
        angle = e.beta;
      } else {
        // Fallback for non-standard rotation: use gamma
        angle = e.gamma || 0;
      }
      this.rawAngle = angle;
      this.hud.updateSteering(angle);
    }, { passive: true });

    // Motion: Accelerometer for Handbrake Jerk
    window.addEventListener("devicemotion", (e) => {
      if (e.accelerationIncludingGravity) {
        this.accel = {
          x: e.accelerationIncludingGravity.x || 0,
          y: e.accelerationIncludingGravity.y || 0,
          z: e.accelerationIncludingGravity.z || 0
        };
      }
    }, { passive: true });

    // Ambient Light Sensor (Thumb Flasher trigger)
    if ("AmbientLightSensor" in window) {
      try {
        const sensor = new AmbientLightSensor();
        sensor.addEventListener("reading", () => {
          if (sensor.illuminance < 8) {
            this.buttons.HIGH_BEAM = true;
          } else {
            this.buttons.HIGH_BEAM = false;
          }
        });
        sensor.start();
      } catch (err) {
        console.debug("AmbientLightSensor unavailable", err);
      }
    }
  }

  _initTouchControls() {
    // Left Trigger: Brake Zone
    const brakeZone = document.getElementById("brake-zone");
    const updateBrake = (e) => {
      const rect = brakeZone.getBoundingClientRect();
      const touch = e.touches ? e.touches[0] : e;
      const y = touch.clientY - rect.top;
      const norm = Math.max(0.0, Math.min(1.0, 1.0 - (y / rect.height)));
      this.brake = norm;
      this.dom.brakeFill.style.height = `${(norm * 100).toFixed(0)}%`;
      this.dom.brakeVal.innerText = `${(norm * 100).toFixed(0)}%`;
    };

    brakeZone.addEventListener("pointerdown", (e) => {
      brakeZone.setPointerCapture(e.pointerId);
      updateBrake(e);
    });
    brakeZone.addEventListener("pointermove", (e) => {
      if (e.buttons > 0) updateBrake(e);
    });
    const releaseBrake = () => {
      this.brake = 0.0;
      this.dom.brakeFill.style.height = "0%";
      this.dom.brakeVal.innerText = "0%";
    };
    brakeZone.addEventListener("pointerup", releaseBrake);
    brakeZone.addEventListener("pointercancel", releaseBrake);

    // Right Trigger: Throttle Zone
    const throttleZone = document.getElementById("throttle-zone");
    const updateThrottle = (e) => {
      const rect = throttleZone.getBoundingClientRect();
      const touch = e.touches ? e.touches[0] : e;
      const y = touch.clientY - rect.top;
      const norm = Math.max(0.0, Math.min(1.0, 1.0 - (y / rect.height)));
      this.throttle = norm;
      this.dom.throttleFill.style.height = `${(norm * 100).toFixed(0)}%`;
      this.dom.throttleVal.innerText = `${(norm * 100).toFixed(0)}%`;
    };

    throttleZone.addEventListener("pointerdown", (e) => {
      throttleZone.setPointerCapture(e.pointerId);
      updateThrottle(e);
    });
    throttleZone.addEventListener("pointermove", (e) => {
      if (e.buttons > 0) updateThrottle(e);
    });
    const releaseThrottle = () => {
      this.throttle = 0.0;
      this.dom.throttleFill.style.height = "0%";
      this.dom.throttleVal.innerText = "0%";
    };
    throttleZone.addEventListener("pointerup", releaseThrottle);
    throttleZone.addEventListener("pointercancel", releaseThrottle);

    // Digital Action Buttons with multi-touch pointer capture
    const bindBtn = (id, buttonKey, aliases = []) => {
      const el = document.getElementById(id);
      if (!el) return;
      const press = (e) => {
        try {
          if (e.pointerId) el.setPointerCapture(e.pointerId);
        } catch (_) {}
        this.buttons[buttonKey] = true;
        for (const a of aliases) this.buttons[a] = true;
        el.classList.add("active");
        this.haptics.triggerClick();
      };
      const release = (e) => {
        this.buttons[buttonKey] = false;
        for (const a of aliases) this.buttons[a] = false;
        el.classList.remove("active");
      };
      el.addEventListener("pointerdown", press);
      el.addEventListener("pointerup", release);
      el.addEventListener("pointercancel", release);
      el.addEventListener("pointerleave", release);
    };

    // Primary Game Controls (Rocket League & Racing)
    bindBtn("btn-jump", "JUMP", ["A"]);
    bindBtn("btn-boost", "BOOST", ["B"]);
    bindBtn("btn-slide", "POWERSLIDE", ["X", "HANDBRAKE"]);
    bindBtn("btn-cam", "BALL_CAM", ["Y"]);
  }

  calibrateZero() {
    this.haptics.triggerClick();
    if (this.ws && this.connected) {
      this.ws.send(JSON.stringify({
        type: "CALIBRATE",
        angle: this.rawAngle
      }));
    }
  }

  connectWebSocket() {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const url = `${proto}//${host}/ws`;

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.dom.statusIndicator.classList.add("online");
      this.dom.statusText.innerText = "CONNECTED";
    };

    this.ws.onmessage = async (event) => {
      const msg = JSON.parse(event.data);

      if (msg.type === "AUTH_CHALLENGE") {
        // Solve HMAC-SHA256 Challenge
        const authResponse = await this.security.solveChallenge(msg.nonce, msg.timestamp);
        this.ws.send(JSON.stringify(authResponse));
      } else if (msg.type === "AUTH_SUCCESS") {
        this.connected = true;
        this.playerSlot = msg.player_slot;
        this.playerColor = msg.player_color;
        this.dom.slotText.innerText = `P${msg.player_slot}`;
        this.dom.slotText.style.color = msg.player_color;
        this.hud.setPlayerSlot(msg.player_slot, msg.player_color);
      } else if (msg.type === "TELEMETRY") {
        // Feed live telemetry into HUD
        this.hud.updateTelemetry(msg.data);

        // Process Closed-Loop Haptics & Shift Tone
        if (msg.haptics) {
          if (msg.haptics.impact_spike) {
            this.haptics.triggerImpact();
          } else if (msg.haptics.slip_rumble) {
            this.haptics.triggerSlip();
          }
          if (msg.haptics.redline_alert) {
            this.haptics.triggerRedline();
            this.synth.beep(1800, 0.05);
          }
        }
      } else if (msg.type === "PONG") {
        const now = performance.now();
        this.rtt = Math.round(now - msg.ts);
        this.dom.rttText.innerText = `${this.rtt}ms`;
      }
    };

    this.ws.onclose = () => {
      this.connected = false;
      this.dom.statusIndicator.classList.remove("online");
      this.dom.statusText.innerText = "OFFLINE";
      // Auto reconnect after 1.5 seconds
      setTimeout(() => this.connectWebSocket(), 1500);
    };
  }

  _startLoops() {
    // 1. 60 FPS HTML5 Canvas HUD Render Loop
    const renderLoop = () => {
      this.hud.render();
      requestAnimationFrame(renderLoop);
    };
    requestAnimationFrame(renderLoop);

    // 2. 60 Hz Teleoperation Transmission Loop
    const sendIntervalMs = 1000 / 60;
    setInterval(() => {
      if (!this.connected || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;

      this.seq++;
      const packet = {
        type: "INPUT",
        seq: this.seq,
        ts: performance.now(),
        angle: this.rawAngle,
        throttle: this.throttle,
        brake: this.brake,
        accel: this.accel,
        buttons: this.buttons
      };

      this.ws.send(JSON.stringify(packet));
      this.packetsSent++;

      // Update transmission frequency metric every 1 second
      const now = performance.now();
      if (now - this.lastRateTime >= 1000) {
        this.packetRate = this.packetsSent;
        this.packetsSent = 0;
        this.lastRateTime = now;
        this.dom.hzText.innerText = `${this.packetRate}Hz`;

        // Send ping for RTT calculation
        this.ws.send(JSON.stringify({ type: "PING", ts: now }));
      }
    }, sendIntervalMs);
  }
}

// Instantiate on DOM load
window.addEventListener("DOMContentLoaded", () => {
  new CockpitController();
});
