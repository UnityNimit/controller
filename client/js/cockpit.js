/**
 * Project Controller - Pure Minimalist Circular Monochromatic Engine
 * Ultra-Responsive Zero-Latency Gamepad Client (100% Circular Architecture)
 * Haptics and Vibration are managed by dedicated js/haptics.js
 */

// =========================================================================
// Pure JavaScript NIST SHA-256 & SecurityEngine are managed by js/auth.js
// =========================================================================

class GamepadClient {
  constructor() {
    this.haptics = (typeof window !== "undefined" && window.hapticEngine) ? window.hapticEngine : new HapticAudioEngine();
    if (this.haptics && typeof this.haptics.setVibrationEnabled === "function") {
      this.haptics.setVibrationEnabled(false);
    }
    this.security = new SecurityEngine();

    // Dedicated Gyroscope Subsystem (js/gyro.js) - Default OFF
    this.gyro = new GamepadGyroSensor({
      enabled: false,
      onStateChange: () => {
        this.sendInputNow(true);
      }
    });

    // Dedicated Layout Customizer Subsystem (js/layout_customizer.js)
    this.customizer = new GamepadLayoutCustomizer({
      getGamepadPoint: (x, y) => this.getGamepadPoint(x, y),
      triggerHaptic: (t) => this.haptics.triggerClick(t),
      onModeChange: (isCust) => {
        if (isCust) {
          this.haptics.initAudio();
          this.leftStickActive = false;
          this.leftStickPointerId = null;
          this.leftStickOrigin = null;
          this._leftStickRestCenter = null;
          this.stickX = 0;
          this.stickY = 0;
          this.rightStickActive = false;
          this.rightStickPointerId = null;
          this.rightStickOrigin = null;
          this._rightStickRestCenter = null;
          this.rightStickX = 0;
          this.rightStickY = 0;
          this.throttle = 0.0;
          this.brake = 0.0;
          this.directBtnPointers.clear();
          for (const k in this.buttons) this.buttons[k] = false;
          if (this.buttonElements) {
            document.querySelectorAll("[data-btn], [data-dir], [data-trigger]").forEach(el => el.classList.remove("active"));
          }
          if (this.dom && this.dom.leftStickPuck) this.dom.leftStickPuck.style.transform = "translate(0px, 0px)";
          if (this.dom && this.dom.rightStickPuck) this.dom.rightStickPuck.style.transform = "translate(0px, 0px)";
          this.sendNeutralPacket();
        } else {
          this.leftStickOrigin = null;
          this.rightStickOrigin = null;
          this._leftStickRestCenter = null;
          this._rightStickRestCenter = null;
          if (this.dom && this.dom.leftStickAnchor && this.customizer) {
            this.customizer._applyElemTransform("left-stick-anchor");
          }
          if (this.dom && this.dom.rightStickAnchor && this.customizer) {
            this.customizer._applyElemTransform("right-stick-anchor");
          }
        }
      }
    });

    this.ws = null;
    this.connected = false;
    this.authenticated = false;
    this._reconnectTimer = null;
    this.playerSlot = 1;
    this.isRotated = false;
    this.seq = 0;

    // Zero-Copy 24-Byte Binary Wire Protocol (v2) Engine
    this.useBinaryProtocol = true;
    this._binBuffer = new ArrayBuffer(24);
    this._binView = new DataView(this._binBuffer);

    let storedClientId = null;
    try {
      if (typeof sessionStorage !== "undefined") {
        storedClientId = sessionStorage.getItem("controller_session_client_id");
      }
    } catch (_) {}
    if (!storedClientId) {
      storedClientId = "node_" + Math.random().toString(36).substring(2, 10);
      try {
        if (typeof sessionStorage !== "undefined") {
          sessionStorage.setItem("controller_session_client_id", storedClientId);
        }
      } catch (_) {}
      localStorage.setItem("controller_client_id", storedClientId);
    }
    this.clientId = storedClientId;

    // Active View Mode (Controller Gamepad vs Settings Dashboard)
    this.isSettingsOpen = false;
    this.currentLayout = 1;
    this.layoutScale = 1.0;
    this.layout1Scale = 1.0;

    // Splash Entrance & Morph Animation State
    this._isEngaging = false;
    this._isEngaged = false;
    this.autoAdvanceTimer = null;

    // Primary Analog State
    this.stickX = 0;
    this.stickY = 0;
    this.rightStickX = 0;
    this.rightStickY = 0;
    this.throttle = 0.0;
    this.brake = 0.0;

    // Floating Stick Tracking & Rest Centers
    this.leftStickPointerId = null;
    this.leftStickActive = false;
    this.leftStickOrigin = null;
    this._leftStickRestCenter = null;

    this.rightStickPointerId = null;
    this.rightStickActive = false;
    this.rightStickOrigin = null;
    this.rightStickMoved = false;
    this._rightStickRestCenter = null;

    this.directBtnPointers = new Map();

    // Standard Buttons State
    this.buttons = {
      A: false,
      B: false,
      X: false,
      Y: false,
      LB: false,
      RB: false,
      LS: false,
      RS: false,
      START: false,
      BACK: false,
      DPAD_UP: false,
      DPAD_DOWN: false,
      DPAD_LEFT: false,
      DPAD_RIGHT: false
    };

    // Diagnostics & Adaptive Anti-Bufferbloat State
    this.rtt = 0;
    this._rttSamples = [];
    this._lastSendTime = 0;
    this._lastRxTime = 0;
    this._lastSentMask = 0;
    this._lastSentStickX = 0;
    this._lastSentStickY = 0;
    this._lastSentRX = 0;
    this._lastSentRY = 0;
    this._lastSentThrottle = 0;
    this._lastSentBrake = 0;
    this._lastSentAngle = 0;
    this._lastSentGyro = false;
    this.layout1Scale = 1.0;
    this._lastLogoActionTime = 0;
    this._settingsLogoPressed = false;
    this._logoHoldState = {
      active: false,
      pointerId: null,
      startTime: 0,
      startX: 0,
      startY: 0,
      timer: null,
      animFrame: null,
      triggered: false,
      moved: false
    };

    this._initDom();
    this._initControls();
    this._initCanvases();

    if (typeof window !== "undefined") {
      window.addEventListener("online", () => {
        if (!this.connected) this.connect();
      });
    }
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", () => {
        if (!document.hidden && !this.connected) {
          this.connect();
        }
      });
    }
  }

  // Subsystem Delegation Getters & Setters
  get gyroEnabled() { return this.gyro ? this.gyro.enabled : false; }
  set gyroEnabled(v) { if (this.gyro) this.gyro.enabled = v; }
  get rawAngle() { return this.gyro ? this.gyro.rawAngle : 0; }
  set rawAngle(v) { if (this.gyro) this.gyro.rawAngle = v; }
  get zeroOffset() { return this.gyro ? this.gyro.zeroOffset : 0; }
  set zeroOffset(v) { if (this.gyro) this.gyro.zeroOffset = v; }
  get accel() { return this.gyro ? this.gyro.accel : { x: 0, y: 0, z: 9.8 }; }
  set accel(v) { if (this.gyro) this.gyro.accel = v; }

  get isCustomizingLayout1() { return this.customizer ? this.customizer.isCustomizing : false; }
  set isCustomizingLayout1(v) { if (this.customizer) this.customizer.isCustomizing = v; }
  get customLayout1Config() { return this.customizer ? this.customizer.config : {}; }
  set customLayout1Config(v) { if (this.customizer) this.customizer.config = v; }
  get customStickRadius() { return this.customizer ? this.customizer.stickRadius : { left: 40, right: 40 }; }
  set customStickRadius(v) { if (this.customizer) this.customizer.stickRadius = v; }
  get activeRadiusPopupStick() { return this.customizer ? this.customizer.activeRadiusPopupStick : null; }

  checkOrientation() {
    this.isRotated = false;
    if (document.body) {
      document.body.classList.remove("forced-landscape-portrait");
    }
    this.updateLayoutScaling();
  }

  getGamepadPoint(clientX, clientY) {
    if (this.isRotated) {
      let vw = window.innerWidth;
      if (window.visualViewport) {
        vw = Math.round(window.visualViewport.width);
      }
      return {
        x: clientY,
        y: vw - clientX
      };
    }
    return { x: clientX, y: clientY };
  }

  getGamepadCenter(element) {
    if (!element) return { x: 0, y: 0 };
    const rect = element.getBoundingClientRect();
    const screenCenterX = rect.left + rect.width / 2;
    const screenCenterY = rect.top + rect.height / 2;
    return this.getGamepadPoint(screenCenterX, screenCenterY);
  }

  _initDom() {
    this.dom = {
      app: document.getElementById("controller-app"),
      frame: document.getElementById("gamepad-frame"),
      splashScreen: document.getElementById("splash-screen"),
      splashBtn: document.getElementById("splash-btn"),

      // Triggers & Bumpers
      ltTrigger: document.getElementById("lt-trigger"),
      rtTrigger: document.getElementById("rt-trigger"),
      btnLb: document.getElementById("btn-lb"),
      btnRb: document.getElementById("btn-rb"),

      // Center Controls
      btnSettingsLogo: document.getElementById("btn-settings-logo"),
      btnBack: document.getElementById("btn-back"),
      btnStart: document.getElementById("btn-start"),
      modGyro: document.getElementById("mod-gyro"),
      gyroCanvas: document.getElementById("gyro-canvas"),
      gyroHorizonLine: document.getElementById("gyro-horizon-line"),

      // Wings, Joysticks & Floating Zones
      leftStickZone: document.getElementById("left-stick-zone"),
      rightStickZone: document.getElementById("right-stick-zone"),
      modLeftWing: document.getElementById("mod-left-wing"),
      leftStickAnchor: document.getElementById("left-stick-anchor"),
      leftStickPuck: document.getElementById("left-stick-puck"),
      dpadUp: document.getElementById("dpad-up"),
      dpadDown: document.getElementById("dpad-down"),
      dpadLeft: document.getElementById("dpad-left"),
      dpadRight: document.getElementById("dpad-right"),

      modRightWing: document.getElementById("mod-right-wing"),
      rightStickAnchor: document.getElementById("right-stick-anchor"),
      rightStickPuck: document.getElementById("right-stick-puck"),
      btnY: document.getElementById("btn-y"),
      btnX: document.getElementById("btn-x"),
      btnB: document.getElementById("btn-b"),
      btnA: document.getElementById("btn-a"),

      // Visualizer Canvas (Compact/Test compatibility)
      modVisualizer: document.getElementById("mod-visualizer"),
      visualizerCanvas: document.getElementById("visualizer-canvas"),

      // Live Ping Diagnostics HUD
      pingDisplay: document.getElementById("live-ping-display"),
      pingText: document.getElementById("ping-text"),
      pingDot: document.getElementById("ping-dot")
    };

    this.dom.logoHoldRing = document.getElementById("logo-hold-ring");
    this.dom.logoHoldCircle = document.getElementById("logo-hold-circle");
    this.dom.l1CustomHud = document.getElementById("l1-custom-hud");
    this.dom.l1RadiusPopup = document.getElementById("l1-radius-popup");
    this.dom.l1RadiusSlider = document.getElementById("l1-radius-slider");
    this.dom.l1RadiusVal = document.getElementById("l1-radius-val");
    this.dom.l1RadiusTitle = document.getElementById("l1-radius-title");

    this.customizer.init(this.dom.frame);

    // Splash Screen Tap Handler (Guaranteed Responsive across Mobile & Desktop)
    if (this.dom.splashScreen) {
      let splashHandled = false;
      const handleSplash = (e) => {
        if (splashHandled) return;
        splashHandled = true;
        if (e) {
          try {
            e.preventDefault();
            e.stopPropagation();
          } catch (_) {}
        }
        this.toggleFullscreen();
        this.lockOrientationLandscape().catch(() => {});
        this.engage();
      };

      this.dom.splashScreen.addEventListener("pointerdown", handleSplash, { passive: false });
      this.dom.splashScreen.addEventListener("touchstart", handleSplash, { passive: false });
      this.dom.splashScreen.addEventListener("click", handleSplash);

      if (this.dom.splashBtn) {
        this.dom.splashBtn.addEventListener("pointerdown", handleSplash, { passive: false });
        this.dom.splashBtn.addEventListener("touchstart", handleSplash, { passive: false });
        this.dom.splashBtn.addEventListener("click", handleSplash);
      }

      const splashImg = this.dom.splashScreen.querySelector(".splash-logo-img");
      if (splashImg) {
        splashImg.addEventListener("pointerdown", handleSplash, { passive: false });
        splashImg.addEventListener("touchstart", handleSplash, { passive: false });
        splashImg.addEventListener("click", handleSplash);
      }

      // Automatically engage fullscreen Layout 1 when rotating device into landscape
      const checkRotationToStart = () => {
        if (this._isEngaged || this._isEngaging) return;
        const isLandscape = (window.innerWidth > window.innerHeight) ||
          (window.screen && window.screen.orientation && window.screen.orientation.type && window.screen.orientation.type.includes("landscape"));
        if (isLandscape) {
          this.engage();
        }
      };

      window.addEventListener("orientationchange", checkRotationToStart);
      if (window.screen && window.screen.orientation) {
        window.screen.orientation.addEventListener("change", checkRotationToStart);
      }
      window.addEventListener("resize", checkRotationToStart);
    }

    // Center Logo in Gamepad -> DUAL BEHAVIOR:
    // 1. TAP (< 450ms): Opens Settings Page seamlessly (or exits Customize mode if customizing)
    // 2. HOLD (>= 450ms): Enters / Exits Customize Layout mode with circular progress ring & haptic pulse
    const HOLD_THRESHOLD_MS = 450;
    if (this.dom.btnSettingsLogo) {
      const resetRing = () => {
        if (this.dom.logoHoldRing) {
          this.dom.logoHoldRing.classList.remove("active");
        }
        if (this.dom.logoHoldCircle) {
          this.dom.logoHoldCircle.style.strokeDashoffset = "176";
        }
      };

      const stopTimersAndRing = () => {
        if (this._logoHoldState.timer) {
          clearTimeout(this._logoHoldState.timer);
          this._logoHoldState.timer = null;
        }
        if (this._logoHoldState.animFrame) {
          cancelAnimationFrame(this._logoHoldState.animFrame);
          this._logoHoldState.animFrame = null;
        }
        resetRing();
      };

      const cancelHold = () => {
        this._logoHoldState.active = false;
        stopTimersAndRing();
      };

      const onLogoDown = (e) => {
        if (e) {
          try { e.stopPropagation(); } catch (_) {}
        }
        if (this.isSettingsOpen) return;
        const now = performance.now();
        // Prevent bleed-through when returning from Settings
        if (now - this._lastLogoActionTime < 300) return;
        // Prevent duplicate touchstart right after pointerdown
        if (this._logoHoldState.active && (now - this._logoHoldState.startTime < 80)) {
          return;
        }

        stopTimersAndRing();

        let clientX = 0, clientY = 0, pointerId = null;
        if (e) {
          if (e.touches && e.touches.length > 0) {
            clientX = e.touches[0].clientX;
            clientY = e.touches[0].clientY;
          } else {
            clientX = e.clientX || 0;
            clientY = e.clientY || 0;
            if (e.pointerId !== undefined) pointerId = e.pointerId;
          }
        }

        this._logoHoldState.active = true;
        this._logoHoldState.triggered = false;
        this._logoHoldState.moved = false;
        this._logoHoldState.pointerId = pointerId;
        this._logoHoldState.startTime = now;
        this._logoHoldState.startX = clientX;
        this._logoHoldState.startY = clientY;

        if (this.dom.logoHoldRing) {
          this.dom.logoHoldRing.classList.add("active");
        }
        if (this.dom.logoHoldCircle) {
          this.dom.logoHoldCircle.style.strokeDashoffset = "176";
        }

        const updateRing = () => {
          if (!this._logoHoldState.active) return;
          const elapsed = performance.now() - this._logoHoldState.startTime;
          const progress = Math.min(1.0, elapsed / HOLD_THRESHOLD_MS);
          const offset = 176 * (1.0 - progress);
          if (this.dom.logoHoldCircle) {
            this.dom.logoHoldCircle.style.strokeDashoffset = offset.toFixed(1);
          }
          if (progress < 1.0) {
            this._logoHoldState.animFrame = requestAnimationFrame(updateRing);
          }
        };
        this._logoHoldState.animFrame = requestAnimationFrame(updateRing);

        this._logoHoldState.timer = setTimeout(() => {
          if (!this._logoHoldState.active || this._logoHoldState.moved) return;
          this._logoHoldState.triggered = true;
          this._logoHoldState.active = false;
          this._lastLogoActionTime = performance.now();
          stopTimersAndRing();
          if (this.haptics) {
            this.haptics.triggerClick("heavy");
          }
          this.toggleCustomizeMode();
        }, HOLD_THRESHOLD_MS);
      };

      const onLogoMove = (e) => {
        if (!this._logoHoldState.active || this._logoHoldState.triggered) return;
        if (this._logoHoldState.pointerId !== null && e && e.pointerId !== undefined && e.pointerId !== this._logoHoldState.pointerId) {
          return;
        }
        let clientX = 0, clientY = 0;
        if (e && e.touches && e.touches.length > 0) {
          clientX = e.touches[0].clientX;
          clientY = e.touches[0].clientY;
        } else if (e && e.clientX !== undefined) {
          clientX = e.clientX;
          clientY = e.clientY;
        } else {
          return;
        }
        const dist = Math.hypot(clientX - this._logoHoldState.startX, clientY - this._logoHoldState.startY);
        if (dist > 45) {
          this._logoHoldState.moved = true;
          cancelHold();
        }
      };

      const onLogoUp = (e) => {
        if (this._logoHoldState.triggered) {
          cancelHold();
          return;
        }
        if (!this._logoHoldState.active) return;
        if (this._logoHoldState.pointerId !== null && e && e.pointerId !== undefined && e.pointerId !== this._logoHoldState.pointerId) {
          return;
        }
        const wasMoved = this._logoHoldState.moved;
        const elapsed = performance.now() - this._logoHoldState.startTime;
        cancelHold();

        if (!wasMoved && elapsed < HOLD_THRESHOLD_MS) {
          const now = performance.now();
          if (now - this._lastLogoActionTime < 300) return;
          this._lastLogoActionTime = now;
          if (e) {
            try {
              if (e.cancelable) e.preventDefault();
              e.stopPropagation();
            } catch (_) {}
          }
          if (this.isCustomizingLayout1) {
            this.toggleCustomizeMode();
          } else {
            this.openSettings();
          }
        }
      };

      this.dom.btnSettingsLogo.addEventListener("contextmenu", (e) => e.preventDefault());
      this.dom.btnSettingsLogo.addEventListener("pointerdown", onLogoDown);
      this.dom.btnSettingsLogo.addEventListener("touchstart", onLogoDown, { passive: true });
      this.dom.btnSettingsLogo.addEventListener("pointerup", onLogoUp);
      this.dom.btnSettingsLogo.addEventListener("touchend", onLogoUp, { passive: false });
      window.addEventListener("pointermove", onLogoMove, { passive: true });
      window.addEventListener("pointerup", onLogoUp);

      this.dom.btnSettingsLogo.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (this._logoHoldState.triggered) {
          this._logoHoldState.triggered = false;
          return;
        }
        const now = performance.now();
        if (now - this._lastLogoActionTime < 350) return;
        this._lastLogoActionTime = now;
        cancelHold();
        if (this.isCustomizingLayout1) {
          this.toggleCustomizeMode();
        } else {
          this.openSettings();
        }
      });
    }

    // Center Logo in Settings -> Tap to return to Gamepad
    const settingsLogo = document.getElementById("settings-btn-logo");
    if (settingsLogo) {
      settingsLogo.addEventListener("contextmenu", (e) => e.preventDefault());
      settingsLogo.addEventListener("pointerdown", (e) => {
        e.stopPropagation();
        if (!this.isSettingsOpen) return;
        if (performance.now() - this._lastLogoActionTime < 300) return;
        this._settingsLogoPressed = true;
      });
      settingsLogo.addEventListener("touchstart", (e) => {
        e.stopPropagation();
        if (!this.isSettingsOpen) return;
        if (performance.now() - this._lastLogoActionTime < 300) return;
        this._settingsLogoPressed = true;
      }, { passive: true });

      const handleReturnToGamepad = (e) => {
        if (e) {
          try {
            if (e.cancelable) e.preventDefault();
            e.stopPropagation();
          } catch (_) {}
        }
        if (!this.isSettingsOpen) return;
        const now = performance.now();
        if (now - this._lastLogoActionTime < 300) return;
        if (e && (e.type === "pointerup" || e.type === "touchend") && !this._settingsLogoPressed) {
          return;
        }
        this._settingsLogoPressed = false;
        this._lastLogoActionTime = now;
        this.closeSettings();
      };

      settingsLogo.addEventListener("pointerup", handleReturnToGamepad);
      settingsLogo.addEventListener("touchend", handleReturnToGamepad, { passive: false });
      settingsLogo.addEventListener("click", handleReturnToGamepad);
    }

    const bindSettingsAction = (el, actionFn) => {
      if (!el) return;
      let lastTrigger = 0;
      const invoke = (e) => {
        if (e) {
          try {
            if (e.cancelable) e.preventDefault();
            e.stopPropagation();
          } catch (_) {}
        }
        const now = performance.now();
        if (now - lastTrigger < 250) return;
        lastTrigger = now;
        actionFn();
      };
      el.addEventListener("pointerup", invoke);
      el.addEventListener("touchend", invoke, { passive: false });
      el.addEventListener("click", invoke);
    };

    // Switch Player Button
    const btnSwitchPlayer = document.getElementById("btn-switch-player");
    bindSettingsAction(btnSwitchPlayer, () => {
      this.cyclePreferredSlot();
    });

    // Direct Slot Selector Pills (P1, P2, P3, P4)
    for (let s = 1; s <= 4; s++) {
      const pill = document.getElementById(`settings-slot-p${s}`);
      bindSettingsAction(pill, () => {
        this.setPlayerSlot(s);
      });
    }

    // Vibration Toggle Button
    const btnToggleVibe = document.getElementById("btn-toggle-vibration");
    bindSettingsAction(btnToggleVibe, () => {
      if (this.haptics) {
        const enabled = this.haptics.toggleVibration();
        this.syncSettingsDom();
        if (enabled) {
          this.haptics.timedRumble(180, 180, 160);
        } else {
          this.haptics.stopAllRumble();
        }
      }
    });

    // Test Vibration Button
    const btnTestVibe = document.getElementById("btn-settings-test-vibe");
    bindSettingsAction(btnTestVibe, () => {
      if (this.haptics) {
        if (!this.haptics.vibrationEnabled) {
          this.haptics.setVibrationEnabled(true);
          this.syncSettingsDom();
        }
        this.haptics.timedRumble(255, 255, 600);
      }
    });

    // Gyroscope Steering Toggle Button
    const btnSettingsGyro = document.getElementById("btn-settings-gyro");
    bindSettingsAction(btnSettingsGyro, () => {
      this.toggleGyro();
      this.syncSettingsDom();
    });

    // Customize Controls Button
    const btnSettingsCust = document.getElementById("btn-settings-customize");
    bindSettingsAction(btnSettingsCust, () => {
      this.closeSettings();
      setTimeout(() => this.toggleCustomizeMode(), 100);
    });

    // Reset Controls Button
    const btnSettingsReset = document.getElementById("btn-settings-reset");
    bindSettingsAction(btnSettingsReset, () => {
      this._leftStickRestCenter = null;
      this._rightStickRestCenter = null;
      this.resetLayout1Config();
      this.haptics.triggerClick("heavy");
      if (btnSettingsReset) {
        btnSettingsReset.textContent = "CONTROLS RESET";
        if (this._resetBtnTimer) clearTimeout(this._resetBtnTimer);
        this._resetBtnTimer = setTimeout(() => {
          btnSettingsReset.textContent = "RESET CONTROLS";
        }, 800);
      }
    });

    // Fullscreen Button
    const btnSettingsFs = document.getElementById("btn-settings-fullscreen");
    bindSettingsAction(btnSettingsFs, () => {
      this.toggleFullscreen();
    });

    // Initialize layout visibility & scale
    this.switchLayout(this.currentLayout, false);

    // Synchronize initial Gyroscope & Settings DOM state (Default OFF)
    this.gyro.syncDomState();
    this.syncSettingsDom();

    // Gyroscope toggle (Tap to turn on/off and show/hide center line)
    if (this.dom.modGyro) {
      let lastGyroTap = 0;
      const handleGyroTap = (e) => {
        const now = performance.now();
        if (now - lastGyroTap < 250) return;
        lastGyroTap = now;
        if (e) {
          e.preventDefault();
          e.stopPropagation();
        }
        this.toggleGyro();
      };
      this.dom.modGyro.addEventListener("click", handleGyroTap);
      this.dom.modGyro.addEventListener("pointerdown", handleGyroTap);
    }

    // Responsive real-time container observer
    if (typeof ResizeObserver !== "undefined" && this.dom.app) {
      try {
        const ro = new ResizeObserver(() => {
          this.updateLayoutScaling();
        });
        ro.observe(this.dom.app);
      } catch (_) {}
    }
  }

  openSettings() {
    this._lastLogoActionTime = performance.now();
    this._settingsLogoPressed = false;
    if (this._logoHoldState) {
      this._logoHoldState.active = false;
    }
    this.isSettingsOpen = true;
    this.haptics.triggerClick("normal");
    const gpFrame = document.getElementById("gamepad-frame");
    const stFrame = document.getElementById("settings-frame");
    if (gpFrame) gpFrame.style.display = "none";
    if (stFrame) {
      stFrame.style.display = "block";
      stFrame.classList.add("settings-entering");
      requestAnimationFrame(() => {
        stFrame.classList.remove("settings-entering");
      });
    }
    this.syncSettingsDom();
    this.updateLayoutScaling();
  }

  closeSettings() {
    if (this.isSettingsOpen) {
      this._lastLogoActionTime = performance.now();
    }
    this._settingsLogoPressed = false;
    if (this._logoHoldState) {
      this._logoHoldState.active = false;
    }
    this.isSettingsOpen = false;
    this.haptics.triggerClick("normal");
    const gpFrame = document.getElementById("gamepad-frame");
    const stFrame = document.getElementById("settings-frame");
    if (stFrame) stFrame.style.display = "none";
    if (gpFrame) gpFrame.style.display = "block";
    if (this.gyro) this.gyro.syncDomState();
    this.updateLayoutScaling();
  }

  toggleSettings() {
    if (this.isSettingsOpen) {
      this.closeSettings();
    } else {
      this.openSettings();
    }
  }

  switchLayout(layoutNum, triggerHaptic = true) {
    // Backward compatibility shim: 2 = Settings, 1 = Controller
    if (layoutNum === 2) {
      this.openSettings();
    } else {
      this.closeSettings();
    }
  }

  syncSettingsDom() {
    const curPText = document.getElementById("settings-current-player-text");
    if (curPText) {
      curPText.textContent = `PLAYER ${this.playerSlot}`;
    }
    const footText = document.getElementById("settings-slot-foot");
    if (footText) {
      footText.textContent = `Assigned to PC Gamepad Slot ${this.playerSlot}`;
    }
    // Update slot pills
    for (let s = 1; s <= 4; s++) {
      const pill = document.getElementById(`settings-slot-p${s}`);
      if (pill) {
        pill.classList.toggle("active", this.playerSlot === s);
      }
    }
    // Update vibration button
    const vibeBtn = document.getElementById("btn-toggle-vibration");
    if (vibeBtn && this.haptics) {
      const isEn = this.haptics.vibrationEnabled;
      vibeBtn.classList.toggle("active", isEn);
      const textSpan = vibeBtn.querySelector(".toggle-text");
      if (textSpan) textSpan.textContent = isEn ? "ON" : "OFF";
    }
    // Update gyro button
    const gyroBtn = document.getElementById("btn-settings-gyro");
    if (gyroBtn && this.gyro) {
      const isGyro = this.gyro.enabled;
      gyroBtn.classList.toggle("active", isGyro);
      const textSpan = gyroBtn.querySelector(".toggle-text");
      if (textSpan) textSpan.textContent = isGyro ? "ON" : "OFF";
    }
    // Update ping text
    const pingEl = document.getElementById("settings-ping-text");
    if (pingEl) {
      pingEl.textContent = `${Math.round(this.rtt || 0)} ms`;
    }
  }

  setPlayerSlot(slotNum) {
    const s = Math.max(1, Math.min(4, parseInt(slotNum, 10) || 1));
    this.playerSlot = s;
    localStorage.setItem("controller_preferred_slot", s.toString());
    this.haptics.triggerClick("heavy");
    this.syncSettingsDom();
    if (this.authenticated && this.connected && this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify({ type: "SWITCH_SLOT", slot: s }));
      } catch (_) {
        this.connect();
      }
    } else {
      this.connect();
    }
  }

  updateLayoutScaling() {
    this._leftStickRestCenter = null;
    this._rightStickRestCenter = null;
    const l1Frame = document.getElementById("gamepad-frame");
    const stFrame = document.getElementById("settings-frame");
    const app = document.getElementById("controller-app");

    let vw = window.innerWidth;
    let vh = window.innerHeight;
    if (window.visualViewport) {
      vw = Math.round(window.visualViewport.width);
      vh = Math.round(window.visualViewport.height);
    }

    // Always maintain fixed landscape gamepad presentation - never rotate on phone tilt or orientation change
    this.isRotated = false;
    if (document.body) {
      document.body.classList.remove("forced-landscape-portrait");
    }

    // Read device safe area insets (notches, Dynamic Islands, Safari navigation bars)
    let safeTop = 0, safeBottom = 0, safeLeft = 0, safeRight = 0;
    const probe = document.getElementById("safe-area-probe");
    if (probe) {
      const cs = window.getComputedStyle(probe);
      safeTop = parseFloat(cs.paddingTop) || 0;
      safeBottom = parseFloat(cs.paddingBottom) || 0;
      safeLeft = parseFloat(cs.paddingLeft) || 0;
      safeRight = parseFloat(cs.paddingRight) || 0;
    }

    const usableW = Math.max(100, vw - safeLeft - safeRight);
    const usableH = Math.max(100, vh - safeTop - safeBottom);

    if (app) {
      app.style.position = "fixed";
      app.style.top = "0px";
      app.style.left = "0px";
      app.style.width = `${vw}px`;
      app.style.height = `${vh}px`;
      app.style.transformOrigin = "center center";
      app.style.transform = "none";
      app.style.overflow = "hidden";
    }

    const availW = usableW;
    const availH = usableH;

    // Scale Gamepad Frame and Settings Frame identically to ensure 100% seamless logo alignment
    const scale1 = Math.max(0.1, Math.min(availW / 907, availH / 400));
    this.layoutScale = scale1 || 1.0;
    this.layout1Scale = scale1 || 1.0;

    if (l1Frame) {
      l1Frame.style.position = "absolute";
      l1Frame.style.left = "50%";
      l1Frame.style.top = "50%";
      l1Frame.style.transform = `translate(-50%, -50%) scale(${scale1})`;
    }

    if (stFrame) {
      stFrame.style.position = "absolute";
      stFrame.style.left = "50%";
      stFrame.style.top = "50%";
      stFrame.style.transform = `translate(-50%, -50%) scale(${scale1})`;
    }
  }

  _refreshButtonElements() {
    this.buttonElements = new Map();
    document.querySelectorAll("[data-btn], [data-dir], [data-trigger]").forEach((el) => {
      const key = el.dataset.btn || el.dataset.dir || el.dataset.trigger;
      if (key) {
        if (!this.buttonElements.has(key)) {
          this.buttonElements.set(key, []);
        }
        this.buttonElements.get(key).push(el);
      }
    });
  }

  cyclePreferredSlot() {
    const nextSlot = (this.playerSlot % 4) + 1;
    this.setPlayerSlot(nextSlot);
  }

  toggleGyro(forceState) {
    this.haptics.triggerClick("normal");
    const en = this.gyro.toggle(forceState);
    if (en) {
      this.gyro.requestPermission().catch(() => {});
      this.gyro.attach();
    }
    this.syncSettingsDom();
    this.sendInputNow(true);
    return en;
  }

  toggleFullscreen() {
    const el = document.documentElement;
    try {
      if (!document.fullscreenElement && !document.webkitFullscreenElement) {
        if (el.requestFullscreen) {
          el.requestFullscreen({ navigationUI: "hide" }).catch(() => {
            el.requestFullscreen().catch(() => {});
          });
        } else if (el.webkitRequestFullscreen) {
          el.webkitRequestFullscreen();
        } else if (el.mozRequestFullScreen) {
          el.mozRequestFullScreen();
        } else if (el.msRequestFullscreen) {
          el.msRequestFullscreen();
        }
      }
    } catch (_) {}
    window.scrollTo(0, 0);
    setTimeout(() => {
      window.scrollTo(0, 0);
      this.checkOrientation();
    }, 50);
  }

  async lockOrientationLandscape() {
    try {
      if (screen.orientation && screen.orientation.lock) {
        await screen.orientation.lock("landscape-primary").catch(async () => {
          await screen.orientation.lock("landscape").catch(() => {});
        });
      } else if (screen.lockOrientationUniversal) {
        screen.lockOrientationUniversal("landscape");
      } else if (screen.lockOrientation) {
        screen.lockOrientation("landscape");
      } else if (screen.mozLockOrientation) {
        screen.mozLockOrientation("landscape");
      } else if (screen.msLockOrientation) {
        screen.msLockOrientation("landscape");
      } else if (screen.webkitLockOrientation) {
        screen.webkitLockOrientation("landscape");
      }
    } catch (_) {}
    this.checkOrientation();
    setTimeout(() => this.checkOrientation(), 100);
    setTimeout(() => this.checkOrientation(), 300);
    setTimeout(() => this.checkOrientation(), 600);
  }

  async engage() {
    if (this._isEngaging || this._isEngaged) return;
    this._isEngaging = true;

    // 1. Ensure Gamepad mode is active on launch
    this.closeSettings();
    this.switchLayout(1, false);

    // 2. Transition cleanly to Layout 1
    this._startMorphAnimation();

    // 3. Concurrently initialize fullscreen, orientation lock, audio, and sensors
    this.toggleFullscreen();
    this.lockOrientationLandscape().catch(() => {});

    await this.gyro.requestPermission();

    try {
      if ("wakeLock" in navigator) {
        await navigator.wakeLock.request("screen");
      }
    } catch (_) {}

    this.haptics.initAudio();
    this.gyro.attach();
    this.connect();
    this._startLoop();
  }

  _startMorphAnimation() {
    const splashScreen = this.dom.splashScreen || document.getElementById("splash-screen");
    const frame = this.dom.frame || document.getElementById("gamepad-frame");

    if (splashScreen) {
      splashScreen.classList.add("splash-morphing");
      splashScreen.classList.add("hidden");
      setTimeout(() => {
        splashScreen.style.display = "none";
      }, 300);
    }

    if (frame) {
      frame.classList.add("layout1-blooming");
      frame.classList.add("morph-complete");
      setTimeout(() => {
        frame.classList.remove("layout1-entering", "layout1-blooming", "morph-complete");
      }, 350);
    }

    this.haptics.triggerClick("heavy");
    this.updateLayoutScaling();
    this._isEngaged = true;
    this._isEngaging = false;
  }

  _attachMotionSensors() {
    this.gyro.attach();
  }

  connect() {
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }

    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onerror = null;
      this.ws.onclose = null;
      try { this.ws.close(); } catch (_) {}
      this.ws = null;
    }

    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${location.host}/ws`;

    this.ws = new WebSocket(url);
    this.ws.binaryType = "arraybuffer";

    this.ws.onopen = () => {
      this.connected = false;
      this.authenticated = false;
      this._lastRxTime = performance.now();
    };

    this.ws.onmessage = async (evt) => {
      try {
        this._lastRxTime = performance.now();
        let msg = null;
        if (typeof evt.data === "string") {
          msg = JSON.parse(evt.data);
        } else if (evt.data instanceof ArrayBuffer) {
          const dec = new TextDecoder();
          msg = JSON.parse(dec.decode(evt.data));
        }
        if (!msg) return;

        if (msg.type === "AUTH_CHALLENGE") {
          const prefSlot = this.playerSlot || 1;
          const authResponse = this.security.solveChallenge(msg.nonce, msg.timestamp, this.clientId, prefSlot);
          this.ws.send(JSON.stringify(authResponse));
        } else if (msg.type === "AUTH_SUCCESS") {
          this.connected = true;
          this.authenticated = true;
          this._rttSamples = [];
          this.playerSlot = msg.player_slot;
          localStorage.setItem("controller_preferred_slot", String(this.playerSlot));
          this.syncSettingsDom();
          this._updatePingDisplay(1);
          this.sendInputNow(true);
          try {
            this.ws.send(JSON.stringify({ type: "PING", ts: performance.now() }));
          } catch (_) {}
        } else if (msg.type === "SLOT_REASSIGNED") {
          this.playerSlot = msg.player_slot;
          localStorage.setItem("controller_preferred_slot", String(this.playerSlot));
          this.syncSettingsDom();
          this.haptics.triggerClick("heavy");
          this.sendInputNow(true);
        } else if (msg.type === "RUMBLE") {
          this.haptics.handleRumble(msg.large, msg.small);
        } else if (msg.type === "PONG") {
          const rawRtt = Math.max(1, Math.round(performance.now() - msg.ts));
          if (!this._rttSamples) this._rttSamples = [];
          this._rttSamples.push(rawRtt);
          if (this._rttSamples.length > 3) {
            this._rttSamples.shift();
          }
          const sorted = this._rttSamples.slice().sort((a, b) => a - b);
          const medianRtt = sorted[Math.floor(sorted.length / 2)];
          this.rtt = this.rtt > 0 ? Math.max(1, Math.round(this.rtt * 0.65 + medianRtt * 0.35)) : medianRtt;
          this._updatePingDisplay(this.rtt);
        }
      } catch (_) {}
    };

    this.ws.onclose = () => {
      this.connected = false;
      this.authenticated = false;
      this.haptics.stopAllRumble();
      this._updatePingDisplay(null);
      if (!this._reconnectTimer) {
        this._reconnectTimer = setTimeout(() => {
          this._reconnectTimer = null;
          this.connect();
        }, 250);
      }
    };

    this.ws.onerror = () => {
      this.connected = false;
      this.authenticated = false;
      this.haptics.stopAllRumble();
    };
  }

  _computeButtonMask() {
    let btnMask = 0;
    if (this.buttons.A) btnMask |= (1 << 0);
    if (this.buttons.B) btnMask |= (1 << 1);
    if (this.buttons.X) btnMask |= (1 << 2);
    if (this.buttons.Y) btnMask |= (1 << 3);
    if (this.buttons.LB) btnMask |= (1 << 4);
    if (this.buttons.RB) btnMask |= (1 << 5);
    if (this.brake > 0.05) btnMask |= (1 << 6);
    if (this.throttle > 0.05) btnMask |= (1 << 7);
    if (this.buttons.START) btnMask |= (1 << 8);
    if (this.buttons.BACK) btnMask |= (1 << 9);
    if (this.buttons.LS) btnMask |= (1 << 10);
    if (this.buttons.RS) btnMask |= (1 << 11);
    if (this.buttons.DPAD_UP) btnMask |= (1 << 12);
    if (this.buttons.DPAD_DOWN) btnMask |= (1 << 13);
    if (this.buttons.DPAD_LEFT) btnMask |= (1 << 14);
    if (this.buttons.DPAD_RIGHT) btnMask |= (1 << 15);
    return btnMask;
  }

  _isInputActiveOrChanged() {
    const btnMask = this._computeButtonMask();
    if (
      this.leftStickActive ||
      this.rightStickActive ||
      this.gyroEnabled ||
      btnMask !== 0 ||
      this.throttle > 0.005 ||
      this.brake > 0.005 ||
      Math.abs(this.stickX) > 50 ||
      Math.abs(this.stickY) > 50 ||
      Math.abs(this.rightStickX) > 50 ||
      Math.abs(this.rightStickY) > 50
    ) {
      return true;
    }
    if (
      btnMask !== this._lastSentMask ||
      Math.round(this.stickX) !== this._lastSentStickX ||
      Math.round(this.stickY) !== this._lastSentStickY ||
      Math.round(this.rightStickX) !== this._lastSentRX ||
      Math.round(this.rightStickY) !== this._lastSentRY ||
      Math.round(this.throttle * 255) !== this._lastSentThrottle ||
      Math.round(this.brake * 255) !== this._lastSentBrake ||
      this.gyroEnabled !== this._lastSentGyro
    ) {
      return true;
    }
    return false;
  }

  sendInputNow(isCritical = false) {
    if (this.isCustomizingLayout1) return;
    if (!this.authenticated || !this.connected || !this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    // Strict 256-byte anti-bufferbloat cap for non-critical frames prevents Wi-Fi TX queue buildup
    if (!isCritical && this.ws.bufferedAmount > 256) return;

    const now = performance.now();
    this._lastSendTime = now;
    this.seq++;

    const manualStickActive = this.leftStickActive || Math.abs(this.stickX) > 500 || Math.abs(this.stickY) > 500;
    const effectiveGyro = this.gyroEnabled && !manualStickActive;
    const effectiveAngle = effectiveGyro ? (this.rawAngle - this.zeroOffset) : 0.0;
    const effectiveStickX = effectiveGyro ? 0 : this.stickX;
    const btnMask = this._computeButtonMask();

    this._lastSentMask = btnMask;
    this._lastSentStickX = Math.round(effectiveStickX);
    this._lastSentStickY = Math.round(this.stickY);
    this._lastSentRX = Math.round(this.rightStickX);
    this._lastSentRY = Math.round(this.rightStickY);
    this._lastSentThrottle = Math.round(this.throttle * 255);
    this._lastSentBrake = Math.round(this.brake * 255);
    this._lastSentAngle = Math.round(effectiveAngle * 100);
    this._lastSentGyro = effectiveGyro;

    if (this.useBinaryProtocol) {
      const v = this._binView;
      // 0: Magic 0x43 ('C'), 1: Version 0x02
      v.setUint8(0, 0x43);
      v.setUint8(1, 0x02);
      // 2-3: seq uint16
      v.setUint16(2, this.seq & 0xffff, true);
      // 4-7: timestamp uint32 ms
      v.setUint32(4, Math.round(now) >>> 0, true);
      // 8-15: axes (stickX, stickY, rightStickX, rightStickY)
      v.setInt16(8, Math.max(-32768, Math.min(32767, this._lastSentStickX)), true);
      v.setInt16(10, Math.max(-32768, Math.min(32767, this._lastSentStickY)), true);
      v.setInt16(12, Math.max(-32768, Math.min(32767, this._lastSentRX)), true);
      v.setInt16(14, Math.max(-32768, Math.min(32767, this._lastSentRY)), true);
      // 16-17: throttle, brake uint8
      v.setUint8(16, Math.max(0, Math.min(255, this._lastSentThrottle)));
      v.setUint8(17, Math.max(0, Math.min(255, this._lastSentBrake)));
      // 18-19: button bitmask uint16
      v.setUint16(18, btnMask, true);
      // 20-21: gyro angle x 100 int16
      const angleX100 = Math.max(-32768, Math.min(32767, this._lastSentAngle));
      v.setInt16(20, angleX100, true);
      // 22: flags (bit 0: gyro_enabled)
      let flags = 0;
      if (effectiveGyro) flags |= 0x01;
      v.setUint8(22, flags);
      // 23: rtt ms uint8
      v.setUint8(23, Math.min(255, Math.round(this.rtt || 0)));

      try {
        this.ws.send(this._binBuffer);
      } catch (_) {}
      return;
    }

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
  }

  _startLoop() {
    let lastPing = 0;

    // Adaptive high-frequency transmission pump:
    // Streams at high rate (>= 2.5ms) during active control changes/holds,
    // and throttles redundant neutral keepalive packets to 25ms (40 Hz) to eliminate Wi-Fi airtime saturation.
    const pumpTick = () => {
      if (this.authenticated && this.connected && this.ws && this.ws.readyState === WebSocket.OPEN) {
        const now = performance.now();
        const elapsed = now - this._lastSendTime;
        const active = this._isInputActiveOrChanged();
        const minInterval = active ? 2.5 : 25.0;
        if (elapsed >= minInterval) {
          this.sendInputNow(false);
        }
      }
    };

    if (this.workerTicker) {
      this.workerTicker.stop();
    }
    if (typeof HighRateWorkerTicker !== "undefined") {
      this.workerTicker = new HighRateWorkerTicker(pumpTick, 2); // 2ms tick interval
      this.workerTicker.start();
    } else {
      if (this._transmitTimer) clearInterval(this._transmitTimer);
      this._transmitTimer = setInterval(pumpTick, 4);
    }

    const loop = () => {
      const now = performance.now();

      if (this.authenticated && this.connected && this._isInputActiveOrChanged()) {
        if (now - this._lastSendTime >= 2.0) {
          this.sendInputNow(false);
        }
      }

      if (now - lastPing >= 500) {
        if (
          this.authenticated &&
          this.connected &&
          this.ws &&
          this.ws.readyState === WebSocket.OPEN &&
          this.ws.bufferedAmount <= 128
        ) {
          lastPing = now;
          try {
            this.ws.send(JSON.stringify({ type: "PING", ts: now }));
          } catch (_) {}
        }
      }

      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  _updatePingDisplay(rtt) {
    if (!this.dom.pingText) {
      this.dom.pingText = document.getElementById("ping-text");
    }
    if (!this.dom.pingText) return;

    if (rtt === null || !this.connected || !this.authenticated) {
      this.dom.pingText.textContent = "-- ms";
    } else {
      this.dom.pingText.textContent = `${rtt} ms`;
    }
  }

  _isPointInElement(el, clientX, clientY) {
    if (!el || typeof el.getBoundingClientRect !== "function") return false;
    const rect = el.getBoundingClientRect();
    return (
      clientX >= rect.left &&
      clientX <= rect.right &&
      clientY >= rect.top &&
      clientY <= rect.bottom
    );
  }

  _getButtonAtPoint(clientX, clientY) {
    if (typeof document === "undefined" || !document.elementsFromPoint) return null;
    const elements = document.elementsFromPoint(clientX, clientY);
    if (!elements || elements.length === 0) return null;

    for (let i = 0; i < elements.length; i++) {
      const el = elements[i];
      if (!el || el.id === "left-stick-anchor" || el.id === "left-stick-puck" ||
          el.id === "right-stick-anchor" || el.id === "right-stick-puck" ||
          el.id === "left-stick-zone" || el.id === "right-stick-zone" ||
          (el.classList && (el.classList.contains("floating-stick-zone") || el.classList.contains("floating-zone-label"))) ||
          el.id === "splash-screen" || el.id === "splash-btn" ||
          el.id === "controller-app" || el.id === "gamepad-frame" ||
          el.id === "settings-frame" || (el.closest && el.closest("#settings-frame"))) {
        continue;
      }
      if (el.id === "btn-settings-logo" || el.id === "mod-gyro" ||
          el.id === "settings-btn-logo" ||
          (el.closest && (el.closest("#btn-settings-logo") || el.closest("#mod-gyro") || el.closest("#settings-btn-logo")))) {
        continue;
      }
      const btn = el.closest ? el.closest("[data-btn], [data-dir], [data-trigger]") : null;
      if (btn) return btn;
    }
    return null;
  }

  _setButtonState(key, isPressed, pressure = 1.0) {
    if (this.isCustomizingLayout1) return;
    if (key === "LT") {
      const p = (pressure !== undefined && pressure > 0.05) ? pressure : 1.0;
      this.brake = isPressed ? Math.max(0.1, Math.min(1.0, p)) : 0.0;
    } else if (key === "RT") {
      const p = (pressure !== undefined && pressure > 0.05) ? pressure : 1.0;
      this.throttle = isPressed ? Math.max(0.1, Math.min(1.0, p)) : 0.0;
    } else if (key in this.buttons) {
      this.buttons[key] = isPressed;
    }

    if (this.buttonElements && this.buttonElements.has(key)) {
      const els = this.buttonElements.get(key);
      if (Array.isArray(els)) {
        els.forEach(el => el.classList.toggle("active", isPressed));
      } else if (els) {
        els.classList.toggle("active", isPressed);
      }
    }
  }

  _initControls() {
    this._refreshButtonElements();

    // =========================================================================
    // 1. Left Analog Stick (Minimalist Circular System)
    // =========================================================================
    const leftAnchor1 = this.dom.leftStickAnchor;
    const leftPuck1 = this.dom.leftStickPuck;

    const resetLeftStick = () => {
      this.leftStickActive = false;
      this.leftStickPointerId = null;
      this.leftStickOrigin = null;
      this._leftStickRestCenter = null;

      const startX = this.stickX;
      const startY = this.stickY;
      const mag = Math.hypot(startX, startY);

      if (leftPuck1) {
        leftPuck1.style.transition = "transform 0.05s cubic-bezier(0.1, 0.9, 0.2, 1)";
        leftPuck1.style.transform = "translate(0px, 0px)";
      }
      if (leftAnchor1) {
        leftAnchor1.style.transition = "transform 0.18s cubic-bezier(0.2, 0.9, 0.3, 1)";
        if (this.customizer && typeof this.customizer._applyElemTransform === "function") {
          this.customizer._applyElemTransform("left-stick-anchor");
        } else {
          leftAnchor1.style.transform = "";
        }
        setTimeout(() => {
          if (!this.leftStickActive && leftAnchor1) {
            leftAnchor1.style.transition = "";
          }
        }, 190);
      }

      if (mag > 1200) {
        // High-speed physical spring-return simulation (decays in ~20ms across 3 steps for game flick detection)
        this.sendInputNow(true);
        setTimeout(() => {
          if (!this.leftStickActive) {
            this.stickX = Math.round(startX * 0.50);
            this.stickY = Math.round(startY * 0.50);
            this.sendInputNow(true);
          }
        }, 6);
        setTimeout(() => {
          if (!this.leftStickActive) {
            this.stickX = Math.round(startX * 0.15);
            this.stickY = Math.round(startY * 0.15);
            this.sendInputNow(true);
          }
        }, 14);
        setTimeout(() => {
          if (!this.leftStickActive) {
            this.stickX = 0;
            this.stickY = 0;
            this.sendInputNow(true);
            if (leftPuck1) leftPuck1.style.transition = "none";
          }
        }, 22);
      } else {
        this.stickX = 0;
        this.stickY = 0;
        this.sendInputNow(true);
        if (leftPuck1) leftPuck1.style.transition = "none";
      }
    };

    const bindLeftStickAnchor = (anchor) => {
      if (!anchor) return;
      anchor.addEventListener("pointerdown", (e) => {
        if (this.isCustomizingLayout1) return;
        e.preventDefault();
        e.stopPropagation();
        this._startLeftStick(e.pointerId, e.clientX, e.clientY);
      }, { passive: false });
    };

    bindLeftStickAnchor(leftAnchor1);
    bindLeftStickAnchor(leftPuck1);

    // =========================================================================
    // 2. Right Analog Stick (Minimalist Circular System)
    // =========================================================================
    const rightAnchor1 = this.dom.rightStickAnchor;
    const rightPuck1 = this.dom.rightStickPuck;

    const resetRightStick = () => {
      this.rightStickActive = false;
      this.rightStickPointerId = null;
      this.rightStickOrigin = null;
      this._rightStickRestCenter = null;

      const startX = this.rightStickX;
      const startY = this.rightStickY;
      const mag = Math.hypot(startX, startY);

      if (rightPuck1) {
        rightPuck1.style.transition = "transform 0.05s cubic-bezier(0.1, 0.9, 0.2, 1)";
        rightPuck1.style.transform = "translate(0px, 0px)";
      }
      if (rightAnchor1) {
        rightAnchor1.style.transition = "transform 0.18s cubic-bezier(0.2, 0.9, 0.3, 1)";
        if (this.customizer && typeof this.customizer._applyElemTransform === "function") {
          this.customizer._applyElemTransform("right-stick-anchor");
        } else {
          rightAnchor1.style.transform = "";
        }
        setTimeout(() => {
          if (!this.rightStickActive && rightAnchor1) {
            rightAnchor1.style.transition = "";
          }
        }, 190);
      }

      if (mag > 1200) {
        // High-speed physical spring-return simulation (decays in ~20ms across 3 steps for game flick detection)
        this.sendInputNow(true);
        setTimeout(() => {
          if (!this.rightStickActive) {
            this.rightStickX = Math.round(startX * 0.50);
            this.rightStickY = Math.round(startY * 0.50);
            this.sendInputNow(true);
          }
        }, 6);
        setTimeout(() => {
          if (!this.rightStickActive) {
            this.rightStickX = Math.round(startX * 0.15);
            this.rightStickY = Math.round(startY * 0.15);
            this.sendInputNow(true);
          }
        }, 14);
        setTimeout(() => {
          if (!this.rightStickActive) {
            this.rightStickX = 0;
            this.rightStickY = 0;
            this.sendInputNow(true);
            if (rightPuck1) rightPuck1.style.transition = "none";
          }
        }, 22);
      } else {
        this.rightStickX = 0;
        this.rightStickY = 0;
        this.sendInputNow(true);
        if (rightPuck1) rightPuck1.style.transition = "none";
      }
    };

    const bindRightStickAnchor = (anchor) => {
      if (!anchor) return;
      anchor.addEventListener("pointerdown", (e) => {
        if (this.isCustomizingLayout1) return;
        e.preventDefault();
        e.stopPropagation();
        this._startRightStick(e.pointerId, e.clientX, e.clientY);
      }, { passive: false });
    };

    bindRightStickAnchor(rightAnchor1);
    bindRightStickAnchor(rightPuck1);

    // =========================================================================
    // 3. Multi-Touch Independent Button Engine (Drag/Glide + Full Concurrency)
    // =========================================================================
    const handleButtonPointerDown = (e) => {
      if (this.isSettingsOpen || this.isCustomizingLayout1) return;
      if (e.pointerId === this.leftStickPointerId || e.pointerId === this.rightStickPointerId) return;

      const targetBtn = this._getButtonAtPoint(e.clientX, e.clientY);
      if (targetBtn) {
        e.preventDefault();
        const key = targetBtn.dataset.btn || targetBtn.dataset.dir || targetBtn.dataset.trigger;
        if (key) {
          const pressure = (e.pressure && e.pressure > 0.05) ? e.pressure : (e.force && e.force > 0.05 ? e.force : 1.0);
          this.directBtnPointers.set(e.pointerId, key);
          this._setButtonState(key, true, pressure);
          this.haptics.triggerClick(key.startsWith("DPAD") ? "dpad" : (key === "LT" || key === "RT" ? "heavy" : "normal"));
          this.sendInputNow(true);
        }
        return;
      }

      // Floating Sticks Ingestion (Controller Gamepad)
      if (!this.isSettingsOpen) {
        if (this.leftStickPointerId === null) {
          const isLeftHit = this._isPointInElement(this.dom.leftStickZone, e.clientX, e.clientY) ||
                            this._isPointInElement(this.dom.leftStickAnchor, e.clientX, e.clientY);
          if (isLeftHit) {
            e.preventDefault();
            this._startLeftStick(e.pointerId, e.clientX, e.clientY);
            return;
          }
        }

        if (this.rightStickPointerId === null) {
          const isRightHit = this._isPointInElement(this.dom.rightStickZone, e.clientX, e.clientY) ||
                             this._isPointInElement(this.dom.rightStickAnchor, e.clientX, e.clientY);
          if (isRightHit) {
            e.preventDefault();
            this._startRightStick(e.pointerId, e.clientX, e.clientY);
            return;
          }
        }
      }
    };

    const handleButtonPointerMove = (e) => {
      if (this.isSettingsOpen || this.isCustomizingLayout1) return;
      if (e.pointerId === this.leftStickPointerId) {
        e.preventDefault();
        this._updateLeftStickFromPointer(e.clientX, e.clientY);
        return;
      }
      if (e.pointerId === this.rightStickPointerId) {
        e.preventDefault();
        this._updateRightStickFromPointer(e.clientX, e.clientY);
        return;
      }

      // Drag / Glide over keys & 3D Touch pressure modulation
      const targetBtn = this._getButtonAtPoint(e.clientX, e.clientY);
      const newKey = targetBtn ? (targetBtn.dataset.btn || targetBtn.dataset.dir || targetBtn.dataset.trigger) : null;
      const currentKey = this.directBtnPointers.get(e.pointerId) || null;
      const pressure = (e.pressure && e.pressure > 0.05) ? e.pressure : (e.force && e.force > 0.05 ? e.force : 1.0);

      if (currentKey !== newKey) {
        if (currentKey !== null) {
          this.directBtnPointers.delete(e.pointerId);
          const isStillHeld = Array.from(this.directBtnPointers.values()).includes(currentKey);
          if (!isStillHeld) {
            this._setButtonState(currentKey, false);
          }
        }
        if (newKey !== null) {
          this.directBtnPointers.set(e.pointerId, newKey);
          const isSoleHolder = Array.from(this.directBtnPointers.values()).filter(k => k === newKey).length === 1;
          if (isSoleHolder) {
            this._setButtonState(newKey, true, pressure);
            this.haptics.triggerClick(newKey.startsWith("DPAD") ? "dpad" : (newKey === "LT" || newKey === "RT" ? "heavy" : "normal"));
          }
        }
        this.sendInputNow(true);
      } else if (currentKey === "LT" || currentKey === "RT") {
        this._setButtonState(currentKey, true, pressure);
        this.sendInputNow();
      }
    };

    const handleButtonPointerUp = (e) => {
      if (this.isSettingsOpen || this.isCustomizingLayout1) return;
      if (e.pointerId === this.leftStickPointerId) {
        if (e.clientX !== undefined && e.clientY !== undefined) {
          this._updateLeftStickFromPointer(e.clientX, e.clientY);
        }
        resetLeftStick();
        return;
      }
      if (e.pointerId === this.rightStickPointerId) {
        if (e.clientX !== undefined && e.clientY !== undefined) {
          this._updateRightStickFromPointer(e.clientX, e.clientY);
        }
        resetRightStick();
        return;
      }

      if (this.directBtnPointers.has(e.pointerId)) {
        const key = this.directBtnPointers.get(e.pointerId);
        this.directBtnPointers.delete(e.pointerId);
        const isStillHeld = Array.from(this.directBtnPointers.values()).includes(key);
        if (!isStillHeld) {
          this._setButtonState(key, false);
        }
        this.sendInputNow(true);
      }
    };

    // =========================================================================
    // High-Frequency Mobile Touch Digitizer Ingestion (Pillar 3)
    // Uses pointerrawupdate & getCoalescedEvents() to bypass VSYNC clamping
    // =========================================================================
    if (typeof TouchDigitizerEngine !== "undefined") {
      this.digitizer = new TouchDigitizerEngine({
        target: window,
        onDown: (s) => handleButtonPointerDown(s.originalEvent || s),
        onSample: (s) => {
          if (this.isCustomizingLayout1) return;
          if (s.pointerId === this.leftStickPointerId) {
            if (s.originalEvent && s.originalEvent.preventDefault) {
              try { s.originalEvent.preventDefault(); } catch (_) {}
            }
            this._updateLeftStickFromPointer(s.clientX, s.clientY);
            this.sendInputNow(s.isRaw || s.isCoalesced);
            return;
          }
          if (s.pointerId === this.rightStickPointerId) {
            if (s.originalEvent && s.originalEvent.preventDefault) {
              try { s.originalEvent.preventDefault(); } catch (_) {}
            }
            this._updateRightStickFromPointer(s.clientX, s.clientY);
            this.sendInputNow(s.isRaw || s.isCoalesced);
            return;
          }
          handleButtonPointerMove(s);
        },
        onUp: (s) => handleButtonPointerUp(s.originalEvent || s),
        onCancel: (s) => handleButtonPointerUp(s.originalEvent || s)
      });
      this.digitizer.start();
    } else {
      window.addEventListener("pointerdown", handleButtonPointerDown, { passive: false });
      window.addEventListener("pointermove", handleButtonPointerMove, { passive: false });
      window.addEventListener("pointerup", handleButtonPointerUp);
      window.addEventListener("pointercancel", handleButtonPointerUp);
    }

    // Multi-touch safety guard: if all fingers leave the screen, reset everything instantly (zero ghost inputs)
    const handleAllTouchesEnd = (e) => {
      if (e.touches.length === 0) {
        if (this.leftStickActive || this.stickX !== 0 || this.stickY !== 0) resetLeftStick();
        if (this.rightStickActive || this.rightStickX !== 0 || this.rightStickY !== 0) resetRightStick();
        for (const k in this.buttons) this.buttons[k] = false;
        this.throttle = 0.0;
        this.brake = 0.0;
        this.directBtnPointers.clear();
        document.querySelectorAll("#gamepad-frame [data-btn].active, #gamepad-frame [data-dir].active, #gamepad-frame [data-trigger].active").forEach(el => el.classList.remove("active"));
        if (this.gyro) this.gyro.syncDomState();
        this.sendInputNow(true);
      }
    };
    window.addEventListener("touchend", handleAllTouchesEnd, { passive: true });
    window.addEventListener("touchcancel", handleAllTouchesEnd, { passive: true });

    // Window blur reset
    window.addEventListener("blur", () => {
      for (const k in this.buttons) this.buttons[k] = false;
      this.throttle = 0.0;
      this.brake = 0.0;
      resetLeftStick();
      resetRightStick();
      this.directBtnPointers.clear();
      document.querySelectorAll("#gamepad-frame [data-btn].active, #gamepad-frame [data-dir].active, #gamepad-frame [data-trigger].active").forEach(el => el.classList.remove("active"));
      if (this.gyro) this.gyro.syncDomState();
      this.sendInputNow(true);
    });
  }

  _startLeftStick(pointerId, clientX, clientY) {
    if (this.isCustomizingLayout1) return;
    if (this.leftStickPointerId !== null) return;

    const leftPuck1 = this.dom.leftStickPuck;
    const leftAnchor1 = this.dom.leftStickAnchor;

    if (leftPuck1) leftPuck1.style.transition = "none";
    if (leftAnchor1) leftAnchor1.style.transition = "none";

    this.leftStickPointerId = pointerId;
    this.leftStickActive = true;
    this.haptics.triggerClick("normal");

    const pt = this.getGamepadPoint(clientX, clientY);

    if (leftAnchor1) {
      if (!this._leftStickRestCenter) {
        this._leftStickRestCenter = this.getGamepadCenter(leftAnchor1);
      }
      this.leftStickOrigin = { x: pt.x, y: pt.y };

      const scale = this.layout1Scale || 1.0;
      const deltaX = (pt.x - this._leftStickRestCenter.x) / scale;
      const deltaY = (pt.y - this._leftStickRestCenter.y) / scale;

      const cfg = (this.customizer && typeof this.customizer._getElemConfig === "function")
        ? this.customizer._getElemConfig("left-stick-anchor")
        : { dx: 0, dy: 0, s: 1.0 };
      const s = cfg.s || 1.0;
      leftAnchor1.style.transform = `translate(calc(var(--l1-dx, ${cfg.dx}px) + ${deltaX}px), calc(var(--l1-dy, ${cfg.dy}px) + ${deltaY}px)) scale(${s})`;
    } else {
      this.leftStickOrigin = null;
    }

    this._updateLeftStickFromPointer(clientX, clientY);
    this.sendInputNow(true);
  }

  _startRightStick(pointerId, clientX, clientY) {
    if (this.isCustomizingLayout1) return;
    if (this.rightStickPointerId !== null) return;

    const rightPuck1 = this.dom.rightStickPuck;
    const rightAnchor1 = this.dom.rightStickAnchor;

    if (rightPuck1) rightPuck1.style.transition = "none";
    if (rightAnchor1) rightAnchor1.style.transition = "none";

    this.rightStickPointerId = pointerId;
    this.rightStickActive = true;
    this.rightStickMoved = false;
    this.haptics.triggerClick("normal");

    const pt = this.getGamepadPoint(clientX, clientY);

    if (rightAnchor1) {
      if (!this._rightStickRestCenter) {
        this._rightStickRestCenter = this.getGamepadCenter(rightAnchor1);
      }
      this.rightStickOrigin = { x: pt.x, y: pt.y };

      const scale = this.layout1Scale || 1.0;
      const deltaX = (pt.x - this._rightStickRestCenter.x) / scale;
      const deltaY = (pt.y - this._rightStickRestCenter.y) / scale;

      const cfg = (this.customizer && typeof this.customizer._getElemConfig === "function")
        ? this.customizer._getElemConfig("right-stick-anchor")
        : { dx: 0, dy: 0, s: 1.0 };
      const s = cfg.s || 1.0;
      rightAnchor1.style.transform = `translate(calc(var(--l1-dx, ${cfg.dx}px) + ${deltaX}px), calc(var(--l1-dy, ${cfg.dy}px) + ${deltaY}px)) scale(${s})`;
    } else {
      this.rightStickOrigin = null;
    }

    this._updateRightStickFromPointer(clientX, clientY);
    this.sendInputNow(true);
  }

  _updateLeftStickFromPointer(clientX, clientY, customBase, customPuck) {
    if (this.isCustomizingLayout1) return;
    const baseEl = customBase || this.dom.leftStickAnchor;
    const puckEl = customPuck || this.dom.leftStickPuck;

    const pt = this.getGamepadPoint(clientX, clientY);
    const center = this.leftStickOrigin ? this.leftStickOrigin : this.getGamepadCenter(baseEl);
    const dx = pt.x - center.x;
    const dy = pt.y - center.y;
    const scale = this.layout1Scale || 1.0;
    const baseRadius = (this.customStickRadius ? (this.customStickRadius.left || 40) : 40);
    const maxRadius = baseRadius * scale;
    const dist = Math.hypot(dx, dy);

    let visualDx = dx;
    let visualDy = dy;
    if (dist > maxRadius) {
      visualDx = (dx / dist) * maxRadius;
      visualDy = (dy / dist) * maxRadius;
    }
    const localDx = visualDx / scale;
    const localDy = visualDy / scale;
    if (puckEl) {
      puckEl.style.transform = `translate(${localDx}px, ${localDy}px)`;
    }

    const deadzone = 0.05;
    const normDist = Math.min(1.0, dist / maxRadius);

    if (normDist < deadzone) {
      this.stickX = 0;
      this.stickY = 0;
    } else {
      const linearScale = (normDist - deadzone) / (1.0 - deadzone);
      const cartY = -dy;
      const cartX = dx;
      const angleRad = Math.atan2(cartY, cartX);
      this.stickX = Math.round(Math.cos(angleRad) * linearScale * 32767);
      this.stickY = Math.round(Math.sin(angleRad) * linearScale * 32767);
    }
    this.sendInputNow();
  }

  _updateRightStickFromPointer(clientX, clientY, customBase, customPuck) {
    if (this.isCustomizingLayout1) return;
    const baseEl = customBase || this.dom.rightStickAnchor;
    const puckEl = customPuck || this.dom.rightStickPuck;

    const pt = this.getGamepadPoint(clientX, clientY);
    const center = this.rightStickOrigin ? this.rightStickOrigin : this.getGamepadCenter(baseEl);
    const dx = pt.x - center.x;
    const dy = pt.y - center.y;
    const scale = this.layout1Scale || 1.0;
    const baseRadius = (this.customStickRadius ? (this.customStickRadius.right || 40) : 40);
    const maxRadius = baseRadius * scale;
    const dist = Math.hypot(dx, dy);

    let visualDx = dx;
    let visualDy = dy;
    if (dist > maxRadius) {
      visualDx = (dx / dist) * maxRadius;
      visualDy = (dy / dist) * maxRadius;
    }
    const localDx = visualDx / scale;
    const localDy = visualDy / scale;
    if (puckEl) {
      puckEl.style.transform = `translate(${localDx}px, ${localDy}px)`;
    }

    const deadzone = 0.05;
    const normDist = Math.min(1.0, dist / maxRadius);

    if (normDist < deadzone) {
      this.rightStickX = 0;
      this.rightStickY = 0;
    } else {
      const linearScale = (normDist - deadzone) / (1.0 - deadzone);
      const cartY = -dy;
      const cartX = dx;
      const angleRad = Math.atan2(cartY, cartX);
      this.rightStickX = Math.round(Math.cos(angleRad) * linearScale * 32767);
      this.rightStickY = Math.round(Math.sin(angleRad) * linearScale * 32767);
    }
    this.sendInputNow();
  }

  // =========================================================================
  // Canvas Renderers: Delegated to js/visualizer.js
  // =========================================================================
  _initCanvases() {
    this.visualizer = new GamepadVisualizerRenderer({
      gyroCanvas: this.dom.gyroCanvas,
      visualizerCanvas: this.dom.visualizerCanvas,
      gyroHorizonLine: this.dom.gyroHorizonLine,
      getGyroSensor: () => this.gyro
    });
    this.visualizer.start();
  }

  _renderGyroCanvas() {
    if (this.visualizer) this.visualizer.renderGyroCanvas();
  }

  _renderVisualizerCanvas() {
    if (this.visualizer) this.visualizer.renderVisualizerCanvas();
  }

  // =========================================================================
  // Layout 1 Customization Engine: Delegated to js/layout_customizer.js
  // Manages controller_layout1_custom_config, --l1-dx, and --l1-press
  // =========================================================================
  _initCustomizationHandlers() {
    if (this.customizer) this.customizer.init(this.dom.frame);
  }

  _saveLayout1Config() {
    if (this.customizer) this.customizer.saveConfig();
  }
  sendNeutralPacket() {
    if (this.authenticated && this.connected && this.ws && this.ws.readyState === WebSocket.OPEN) {
      const neutralPacket = {
        type: "INPUT",
        seq: ++this.seq,
        client_id: this.clientId,
        slot: this.playerSlot,
        gyro_enabled: false,
        angle: 0.0,
        stick_x: 0,
        stick_y: 0,
        right_stick_x: 0,
        right_stick_y: 0,
        throttle: 0.0,
        brake: 0.0,
        rtt: this.rtt || 0,
        buttons: this.buttons
      };
      try { this.ws.send(JSON.stringify(neutralPacket)); } catch (_) {}
    }
  }

  toggleCustomizeMode() {
    return this.customizer.toggleMode();
  }

  openRadiusPopup(stick, anchorEl) {
    return this.customizer.openRadiusPopup(stick, anchorEl);
  }

  closeRadiusPopup() {
    return this.customizer.closeRadiusPopup();
  }

  resetLayout1Config() {
    return this.customizer.resetDefaults();
  }
}

// Instantiate on load
window.addEventListener("DOMContentLoaded", () => {
  window.gamepadClient = new GamepadClient();
  if (window.gamepadClient) {
    window.gamepadClient.lockOrientationLandscape().catch(() => {});
  }
  window.addEventListener("resize", () => {
    if (window.gamepadClient) window.gamepadClient.checkOrientation();
  });
  window.addEventListener("orientationchange", () => {
    if (window.gamepadClient) {
      window.gamepadClient.lockOrientationLandscape().catch(() => {});
      window.gamepadClient.checkOrientation();
      setTimeout(() => window.gamepadClient && window.gamepadClient.checkOrientation(), 100);
      setTimeout(() => window.gamepadClient && window.gamepadClient.checkOrientation(), 300);
    }
  });
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", () => {
      if (window.gamepadClient) window.gamepadClient.checkOrientation();
    });
    window.visualViewport.addEventListener("scroll", () => {
      if (window.gamepadClient) window.gamepadClient.checkOrientation();
    });
  }
  window.addEventListener("pointerdown", () => {
    if (window.gamepadClient) {
      if (window.gamepadClient._isEngaged) {
        window.gamepadClient.toggleFullscreen();
      }
      window.gamepadClient.lockOrientationLandscape().catch(() => {});
    }
  }, { passive: true });
  document.addEventListener("fullscreenchange", () => {
    if (document.fullscreenElement && window.gamepadClient) {
      window.gamepadClient.lockOrientationLandscape().catch(() => {});
    }
  });
  document.addEventListener("webkitfullscreenchange", () => {
    if (document.webkitFullscreenElement && window.gamepadClient) {
      window.gamepadClient.lockOrientationLandscape().catch(() => {});
    }
  });
});
