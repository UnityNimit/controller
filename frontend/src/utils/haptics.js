/**
 * Project Controller - Dynamic Haptic Actuation & Audio Shift Tone Synthesizer
 * Implements Closed-Loop Physical Feedback from Live Game Telemetry.
 */

export class HapticEngine {
  constructor() {
    this.hasVibration = typeof navigator !== 'undefined' && "vibrate" in navigator;
    this.lastSlipTime = 0;
    this.lastImpactTime = 0;
    this.lastRedlineTime = 0;
    this.lastRumbleTime = 0;
    this.audioCtx = null;
    this.analyser = null;
    this.audioInitialized = false;
    this.pulseEnergy = 0.0;
    this.enabled = true;
  }

  initAudio() {
    if (!this.audioCtx && typeof window !== 'undefined') {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) {
        this.audioCtx = new AudioContextClass();
        this.analyser = this.audioCtx.createAnalyser();
        this.analyser.fftSize = 64;
        this.analyser.smoothingTimeConstant = 0.75;
        this.analyser.connect(this.audioCtx.destination);
        this.audioInitialized = true;
      }
    }
    if (this.audioCtx && this.audioCtx.state === "suspended") {
      this.audioCtx.resume();
    }
  }

  playTactileSubBass(freq = 55, durationSec = 0.08, gainVal = 0.25) {
    if (!this.enabled) return;
    this.pulseEnergy = Math.min(1.0, this.pulseEnergy + 0.4);
    if (!this.audioCtx || this.audioCtx.state !== "running") return;
    try {
      const osc = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();

      osc.type = "triangle";
      osc.frequency.setValueAtTime(freq, this.audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(freq * 0.5, this.audioCtx.currentTime + durationSec);

      gain.gain.setValueAtTime(gainVal, this.audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + durationSec);

      osc.connect(gain);
      if (this.analyser) {
        gain.connect(this.analyser);
      } else {
        gain.connect(this.audioCtx.destination);
      }

      osc.start();
      osc.stop(this.audioCtx.currentTime + durationSec);
    } catch (_) {}
  }

  handleRumble(largeMotor, smallMotor) {
    if (!this.enabled) return;
    const now = performance.now();
    if (now - this.lastRumbleTime < 45) return;
    this.lastRumbleTime = now;

    const large = Math.max(0, Math.min(255, parseInt(largeMotor) || 0));
    const small = Math.max(0, Math.min(255, parseInt(smallMotor) || 0));

    if (large === 0 && small === 0) return;

    this.pulseEnergy = Math.min(1.0, this.pulseEnergy + Math.max(large, small) / 255.0);

    if (large > 160 && small > 160) {
      if (this.hasVibration) {
        navigator.vibrate([70, 20, 110, 25, 50]);
      }
      this.playTactileSubBass(45, 0.14, 0.35);
      return;
    }

    if (large > 0) {
      const dur = Math.max(25, Math.round((large / 255) * 120));
      if (this.hasVibration) {
        if (large > 120) {
          navigator.vibrate([dur, 20, Math.round(dur * 0.5)]);
        } else {
          navigator.vibrate(dur);
        }
      }
      if (large > 100) {
        this.playTactileSubBass(52, 0.08, 0.22);
      }
      return;
    }

    if (small > 0) {
      const dur = Math.max(12, Math.round((small / 255) * 45));
      if (this.hasVibration) {
        navigator.vibrate([dur, 12, dur]);
      }
    }
  }

  triggerSlip() {
    if (!this.enabled) return;
    this.pulseEnergy = Math.min(1.0, this.pulseEnergy + 0.4);
    if (!this.hasVibration) return;
    const now = performance.now();
    if (now - this.lastSlipTime > 100) {
      this.lastSlipTime = now;
      navigator.vibrate([25, 15, 25]);
    }
  }

  triggerImpact() {
    if (!this.enabled) return;
    this.pulseEnergy = 1.0;
    const now = performance.now();
    if (now - this.lastImpactTime > 400) {
      this.lastImpactTime = now;
      if (this.hasVibration) {
        navigator.vibrate([160, 40, 100]);
      }
      this.playTactileSubBass(48, 0.12, 0.30);
    }
  }

  triggerRedline() {
    if (!this.enabled) return;
    this.pulseEnergy = Math.min(1.0, this.pulseEnergy + 0.6);
    if (!this.hasVibration) return;
    const now = performance.now();
    if (now - this.lastRedlineTime > 250) {
      this.lastRedlineTime = now;
      navigator.vibrate([45]);
    }
  }

  triggerClick(style = "normal") {
    if (!this.enabled || !this.hasVibration) return;
    if (style === "heavy") {
      navigator.vibrate(28);
    } else if (style === "dpad") {
      navigator.vibrate(14);
    } else if (style === "detent") {
      navigator.vibrate(8);
    } else {
      navigator.vibrate(16);
    }
  }

  triggerDpadClick() {
    this.triggerClick("dpad");
  }

  getFrequencyData(array) {
    if (this.analyser && this.audioInitialized) {
      this.analyser.getByteFrequencyData(array);
    } else if (array) {
      array.fill(0);
    }
    const energy = this.pulseEnergy;
    this.pulseEnergy = Math.max(0.0, this.pulseEnergy * 0.92 - 0.01);
    return energy;
  }
}
