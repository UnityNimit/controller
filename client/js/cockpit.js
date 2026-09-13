/**
 * Project Controller - Pure Minimalist Circular Monochromatic Engine
 * Ultra-Responsive Zero-Latency Gamepad Client (100% Circular Architecture)
 */

class HapticAudioEngine {
  constructor() {
    this.ctx = null;
    this.canVibrate = typeof navigator !== "undefined" && "vibrate" in navigator;
  }

  initAudio() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) {
        this.ctx = new AudioCtx();
      }
    }
    if (this.ctx && this.ctx.state === "suspended") {
      this.ctx.resume().catch(() => {});
    }
  }

  triggerClick(intensity = "normal") {
    if (this.canVibrate) {
      try {
        if (intensity === "heavy") {
          navigator.vibrate([16]);
        } else if (intensity === "dpad") {
          navigator.vibrate([10]);
        } else {
          navigator.vibrate([8]);
        }
      } catch (_) {}
    }

    if (!this.ctx) return;
    try {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      const now = this.ctx.currentTime;

      osc.type = "sine";
      const freq = intensity === "heavy" ? 110 : intensity === "dpad" ? 160 : 190;
      osc.frequency.setValueAtTime(freq, now);
      osc.frequency.exponentialRampToValueAtTime(30, now + 0.035);

      gain.gain.setValueAtTime(0.2, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.035);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start(now);
      osc.stop(now + 0.035);
    } catch (_) {}
  }

  handleRumble(largeMotor = 0, smallMotor = 0) {
    if (!this.canVibrate) return;
    const intensity = Math.max(largeMotor, smallMotor);
    if (intensity > 0.05) {
      const ms = Math.min(120, Math.round(intensity * 75));
      try {
        navigator.vibrate([ms]);
      } catch (_) {}
    }
  }
}

// =========================================================================
// Pure JavaScript NIST-Compliant SHA-256 & HMAC-SHA256
// Compatible with all mobile edge browsers without requiring window.crypto.subtle
// =========================================================================
function sha256Bytes(data) {
  function rotr(n, x) { return (x >>> n) | (x << (32 - n)); }
  function ch(x, y, z) { return (x & y) ^ (~x & z); }
  function maj(x, y, z) { return (x & y) ^ (x & z) ^ (y & z); }
  function sigma0(x) { return rotr(2, x) ^ rotr(13, x) ^ rotr(22, x); }
  function sigma1(x) { return rotr(6, x) ^ rotr(11, x) ^ rotr(25, x); }
  function gamma0(x) { return rotr(7, x) ^ rotr(18, x) ^ (x >>> 3); }
  function gamma1(x) { return rotr(17, x) ^ rotr(19, x) ^ (x >>> 10); }

  const K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ];

  let bytes;
  if (typeof data === "string") {
    bytes = [];
    for (let i = 0; i < data.length; i++) {
      const code = data.charCodeAt(i);
      if (code < 128) {
        bytes.push(code);
      } else if (code < 2048) {
        bytes.push(192 | (code >> 6), 128 | (code & 63));
      } else {
        bytes.push(224 | (code >> 12), 128 | ((code >> 6) & 63), 128 | (code & 63));
      }
    }
  } else {
    bytes = Array.from(data);
  }

  const bitLen = bytes.length * 8;
  bytes.push(0x80);
  while ((bytes.length + 8) % 64 !== 0) {
    bytes.push(0);
  }
  bytes.push(0, 0, 0, 0);
  bytes.push((bitLen >>> 24) & 0xff);
  bytes.push((bitLen >>> 16) & 0xff);
  bytes.push((bitLen >>> 8) & 0xff);
  bytes.push(bitLen & 0xff);

  let H = [
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
  ];

  const W = new Uint32Array(64);

  for (let i = 0; i < bytes.length; i += 64) {
    for (let t = 0; t < 16; t++) {
      W[t] = ((bytes[i + t * 4] << 24) |
             (bytes[i + t * 4 + 1] << 16) |
             (bytes[i + t * 4 + 2] << 8) |
             (bytes[i + t * 4 + 3])) >>> 0;
    }
    for (let t = 16; t < 64; t++) {
      W[t] = (gamma1(W[t - 2]) + W[t - 7] + gamma0(W[t - 15]) + W[t - 16]) >>> 0;
    }

    let [a, b, c, d, e, f, g, h] = H;

    for (let t = 0; t < 64; t++) {
      const T1 = (h + sigma1(e) + ch(e, f, g) + K[t] + W[t]) >>> 0;
      const T2 = (sigma0(a) + maj(a, b, c)) >>> 0;
      h = g;
      g = f;
      f = e;
      e = (d + T1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (T1 + T2) >>> 0;
    }

    H[0] = (H[0] + a) >>> 0;
    H[1] = (H[1] + b) >>> 0;
    H[2] = (H[2] + c) >>> 0;
    H[3] = (H[3] + d) >>> 0;
    H[4] = (H[4] + e) >>> 0;
    H[5] = (H[5] + f) >>> 0;
    H[6] = (H[6] + g) >>> 0;
    H[7] = (H[7] + h) >>> 0;
  }

  const out = [];
  for (let i = 0; i < 8; i++) {
    for (let j = 3; j >= 0; j--) {
      out.push((H[i] >>> (j * 8)) & 0xff);
    }
  }
  return out;
}

function hmacSha256Hex(keyStr, msgStr) {
  let keyBytes = [];
  for (let i = 0; i < keyStr.length; i++) keyBytes.push(keyStr.charCodeAt(i) & 0xff);
  if (keyBytes.length > 64) {
    keyBytes = sha256Bytes(keyBytes);
  }
  while (keyBytes.length < 64) keyBytes.push(0);

  const oPad = keyBytes.map(b => b ^ 0x5c);
  const iPad = keyBytes.map(b => b ^ 0x36);

  let msgBytes = [];
  for (let i = 0; i < msgStr.length; i++) msgBytes.push(msgStr.charCodeAt(i) & 0xff);

  const inner = sha256Bytes(iPad.concat(msgBytes));
  const outer = sha256Bytes(oPad.concat(inner));

  return outer.map(b => b.toString(16).padStart(2, "0")).join("");
}

class SecurityEngine {
  solveChallenge(nonceHex, timestamp, clientId, preferredSlot) {
    const payload = `${nonceHex}:${timestamp}`;
    const signature = hmacSha256Hex("controller-cyber-physical-key-2026", payload);
    return {
      type: "AUTH_RESPONSE",
      nonce: nonceHex,
      timestamp: parseFloat(timestamp),
      signature: signature,
      client_id: clientId || ("node_" + Math.random().toString(36).substring(2, 10)),
      preferred_slot: preferredSlot || 1
    };
  }
}

class GamepadClient {
  constructor() {
    this.haptics = new HapticAudioEngine();
    this.security = new SecurityEngine();
    this.ws = null;
    this.connected = false;
    this.playerSlot = parseInt(localStorage.getItem("controller_preferred_slot") || "1", 10);
    this.isRotated = false;
    this.seq = 0;

    let storedClientId = localStorage.getItem("controller_client_id");
    if (!storedClientId) {
      storedClientId = "node_" + Math.random().toString(36).substring(2, 10);
      localStorage.setItem("controller_client_id", storedClientId);
    }
    this.clientId = storedClientId;

    // Active Layout Mode (1 = Circular Monochromatic, 2 = Tactical Figma Master)
    this.currentLayout = parseInt(localStorage.getItem("controller_active_layout") || "1", 10);
    this.layout2Scale = 1.0;

    // Layout 1 Customization Engine
    this.isCustomizingLayout1 = false;
    this.customLayout1Config = {};
    this.customStickRadius = { left: 40, right: 40 };
    this.logoHoldTimer = null;
    this.logoHoldStart = 0;
    this.logoHoldTriggered = false;
    this._activeRadiusPopupStick = null;

    // Splash Entrance & Morph Animation State
    this._isEngaging = false;
    this._isEngaged = false;
    this.autoAdvanceTimer = null;

    // Motion & Gyro
    this.gyroEnabled = true;
    this.rawAngle = 0;
    this.zeroOffset = 0;
    this.accel = { x: 0, y: 0, z: 9.8 };

    // Primary Analog State
    this.stickX = 0;
    this.stickY = 0;
    this.rightStickX = 0;
    this.rightStickY = 0;
    this.throttle = 0.0;
    this.brake = 0.0;

    // Pointer Tracking
    this.leftStickPointerId = null;
    this.leftStickActive = false;
    this.rightStickPointerId = null;
    this.rightStickActive = false;
    this.rightStickMoved = false;

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

    // Diagnostics
    this.rtt = 0;
    this._lastSendTime = 0;

    this._initDom();
    this._initControls();
    this._initCanvases();
  }

  checkOrientation() {
    const isPortrait = window.innerHeight > window.innerWidth;
    this.isRotated = isPortrait;
    if (document.body) {
      document.body.classList.toggle("forced-landscape-portrait", isPortrait);
    }
    this.updateLayoutScaling();
  }

  getGamepadPoint(clientX, clientY) {
    if (this.isRotated) {
      return {
        x: clientY,
        y: window.innerWidth - clientX
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

      // Wings & Joysticks
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

    this._loadLayout1Config();

    // Splash Screen Tap Handler (Guaranteed Responsive across Mobile & Desktop)
    if (this.dom.splashScreen) {
      const handleSplash = (e) => {
        if (e) {
          try {
            e.preventDefault();
            e.stopPropagation();
          } catch (_) {}
        }
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

    // Center Logo in Layout 1 -> Hold (>=600ms) to Customize/Save, Tap (<600ms) to Switch to Layout 2
    if (this.dom.btnSettingsLogo) {
      let holdRaf = null;

      const startHoldAnim = () => {
        if (!this.dom.logoHoldCircle) return;
        const startTime = performance.now();
        const duration = 600;
        const tick = (now) => {
          const elapsed = now - startTime;
          const progress = Math.min(1.0, elapsed / duration);
          const offset = 176 * (1.0 - progress);
          if (this.dom.logoHoldCircle) {
            this.dom.logoHoldCircle.style.strokeDashoffset = offset.toString();
          }
          if (progress < 1.0 && this.logoHoldTimer) {
            holdRaf = requestAnimationFrame(tick);
          }
        };
        holdRaf = requestAnimationFrame(tick);
      };

      const resetHoldAnim = () => {
        if (holdRaf) {
          cancelAnimationFrame(holdRaf);
          holdRaf = null;
        }
        if (this.dom.logoHoldCircle) {
          this.dom.logoHoldCircle.style.strokeDashoffset = "176";
        }
      };

      this.dom.btnSettingsLogo.addEventListener("pointerdown", (e) => {
        if (e) { e.preventDefault(); e.stopPropagation(); }
        this.logoHoldTriggered = false;
        this.logoHoldStart = performance.now();
        resetHoldAnim();
        startHoldAnim();

        clearTimeout(this.logoHoldTimer);
        this.logoHoldTimer = setTimeout(() => {
          this.logoHoldTriggered = true;
          resetHoldAnim();
          this.toggleCustomizeMode();
        }, 600);
      }, { passive: false });

      const handleLogoUp = (e) => {
        if (this.logoHoldTimer) {
          clearTimeout(this.logoHoldTimer);
          this.logoHoldTimer = null;
        }
        resetHoldAnim();

        if (this.logoHoldTriggered) {
          if (e) { e.preventDefault(); e.stopPropagation(); }
          return;
        }

        // Quick Tap (< 600ms)
        const pressDuration = performance.now() - (this.logoHoldStart || 0);
        if (pressDuration < 600) {
          if (e) { e.preventDefault(); e.stopPropagation(); }
          if (!this.isCustomizingLayout1) {
            this.switchLayout(2);
          }
        }
      };

      this.dom.btnSettingsLogo.addEventListener("pointerup", handleLogoUp);
      this.dom.btnSettingsLogo.addEventListener("pointercancel", () => {
        if (this.logoHoldTimer) {
          clearTimeout(this.logoHoldTimer);
          this.logoHoldTimer = null;
        }
        resetHoldAnim();
      });

      this.dom.btnSettingsLogo.addEventListener("click", (e) => {
        if (e) { e.preventDefault(); e.stopPropagation(); }
      });
    }

    this._initCustomizationHandlers();

    // Center Logo in Layout 2 -> Tap to switch to Layout 1
    const l2Logo = document.getElementById("l2-btn-settings-logo");
    if (l2Logo) {
      let lastL2Tap = 0;
      const handleL2Tap = (e) => {
        const now = performance.now();
        if (now - lastL2Tap < 250) return;
        lastL2Tap = now;
        if (e) { e.preventDefault(); e.stopPropagation(); }
        this.switchLayout(1);
      };
      l2Logo.addEventListener("click", handleL2Tap);
      l2Logo.addEventListener("pointerdown", handleL2Tap);
    }

    // Touchpad in Layout 2 -> Toggle Gyroscope
    const l2Touchpad = document.getElementById("l2-touchpad-gyro");
    if (l2Touchpad) {
      let lastL2Tap = 0;
      const handleL2GyroTap = (e) => {
        const now = performance.now();
        if (now - lastL2Tap < 250) return;
        lastL2Tap = now;
        if (e) { e.preventDefault(); e.stopPropagation(); }
        this.toggleGyro();
      };
      l2Touchpad.addEventListener("click", handleL2GyroTap);
      l2Touchpad.addEventListener("pointerdown", handleL2GyroTap);
    }

    // Initialize layout visibility & scale
    this.switchLayout(this.currentLayout, false);

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
  }

  switchLayout(layoutNum, triggerHaptic = true) {
    this.currentLayout = layoutNum;
    localStorage.setItem("controller_active_layout", layoutNum.toString());
    if (triggerHaptic) {
      this.haptics.triggerClick("heavy");
    }

    const layout1Frame = document.getElementById("gamepad-frame");
    const layout2Wrapper = document.getElementById("layout2-wrapper");

    if (layoutNum === 2) {
      if (layout1Frame) layout1Frame.style.display = "none";
      if (layout2Wrapper) layout2Wrapper.style.display = "flex";
      this.updateLayoutScaling();
      if (typeof requestAnimationFrame !== "undefined") {
        requestAnimationFrame(() => this.updateLayoutScaling());
      }
      setTimeout(() => this.updateLayoutScaling(), 50);
      setTimeout(() => this.updateLayoutScaling(), 150);
    } else {
      if (layout1Frame) layout1Frame.style.display = "block";
      if (layout2Wrapper) layout2Wrapper.style.display = "none";
    }

    this._refreshButtonElements();
  }

  updateLayoutScaling() {
    const l2Frame = document.getElementById("layout2-frame");
    const l2Wrapper = document.getElementById("layout2-wrapper");
    if (!l2Frame) return;

    let availW = window.innerWidth;
    let availH = window.innerHeight;

    if (this.isRotated) {
      availW = window.innerHeight;
      availH = window.innerWidth;
    }

    if (l2Wrapper && l2Wrapper.clientWidth > 50 && l2Wrapper.clientHeight > 50) {
      availW = l2Wrapper.clientWidth;
      availH = l2Wrapper.clientHeight;
    }

    const scale = Math.max(0.1, Math.min(availW / 2048, availH / 868));
    this.layout2Scale = scale || 1.0;
    l2Frame.style.transform = `scale(${scale})`;
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
    this.playerSlot = (this.playerSlot % 4) + 1;
    localStorage.setItem("controller_preferred_slot", this.playerSlot.toString());
    this.haptics.triggerClick("heavy");
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.close();
    }
  }

  toggleGyro() {
    this.gyroEnabled = !this.gyroEnabled;
    this.haptics.triggerClick("normal");

    // Layout 1 Gyro
    if (this.dom.modGyro) {
      this.dom.modGyro.classList.toggle("active", this.gyroEnabled);
    }
    if (this.dom.gyroHorizonLine) {
      this.dom.gyroHorizonLine.style.display = this.gyroEnabled ? "block" : "none";
    }

    // Layout 2 Gyro
    const l2Touchpad = document.getElementById("l2-touchpad-gyro");
    const l2Line = document.getElementById("l2-touchpad-divider-line");
    if (l2Touchpad) {
      l2Touchpad.classList.toggle("active", this.gyroEnabled);
    }
    if (l2Line) {
      l2Line.style.display = this.gyroEnabled ? "block" : "none";
    }

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
        }
      }
    } catch (_) {}
    window.scrollTo(0, 1);
  }

  async lockOrientationLandscape() {
    try {
      if (screen.orientation && screen.orientation.lock) {
        await screen.orientation.lock("landscape").catch(() => {});
      } else if (screen.lockOrientationUniversal) {
        screen.lockOrientationUniversal("landscape");
      }
    } catch (_) {}
    this.checkOrientation();
  }

  async engage() {
    if (this._isEngaging || this._isEngaged) return;
    this._isEngaging = true;

    // 1. ALWAYS force Layout 1 on launch as requested
    this.currentLayout = 1;
    localStorage.setItem("controller_active_layout", "1");
    this.switchLayout(1, false);

    // 2. Transition cleanly to Layout 1
    this._startMorphAnimation();

    // 3. Concurrently initialize fullscreen, orientation lock, audio, and sensors
    this.toggleFullscreen();
    this.lockOrientationLandscape().catch(() => {});

    if (typeof DeviceOrientationEvent !== "undefined" && typeof DeviceOrientationEvent.requestPermission === "function") {
      try {
        await DeviceOrientationEvent.requestPermission();
      } catch (_) {}
    }

    try {
      if ("wakeLock" in navigator) {
        await navigator.wakeLock.request("screen");
      }
    } catch (_) {}

    this.haptics.initAudio();
    this._attachMotionSensors();
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

  connect() {
    if (this.ws) {
      try { this.ws.close(); } catch (_) {}
    }

    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${location.host}/ws`;

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      this.connected = true;
    };

    this.ws.onmessage = async (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === "AUTH_CHALLENGE") {
          const prefSlot = parseInt(localStorage.getItem("controller_preferred_slot") || "1", 10);
          const authResponse = this.security.solveChallenge(msg.nonce, msg.timestamp, this.clientId, prefSlot);
          this.ws.send(JSON.stringify(authResponse));
        } else if (msg.type === "AUTH_SUCCESS") {
          this.connected = true;
          this.playerSlot = msg.player_slot;
          this._updatePingDisplay(1);
          this.sendInputNow(true);
        } else if (msg.type === "SLOT_REASSIGNED") {
          this.playerSlot = msg.player_slot;
          this.haptics.triggerClick("heavy");
        } else if (msg.type === "RUMBLE") {
          this.haptics.handleRumble(msg.large, msg.small);
        } else if (msg.type === "PONG") {
          this.rtt = Math.max(1, Math.round(performance.now() - msg.ts));
          this._updatePingDisplay(this.rtt);
        }
      } catch (_) {}
    };

    this.ws.onclose = () => {
      this.connected = false;
      this._updatePingDisplay(null);
      setTimeout(() => this.connect(), 1500);
    };
  }

  sendInputNow(isCritical = false) {
    if (this.isCustomizingLayout1) return;
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
  }

  _startLoop() {
    let lastPing = 0;
    const loop = () => {
      const now = performance.now();

      if (
        this.leftStickActive ||
        this.rightStickActive ||
        this.throttle > 0 ||
        this.brake > 0 ||
        this.gyroEnabled
      ) {
        this.sendInputNow();
      }

      if (now - lastPing >= 1000) {
        lastPing = now;
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify({ type: "PING", ts: now }));
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

    if (rtt === null || !this.connected) {
      this.dom.pingText.textContent = "-- ms";
    } else {
      this.dom.pingText.textContent = `${rtt} ms`;
    }
  }

  _getButtonAtPoint(clientX, clientY) {
    if (typeof document === "undefined" || !document.elementsFromPoint) return null;
    const elements = document.elementsFromPoint(clientX, clientY);
    if (!elements || elements.length === 0) return null;

    for (let i = 0; i < elements.length; i++) {
      const el = elements[i];
      if (!el || el.id === "left-stick-anchor" || el.id === "left-stick-puck" ||
          el.id === "right-stick-anchor" || el.id === "right-stick-puck" ||
          el.id === "l2-left-stick-anchor" || el.id === "l2-left-stick-puck" ||
          el.id === "l2-right-stick-anchor" || el.id === "l2-right-stick-puck" ||
          el.id === "splash-screen" || el.id === "splash-btn" ||
          el.id === "controller-app" || el.id === "gamepad-frame" ||
          el.id === "layout2-wrapper" || el.id === "layout2-frame") {
        continue;
      }
      if (el.id === "btn-settings-logo" || el.id === "mod-gyro" ||
          el.id === "l2-btn-settings-logo" || el.id === "l2-touchpad-gyro" ||
          (el.closest && (el.closest("#btn-settings-logo") || el.closest("#mod-gyro") || el.closest("#l2-btn-settings-logo") || el.closest("#l2-touchpad-gyro")))) {
        continue;
      }
      const btn = el.closest ? el.closest("[data-btn], [data-dir], [data-trigger]") : null;
      if (btn) return btn;
    }
    return null;
  }

  _setButtonState(key, isPressed) {
    if (this.isCustomizingLayout1) return;
    if (key === "LT") {
      this.brake = isPressed ? 1.0 : 0.0;
    } else if (key === "RT") {
      this.throttle = isPressed ? 1.0 : 0.0;
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
    this.buttonElements = new Map();
    document.querySelectorAll("[data-btn], [data-dir], [data-trigger]").forEach((el) => {
      const key = el.dataset.btn || el.dataset.dir || el.dataset.trigger;
      if (key) this.buttonElements.set(key, el);
    });

    this._refreshButtonElements();

    // =========================================================================
    // 1. Left Analog Stick (Layout 1 & Layout 2)
    // =========================================================================
    const leftAnchor1 = this.dom.leftStickAnchor;
    const leftPuck1 = this.dom.leftStickPuck;
    const leftAnchor2 = document.getElementById("l2-left-stick-anchor");
    const leftPuck2 = document.getElementById("l2-left-stick-puck");

    const resetLeftStick = () => {
      this.leftStickActive = false;
      this.leftStickPointerId = null;
      this.stickX = 0;
      this.stickY = 0;
      if (leftPuck1) leftPuck1.style.transform = "translate(0px, 0px)";
      if (leftPuck2) leftPuck2.style.transform = "translate(0px, 0px)";
      this.sendInputNow(true);
      setTimeout(() => this.sendInputNow(true), 8);
      setTimeout(() => this.sendInputNow(true), 24);
    };

    const bindLeftStickAnchor = (anchor) => {
      if (!anchor) return;
      anchor.addEventListener("pointerdown", (e) => {
        if (this.isCustomizingLayout1) return;
        e.preventDefault();
        e.stopPropagation();
        if (this.leftStickPointerId !== null) return;

        this.leftStickPointerId = e.pointerId;
        this.leftStickActive = true;
        this.haptics.triggerClick();
        this._updateLeftStickFromPointer(e.clientX, e.clientY);
        this.sendInputNow(true);
      }, { passive: false });
    };

    bindLeftStickAnchor(leftAnchor1);
    bindLeftStickAnchor(leftAnchor2);

    // =========================================================================
    // 2. Right Analog Stick (Layout 1 & Layout 2)
    // =========================================================================
    const rightAnchor1 = this.dom.rightStickAnchor;
    const rightPuck1 = this.dom.rightStickPuck;
    const rightAnchor2 = document.getElementById("l2-right-stick-anchor");
    const rightPuck2 = document.getElementById("l2-right-stick-puck");

    const resetRightStick = () => {
      this.rightStickActive = false;
      this.rightStickPointerId = null;
      this.rightStickX = 0;
      this.rightStickY = 0;
      if (rightPuck1) rightPuck1.style.transform = "translate(0px, 0px)";
      if (rightPuck2) rightPuck2.style.transform = "translate(0px, 0px)";
      this.sendInputNow(true);
      setTimeout(() => this.sendInputNow(true), 8);
      setTimeout(() => this.sendInputNow(true), 24);
    };

    const bindRightStickAnchor = (anchor) => {
      if (!anchor) return;
      anchor.addEventListener("pointerdown", (e) => {
        if (this.isCustomizingLayout1) return;
        e.preventDefault();
        e.stopPropagation();
        if (this.rightStickPointerId !== null) return;

        this.rightStickPointerId = e.pointerId;
        this.rightStickActive = true;
        this.rightStickMoved = false;
        this.haptics.triggerClick();
        this._updateRightStickFromPointer(e.clientX, e.clientY);
        this.sendInputNow(true);
      }, { passive: false });
    };

    bindRightStickAnchor(rightAnchor1);
    bindRightStickAnchor(rightAnchor2);

    // =========================================================================
    // 3. Multi-Touch Independent Button Engine (Drag/Glide + Full Concurrency)
    // =========================================================================
    const handleButtonPointerDown = (e) => {
      if (this.isCustomizingLayout1) return;
      if (e.pointerId === this.leftStickPointerId || e.pointerId === this.rightStickPointerId) return;

      const targetBtn = this._getButtonAtPoint(e.clientX, e.clientY);
      if (targetBtn) {
        e.preventDefault();
        const key = targetBtn.dataset.btn || targetBtn.dataset.dir || targetBtn.dataset.trigger;
        if (key) {
          this.directBtnPointers.set(e.pointerId, key);
          this._setButtonState(key, true);
          this.haptics.triggerClick(key.startsWith("DPAD") ? "dpad" : (key === "LT" || key === "RT" ? "heavy" : "normal"));
          this.sendInputNow(true);
        }
      }
    };

    const handleButtonPointerMove = (e) => {
      if (this.isCustomizingLayout1) return;
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

      // Drag / Glide over keys
      const targetBtn = this._getButtonAtPoint(e.clientX, e.clientY);
      const newKey = targetBtn ? (targetBtn.dataset.btn || targetBtn.dataset.dir || targetBtn.dataset.trigger) : null;
      const currentKey = this.directBtnPointers.get(e.pointerId) || null;

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
            this._setButtonState(newKey, true);
            this.haptics.triggerClick(newKey.startsWith("DPAD") ? "dpad" : (newKey === "LT" || newKey === "RT" ? "heavy" : "normal"));
          }
        }
        this.sendInputNow(true);
      }
    };

    const handleButtonPointerUp = (e) => {
      if (this.isCustomizingLayout1) return;
      if (e.pointerId === this.leftStickPointerId) {
        resetLeftStick();
        return;
      }
      if (e.pointerId === this.rightStickPointerId) {
        if (!this.rightStickMoved) {
          this.buttons.RS = true;
          this.haptics.triggerClick("heavy");
          this.sendInputNow(true);
          setTimeout(() => {
            this.buttons.RS = false;
            this.sendInputNow(true);
          }, 80);
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

    window.addEventListener("pointerdown", handleButtonPointerDown, { passive: false });
    window.addEventListener("pointermove", handleButtonPointerMove, { passive: false });
    window.addEventListener("pointerup", handleButtonPointerUp);
    window.addEventListener("pointercancel", handleButtonPointerUp);

    // Multi-touch safety guard: if all fingers leave the screen, joysticks release instantly
    window.addEventListener("touchend", (e) => {
      if (e.touches.length === 0) {
        if (this.leftStickActive || this.stickX !== 0 || this.stickY !== 0) resetLeftStick();
        if (this.rightStickActive || this.rightStickX !== 0 || this.rightStickY !== 0) resetRightStick();
      }
    }, { passive: true });

    window.addEventListener("touchcancel", (e) => {
      if (e.touches.length === 0) {
        if (this.leftStickActive || this.stickX !== 0 || this.stickY !== 0) resetLeftStick();
        if (this.rightStickActive || this.rightStickX !== 0 || this.rightStickY !== 0) resetRightStick();
      }
    }, { passive: true });

    // Window blur reset
    window.addEventListener("blur", () => {
      for (const k in this.buttons) this.buttons[k] = false;
      this.throttle = 0.0;
      this.brake = 0.0;
      resetLeftStick();
      resetRightStick();
      this.directBtnPointers.clear();
      document.querySelectorAll(".active").forEach(el => el.classList.remove("active"));
      this.sendInputNow(true);
    });
  }

  _updateLeftStickFromPointer(clientX, clientY, customBase, customPuck) {
    if (this.isCustomizingLayout1) return;
    const isL2 = this.currentLayout === 2;
    const baseEl = customBase || (isL2 ? document.getElementById("l2-left-stick-anchor") : this.dom.leftStickAnchor);
    const puckEl = customPuck || (isL2 ? document.getElementById("l2-left-stick-puck") : this.dom.leftStickPuck);

    const pt = this.getGamepadPoint(clientX, clientY);
    const center = this.getGamepadCenter(baseEl);
    const dx = pt.x - center.x;
    const dy = pt.y - center.y;
    const maxRadius = isL2 ? 65 : (this.customStickRadius ? (this.customStickRadius.left || 40) : 40);
    const dist = Math.hypot(dx, dy);

    let visualDx = dx;
    let visualDy = dy;
    if (dist > maxRadius) {
      visualDx = (dx / dist) * maxRadius;
      visualDy = (dy / dist) * maxRadius;
    }
    const scale = isL2 ? (this.layout2Scale || 1.0) : 1.0;
    const localDx = visualDx / scale;
    const localDy = visualDy / scale;
    if (puckEl) {
      puckEl.style.transform = `translate(${localDx}px, ${localDy}px)`;
    }

    const deadzone = 0.08;
    const normDist = Math.min(1.0, dist / maxRadius);

    if (normDist < deadzone) {
      this.stickX = 0;
      this.stickY = 0;
    } else {
      const linearScale = (normDist - deadzone) / (1.0 - deadzone);
      const cartY = -dy;
      const cartX = dx;
      const angleRad = Math.atan2(cartY, cartX);
      const angleDeg = ((angleRad * 180 / Math.PI) + 360) % 360;

      // Cardinal Snapping for Menus (+/- 18 degrees around 90, 270, 0/360, 180)
      const snapThreshold = 18;
      let snapX = null;
      let snapY = null;

      if (Math.abs(angleDeg - 90) < snapThreshold) {
        snapX = 0;
        snapY = Math.round(linearScale * 32767);
      } else if (Math.abs(angleDeg - 270) < snapThreshold) {
        snapX = 0;
        snapY = -Math.round(linearScale * 32767);
      } else if (angleDeg < snapThreshold || angleDeg > (360 - snapThreshold)) {
        snapX = Math.round(linearScale * 32767);
        snapY = 0;
      } else if (Math.abs(angleDeg - 180) < snapThreshold) {
        snapX = -Math.round(linearScale * 32767);
        snapY = 0;
      }

      if (snapX !== null && snapY !== null) {
        this.stickX = snapX;
        this.stickY = snapY;
      } else {
        this.stickX = Math.round(Math.cos(angleRad) * linearScale * 32767);
        this.stickY = Math.round(Math.sin(angleRad) * linearScale * 32767);
      }
    }
    this.sendInputNow();
  }

  _updateRightStickFromPointer(clientX, clientY, customBase, customPuck) {
    if (this.isCustomizingLayout1) return;
    const isL2 = this.currentLayout === 2;
    const baseEl = customBase || (isL2 ? document.getElementById("l2-right-stick-anchor") : this.dom.rightStickAnchor);
    const puckEl = customPuck || (isL2 ? document.getElementById("l2-right-stick-puck") : this.dom.rightStickPuck);

    const pt = this.getGamepadPoint(clientX, clientY);
    const center = this.getGamepadCenter(baseEl);
    const dx = pt.x - center.x;
    const dy = pt.y - center.y;
    const maxRadius = isL2 ? 55 : (this.customStickRadius ? (this.customStickRadius.right || 40) : 40);
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
    const scale = isL2 ? (this.layout2Scale || 1.0) : 1.0;
    const localDx = visualDx / scale;
    const localDy = visualDy / scale;
    if (puckEl) {
      puckEl.style.transform = `translate(${localDx}px, ${localDy}px)`;
    }

    const deadzone = 0.06;
    const normDist = Math.min(1.0, dist / maxRadius);

    if (normDist < deadzone) {
      this.rightStickX = 0;
      this.rightStickY = 0;
    } else {
      const linearScale = (normDist - deadzone) / (1.0 - deadzone);
      const cartY = -dy;
      const cartX = dx;
      const angleRad = Math.atan2(cartY, cartX);
      const angleDeg = ((angleRad * 180 / Math.PI) + 360) % 360;

      const snapThreshold = 18;
      let snapX = null;
      let snapY = null;

      if (Math.abs(angleDeg - 90) < snapThreshold) {
        snapX = 0;
        snapY = Math.round(linearScale * 32767);
      } else if (Math.abs(angleDeg - 270) < snapThreshold) {
        snapX = 0;
        snapY = -Math.round(linearScale * 32767);
      } else if (angleDeg < snapThreshold || angleDeg > (360 - snapThreshold)) {
        snapX = Math.round(linearScale * 32767);
        snapY = 0;
      } else if (Math.abs(angleDeg - 180) < snapThreshold) {
        snapX = -Math.round(linearScale * 32767);
        snapY = 0;
      }

      if (snapX !== null && snapY !== null) {
        this.rightStickX = snapX;
        this.rightStickY = snapY;
      } else {
        this.rightStickX = Math.round(Math.cos(angleRad) * linearScale * 32767);
        this.rightStickY = Math.round(Math.sin(angleRad) * linearScale * 32767);
      }
    }
    this.sendInputNow();
  }

  // =========================================================================
  // Canvas Renderers: Gyro Horizon & Visualizer
  // =========================================================================
  _initCanvases() {
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
    const roll = this.rawAngle || 0;

    if (this.dom.gyroHorizonLine) {
      if (!this.gyroEnabled) {
        this.dom.gyroHorizonLine.style.display = "none";
      } else {
        this.dom.gyroHorizonLine.style.display = "block";
        this.dom.gyroHorizonLine.style.transform = `rotate(${roll}deg)`;
      }
    }

    const l2Line = document.getElementById("l2-touchpad-divider-line");
    if (l2Line) {
      if (!this.gyroEnabled) {
        l2Line.style.display = "none";
      } else {
        l2Line.style.display = "block";
        l2Line.style.transform = `rotate(${roll}deg)`;
      }
    }

    const canvas = this.dom.gyroCanvas;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const w = canvas.width;
    const h = canvas.height;
    if (w <= 0 || h <= 0) return;

    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, h / 2);
    ctx.lineTo(w, h / 2);
    ctx.stroke();
  }

  _renderVisualizerCanvas() {
    const canvas = this.dom.visualizerCanvas;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }

  // =========================================================================
  // LAYOUT 1 CUSTOMIZATION ENGINE (DRAG, RESIZE, JOYSTICK RADIUS & STORAGE)
  // =========================================================================
  toggleCustomizeMode() {
    this.isCustomizingLayout1 = !this.isCustomizingLayout1;
    this.haptics.triggerClick("heavy");

    const frame = this.dom.frame || document.getElementById("gamepad-frame");
    if (frame) {
      frame.classList.toggle("customizing-mode", this.isCustomizingLayout1);
    }

    if (this.isCustomizingLayout1) {
      this.haptics.initAudio();
      this.closeRadiusPopup();

      // Completely disable and neutralize all gaming input state
      this.leftStickActive = false;
      this.leftStickPointerId = null;
      this.stickX = 0;
      this.stickY = 0;
      this.rightStickActive = false;
      this.rightStickPointerId = null;
      this.rightStickX = 0;
      this.rightStickY = 0;
      this.throttle = 0.0;
      this.brake = 0.0;
      this.directBtnPointers.clear();
      for (const k in this.buttons) {
        this.buttons[k] = false;
      }
      if (this.buttonElements) {
        document.querySelectorAll("[data-btn], [data-dir], [data-trigger]").forEach(el => el.classList.remove("active"));
      }
      if (this.dom.leftStickPuck) this.dom.leftStickPuck.style.transform = "translate(0px, 0px)";
      if (this.dom.rightStickPuck) this.dom.rightStickPuck.style.transform = "translate(0px, 0px)";

      // Send neutral frame to game server
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
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
    } else {
      this.closeRadiusPopup();
      this._saveLayout1Config();
    }
  }

  _initCustomizationHandlers() {
    const frame = this.dom.frame || document.getElementById("gamepad-frame");
    if (!frame) return;

    let activeDrag = null; // { id, el, startX, startY, origDx, origDy, origScale, isResize, moved }

    const getCustomElement = (target) => {
      if (!target || !target.closest) return null;
      return target.closest("[data-custom-id]");
    };

    const getResizeHandle = (target) => {
      if (!target || !target.closest) return null;
      return target.closest(".l1-resize-handle");
    };

    frame.addEventListener("pointerdown", (e) => {
      if (!this.isCustomizingLayout1) return;
      if (e.target.closest(".l1-custom-hud") || e.target.closest(".l1-radius-popup") || e.target.closest("#btn-settings-logo")) {
        return;
      }

      const resizeHandle = getResizeHandle(e.target);
      if (resizeHandle) {
        e.preventDefault();
        e.stopPropagation();
        const targetId = resizeHandle.dataset.target;
        const targetEl = document.querySelector(`[data-custom-id="${targetId}"]`);
        if (!targetEl) return;

        const cfg = this._getElemConfig(targetId);
        const pt = this.getGamepadPoint(e.clientX, e.clientY);
        activeDrag = {
          id: targetId,
          el: targetEl,
          startX: pt.x,
          startY: pt.y,
          origDx: cfg.dx,
          origDy: cfg.dy,
          origScale: cfg.s,
          isResize: true,
          moved: false
        };
        return;
      }

      const customEl = getCustomElement(e.target);
      if (customEl) {
        e.preventDefault();
        e.stopPropagation();
        const targetId = customEl.dataset.customId;
        const cfg = this._getElemConfig(targetId);
        const pt = this.getGamepadPoint(e.clientX, e.clientY);

        activeDrag = {
          id: targetId,
          el: customEl,
          startX: pt.x,
          startY: pt.y,
          origDx: cfg.dx,
          origDy: cfg.dy,
          origScale: cfg.s,
          isResize: false,
          moved: false
        };
      }
    }, { passive: false });

    window.addEventListener("pointermove", (e) => {
      if (!this.isCustomizingLayout1 || !activeDrag) return;
      e.preventDefault();

      const pt = this.getGamepadPoint(e.clientX, e.clientY);
      const dx = pt.x - activeDrag.startX;
      const dy = pt.y - activeDrag.startY;
      if (Math.hypot(dx, dy) > 6) {
        activeDrag.moved = true;
      }

      if (activeDrag.isResize) {
        const delta = (dx + dy) / 2;
        const scaleChange = delta / 110;
        const newScale = Math.max(0.60, Math.min(1.85, activeDrag.origScale + scaleChange));
        this._setElemScale(activeDrag.id, newScale);
      } else {
        const newDx = activeDrag.origDx + dx;
        const newDy = activeDrag.origDy + dy;
        this._setElemTranslate(activeDrag.id, newDx, newDy);
      }
    }, { passive: false });

    window.addEventListener("pointerup", () => {
      if (!this.isCustomizingLayout1 || !activeDrag) return;

      if (!activeDrag.isResize && !activeDrag.moved) {
        if (activeDrag.id === "left-stick-anchor") {
          this.openRadiusPopup("left", activeDrag.el);
        } else if (activeDrag.id === "right-stick-anchor") {
          this.openRadiusPopup("right", activeDrag.el);
        }
      }

      activeDrag = null;
    });

    // Dedicated Tap-to-Open Slider Listeners for Joysticks
    const setupStickTap = (anchorEl, stickSide) => {
      if (!anchorEl) return;
      let downTime = 0;
      let startX = 0, startY = 0;
      anchorEl.addEventListener("pointerdown", (e) => {
        if (!this.isCustomizingLayout1) return;
        if (e.target.closest(".l1-resize-handle")) return;
        downTime = performance.now();
        startX = e.clientX;
        startY = e.clientY;
      });
      anchorEl.addEventListener("pointerup", (e) => {
        if (!this.isCustomizingLayout1 || !downTime) return;
        if (e.target.closest(".l1-resize-handle")) return;
        const dist = Math.hypot(e.clientX - startX, e.clientY - startY);
        const elapsed = performance.now() - downTime;
        downTime = 0;
        if (dist < 12 && elapsed < 450) {
          this.openRadiusPopup(stickSide, anchorEl);
        }
      });
    };
    setupStickTap(this.dom.leftStickAnchor, "left");
    setupStickTap(this.dom.rightStickAnchor, "right");

    // Joystick Radius Slider Event
    const slider = document.getElementById("l1-radius-slider");
    if (slider) {
      const handleSliderChange = (e) => {
        const val = parseInt(e.target.value, 10);
        if (this._activeRadiusPopupStick) {
          this.customStickRadius[this._activeRadiusPopupStick] = val;
          const valLabel = document.getElementById("l1-radius-val");
          if (valLabel) valLabel.textContent = `${val}px`;

          const previewRing = document.getElementById(`${this._activeRadiusPopupStick}-stick-radius-preview`);
          if (previewRing) {
            previewRing.style.width = `${val * 2}px`;
            previewRing.style.height = `${val * 2}px`;
          }
          this.haptics.triggerClick("dpad");
        }
      };
      slider.addEventListener("input", handleSliderChange);
      slider.addEventListener("change", handleSliderChange);
    }

    // Close Button on Radius Slider Popup
    const closeBtn = document.getElementById("l1-radius-close-btn");
    if (closeBtn) {
      closeBtn.addEventListener("click", (e) => {
        if (e) { e.preventDefault(); e.stopPropagation(); }
        this.closeRadiusPopup();
      });
    }

    // Reset Defaults Button
    const resetBtn = document.getElementById("l1-reset-btn");
    if (resetBtn) {
      resetBtn.addEventListener("click", (e) => {
        if (e) { e.preventDefault(); e.stopPropagation(); }
        this.resetLayout1Config();
      });
    }
  }

  openRadiusPopup(stick, anchorEl) {
    this._activeRadiusPopupStick = stick;
    const popup = document.getElementById("l1-radius-popup");
    const title = document.getElementById("l1-radius-title");
    const valLabel = document.getElementById("l1-radius-val");
    const slider = document.getElementById("l1-radius-slider");
    if (!popup || !anchorEl) return;

    const currentR = this.customStickRadius[stick] || 40;
    if (title) title.textContent = `${stick.toUpperCase()} STICK DRAG RADIUS`;
    if (valLabel) valLabel.textContent = `${currentR}px`;
    if (slider) {
      slider.min = "20";
      slider.max = "85";
      slider.value = currentR;
    }

    const frame = this.dom.frame || document.getElementById("gamepad-frame");
    let localX = anchorEl.offsetLeft;
    let localY = anchorEl.offsetTop;
    let parent = anchorEl.offsetParent;
    while (parent && parent !== frame) {
      localX += parent.offsetLeft;
      localY += parent.offsetTop;
      parent = parent.offsetParent;
    }

    const frameW = frame.clientWidth || 907;
    const frameH = frame.clientHeight || 400;

    let top = localY - 95;
    if (top < 15) top = localY + (anchorEl.clientHeight || 140) + 12;
    top = Math.max(15, Math.min(frameH - 120, top));

    let left = localX - 25;
    if (left + 235 > frameW) left = frameW - 245;
    left = Math.max(15, left);

    popup.style.top = `${top}px`;
    popup.style.left = `${left}px`;
    popup.classList.add("active");
    this.haptics.triggerClick("normal");
  }

  closeRadiusPopup() {
    this._activeRadiusPopupStick = null;
    const popup = document.getElementById("l1-radius-popup");
    if (popup) popup.classList.remove("active");
  }

  _ensureLayout1Config() {
    if (!this.customLayout1Config) {
      this.customLayout1Config = {};
    }
  }

  _getElemConfig(id) {
    this._ensureLayout1Config();
    if (!this.customLayout1Config[id]) {
      this.customLayout1Config[id] = { dx: 0, dy: 0, s: 1.0 };
    }
    return this.customLayout1Config[id];
  }

  _applyElemTransform(id) {
    const el = document.querySelector(`[data-custom-id="${id}"]`);
    if (!el) return;
    const cfg = this._getElemConfig(id);
    el.style.setProperty("--l1-dx", `${cfg.dx}px`);
    el.style.setProperty("--l1-dy", `${cfg.dy}px`);
    el.style.setProperty("--l1-s", `${cfg.s}`);
    el.style.transform = `translate(var(--l1-dx, ${cfg.dx}px), var(--l1-dy, ${cfg.dy}px)) scale(calc(var(--l1-s, ${cfg.s}) * var(--l1-press, 1)))`;
  }

  _setElemTranslate(id, dx, dy) {
    const cfg = this._getElemConfig(id);
    cfg.dx = Math.round(dx);
    cfg.dy = Math.round(dy);
    this._applyElemTransform(id);
  }

  _setElemScale(id, s) {
    const cfg = this._getElemConfig(id);
    cfg.s = parseFloat(s.toFixed(2));
    this._applyElemTransform(id);
  }

  _saveLayout1Config() {
    try {
      const data = {
        elements: this.customLayout1Config || {},
        stickRadius: this.customStickRadius || { left: 40, right: 40 }
      };
      localStorage.setItem("controller_layout1_custom_config", JSON.stringify(data));
      this.haptics.triggerClick("heavy");
    } catch (_) {}
  }

  _loadLayout1Config() {
    try {
      const raw = localStorage.getItem("controller_layout1_custom_config");
      if (raw) {
        const data = JSON.parse(raw);
        if (data.elements) {
          this.customLayout1Config = data.elements;
          Object.keys(this.customLayout1Config).forEach((id) => {
            this._applyElemTransform(id);
          });
        }
        if (data.stickRadius) {
          this.customStickRadius = {
            left: data.stickRadius.left || 40,
            right: data.stickRadius.right || 40
          };
          const leftRing = document.getElementById("left-stick-radius-preview");
          if (leftRing) {
            leftRing.style.width = `${this.customStickRadius.left * 2}px`;
            leftRing.style.height = `${this.customStickRadius.left * 2}px`;
          }
          const rightRing = document.getElementById("right-stick-radius-preview");
          if (rightRing) {
            rightRing.style.width = `${this.customStickRadius.right * 2}px`;
            rightRing.style.height = `${this.customStickRadius.right * 2}px`;
          }
        }
      }
    } catch (_) {}
  }

  resetLayout1Config() {
    try {
      localStorage.removeItem("controller_layout1_custom_config");
      this.customLayout1Config = {};
      this.customStickRadius = { left: 40, right: 40 };

      document.querySelectorAll("[data-custom-id]").forEach((el) => {
        el.style.transform = "";
        el.style.removeProperty("--l1-dx");
        el.style.removeProperty("--l1-dy");
        el.style.removeProperty("--l1-s");
      });

      const leftRing = document.getElementById("left-stick-radius-preview");
      if (leftRing) {
        leftRing.style.width = "80px";
        leftRing.style.height = "80px";
      }
      const rightRing = document.getElementById("right-stick-radius-preview");
      if (rightRing) {
        rightRing.style.width = "80px";
        rightRing.style.height = "80px";
      }

      this.closeRadiusPopup();
      this.haptics.triggerClick("heavy");
    } catch (_) {}
  }
}

// Instantiate on load
window.addEventListener("DOMContentLoaded", () => {
  window.gamepadClient = new GamepadClient();
  window.addEventListener("resize", () => {
    if (window.gamepadClient) window.gamepadClient.checkOrientation();
  });
  window.addEventListener("orientationchange", () => {
    if (window.gamepadClient) window.gamepadClient.checkOrientation();
  });
  window.addEventListener("pointerdown", () => {
    if (window.gamepadClient && window.gamepadClient._isEngaged) {
      window.gamepadClient.toggleFullscreen();
      window.gamepadClient.lockOrientationLandscape().catch(() => {});
    }
  }, { passive: true });
});
