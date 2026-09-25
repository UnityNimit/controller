/**
 * Project Controller - Dedicated Gyroscope & Motion Sensor Engine
 * Handles DeviceOrientation, DeviceMotion, orientation changes, zero-calibration,
 * and real-time horizon visual rendering.
 */

class GamepadGyroSensor {
  constructor(options = {}) {
    const stored = (typeof localStorage !== "undefined") ? localStorage.getItem("controller_gyro_enabled") : null;
    this.enabled = (stored !== null) ? (stored === "true") : (options.enabled !== undefined ? !!options.enabled : false);
    this.rawAngle = 0;
    this.zeroOffset = 0;
    this.accel = { x: 0, y: 0, z: 9.8 };
    this.onStateChange = options.onStateChange || null;

    this._attached = false;
    this._handleOrientation = this._handleOrientation.bind(this);
    this._handleMotion = this._handleMotion.bind(this);
  }

  async requestPermission() {
    if (typeof DeviceOrientationEvent !== "undefined" && typeof DeviceOrientationEvent.requestPermission === "function") {
      try {
        const response = await DeviceOrientationEvent.requestPermission();
        return response === "granted";
      } catch (_) {
        return false;
      }
    }
    return true;
  }

  attach() {
    if (this._attached) return;
    this._attached = true;
    window.addEventListener("deviceorientation", this._handleOrientation, { passive: true });
    window.addEventListener("devicemotion", this._handleMotion, { passive: true });
  }

  detach() {
    if (!this._attached) return;
    this._attached = false;
    window.removeEventListener("deviceorientation", this._handleOrientation);
    window.removeEventListener("devicemotion", this._handleMotion);
  }

  _handleOrientation(e) {
    let screenAngle = 0;
    if (screen.orientation && typeof screen.orientation.angle === "number") {
      screenAngle = screen.orientation.angle;
    } else if (typeof window.orientation === "number") {
      screenAngle = window.orientation;
    }

    const beta = (typeof e.beta === "number" && !isNaN(e.beta)) ? e.beta : 0;
    const gamma = (typeof e.gamma === "number" && !isNaN(e.gamma)) ? e.gamma : 0;

    let angle = 0;
    if (screenAngle === 90) {
      angle = -beta;
    } else if (screenAngle === 270 || screenAngle === -90) {
      angle = beta;
    } else {
      angle = gamma;
    }
    this.rawAngle = !isNaN(angle) ? angle : 0;
  }

  _handleMotion(e) {
    if (e.accelerationIncludingGravity) {
      this.accel = {
        x: e.accelerationIncludingGravity.x || 0,
        y: e.accelerationIncludingGravity.y || 0,
        z: e.accelerationIncludingGravity.z || 9.8
      };
    }
  }

  toggle(forceState) {
    if (typeof forceState === "boolean") {
      this.enabled = forceState;
    } else {
      this.enabled = !this.enabled;
    }
    if (typeof localStorage !== "undefined") {
      localStorage.setItem("controller_gyro_enabled", this.enabled ? "true" : "false");
    }
    this.syncDomState();
    if (this.onStateChange) {
      this.onStateChange(this.enabled);
    }
    return this.enabled;
  }

  calibrateZero() {
    this.zeroOffset = this.rawAngle;
  }

  resetCalibration() {
    this.zeroOffset = 0;
  }

  getEffectiveAngle(isManualStickActive = false) {
    if (!this.enabled || isManualStickActive) {
      return 0.0;
    }
    const eff = this.rawAngle - this.zeroOffset;
    return (!isNaN(eff) && eff !== null) ? eff : 0.0;
  }

  syncDomState() {
    const modGyro = document.getElementById("mod-gyro");
    const horizonLine = document.getElementById("gyro-horizon-line");
    if (modGyro) {
      modGyro.classList.toggle("active", this.enabled);
    }
    if (horizonLine) {
      horizonLine.style.display = this.enabled ? "block" : "none";
    }
  }

  renderHorizonLines(horizonLine1) {
    const line1 = horizonLine1 || document.getElementById("gyro-horizon-line");
    if (!line1) return;

    if (!this.enabled) {
      if (line1.style.display !== "none") {
        line1.style.display = "none";
      }
      return;
    }

    if (line1.style.display !== "block") {
      line1.style.display = "block";
    }

    // Auto-heal mod-gyro active state if touched or cleared
    const modGyro = document.getElementById("mod-gyro");
    if (modGyro && !modGyro.classList.contains("active")) {
      modGyro.classList.add("active");
    }

    const effectiveAngle = this.getEffectiveAngle();
    const roll = (!isNaN(effectiveAngle) && effectiveAngle !== null) ? effectiveAngle : 0;
    line1.style.transform = `rotate(${roll}deg)`;
  }
}

if (typeof window !== "undefined") {
  window.GamepadGyroSensor = GamepadGyroSensor;
}
if (typeof module !== "undefined" && module.exports) {
  module.exports = { GamepadGyroSensor };
}
