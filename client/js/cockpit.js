/**
 * Project Controller - Pro Gamepad Client Engine
 * High-performance virtual Xbox controller for Rocket League and PC Games.
 */

import { SecurityClient } from "./security_client.js";
import { HapticEngine } from "./haptics.js";

class GamepadController {
  constructor() {
    this.security = new SecurityClient();
    this.haptics = new HapticEngine();

    // Network State
    this.ws = null;
    this.seq = 0;
    this.connected = false;
    this.playerSlot = 1;

    // Gyro & Sensor State
    this.gyroEnabled = true;
    this.rawAngle = 0.0;
    this.zeroOffset = 0.0;
    this.accel = { x: 0.0, y: 0.0, z: 9.8 };

    // Virtual Thumbstick State
    this.stickX = 0;
    this.stickY = 0;

    // Trigger States [0.0, 1.0]
    this.throttle = 0.0;
    this.brake = 0.0;

    // Button States
    this.buttons = {
      A: false,
      B: false,
      X: false,
      Y: false,
      LB: false,
      RB: false,
      START: false,
      BACK: false,
      JUMP: false,
      BOOST: false,
      POWERSLIDE: false,
      BALL_CAM: false
    };

    // Diagnostics
    this.rtt = 0;
    this.speed = 0;

    this._initDom();
    this._initControls();
  }

  _initDom() {
    this.dom = {
      statusDot: document.getElementById("status-dot"),
      statusText: document.getElementById("link-status"),
      rttText: document.getElementById("rtt-val"),
      gyroBadge: document.getElementById("gyro-badge"),
      gyroBtn: document.getElementById("gyro-toggle-btn"),
      fullscreenBtn: document.getElementById("fullscreen-btn"),
      calibrateBtn: document.getElementById("calibrate-btn"),
      engageModal: document.getElementById("engage-modal"),
      engageBtn: document.getElementById("engage-btn"),
      ltFill: document.getElementById("lt-fill"),
      rtFill: document.getElementById("rt-fill"),
      stickZone: document.getElementById("stick-zone"),
      stickKnob: document.getElementById("stick-knob")
    };

    this.dom.engageBtn.addEventListener("click", () => this.engage());
    this.dom.fullscreenBtn.addEventListener("click", () => this.toggleFullscreen());
    this.dom.calibrateBtn.addEventListener("click", () => this.calibrateZero());
    this.dom.gyroBtn.addEventListener("click", () => this.toggleGyro());
  }

  toggleGyro() {
    this.gyroEnabled = !this.gyroEnabled;
    this.haptics.triggerClick();
    if (this.gyroEnabled) {
      this.dom.gyroBtn.innerText = "GYRO STEER: ON";
      this.dom.gyroBtn.classList.remove("active");
      this.dom.gyroBadge.innerText = "TILT STEERING ACTIVE";
      this.dom.gyroBadge.style.display = "block";
    } else {
      this.dom.gyroBtn.innerText = "GYRO STEER: OFF";
      this.dom.gyroBtn.classList.add("active");
      this.dom.gyroBadge.innerText = "THUMBSTICK STEERING";
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
      console.debug("Fullscreen toggle error", e);
    }
    window.scrollTo(0, 1);
  }

  async engage() {
    // 1. Fullscreen request
    this.toggleFullscreen();

    // 2. iOS Motion permission request
    if (typeof DeviceOrientationEvent !== "undefined" && typeof DeviceOrientationEvent.requestPermission === "function") {
      try {
        const perm = await DeviceOrientationEvent.requestPermission();
        if (perm !== "granted") {
          console.warn("Motion permission denied");
        }
      } catch (err) {
        console.warn("Motion permission error", err);
      }
    }

    // 3. Screen WakeLock
    try {
      if ("wakeLock" in navigator) {
        await navigator.wakeLock.request("screen");
      }
    } catch (e) {}

    // 4. Attach Motion Listeners
    this._attachMotionSensors();

    // 5. Hide Modal & Connect
    this.dom.engageModal.style.display = "none";
    this.connect();

    // 6. Start high-frequency transmission loop
    this._startLoop();
  }

  _attachMotionSensors() {
    window.addEventListener("deviceorientation", (e) => {
      const orientation = window.orientation || (screen.orientation ? screen.orientation.angle : 0);
      let angle = 0;
      if (orientation === 90) {
        angle = -e.beta;
      } else if (orientation === -90) {
        angle = e.beta;
      } else {
        angle = e.gamma || 0;
      }
      this.rawAngle = angle;
    }, { passive: true });

    window.addEventListener("devicemotion", (e) => {
      if (e.accelerationIncludingGravity) {
        this.accel = {
          x: e.accelerationIncludingGravity.x || 0,
          y: e.accelerationIncludingGravity.y || 0,
          z: e.accelerationIncludingGravity.z || 0
        };
      }
    }, { passive: true });
  }

  _initControls() {
    // 1. Left Trigger (LT: Brake / Reverse)
    const ltZone = document.getElementById("lt-zone");
    const updateLT = (e) => {
      const rect = ltZone.getBoundingClientRect();
      const touch = e.touches ? e.touches[0] : e;
      const y = touch.clientY - rect.top;
      const norm = Math.max(0.0, Math.min(1.0, 1.0 - (y / rect.height)));
      // If tapped top half, snap to full brake
      const val = norm > 0.3 ? Math.min(1.0, norm * 1.3) : norm;
      this.brake = val;
      this.dom.ltFill.style.height = `${(val * 100).toFixed(0)}%`;
    };
    ltZone.addEventListener("pointerdown", (e) => {
      try { ltZone.setPointerCapture(e.pointerId); } catch (_) {}
      this.haptics.triggerClick();
      updateLT(e);
    });
    ltZone.addEventListener("pointermove", (e) => {
      if (e.buttons > 0) updateLT(e);
    });
    const releaseLT = () => {
      this.brake = 0.0;
      this.dom.ltFill.style.height = "0%";
    };
    ltZone.addEventListener("pointerup", releaseLT);
    ltZone.addEventListener("pointercancel", releaseLT);

    // 2. Right Trigger (RT: Drive / Accelerate)
    const rtZone = document.getElementById("rt-zone");
    const updateRT = (e) => {
      const rect = rtZone.getBoundingClientRect();
      const touch = e.touches ? e.touches[0] : e;
      const y = touch.clientY - rect.top;
      const norm = Math.max(0.0, Math.min(1.0, 1.0 - (y / rect.height)));
      const val = norm > 0.3 ? Math.min(1.0, norm * 1.3) : norm;
      this.throttle = val;
      this.dom.rtFill.style.height = `${(val * 100).toFixed(0)}%`;
    };
    rtZone.addEventListener("pointerdown", (e) => {
      try { rtZone.setPointerCapture(e.pointerId); } catch (_) {}
      this.haptics.triggerClick();
      updateRT(e);
    });
    rtZone.addEventListener("pointermove", (e) => {
      if (e.buttons > 0) updateRT(e);
    });
    const releaseRT = () => {
      this.throttle = 0.0;
      this.dom.rtFill.style.height = "0%";
    };
    rtZone.addEventListener("pointerup", releaseRT);
    rtZone.addEventListener("pointercancel", releaseRT);

    // 3. Virtual Thumbstick (Left Stick)
    const stickZone = this.dom.stickZone;
    const stickKnob = this.dom.stickKnob;
    let stickActive = false;

    const handleStick = (e) => {
      const rect = stickZone.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const touch = e.touches ? e.touches[0] : e;
      
      let dx = touch.clientX - cx;
      let dy = touch.clientY - cy;
      const maxRadius = (rect.width / 2) - 15;
      const dist = Math.sqrt(dx * dx + dy * dy);

      if (dist > maxRadius) {
        dx = (dx / dist) * maxRadius;
        dy = (dy / dist) * maxRadius;
      }

      stickKnob.style.transform = `translate(${dx}px, ${dy}px)`;

      // Map to 16-bit signed integer [-32768, 32767]
      // Invert Y: Up on joystick is negative Y on screen, positive Y on thumbstick
      this.stickX = Math.round((dx / maxRadius) * 32767);
      this.stickY = Math.round((-dy / maxRadius) * 32767);
    };

    stickZone.addEventListener("pointerdown", (e) => {
      stickActive = true;
      try { stickZone.setPointerCapture(e.pointerId); } catch (_) {}
      this.haptics.triggerClick();
      handleStick(e);
    });
    stickZone.addEventListener("pointermove", (e) => {
      if (stickActive) handleStick(e);
    });
    const releaseStick = () => {
      stickActive = false;
      stickKnob.style.transform = "translate(0px, 0px)";
      this.stickX = 0;
      this.stickY = 0;
    };
    stickZone.addEventListener("pointerup", releaseStick);
    stickZone.addEventListener("pointercancel", releaseStick);

    // 4. Digital Buttons with Multi-Touch Pointer Capture
    const bindBtn = (id, primaryKey, aliases = []) => {
      const el = document.getElementById(id);
      if (!el) return;

      const press = (e) => {
        try {
          if (e.pointerId) el.setPointerCapture(e.pointerId);
        } catch (_) {}
        this.buttons[primaryKey] = true;
        for (const a of aliases) this.buttons[a] = true;
        el.classList.add("active");
        this.haptics.triggerClick();
      };

      const release = (e) => {
        this.buttons[primaryKey] = false;
        for (const a of aliases) this.buttons[a] = false;
        el.classList.remove("active");
      };

      el.addEventListener("pointerdown", press);
      el.addEventListener("pointerup", release);
      el.addEventListener("pointercancel", release);
      el.addEventListener("pointerleave", release);
    };

    // ABXY Diamond Cluster
    bindBtn("btn-a", "A", ["JUMP"]);
    bindBtn("btn-b", "B", ["BOOST"]);
    bindBtn("btn-x", "X", ["POWERSLIDE", "HANDBRAKE"]);
    bindBtn("btn-y", "Y", ["BALL_CAM"]);

    // Bumpers & Menu
    bindBtn("btn-lb", "LB");
    bindBtn("btn-rb", "RB");
    bindBtn("btn-start", "START");
    bindBtn("btn-back", "BACK");
    bindBtn("btn-guide", "GUIDE");
  }

  calibrateZero() {
    this.haptics.triggerClick();
    this.zeroOffset = this.rawAngle;
    if (this.ws && this.connected) {
      this.ws.send(JSON.stringify({
        type: "CALIBRATE",
        angle: this.rawAngle
      }));
    }
  }

  connect() {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const url = `${proto}//${host}/ws`;

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.dom.statusDot.classList.add("online");
      this.dom.statusText.innerText = "ONLINE";
      this.dom.statusText.style.color = "var(--accent-a)";
    };

    this.ws.onmessage = async (event) => {
      const msg = JSON.parse(event.data);

      if (msg.type === "AUTH_CHALLENGE") {
        const authResponse = await this.security.solveChallenge(msg.nonce, msg.timestamp);
        this.ws.send(JSON.stringify(authResponse));
      } else if (msg.type === "AUTH_SUCCESS") {
        this.connected = true;
        this.playerSlot = msg.player_slot;
      } else if (msg.type === "TELEMETRY") {
        // Telemetry received (pure gaming mode: no random vibrations)
      } else if (msg.type === "PONG") {
        const now = performance.now();
        this.rtt = Math.round(now - msg.ts);
        this.dom.rttText.innerText = `${this.rtt}ms`;
      }
    };

    this.ws.onclose = () => {
      this.connected = false;
      this.dom.statusDot.classList.remove("online");
      this.dom.statusText.innerText = "OFFLINE";
      this.dom.statusText.style.color = "#888";
      setTimeout(() => this.connect(), 1500);
    };
  }

  _startLoop() {
    let lastPing = performance.now();
    const intervalMs = 1000 / 60;

    setInterval(() => {
      if (!this.connected || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;

      this.seq++;
      const now = performance.now();

      // Steering determination:
      // If Gyro enabled: use physical wrist angle
      // If Gyro disabled: use virtual thumbstick X
      const effectiveAngle = this.gyroEnabled ? (this.rawAngle - this.zeroOffset) : 0.0;
      const effectiveStickX = this.gyroEnabled ? 0 : this.stickX;

      const packet = {
        type: "INPUT",
        seq: this.seq,
        ts: now,
        gyro_enabled: this.gyroEnabled,
        angle: effectiveAngle,
        stick_x: effectiveStickX,
        stick_y: this.stickY,
        throttle: this.throttle,
        brake: this.brake,
        accel: this.accel,
        buttons: this.buttons
      };

      this.ws.send(JSON.stringify(packet));

      // Periodic ping every 1 second
      if (now - lastPing >= 1000) {
        lastPing = now;
        this.ws.send(JSON.stringify({ type: "PING", ts: now }));
      }
    }, intervalMs);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  new GamepadController();
});
