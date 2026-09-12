/**
 * Project Controller - Pro Esports Gamepad Client Engine
 * Tactical Monochrome Edition matching Custom Figma Proportions (907x400).
 * Rock-Solid Multi-Touch Isolation, Dual Fixed-Anchor Sticks, Gyro HUD Screen & Audio/Haptic Visualizer.
 * Complete Dual Preset Engine (Preset 1: Symmetrical Esport, Preset 2: Ergonomic Tactical).
 */

import { SecurityClient } from "./security_client.js";
import { HapticEngine } from "./haptics.js";

class GamepadController {
  constructor() {
    this.security = new SecurityClient();
    this.haptics = new HapticEngine();

    // Preset Layout State: "preset1" or "preset2"
    this.preset = localStorage.getItem("controller_preset") || "preset1";

    // Network State
    this.ws = null;
    this.seq = 0;
    this.connected = false;
    this.playerSlot = 1;
    this.preferredSlot = localStorage.getItem("controller_preferred_slot")
      ? parseInt(localStorage.getItem("controller_preferred_slot"))
      : null;

    // Forced Landscape & Orientation Engine
    this.isRotated = false;
    this.checkOrientation();
    window.addEventListener("resize", () => this.checkOrientation());
    window.addEventListener("orientationchange", () => this.checkOrientation());

    // Gyro & Attitude State
    this.gyroEnabled = false;
    this.rawAngle = 0.0;
    this.zeroOffset = 0.0;
    this.accel = { x: 0.0, y: 0.0, z: 9.8 };

    // Fixed Center Left Stick State
    this.leftStickActive = false;
    this.leftStickPointerId = null;
    this.stickX = 0;
    this.stickY = 0;
    this._lastSentStickX = 0;
    this._lastSentStickY = 0;
    this.leftStickTouchStartTime = 0;
    this.leftStickCadenceTimer = null;
    this.leftStickLastStepDir = null;

    // Fixed Center Right Stick State
    this.rightStickActive = false;
    this.rightStickPointerId = null;
    this.rightStickMoved = false;
    this.rightStickX = 0;
    this.rightStickY = 0;

    // Pure Esports Hair-Triggers: 0.0 (Released) | 1.0 (Pressed)
    this.throttle = 0.0;
    this.brake = 0.0;
    this.ltPointerId = null;
    this.rtPointerId = null;

    // Multi-Touch Pointer Registries (Strict Isolation)
    this.directBtnPointers = new Map(); // pointerId -> buttonName
    this.dpadPointers = new Map();      // pointerId -> { dir, el }
    this.clusterPointers = new Map();   // pointerId -> "A" | "B" | "X" | "Y"

    // Canonical Xbox Buttons strictly 1:1 + Tactical D-Pad
    this.buttons = {
      A: false,
      B: false,
      X: false,
      Y: false,
      LB: false,
      RB: false,
      RS: false,
      LS: false,
      START: false,
      BACK: false,
      DPAD_UP: false,
      DPAD_DOWN: false,
      DPAD_LEFT: false,
      DPAD_RIGHT: false
    };

    // Diagnostics
    this.rtt = 0;
    this._lastSendTime = 0;

    // Visualizer Buffers
    this.freqData = new Uint8Array(32);
    this.peakBars = new Float32Array(32);

    this._initDom();
    this._applyPreset(this.preset);
    this._initControls();
    this._initCanvases();
  }

  /**
   * Forced Landscape Engine: detects portrait aspect ratio and forces 90deg rotation.
   */
  checkOrientation() {
    const isPortrait = window.innerHeight > window.innerWidth;
    this.isRotated = isPortrait;
    if (document.body) {
      document.body.classList.toggle("forced-landscape-portrait", isPortrait);
    }
    if (this._resizeCanvases) {
      setTimeout(() => this._resizeCanvases(), 50);
    }
  }

  /**
   * Transforms physical viewport coordinates into gamepad coordinate space.
   */
  getGamepadPoint(clientX, clientY) {
    if (this.isRotated) {
      return {
        x: clientY,
        y: window.innerWidth - clientX
      };
    }
    return { x: clientX, y: clientY };
  }

  /**
   * Computes center of a DOM element in gamepad coordinate space.
   */
  getGamepadCenter(element) {
    if (!element) return { x: 0, y: 0 };
    const rect = element.getBoundingClientRect();
    const screenCenterX = rect.left + rect.width / 2;
    const screenCenterY = rect.top + rect.height / 2;
    return this.getGamepadPoint(screenCenterX, screenCenterY);
  }

  _applyPreset(presetName) {
    this.preset = presetName;
    localStorage.setItem("controller_preset", presetName);

    document.body.classList.toggle("preset-1-active", presetName === "preset1");
    document.body.classList.toggle("preset-2-active", presetName === "preset2");

    if (this.dom.btnPreset1) {
      this.dom.btnPreset1.classList.toggle("active", presetName === "preset1");
    }
    if (this.dom.btnPreset2) {
      this.dom.btnPreset2.classList.toggle("active", presetName === "preset2");
    }

    if (this._resizeCanvases) {
      setTimeout(() => this._resizeCanvases(), 50);
    }
  }

  switchPreset(presetName) {
    this.haptics.triggerClick("heavy");
    this._applyPreset(presetName);
    this.closeSettingsModal();
  }

  openSettingsModal() {
    this.haptics.triggerClick();
    if (this.dom.settingsModal) {
      this.dom.settingsModal.style.display = "flex";
      if (this.dom.btnPreset1) {
        this.dom.btnPreset1.classList.toggle("active", this.preset === "preset1");
      }
      if (this.dom.btnPreset2) {
        this.dom.btnPreset2.classList.toggle("active", this.preset === "preset2");
      }
    }
  }

  closeSettingsModal() {
    if (this.dom.settingsModal) {
      this.dom.settingsModal.style.display = "none";
    }
  }

  _initDom() {
    this.dom = {
      app: document.getElementById("controller-app"),
      frame: document.getElementById("gamepad-frame"),

      // Preset 1 DOM Elements
      modLt: document.getElementById("mod-lt"),
      ltTrigger: document.getElementById("lt-trigger"),
      ltFill: document.getElementById("lt-fill"),
      modRt: document.getElementById("mod-rt"),
      rtTrigger: document.getElementById("rt-trigger"),
      rtFill: document.getElementById("rt-fill"),
      btnLb: document.getElementById("btn-lb"),
      btnRb: document.getElementById("btn-rb"),
      modSlotPing: document.getElementById("mod-slot-ping"),
      slotText: document.getElementById("slot-text"),
      pingText: document.getElementById("ping-text"),
      btnBack: document.getElementById("btn-back"),
      btnStart: document.getElementById("btn-start"),
      modGyro: document.getElementById("mod-gyro"),
      gyroCanvas: document.getElementById("gyro-canvas"),
      gyroTelemetry: document.getElementById("gyro-telemetry"),
      btnSettingsLogo: document.getElementById("btn-settings-logo"),
      modVisualizer: document.getElementById("mod-visualizer"),
      visualizerCanvas: document.getElementById("visualizer-canvas"),
      modLeftWing: document.getElementById("mod-left-wing"),
      leftDpadCluster: document.getElementById("left-dpad-cluster"),
      dpadUp: document.getElementById("dpad-up"),
      dpadDown: document.getElementById("dpad-down"),
      dpadLeft: document.getElementById("dpad-left"),
      dpadRight: document.getElementById("dpad-right"),
      leftStickAnchor: document.getElementById("left-stick-anchor"),
      leftStickBase: document.getElementById("left-stick-base"),
      leftStickPuck: document.getElementById("left-stick-puck"),
      modRightWing: document.getElementById("mod-right-wing"),
      rightAbxyCluster: document.getElementById("right-abxy-cluster"),
      btnY: document.getElementById("btn-y"),
      btnX: document.getElementById("btn-x"),
      btnB: document.getElementById("btn-b"),
      btnA: document.getElementById("btn-a"),
      rightStickAnchor: document.getElementById("right-stick-anchor"),
      rightStickBase: document.getElementById("right-stick-base"),
      rightStickPuck: document.getElementById("right-stick-puck"),

      // Preset 2 DOM Elements
      modLtP2: document.getElementById("mod-lt-p2"),
      ltFillP2: document.getElementById("lt-fill-p2"),
      modRtP2: document.getElementById("mod-rt-p2"),
      rtFillP2: document.getElementById("rt-fill-p2"),
      btnLbP2: document.getElementById("btn-lb-p2"),
      btnRbP2: document.getElementById("btn-rb-p2"),
      btnSettingsLogoP2: document.getElementById("btn-settings-logo-p2"),
      tacticalSubBadgeP2: document.getElementById("tactical-sub-badge-p2"),
      slotTextP2: document.getElementById("slot-text-p2"),
      pingTextP2: document.getElementById("ping-text-p2"),
      btnBackP2: document.getElementById("btn-back-p2"),
      btnStartP2: document.getElementById("btn-start-p2"),
      modGyroP2: document.getElementById("mod-gyro-p2"),
      gyroCanvasP2: document.getElementById("gyro-canvas-p2"),
      gyroTelemetryP2: document.getElementById("gyro-telemetry-p2"),
      leftStickAnchorP2: document.getElementById("left-stick-anchor-p2"),
      leftStickBaseP2: document.getElementById("left-stick-base-p2"),
      leftStickPuckP2: document.getElementById("left-stick-puck-p2"),
      rightStickAnchorP2: document.getElementById("right-stick-anchor-p2"),
      rightStickBaseP2: document.getElementById("right-stick-base-p2"),
      rightStickPuckP2: document.getElementById("right-stick-puck-p2"),
      btnYP2: document.getElementById("btn-y-p2"),
      btnXP2: document.getElementById("btn-x-p2"),
      btnAP2: document.getElementById("btn-a-p2"),
      btnBP2: document.getElementById("btn-b-p2"),

      // Modals
      engageModal: document.getElementById("engage-modal"),
      engageBtn: document.getElementById("engage-btn"),
      settingsModal: document.getElementById("settings-modal"),
      btnPreset1: document.getElementById("btn-preset-1"),
      btnPreset2: document.getElementById("btn-preset-2")
    };

    if (this.dom.engageBtn) {
      this.dom.engageBtn.addEventListener("click", () => this.engage());
    }

    // Settings Modal Triggers (Clean Logo Buttons in both presets)
    if (this.dom.btnSettingsLogo) {
      this.dom.btnSettingsLogo.addEventListener("click", () => this.openSettingsModal());
    }
    if (this.dom.btnSettingsLogoP2) {
      this.dom.btnSettingsLogoP2.addEventListener("click", () => this.openSettingsModal());
    }

    // Modal Background Click (Close)
    if (this.dom.settingsModal) {
      this.dom.settingsModal.addEventListener("click", (e) => {
        if (e.target === this.dom.settingsModal) {
          this.closeSettingsModal();
        }
      });
    }

    // Minimalist 1 and 2 Preset Switcher Buttons
    if (this.dom.btnPreset1) {
      this.dom.btnPreset1.addEventListener("click", () => this.switchPreset("preset1"));
    }
    if (this.dom.btnPreset2) {
      this.dom.btnPreset2.addEventListener("click", () => this.switchPreset("preset2"));
    }

    // Player Slot Tapping
    if (this.dom.modSlotPing) {
      this.dom.modSlotPing.addEventListener("click", () => this.cyclePreferredSlot());
    }
    if (this.dom.tacticalSubBadgeP2) {
      this.dom.tacticalSubBadgeP2.addEventListener("click", () => this.cyclePreferredSlot());
    }

    // Gyro Screen Tapping
    if (this.dom.modGyro) {
      this.dom.modGyro.addEventListener("click", () => this.toggleGyro());
    }
    if (this.dom.modGyroP2) {
      this.dom.modGyroP2.addEventListener("click", () => this.toggleGyro());
    }
  }

  /**
   * Dispatches input state to the WebSocket server IMMEDIATELY with 0ms client latency.
   */
  sendInputNow(isCritical = false) {
    if (!this.connected || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;

    const now = performance.now();
    this._lastSendTime = now;
    this.seq++;

    const manualStickActive = this.leftStickActive || Math.abs(this.stickX) > 500 || Math.abs(this.stickY) > 500;
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
      right_stick_x: this.rightStickX,
      right_stick_y: this.rightStickY,
      throttle: this.throttle,
      brake: this.brake,
      accel: this.accel,
      rtt: this.rtt || 0,
      buttons: this.buttons
    };

    try {
      this.ws.send(JSON.stringify(packet));
    } catch (_) {}

    this._lastSentStickX = this.stickX;
    this._lastSentStickY = this.stickY;
  }

  toggleGyro() {
    this.gyroEnabled = !this.gyroEnabled;
    this.haptics.triggerClick();
    const txt = this.gyroEnabled
      ? `ON // ${this.rawAngle >= 0 ? '+' : ''}${this.rawAngle.toFixed(1)}°`
      : `${this.rawAngle >= 0 ? '+' : ''}${this.rawAngle.toFixed(1)}°`;

    if (this.dom.gyroTelemetry) this.dom.gyroTelemetry.innerText = txt;
    if (this.dom.gyroTelemetryP2) this.dom.gyroTelemetryP2.innerText = txt;
    this.sendInputNow(true);
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
      }
    } catch (e) {
      console.debug("Fullscreen toggle error", e);
    }
    window.scrollTo(0, 1);
  }

  async lockOrientationLandscape() {
    try {
      if (screen.orientation && screen.orientation.lock) {
        await screen.orientation.lock("landscape").catch(() => {});
      } else if (screen.lockOrientationUniversal) {
        screen.lockOrientationUniversal("landscape");
      } else if (screen.mozLockOrientation) {
        screen.mozLockOrientation("landscape");
      } else if (screen.msLockOrientation) {
        screen.msLockOrientation("landscape");
      }
    } catch (_) {}
    this.checkOrientation();
  }

  async engage() {
    this.toggleFullscreen();
    await this.lockOrientationLandscape();

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

    try {
      if ("wakeLock" in navigator) {
        await navigator.wakeLock.request("screen");
      }
    } catch (_) {}

    this.haptics.initAudio();
    this._attachMotionSensors();

    if (this.dom.engageModal) {
      this.dom.engageModal.style.display = "none";
    }
    this.connect();
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
          z: e.accelerationIncludingGravity.z || 9.8
        };
      }
    }, { passive: true });
  }

  _initControls() {
    // =========================================================================
    // 1. Left Analog Stick (Preset 1 and Preset 2)
    // =========================================================================
    const bindLeftStick = (anchorEl, baseEl, puckEl) => {
      if (!anchorEl || !puckEl) return;

      anchorEl.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (this.leftStickPointerId !== null) return;

        this.leftStickPointerId = e.pointerId;
        this.leftStickActive = true;
        this.leftStickTouchStartTime = performance.now();
        this.leftStickCadenceTimer = null;
        this.leftStickLastStepDir = null;

        this.haptics.triggerClick();
        this._updateLeftStickFromPointer(e.clientX, e.clientY, baseEl, puckEl);
        this.sendInputNow(true);
      }, { passive: false });

      window.addEventListener("pointermove", (e) => {
        if (!this.leftStickActive || e.pointerId !== this.leftStickPointerId) return;
        e.preventDefault();
        this._updateLeftStickFromPointer(e.clientX, e.clientY, baseEl, puckEl);
      }, { passive: false });

      const releaseLeftStick = (e) => {
        if (this.leftStickPointerId === null || e.pointerId !== this.leftStickPointerId) return;

        this.leftStickActive = false;
        this.leftStickPointerId = null;
        this.stickX = 0;
        this.stickY = 0;
        this.leftStickLastStepDir = null;
        if (this.leftStickCadenceTimer) {
          clearTimeout(this.leftStickCadenceTimer);
          this.leftStickCadenceTimer = null;
        }
        if (puckEl) {
          puckEl.style.transform = "translate(0px, 0px)";
        }

        this.sendInputNow(true);
        setTimeout(() => this.sendInputNow(true), 8);
        setTimeout(() => this.sendInputNow(true), 16);
      };

      window.addEventListener("pointerup", releaseLeftStick);
      window.addEventListener("pointercancel", releaseLeftStick);
    };

    bindLeftStick(this.dom.leftStickAnchor, this.dom.leftStickBase, this.dom.leftStickPuck);
    bindLeftStick(this.dom.leftStickAnchorP2, this.dom.leftStickBaseP2, this.dom.leftStickPuckP2);

    // =========================================================================
    // 2. Right Analog Stick (Preset 1 and Preset 2)
    // =========================================================================
    const bindRightStick = (anchorEl, baseEl, puckEl) => {
      if (!anchorEl || !puckEl) return;

      anchorEl.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (this.rightStickPointerId !== null) return;

        this.rightStickPointerId = e.pointerId;
        this.rightStickActive = true;
        this.rightStickMoved = false;

        this.haptics.triggerClick();
        this._updateRightStickFromPointer(e.clientX, e.clientY, baseEl, puckEl);
        this.sendInputNow(true);
      }, { passive: false });

      window.addEventListener("pointermove", (e) => {
        if (!this.rightStickActive || e.pointerId !== this.rightStickPointerId) return;
        e.preventDefault();
        this._updateRightStickFromPointer(e.clientX, e.clientY, baseEl, puckEl);
      }, { passive: false });

      const releaseRightStick = (e) => {
        if (this.rightStickPointerId === null || e.pointerId !== this.rightStickPointerId) return;

        if (!this.rightStickMoved) {
          this.buttons.RS = true;
          this.haptics.triggerClick("heavy");
          this.sendInputNow(true);
          setTimeout(() => {
            this.buttons.RS = false;
            this.sendInputNow(true);
          }, 80);
        }

        this.rightStickActive = false;
        this.rightStickPointerId = null;
        this.rightStickX = 0;
        this.rightStickY = 0;
        if (puckEl) {
          puckEl.style.transform = "translate(0px, 0px)";
        }

        this.sendInputNow(true);
        setTimeout(() => this.sendInputNow(true), 8);
        setTimeout(() => this.sendInputNow(true), 16);
      };

      window.addEventListener("pointerup", releaseRightStick);
      window.addEventListener("pointercancel", releaseRightStick);
    };

    bindRightStick(this.dom.rightStickAnchor, this.dom.rightStickBase, this.dom.rightStickPuck);
    bindRightStick(this.dom.rightStickAnchorP2, this.dom.rightStickBaseP2, this.dom.rightStickPuckP2);

    // =========================================================================
    // 3. Hair-Triggers (LT / RT) across presets
    // =========================================================================
    const bindTrigger = (modEl, fillEl, triggerKey) => {
      if (!modEl) return;
      modEl.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        if (triggerKey === "LT") {
          this.brake = 1.0;
          this.ltPointerId = e.pointerId;
        } else {
          this.throttle = 1.0;
          this.rtPointerId = e.pointerId;
        }
        if (fillEl) fillEl.style.height = "100%";
        modEl.classList.add("active");
        this.haptics.triggerClick("heavy");
        this.sendInputNow(true);
      }, { passive: false });

      const releaseTrig = (e) => {
        const ptrId = triggerKey === "LT" ? this.ltPointerId : this.rtPointerId;
        if (ptrId === null || e.pointerId !== ptrId) return;

        if (triggerKey === "LT") {
          this.brake = 0.0;
          this.ltPointerId = null;
        } else {
          this.throttle = 0.0;
          this.rtPointerId = null;
        }
        if (fillEl) fillEl.style.height = "0%";
        modEl.classList.remove("active");

        this.sendInputNow(true);
        setTimeout(() => this.sendInputNow(true), 8);
        setTimeout(() => this.sendInputNow(true), 16);
      };

      window.addEventListener("pointerup", releaseTrig);
      window.addEventListener("pointercancel", releaseTrig);
    };

    bindTrigger(this.dom.modLt, this.dom.ltFill, "LT");
    bindTrigger(this.dom.modRt, this.dom.rtFill, "RT");
    bindTrigger(this.dom.modLtP2, this.dom.ltFillP2, "LT");
    bindTrigger(this.dom.modRtP2, this.dom.rtFillP2, "RT");

    // =========================================================================
    // 4. Bumpers (LB / RB) & Menu Wedges (START / BACK)
    // =========================================================================
    const bindDirectBtn = (btnEl, key) => {
      if (!btnEl) return;
      btnEl.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        this.directBtnPointers.set(e.pointerId, key);
        this.buttons[key] = true;
        btnEl.classList.add("active");
        this.haptics.triggerClick();
        this.sendInputNow(true);
      }, { passive: false });
    };

    bindDirectBtn(this.dom.btnLb, "LB");
    bindDirectBtn(this.dom.btnRb, "RB");
    bindDirectBtn(this.dom.btnStart, "START");
    bindDirectBtn(this.dom.btnBack, "BACK");

    bindDirectBtn(this.dom.btnLbP2, "LB");
    bindDirectBtn(this.dom.btnRbP2, "RB");
    bindDirectBtn(this.dom.btnStartP2, "START");
    bindDirectBtn(this.dom.btnBackP2, "BACK");

    const releaseDirectBtn = (e) => {
      if (this.directBtnPointers.has(e.pointerId)) {
        const key = this.directBtnPointers.get(e.pointerId);
        this.directBtnPointers.delete(e.pointerId);
        this.buttons[key] = false;

        document.querySelectorAll(`.active`).forEach(el => {
          if (el.innerText === key || el.id.includes(key.toLowerCase())) {
            el.classList.remove("active");
          }
        });
        this.sendInputNow(true);
      }
    };

    window.addEventListener("pointerup", releaseDirectBtn);
    window.addEventListener("pointercancel", releaseDirectBtn);

    // =========================================================================
    // 5. Tactical D-Pad Triangles (Preset 1 Left Wing)
    // =========================================================================
    const dpadButtons = [this.dom.dpadUp, this.dom.dpadDown, this.dom.dpadLeft, this.dom.dpadRight].filter(Boolean);

    const getDpadBtnFromPoint = (clientX, clientY) => {
      const el = document.elementFromPoint(clientX, clientY);
      if (!el) return null;
      return el.closest(".dpad-tri-btn");
    };

    const updateDpadStates = () => {
      const activeDirs = new Set();
      for (const info of this.dpadPointers.values()) {
        activeDirs.add(info.dir);
      }
      let changed = false;
      for (const dir of ["DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT"]) {
        const isPressed = activeDirs.has(dir);
        if (this.buttons[dir] !== isPressed) {
          this.buttons[dir] = isPressed;
          changed = true;
        }
      }
      dpadButtons.forEach(btn => {
        const dir = btn.dataset.dir;
        btn.classList.toggle("active", activeDirs.has(dir));
      });
      if (changed) {
        this.sendInputNow(true);
      }
    };

    dpadButtons.forEach(btn => {
      btn.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        const dir = btn.dataset.dir;
        this.dpadPointers.set(e.pointerId, { dir, el: btn });
        this.haptics.triggerDpadClick();
        updateDpadStates();
      }, { passive: false });
    });

    window.addEventListener("pointermove", (e) => {
      if (!this.dpadPointers.has(e.pointerId)) return;
      e.preventDefault();
      const current = this.dpadPointers.get(e.pointerId);
      const newBtn = getDpadBtnFromPoint(e.clientX, e.clientY);

      if (newBtn) {
        const newDir = newBtn.dataset.dir;
        if (newDir !== current.dir) {
          this.dpadPointers.set(e.pointerId, { dir: newDir, el: newBtn });
          this.haptics.triggerDpadClick();
          updateDpadStates();
        }
      } else {
        this.dpadPointers.delete(e.pointerId);
        updateDpadStates();
      }
    }, { passive: false });

    const releaseDpad = (e) => {
      if (this.dpadPointers.has(e.pointerId)) {
        this.dpadPointers.delete(e.pointerId);
        updateDpadStates();
      }
    };

    window.addEventListener("pointerup", releaseDpad);
    window.addEventListener("pointercancel", releaseDpad);

    // =========================================================================
    // 6. YAXB Action Buttons (Preset 1 Triangles & Preset 2 Polygons)
    // =========================================================================
    const abxyButtons = [
      this.dom.btnY, this.dom.btnX, this.dom.btnB, this.dom.btnA,
      this.dom.btnYP2, this.dom.btnXP2, this.dom.btnBP2, this.dom.btnAP2
    ].filter(Boolean);

    const updateClusterStates = () => {
      const activeKeys = new Set(this.clusterPointers.values());
      let changed = false;

      for (const key of ["A", "B", "X", "Y"]) {
        const isPressed = activeKeys.has(key);
        if (this.buttons[key] !== isPressed) {
          this.buttons[key] = isPressed;
          changed = true;
          abxyButtons.forEach(btn => {
            if (btn.dataset.btn === key) {
              btn.classList.toggle("active", isPressed);
            }
          });
        }
      }

      if (changed) {
        this.sendInputNow(true);
      }
    };

    abxyButtons.forEach(btn => {
      btn.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        const key = btn.dataset.btn;
        this.clusterPointers.set(e.pointerId, key);
        this.haptics.triggerClick();
        updateClusterStates();
      }, { passive: false });
    });

    const releaseClusterPointer = (e) => {
      if (this.clusterPointers.has(e.pointerId)) {
        this.clusterPointers.delete(e.pointerId);
        updateClusterStates();
      }
    };

    window.addEventListener("pointerup", releaseClusterPointer);
    window.addEventListener("pointercancel", releaseClusterPointer);

    // Safety Blur
    const resetAllInputs = () => {
      for (const k in this.buttons) this.buttons[k] = false;
      this.throttle = 0.0;
      this.brake = 0.0;
      this.ltPointerId = null;
      this.rtPointerId = null;
      this.stickX = 0;
      this.stickY = 0;
      this.leftStickActive = false;
      this.leftStickPointerId = null;
      this.rightStickX = 0;
      this.rightStickY = 0;
      this.rightStickActive = false;
      this.rightStickPointerId = null;
      this.directBtnPointers.clear();
      this.dpadPointers.clear();
      this.clusterPointers.clear();

      document.querySelectorAll(".active").forEach(el => el.classList.remove("active"));
      if (this.dom.ltFill) this.dom.ltFill.style.height = "0%";
      if (this.dom.rtFill) this.dom.rtFill.style.height = "0%";
      if (this.dom.ltFillP2) this.dom.ltFillP2.style.height = "0%";
      if (this.dom.rtFillP2) this.dom.rtFillP2.style.height = "0%";
      if (this.dom.leftStickPuck) this.dom.leftStickPuck.style.transform = "translate(0px, 0px)";
      if (this.dom.rightStickPuck) this.dom.rightStickPuck.style.transform = "translate(0px, 0px)";
      if (this.dom.leftStickPuckP2) this.dom.leftStickPuckP2.style.transform = "translate(0px, 0px)";
      if (this.dom.rightStickPuckP2) this.dom.rightStickPuckP2.style.transform = "translate(0px, 0px)";

      this.sendInputNow(true);
      setTimeout(() => this.sendInputNow(true), 16);
    };

    window.addEventListener("blur", resetAllInputs);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) resetAllInputs();
    });
  }

  _updateLeftStickFromPointer(clientX, clientY, customBase, customPuck) {
    const baseEl = customBase || this.dom.leftStickBase || this.dom.leftStickAnchor;
    const puckEl = customPuck || this.dom.leftStickPuck;

    const pt = this.getGamepadPoint(clientX, clientY);
    const center = this.getGamepadCenter(baseEl);
    const dx = pt.x - center.x;
    const dy = pt.y - center.y;
    const maxRadius = 34;
    const dist = Math.hypot(dx, dy);

    let visualDx = dx;
    let visualDy = dy;
    if (dist > maxRadius) {
      visualDx = (dx / dist) * maxRadius;
      visualDy = (dy / dist) * maxRadius;
    }
    if (puckEl) {
      puckEl.style.transform = `translate(${visualDx}px, ${visualDy}px)`;
    }

    const deadzone = 0.08;
    const normDist = Math.min(1.0, dist / maxRadius);

    if (normDist < deadzone) {
      this.stickX = 0;
      this.stickY = 0;
      this.leftStickLastStepDir = null;
      if (this.leftStickCadenceTimer) {
        clearTimeout(this.leftStickCadenceTimer);
        this.leftStickCadenceTimer = null;
      }
      this.sendInputNow();
    } else {
      const linearScale = (normDist - deadzone) / (1.0 - deadzone);
      const angleRad = Math.atan2(-dy, dx);
      const angleDeg = angleRad * (180.0 / Math.PI);

      const snapThresholdDeg = 16.0;
      let targetX = 0;
      let targetY = 0;

      if (Math.abs(angleDeg) <= snapThresholdDeg) {
        targetX = Math.round(linearScale * 32767);
        targetY = 0;
      } else if (Math.abs(angleDeg - 90.0) <= snapThresholdDeg) {
        targetX = 0;
        targetY = Math.round(linearScale * 32767);
      } else if (Math.abs(angleDeg - (-90.0)) <= snapThresholdDeg) {
        targetX = 0;
        targetY = Math.round(-linearScale * 32767);
      } else if (Math.abs(angleDeg) >= (180.0 - snapThresholdDeg)) {
        targetX = Math.round(-linearScale * 32767);
        targetY = 0;
      } else {
        targetX = Math.round(Math.cos(angleRad) * linearScale * 32767);
        targetY = Math.round(Math.sin(angleRad) * linearScale * 32767);
      }

      this.stickX = targetX;
      this.stickY = targetY;
      this.sendInputNow();
    }
  }

  _updateRightStickFromPointer(clientX, clientY, customBase, customPuck) {
    const baseEl = customBase || this.dom.rightStickBase || this.dom.rightStickAnchor;
    const puckEl = customPuck || this.dom.rightStickPuck;

    const pt = this.getGamepadPoint(clientX, clientY);
    const center = this.getGamepadCenter(baseEl);
    const dx = pt.x - center.x;
    const dy = pt.y - center.y;
    const maxRadius = 34;
    const dist = Math.hypot(dx, dy);

    if (dist > 5) {
      this.rightStickMoved = true;
    }

    let visualDx = dx;
    let visualDy = dy;
    if (dist > maxRadius) {
      visualDx = (dx / dist) * maxRadius;
      visualDy = (dy / dist) * maxRadius;
    }
    if (puckEl) {
      puckEl.style.transform = `translate(${visualDx}px, ${visualDy}px)`;
    }

    const deadzone = 0.06;
    const normDist = Math.min(1.0, dist / maxRadius);

    if (normDist < deadzone) {
      this.rightStickX = 0;
      this.rightStickY = 0;
    } else {
      const linearScale = (normDist - deadzone) / (1.0 - deadzone);
      const angle = Math.atan2(dy, dx);
      this.rightStickX = Math.round(Math.cos(angle) * linearScale * 32767);
      this.rightStickY = Math.round(-Math.sin(angle) * linearScale * 32767);
    }

    this.sendInputNow();
  }

  // =========================================================================
  // Canvas Renderers: Gyro HUD Screen & Audio/Haptic Visualizer
  // =========================================================================
  _initCanvases() {
    this._resizeCanvases = () => {
      const dpr = window.devicePixelRatio || 1;

      const resizeCanvas = (canvasEl, containerEl) => {
        if (canvasEl && containerEl) {
          const rect = containerEl.getBoundingClientRect();
          if (rect.width > 0 && rect.height > 0) {
            canvasEl.width = Math.round(rect.width * dpr);
            canvasEl.height = Math.round(rect.height * dpr);
          }
        }
      };

      resizeCanvas(this.dom.gyroCanvas, this.dom.modGyro);
      resizeCanvas(this.dom.gyroCanvasP2, this.dom.modGyroP2);
      resizeCanvas(this.dom.visualizerCanvas, this.dom.modVisualizer);
    };

    window.addEventListener("resize", this._resizeCanvases);
    setTimeout(this._resizeCanvases, 100);

    this._startRenderLoops();
  }

  _startRenderLoops() {
    const render = () => {
      this._renderGyroCanvas();
      this._renderVisualizerCanvas();
      requestAnimationFrame(render);
    };
    requestAnimationFrame(render);
  }

  _renderGyroCanvas() {
    const canvases = [this.dom.gyroCanvas, this.dom.gyroCanvasP2].filter(Boolean);

    canvases.forEach(canvas => {
      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      const w = canvas.width;
      const h = canvas.height;
      if (w <= 0 || h <= 0) return;

      ctx.clearRect(0, 0, w, h);

      const cx = w / 2;
      const cy = h / 2;

      const rollRad = (this.rawAngle || 0) * (Math.PI / 180.0);
      const pitchOffset = Math.max(-h * 0.35, Math.min(h * 0.35, (this.accel.y || 0) * 4.0));

      ctx.save();
      ctx.translate(cx, cy + pitchOffset);
      ctx.rotate(rollRad);

      // Horizon line
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = Math.max(2, w * 0.012);
      ctx.beginPath();
      ctx.moveTo(-w * 0.8, 0);
      ctx.lineTo(w * 0.8, 0);
      ctx.stroke();

      // Pitch ladder
      const step = h * 0.16;
      ctx.lineWidth = Math.max(1.5, w * 0.008);
      for (let i = -2; i <= 2; i++) {
        if (i === 0) continue;
        const py = i * step;
        const tickW = (3 - Math.abs(i)) * (w * 0.1);
        ctx.beginPath();
        ctx.moveTo(-tickW, py);
        ctx.lineTo(tickW, py);
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(-tickW, py);
        ctx.lineTo(-tickW, py + (i > 0 ? -4 : 4));
        ctx.moveTo(tickW, py);
        ctx.lineTo(tickW, py + (i > 0 ? -4 : 4));
        ctx.stroke();
      }

      ctx.restore();

      // Center Fixed Aircraft Reticle
      ctx.save();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = Math.max(2, w * 0.014);
      if (this.gyroEnabled) {
        ctx.shadowColor = "#ffffff";
        ctx.shadowBlur = 8;
      }
      const reticleSize = w * 0.08;

      ctx.beginPath();
      ctx.moveTo(cx - reticleSize * 1.6, cy);
      ctx.lineTo(cx - reticleSize * 0.5, cy);
      ctx.lineTo(cx - reticleSize * 0.5, cy + 5);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(cx + reticleSize * 1.6, cy);
      ctx.lineTo(cx + reticleSize * 0.5, cy);
      ctx.lineTo(cx + reticleSize * 0.5, cy + 5);
      ctx.stroke();

      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(cx, cy, Math.max(3, w * 0.012), 0, Math.PI * 2);
      ctx.fill();

      // Bank Arc
      ctx.strokeStyle = "rgba(255, 255, 255, 0.4)";
      ctx.lineWidth = 1.5;
      ctx.shadowBlur = 0;
      ctx.beginPath();
      const arcRadius = Math.min(cx, cy) * 0.85;
      ctx.arc(cx, cy, arcRadius, -Math.PI * 0.8, -Math.PI * 0.2);
      ctx.stroke();

      ctx.restore();
    });
  }

  _renderVisualizerCanvas() {
    const canvas = this.dom.visualizerCanvas;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    if (w <= 0 || h <= 0) return;

    ctx.clearRect(0, 0, w, h);

    const pulseEnergy = this.haptics.getFrequencyData(this.freqData);
    const numBars = 24;
    const barSpacing = w / numBars;
    const barWidth = Math.max(2, barSpacing * 0.65);
    const now = performance.now() * 0.003;

    for (let i = 0; i < numBars; i++) {
      let rawVal = (this.freqData[i % this.freqData.length] || 0) / 255.0;
      if (rawVal < 0.05) {
        rawVal = 0.06 + 0.05 * Math.sin(now + i * 0.45);
      }

      const energyBoost = pulseEnergy * (0.4 + 0.6 * Math.sin(i * 0.3));
      const normalizedHeight = Math.min(1.0, rawVal + energyBoost);
      const barHeight = Math.max(4, normalizedHeight * (h * 0.72));

      if (barHeight > this.peakBars[i]) {
        this.peakBars[i] = barHeight;
      } else {
        this.peakBars[i] = Math.max(4, this.peakBars[i] - 1.2);
      }

      const x = i * barSpacing + (barSpacing - barWidth) / 2;
      const y = h - barHeight - 8;

      ctx.fillStyle = normalizedHeight > 0.7 ? "#ffffff" : "rgba(255, 255, 255, 0.45)";
      ctx.fillRect(x, y, barWidth, barHeight);

      ctx.save();
      ctx.fillStyle = "#ffffff";
      ctx.shadowColor = "#ffffff";
      ctx.shadowBlur = 4;
      ctx.fillRect(x, h - this.peakBars[i] - 11, barWidth, Math.max(2, h * 0.015));
      ctx.restore();
    }

    // Oscilloscope wave
    ctx.save();
    ctx.strokeStyle = pulseEnergy > 0.2 ? "#ffffff" : "rgba(255, 255, 255, 0.4)";
    ctx.lineWidth = pulseEnergy > 0.2 ? 2.5 : 1.5;
    if (pulseEnergy > 0.2) {
      ctx.shadowColor = "#ffffff";
      ctx.shadowBlur = 8;
    }
    ctx.beginPath();

    const waveMid = h * 0.38;
    const waveAmp = (h * 0.22) * (0.15 + pulseEnergy * 0.85);

    for (let x = 0; x <= w; x += 4) {
      const angle = (x / w) * Math.PI * 6 + now * 3;
      const wy = waveMid + Math.sin(angle) * waveAmp * Math.sin((x / w) * Math.PI);
      if (x === 0) ctx.moveTo(x, wy);
      else ctx.lineTo(x, wy);
    }
    ctx.stroke();
    ctx.restore();
  }

  connect() {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const url = `${proto}//${host}/ws`;

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this._updateSlotBadge(this.playerSlot);
    };

    this.ws.onmessage = async (event) => {
      const msg = JSON.parse(event.data);

      if (msg.type === "AUTH_CHALLENGE") {
        const authResponse = await this.security.solveChallenge(msg.nonce, msg.timestamp);
        if (this.preferredSlot !== null) {
          authResponse.preferred_slot = this.preferredSlot;
        }
        this.ws.send(JSON.stringify(authResponse));
      } else if (msg.type === "AUTH_SUCCESS") {
        this.connected = true;
        this.playerSlot = msg.player_slot;
        this._updateSlotBadge(msg.player_slot);
        this.sendInputNow(true);
      } else if (msg.type === "SLOT_REASSIGNED") {
        this.playerSlot = msg.player_slot;
        this._updateSlotBadge(msg.player_slot);
        this.haptics.triggerClick("heavy");
      } else if (msg.type === "RUMBLE") {
        this.haptics.handleRumble(msg.large, msg.small);
      } else if (msg.type === "TELEMETRY") {
        if (msg.haptics?.slip) this.haptics.triggerSlip();
        if (msg.haptics?.impact) this.haptics.triggerImpact();
        if (msg.haptics?.redline) this.haptics.triggerRedline();
      } else if (msg.type === "PONG") {
        const now = performance.now();
        this.rtt = Math.round(now - msg.ts);
        if (this.dom.pingText) this.dom.pingText.innerText = `${this.rtt}ms`;
        if (this.dom.pingTextP2) this.dom.pingTextP2.innerText = `${this.rtt}ms`;
      }
    };

    this.ws.onclose = () => {
      this.connected = false;
      if (this.dom.pingText) this.dom.pingText.innerText = "--";
      if (this.dom.pingTextP2) this.dom.pingTextP2.innerText = "--";
      setTimeout(() => this.connect(), 1500);
    };
  }

  setSlot(slotNum) {
    this.preferredSlot = slotNum;
    localStorage.setItem("controller_preferred_slot", slotNum.toString());
    this.haptics.triggerClick("heavy");
    this._updateSlotBadge(slotNum);
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.close();
    }
  }

  cyclePreferredSlot() {
    const nextSlot = (this.playerSlot % 4) + 1;
    this.setSlot(nextSlot);
  }

  _updateSlotBadge(slotNum) {
    if (this.dom.slotText) this.dom.slotText.innerText = `P${slotNum}`;
    if (this.dom.slotTextP2) this.dom.slotTextP2.innerText = `P${slotNum}`;
  }

  _startLoop() {
    let lastPing = performance.now();
    const intervalMs = 1000 / 120;

    setInterval(() => {
      if (!this.connected || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;

      const now = performance.now();

      if (this.leftStickActive || this.rightStickActive || this.throttle > 0 || this.brake > 0 || this.gyroEnabled) {
        this.sendInputNow();
      }

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
