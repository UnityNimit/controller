/**
 * Project Controller - Dynamic Haptic Actuation & Audio Shift Tone Synthesizer
 * Implements Closed-Loop Physical Feedback from Live Game Telemetry.
 */

export class HapticEngine {
  constructor() {
    this.hasVibration = "vibrate" in navigator;
    this.lastSlipTime = 0;
    this.lastImpactTime = 0;
    this.lastRedlineTime = 0;
  }

  /**
   * High-Frequency Buzz for Tire Slip / Understeer Loss of Grip
   */
  triggerSlip() {
    if (!this.hasVibration) return;
    const now = performance.now();
    if (now - this.lastSlipTime > 120) {
      this.lastSlipTime = now;
      navigator.vibrate([35, 20, 35]);
    }
  }

  /**
   * Heavy Pulse Waveform for Vehicle Collision / Barrier Impact Spike
   */
  triggerImpact() {
    if (!this.hasVibration) return;
    const now = performance.now();
    if (now - this.lastImpactTime > 500) {
      this.lastImpactTime = now;
      navigator.vibrate([180, 50, 120]);
    }
  }

  /**
   * Tactile Tick for Redline Engine RPM Peak
   */
  triggerRedline() {
    if (!this.hasVibration) return;
    const now = performance.now();
    if (now - this.lastRedlineTime > 300) {
      this.lastRedlineTime = now;
      navigator.vibrate([60]);
    }
  }

  /**
   * Button Press Haptic Feedback
   */
  triggerClick() {
    if (this.hasVibration) {
      navigator.vibrate(15);
    }
  }
}


export class ShiftToneSynthesizer {
  constructor() {
    this.audioCtx = null;
    this.lastToneTime = 0;
    this.cooldownMs = 400;
  }

  initAudio() {
    if (!this.audioCtx) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) {
        this.audioCtx = new AudioContextClass();
      }
    }
    if (this.audioCtx && this.audioCtx.state === "suspended") {
      this.audioCtx.resume();
    }
  }

  /**
   * Generates a high-pitch F1/GT3 cockpit shift beep at engine redline.
   */
  beep(freq = 1750, duration = 0.05) {
    if (!this.audioCtx) return;
    const now = performance.now();
    if (now - this.lastToneTime < this.cooldownMs) return;
    this.lastToneTime = now;

    try {
      const osc = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, this.audioCtx.currentTime);

      gain.gain.setValueAtTime(0.15, this.audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + duration);

      osc.connect(gain);
      gain.connect(this.audioCtx.destination);

      osc.start();
      osc.stop(this.audioCtx.currentTime + duration);
    } catch (e) {
      console.debug("Audio play error", e);
    }
  }
}
