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

    // Dynamic Floating Thumbstick State
    this.stickActive = false;
    this.stickPointerId = null;
    this.stickOrigin = { x: 0, y: 0 };
    this.stickX = 0;
    this.stickY = 0;

    // Trigger Modes: "TAP" (instant 100% digital) | "SLIDER" (analog progressive)
    this.triggerMode = "TAP";
    this.throttle = 0.0;
    this.brake = 0.0;
    this.ltPointerId = null;
    this.rtPointerId = null;

    // Digital Buttons
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

    // Multi-touch tracking
    this.activeButtonPointers = new Map();

    // Diagnostics
    this.rtt = 0;

    this._initDom();
    this._initControls();
  }

  _initDom() {
    this.dom = {
      statusDot: document.getElementById("status-dot"),
      rttVal: document.getElementById("rtt-val"),
      pillFullscreen: document.getElementById("pill-fullscreen"),
      btnToggleGyro: document.getElementById("btn-toggle-gyro"),
      btnToggleTrig: document.getElementById("btn-toggle-trig"),
      btnCalibrate: document.getElementById("btn-calibrate"),
      btnBack: document.getElementById("btn-back"),
      btnStart: document.getElementById("btn-start"),

      // Left Zone
      leftStickArena: document.getElementById("left-stick-arena"),
      floatingJoystick: document.getElementById("floating-joystick"),
      stickStick: document.getElementById("stick-stick"),
      stickHint: document.getElementById("stick-hint"),
      ltTrigger: document.getElementById("lt-trigger"),
      ltFill: document.getElementById("lt-fill"),
      btnLb: document.getElementById("btn-lb"),

      // Right Zone
      rtTrigger: document.getElementById("rt-trigger"),
      rtFill: document.getElementById("rt-fill"),
      btnRb: document.getElementById("btn-rb"),
      btnA: document.getElementById("btn-a"),
      btnB: document.getElementById("btn-b"),
      btnX: document.getElementById("btn-x"),
      btnY: document.getElementById("btn-y"),

      // Modals
      engageModal: document.getElementById("engage-modal"),
      engageBtn: document.getElementById("engage-btn")
    };

    if (this.dom.engageBtn) {
      this.dom.engageBtn.addEventListener("click", () => this.engage());
    }
    if (this.dom.pillFullscreen) {
      this.dom.pillFullscreen.addEventListener("click", () => this.toggleFullscreen());
    }
    if (this.dom.btnToggleGyro) {
      this.dom.btnToggleGyro.addEventListener("click", () => this.toggleGyro());
    }
    if (this.dom.btnToggleTrig) {
      this.dom.btnToggleTrig.addEventListener("click", () => this.toggleTriggerMode());
    }
    if (this.dom.btnCalibrate) {
      this.dom.btnCalibrate.addEventListener("click", () => this.calibrateZero());
    }
  }

  toggleGyro() {
    this.gyroEnabled = !this.gyroEnabled;
    this.haptics.triggerClick();
    if (this.gyroEnabled) {
      this.dom.btnToggleGyro.innerText = "GYRO: ON";
      this.dom.btnToggleGyro.classList.add("active");
    } else {
      this.dom.btnToggleGyro.innerText = "GYRO: OFF";
      this.dom.btnToggleGyro.classList.remove("active");
    }
  }

  toggleTriggerMode() {
    this.triggerMode = this.triggerMode === "TAP" ? "SLIDER" : "TAP";
    this.haptics.triggerClick();
    if (this.triggerMode === "TAP") {
      this.dom.btnToggleTrig.innerText = "TRIG: TAP";
      this.dom.btnToggleTrig.classList.add("active");
    } else {
      this.dom.btnToggleTrig.innerText = "TRIG: SLIDER";
      this.dom.btnToggleTrig.classList.remove("active");
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
    // 1. Request Fullscreen
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

    // 3. Screen WakeLock to prevent phone screen timeout
    try {
      if ("wakeLock" in navigator) {
        await navigator.wakeLock.request("screen");
      }
    } catch (_) {}

    // 4. Attach Motion Listeners
    this._attachMotionSensors();

    // 5. Hide Modal & Connect
    if (this.dom.engageModal) {
      this.dom.engageModal.style.display = "none";
    }
    this.connect();

    // 6. Start high-frequency 60 Hz transmission loop
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
    // =========================================================================
    // 1. Dynamic Floating Joystick (Left Arena)
    // =========================================================================
    const arena = this.dom.leftStickArena;
    const floatingStick = this.dom.floatingJoystick;
    const stickKnob = this.dom.stickStick;
    const stickHint = this.dom.stickHint;

    if (arena && floatingStick && stickKnob) {
      arena.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        if (this.stickPointerId !== null) return;

        this.stickPointerId = e.pointerId;
        this.stickActive = true;
        this.stickOrigin = { x: e.clientX, y: e.clientY };

        // Position 130px floating joystick centered at touch point
        floatingStick.style.left = `${e.clientX - 65}px`;
        floatingStick.style.top = `${e.clientY - 65}px`;
        floatingStick.style.opacity = "1";
        stickKnob.style.transform = "translate(0px, 0px)";

        if (stickHint) stickHint.style.opacity = "0.04";

        try {
          arena.setPointerCapture(e.pointerId);
        } catch (_) {}

        this.haptics.triggerClick();
      });

      arena.addEventListener("pointermove", (e) => {
        if (!this.stickActive || e.pointerId !== this.stickPointerId) return;
        e.preventDefault();

        let dx = e.clientX - this.stickOrigin.x;
        let dy = e.clientY - this.stickOrigin.y;
        const maxRadius = 45;
        const dist = Math.hypot(dx, dy);

        if (dist > maxRadius) {
          dx = (dx / dist) * maxRadius;
          dy = (dy / dist) * maxRadius;
        }

        stickKnob.style.transform = `translate(${dx}px, ${dy}px)`;

        // Map to 16-bit signed integer [-32768, 32767]
        // Invert Y: pushing forward on screen is positive Y on thumbstick
        this.stickX = Math.round((dx / maxRadius) * 32767);
        this.stickY = Math.round((-dy / maxRadius) * 32767);
      });

      const releaseStick = (e) => {
        if (e.pointerId !== this.stickPointerId) return;
        this.stickActive = false;
        this.stickPointerId = null;
        this.stickX = 0;
        this.stickY = 0;
        stickKnob.style.transform = "translate(0px, 0px)";
        floatingStick.style.opacity = "0";
        if (stickHint) stickHint.style.opacity = "0.2";
      };

      arena.addEventListener("pointerup", releaseStick);
      arena.addEventListener("pointercancel", releaseStick);
      window.addEventListener("pointerup", (e) => {
        if (e.pointerId === this.stickPointerId) releaseStick(e);
      });
      window.addEventListener("pointercancel", (e) => {
        if (e.pointerId === this.stickPointerId) releaseStick(e);
      });
    }

    // =========================================================================
    // 2. LT Trigger (Brake / Reverse) - TAP & SLIDER Modes
    // =========================================================================
    const lt = this.dom.ltTrigger;
    const ltFill = this.dom.ltFill;

    const updateLtSlider = (clientY) => {
      const rect = lt.getBoundingClientRect();
      const norm = Math.max(0.0, Math.min(1.0, 1.0 - (clientY - rect.top) / rect.height));
      this.brake = norm;
      ltFill.style.height = `${(norm * 100).toFixed(0)}%`;
    };

    if (lt) {
      lt.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        this.ltPointerId = e.pointerId;
        lt.classList.add("active");
        this.haptics.triggerClick();

        if (this.triggerMode === "TAP") {
          this.brake = 1.0;
          ltFill.style.height = "100%";
        } else {
          updateLtSlider(e.clientY);
        }

        try { lt.setPointerCapture(e.pointerId); } catch (_) {}
      });

      lt.addEventListener("pointermove", (e) => {
        if (e.pointerId !== this.ltPointerId) return;
        if (this.triggerMode === "SLIDER") {
          updateLtSlider(e.clientY);
        }
      });

      const releaseLt = (e) => {
        if (e.pointerId !== this.ltPointerId) return;
        this.ltPointerId = null;
        this.brake = 0.0;
        ltFill.style.height = "0%";
        lt.classList.remove("active");
      };

      lt.addEventListener("pointerup", releaseLt);
      lt.addEventListener("pointercancel", releaseLt);
      window.addEventListener("pointerup", (e) => {
        if (e.pointerId === this.ltPointerId) releaseLt(e);
      });
      window.addEventListener("pointercancel", (e) => {
        if (e.pointerId === this.ltPointerId) releaseLt(e);
      });
    }

    // =========================================================================
    // 3. RT Trigger (Drive / Accelerate) - TAP & SLIDER Modes
    // =========================================================================
    const rt = this.dom.rtTrigger;
    const rtFill = this.dom.rtFill;

    const updateRtSlider = (clientY) => {
      const rect = rt.getBoundingClientRect();
      const norm = Math.max(0.0, Math.min(1.0, 1.0 - (clientY - rect.top) / rect.height));
      this.throttle = norm;
      rtFill.style.height = `${(norm * 100).toFixed(0)}%`;
    };

    if (rt) {
      rt.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        this.rtPointerId = e.pointerId;
        rt.classList.add("active");
        this.haptics.triggerClick();

        if (this.triggerMode === "TAP") {
          this.throttle = 1.0;
          rtFill.style.height = "100%";
        } else {
          updateRtSlider(e.clientY);
        }

        try { rt.setPointerCapture(e.pointerId); } catch (_) {}
      });

      rt.addEventListener("pointermove", (e) => {
        if (e.pointerId !== this.rtPointerId) return;
        if (this.triggerMode === "SLIDER") {
          updateRtSlider(e.clientY);
        }
      });

      const releaseRt = (e) => {
        if (e.pointerId !== this.rtPointerId) return;
        this.rtPointerId = null;
        this.throttle = 0.0;
        rtFill.style.height = "0%";
        rt.classList.remove("active");
      };

      rt.addEventListener("pointerup", releaseRt);
      rt.addEventListener("pointercancel", releaseRt);
      window.addEventListener("pointerup", (e) => {
        if (e.pointerId === this.rtPointerId) releaseRt(e);
      });
      window.addEventListener("pointercancel", (e) => {
        if (e.pointerId === this.rtPointerId) releaseRt(e);
      });
    }

    // =========================================================================
    // 4. Digital Action Buttons with Multi-Touch Pointer Capture
    // =========================================================================
    const bindBtn = (id, primaryKey, aliases = []) => {
      const el = document.getElementById(id);
      if (!el) return;

      const press = (e) => {
        e.preventDefault();
        this.activeButtonPointers.set(e.pointerId, { el, primaryKey, aliases });
        this.buttons[primaryKey] = true;
        for (const a of aliases) this.buttons[a] = true;
        el.classList.add("active");
        this.haptics.triggerClick();
        try { el.setPointerCapture(e.pointerId); } catch (_) {}
      };

      const release = (e) => {
        if (this.activeButtonPointers.has(e.pointerId)) {
          const entry = this.activeButtonPointers.get(e.pointerId);
          this.buttons[entry.primaryKey] = false;
          for (const a of entry.aliases) this.buttons[a] = false;
          entry.el.classList.remove("active");
          this.activeButtonPointers.delete(e.pointerId);
        }
      };

      el.addEventListener("pointerdown", press);
      el.addEventListener("pointerup", release);
      el.addEventListener("pointercancel", release);
    };

    // ABXY Huge Diamond Cluster
    bindBtn("btn-a", "A", ["JUMP"]);
    bindBtn("btn-b", "B", ["BOOST"]);
    bindBtn("btn-x", "X", ["POWERSLIDE", "HANDBRAKE"]);
    bindBtn("btn-y", "Y", ["BALL_CAM"]);

    // Bumpers & Menu
    bindBtn("btn-lb", "LB");
    bindBtn("btn-rb", "RB");
    bindBtn("btn-start", "START");
    bindBtn("btn-back", "BACK");

    // Global Safety: Clean up any pointers lifted anywhere
    window.addEventListener("pointerup", (e) => {
      if (this.activeButtonPointers.has(e.pointerId)) {
        const entry = this.activeButtonPointers.get(e.pointerId);
        this.buttons[entry.primaryKey] = false;
        for (const a of entry.aliases) this.buttons[a] = false;
        entry.el.classList.remove("active");
        this.activeButtonPointers.delete(e.pointerId);
      }
    });

    window.addEventListener("pointercancel", (e) => {
      if (this.activeButtonPointers.has(e.pointerId)) {
        const entry = this.activeButtonPointers.get(e.pointerId);
        this.buttons[entry.primaryKey] = false;
        for (const a of entry.aliases) this.buttons[a] = false;
        entry.el.classList.remove("active");
        this.activeButtonPointers.delete(e.pointerId);
      }
    });

    // Window Blur / Tab Switch safety: Zero out all inputs
    const resetAllInputs = () => {
      for (const k in this.buttons) this.buttons[k] = false;
      this.throttle = 0.0;
      this.brake = 0.0;
      this.stickX = 0;
      this.stickY = 0;
      this.stickActive = false;
      this.activeButtonPointers.clear();
      document.querySelectorAll(".active").forEach(el => {
        if (el.id !== "btn-toggle-gyro" && el.id !== "btn-toggle-trig") {
          el.classList.remove("active");
        }
      });
      if (this.dom.ltFill) this.dom.ltFill.style.height = "0%";
      if (this.dom.rtFill) this.dom.rtFill.style.height = "0%";
      if (this.dom.floatingJoystick) this.dom.floatingJoystick.style.opacity = "0";
    };

    window.addEventListener("blur", resetAllInputs);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) resetAllInputs();
    });
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
      if (this.dom.statusDot) this.dom.statusDot.classList.add("online");
    };

    this.ws.onmessage = async (event) => {
      const msg = JSON.parse(event.data);

      if (msg.type === "AUTH_CHALLENGE") {
        const authResponse = await this.security.solveChallenge(msg.nonce, msg.timestamp);
        this.ws.send(JSON.stringify(authResponse));
      } else if (msg.type === "AUTH_SUCCESS") {
        this.connected = true;
        this.playerSlot = msg.player_slot;
        if (this.dom.statusDot) this.dom.statusDot.classList.add("online");
      } else if (msg.type === "TELEMETRY") {
        // Pure gaming mode: no random vibrations
      } else if (msg.type === "PONG") {
        const now = performance.now();
        this.rtt = Math.round(now - msg.ts);
        if (this.dom.rttVal) {
          this.dom.rttVal.innerText = `${this.rtt}ms`;
        }
      }
    };

    this.ws.onclose = () => {
      this.connected = false;
      if (this.dom.statusDot) this.dom.statusDot.classList.remove("online");
      if (this.dom.rttVal) this.dom.rttVal.innerText = "-- ms";
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
      // If user is actively touching the joystick, manual joystick steering overrides gyro.
      // Otherwise, if Gyro is enabled, use calibrated wrist tilt angle.
      const manualStickActive = this.stickActive || Math.abs(this.stickX) > 1000;
      const effectiveGyro = this.gyroEnabled && !manualStickActive;
      const effectiveAngle = effectiveGyro ? (this.rawAngle - this.zeroOffset) : 0.0;
      const effectiveStickX = effectiveGyro ? 0 : this.stickX;

      const packet = {
        type: "INPUT",
        seq: this.seq,
        ts: now,
        gyro_enabled: effectiveGyro,
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
