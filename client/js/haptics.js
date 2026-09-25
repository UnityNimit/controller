/**
 * Project Controller - Dedicated Vibration & Haptics Engine
 * Standalone module for managing mobile device physical vibration (navigator.vibrate),
 * Web Audio sub-bass acoustic resonance, and iOS Taptic Engine feedback.
 */

class HapticAudioEngine {
  constructor() {
    this.ctx = null;
    this.canVibrate = typeof navigator !== "undefined" && typeof navigator.vibrate === "function";
    this.currentLarge = 0;
    this.currentSmall = 0;
    this.isContinuous = false;
    this.timedStopTimer = null;
    this.rumbleLoopTimer = null;
    this.lastRumbleTime = 0;
    this._lastHardwareVibrateTime = 0;
    this.hapticGain = null;
    this.oscLarge = null;
    this.oscSmall = null;
    this.iosSwitch = null;
    this.onRumbleChange = null; // Optional callback for diagnostics & test benches
    // Default vibration strictly OFF on startup (localStorage.getItem("controller_vibration_enabled") === "true" when toggled on)
    this.vibrationEnabled = false;

    // Global once-listener to unlock Web Audio on first user gesture without rogue vibrations
    if (typeof window !== "undefined") {
      const unlockAudio = () => {
        this.initAudio();
      };
      window.addEventListener("pointerdown", unlockAudio, { passive: true, once: true });
      window.addEventListener("touchstart", unlockAudio, { passive: true, once: true });
      window.addEventListener("click", unlockAudio, { passive: true, once: true });
    }
  }

  setVibrationEnabled(enabled) {
    this.vibrationEnabled = !!enabled;
    if (typeof localStorage !== "undefined") {
      localStorage.setItem("controller_vibration_enabled", this.vibrationEnabled ? "true" : "false");
    }
    if (!this.vibrationEnabled) {
      this.stopAllRumble();
    } else {
      this.triggerClick("heavy");
    }
    return this.vibrationEnabled;
  }

  toggleVibration() {
    return this.setVibrationEnabled(!this.vibrationEnabled);
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
    this._ensureIOSSwitch();
  }

  _ensureIOSSwitch() {
    if (!this.iosSwitch && typeof document !== "undefined" && document.body) {
      let sw = document.getElementById("ios-haptic-switch");
      if (!sw) {
        try {
          sw = document.createElement("input");
          sw.type = "checkbox";
          sw.setAttribute("switch", "");
          sw.id = "ios-haptic-switch";
          sw.tabIndex = -1;
          sw.setAttribute("aria-hidden", "true");
          sw.style.cssText = "position:fixed;top:-500px;left:-500px;opacity:0.0001;pointer-events:none;z-index:-9999;";
          document.body.appendChild(sw);
        } catch (_) {}
      }
      this.iosSwitch = sw;
    }
  }

  triggerClick(intensity = "normal") {
    if (!this.vibrationEnabled) return;
    this._triggerIOSTapticSwitch();

    // Do NOT interrupt or abort active continuous rumble with a micro-click
    const isRumbling = (this.currentLarge > 0 || this.currentSmall > 0);
    if (!isRumbling && this.canVibrate) {
      try {
        if (intensity === "heavy") {
          navigator.vibrate(28);
        } else if (intensity === "dpad") {
          navigator.vibrate(18);
        } else {
          navigator.vibrate(12);
        }
      } catch (_) {}
    }

    if (!this.ctx) this.initAudio();
    if (!this.ctx) return;
    try {
      const now = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = "sine";
      const freq = intensity === "heavy" ? 110 : intensity === "dpad" ? 150 : 180;
      osc.frequency.setValueAtTime(freq, now);
      osc.frequency.exponentialRampToValueAtTime(35, now + 0.038);

      const vol = intensity === "heavy" ? 0.35 : 0.22;
      gain.gain.setValueAtTime(vol, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.038);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start(now);
      osc.stop(now + 0.040);
    } catch (_) {}
  }

  timedRumble(largeMotor = 0, smallMotor = 0, durationMs = 1000) {
    if (!this.vibrationEnabled) {
      this.stopAllRumble();
      return;
    }
    const rawL = Number(largeMotor) || 0;
    const rawS = Number(smallMotor) || 0;
    const large = rawL > 255 ? Math.round(rawL / 256) : Math.round(rawL);
    const small = rawS > 255 ? Math.round(rawS / 256) : Math.round(rawS);
    const clampedLarge = Math.max(0, Math.min(255, large));
    const clampedSmall = Math.max(0, Math.min(255, small));
    const dur = Math.max(0, Math.round(Number(durationMs) || 0));

    if (dur <= 0 || (clampedLarge === 0 && clampedSmall === 0)) {
      this.stopAllRumble();
      return;
    }

    if (this.timedStopTimer) {
      clearTimeout(this.timedStopTimer);
      this.timedStopTimer = null;
    }
    if (this.rumbleLoopTimer) {
      clearInterval(this.rumbleLoopTimer);
      this.rumbleLoopTimer = null;
    }

    this.currentLarge = clampedLarge;
    this.currentSmall = clampedSmall;
    this.isContinuous = false;
    const now = performance.now();
    this.lastRumbleTime = now;
    this._lastHardwareVibrateTime = now;

    if (typeof this.onRumbleChange === "function") {
      try {
        this.onRumbleChange(clampedLarge, clampedSmall, true);
      } catch (_) {}
    }

    // Direct hardware vibration for the EXACT requested millisecond duration
    if (this.canVibrate) {
      try {
        navigator.vibrate(dur);
      } catch (_) {}
    }

    this._triggerIOSTapticSwitch();
    this._triggerAcousticHaptics(clampedLarge, clampedSmall);
    this._triggerVisualHaptics(clampedLarge, clampedSmall);

    this.timedStopTimer = setTimeout(() => {
      this.stopAllRumble();
    }, dur);
  }

  handleRumble(largeMotor = 0, smallMotor = 0) {
    if (!this.vibrationEnabled) {
      this.stopAllRumble();
      return;
    }
    const rawL = Number(largeMotor) || 0;
    const rawS = Number(smallMotor) || 0;
    const large = rawL > 255 ? Math.round(rawL / 256) : Math.round(rawL);
    const small = rawS > 255 ? Math.round(rawS / 256) : Math.round(rawS);
    const clampedLarge = Math.max(0, Math.min(255, large));
    const clampedSmall = Math.max(0, Math.min(255, small));

    const wasActive = (this.currentLarge > 0 || this.currentSmall > 0);
    const isNowActive = (clampedLarge > 0 || clampedSmall > 0);

    if (this.timedStopTimer) {
      clearTimeout(this.timedStopTimer);
      this.timedStopTimer = null;
    }

    this.currentLarge = clampedLarge;
    this.currentSmall = clampedSmall;
    this.isContinuous = isNowActive;
    const now = performance.now();
    this.lastRumbleTime = now;

    if (typeof this.onRumbleChange === "function") {
      try {
        this.onRumbleChange(clampedLarge, clampedSmall, isNowActive);
      } catch (_) {}
    }

    // Motor OFF command received from game engine / XInput: STOP IMMEDIATELY (0ms)
    if (!isNowActive) {
      this._stopAllRumble();
      return;
    }

    // Motor ON: Responsive rolling 1000ms lease.
    // If motor was OFF, start immediately.
    // If running, re-arm when lease is nearing expiration (>700ms elapsed),
    // eliminating restart stutter while guaranteeing immediate zero-latency stop on (0, 0).
    if (!wasActive || (now - (this._lastHardwareVibrateTime || 0)) > 700) {
      this._startHardwareVibrate(clampedLarge, clampedSmall, 1000);
      this._lastHardwareVibrateTime = now;
      if (!wasActive) {
        this._triggerIOSTapticSwitch();
      }
    }

    this._triggerAcousticHaptics(clampedLarge, clampedSmall);
    this._triggerVisualHaptics(clampedLarge, clampedSmall);

    // Keep active vibration armed continuously for infinite/sustained duration
    this._ensureRumbleLoop();
  }

  _startHardwareVibrate(large, small, durationMs = 1000) {
    if (!this.canVibrate) return;
    try {
      const ms = Math.max(1, Math.round(durationMs));
      navigator.vibrate(ms);
    } catch (_) {}
  }

  _ensureRumbleLoop() {
    if (this.rumbleLoopTimer) return;
    // Seamless keep-alive loop: re-arms hardware vibration every 200ms while active
    this.rumbleLoopTimer = setInterval(() => {
      const now = performance.now();
      if (this.currentLarge === 0 && this.currentSmall === 0) {
        this._stopAllRumble();
        return;
      }

      if (now - this._lastHardwareVibrateTime > 700) {
        this._startHardwareVibrate(this.currentLarge, this.currentSmall, 1000);
        this._lastHardwareVibrateTime = now;
      }
    }, 200);
  }

  _stopAllRumble() {
    if (this.timedStopTimer) {
      clearTimeout(this.timedStopTimer);
      this.timedStopTimer = null;
    }
    if (this.rumbleLoopTimer) {
      clearInterval(this.rumbleLoopTimer);
      this.rumbleLoopTimer = null;
    }

    const hadActivity = (this.currentLarge > 0 || this.currentSmall > 0);
    this.currentLarge = 0;
    this.currentSmall = 0;
    this.isContinuous = false;
    this._lastHardwareVibrateTime = 0;

    if (this.canVibrate) {
      try {
        navigator.vibrate(0);
      } catch (_) {}
      try {
        navigator.vibrate([]);
      } catch (_) {}
    }

    this._stopAcousticHaptics();
    this._stopVisualHaptics();

    if (hadActivity && typeof this.onRumbleChange === "function") {
      try {
        this.onRumbleChange(0, 0, false);
      } catch (_) {}
    }
  }

  stopAllRumble() {
    this._stopAllRumble();
  }

  _triggerIOSTapticSwitch() {
    this._ensureIOSSwitch();
    if (this.iosSwitch) {
      try {
        this.iosSwitch.click();
      } catch (_) {}
    }
  }

  _triggerAcousticHaptics(large, small) {
    if (!this.ctx) this.initAudio();
    if (!this.ctx) return;
    if (this.ctx.state === "suspended") {
      this.ctx.resume().catch(() => {});
    }
    try {
      const now = this.ctx.currentTime;
      if (!this.hapticGain) {
        this.hapticGain = this.ctx.createGain();
        this.hapticGain.gain.setValueAtTime(0.0001, now);
        this.hapticGain.connect(this.ctx.destination);

        // Sub-bass 48Hz sine wave (Smartphone chassis mechanical resonance)
        this.oscLarge = this.ctx.createOscillator();
        this.oscLarge.type = "sine";
        this.oscLarge.frequency.setValueAtTime(48, now);
        this.oscLarge.connect(this.hapticGain);
        this.oscLarge.start();

        // 96Hz harmonic (Direct physical acoustic kick through speaker body)
        this.oscSmall = this.ctx.createOscillator();
        this.oscSmall.type = "triangle";
        this.oscSmall.frequency.setValueAtTime(96, now);
        this.oscSmall.connect(this.hapticGain);
        this.oscSmall.start();
      }

      const normL = large / 255.0;
      const normS = small / 255.0;
      // Proportional acoustic haptic resonance (accurate to motor intensity)
      const targetGain = Math.min(0.75, Math.max(0.001, (normL * 0.45) + (normS * 0.30)));
      this.hapticGain.gain.cancelScheduledValues(now);
      this.hapticGain.gain.setTargetAtTime(targetGain, now, 0.02);
    } catch (_) {}
  }

  _stopAcousticHaptics() {
    if (this.hapticGain && this.ctx) {
      try {
        const now = this.ctx.currentTime;
        this.hapticGain.gain.cancelScheduledValues(now);
        this.hapticGain.gain.setTargetAtTime(0.0001, now, 0.025);
      } catch (_) {}
    }
  }

  _triggerVisualHaptics(large, small) {
    if (typeof document === "undefined") return;
    const isRumbling = (large > 0 || small > 0);
    const frame1 = document.getElementById("gamepad-frame");
    const frame2 = document.getElementById("settings-frame");
    if (frame1) frame1.classList.toggle("haptic-rumbling", isRumbling);
    if (frame2) frame2.classList.toggle("haptic-rumbling", isRumbling);
  }

  _stopVisualHaptics() {
    if (typeof document === "undefined") return;
    const frame1 = document.getElementById("gamepad-frame");
    const frame2 = document.getElementById("settings-frame");
    if (frame1) frame1.classList.remove("haptic-rumbling");
    if (frame2) frame2.classList.remove("haptic-rumbling");
  }

  testHapticPulse() {
    this.initAudio();
    this.timedRumble(255, 255, 300);
  }
}

// Export for browser script tag and module environments
if (typeof window !== "undefined") {
  window.HapticAudioEngine = HapticAudioEngine;
}
if (typeof module !== "undefined" && module.exports) {
  module.exports = { HapticAudioEngine };
}
