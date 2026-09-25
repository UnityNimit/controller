/**
 * Project Controller - High-Rate Web Worker Background Ticker (Pillar 3)
 * Bypasses mobile browser main-thread setInterval throttling (10-15 Hz when stationary).
 * Delivers unthrottled, high-precision ticks (250 Hz - 500 Hz) directly to the transmission pump.
 */

class HighRateWorkerTicker {
  constructor(callback, intervalMs = 4) {
    this.callback = callback;
    this.intervalMs = Math.max(1, intervalMs);
    this.worker = null;
    this.fallbackTimer = null;
    this.isRunning = false;
    this._initWorker();
  }

  _initWorker() {
    try {
      if (typeof Worker !== "undefined" && typeof Blob !== "undefined" && typeof URL !== "undefined") {
        const workerCode = `
          let timerId = null;
          self.onmessage = function(e) {
            const data = e.data;
            if (data.command === 'start') {
              const ms = data.intervalMs || 4;
              if (timerId !== null) clearInterval(timerId);
              timerId = setInterval(function() {
                self.postMessage('tick');
              }, ms);
            } else if (data.command === 'stop') {
              if (timerId !== null) {
                clearInterval(timerId);
                timerId = null;
              }
            } else if (data.command === 'setInterval') {
              const ms = data.intervalMs || 4;
              if (timerId !== null) {
                clearInterval(timerId);
                timerId = setInterval(function() {
                  self.postMessage('tick');
                }, ms);
              }
            }
          };
        `;
        const blob = new Blob([workerCode], { type: "application/javascript" });
        const workerUrl = URL.createObjectURL(blob);
        this.worker = new Worker(workerUrl);
        this.worker.onmessage = (e) => {
          if (e.data === "tick" && this.isRunning && typeof this.callback === "function") {
            this.callback();
          }
        };
        // Revoke blob URL once worker is instantiated
        URL.revokeObjectURL(workerUrl);
        return;
      }
    } catch (err) {
      console.warn("[HighRateWorkerTicker] Web Worker initialization failed, falling back to window timer:", err);
    }
    this.worker = null;
  }

  start() {
    if (this.isRunning) return;
    this.isRunning = true;
    if (this.worker) {
      this.worker.postMessage({ command: "start", intervalMs: this.intervalMs });
    } else {
      if (this.fallbackTimer !== null) clearInterval(this.fallbackTimer);
      this.fallbackTimer = setInterval(() => {
        if (this.isRunning && typeof this.callback === "function") {
          this.callback();
        }
      }, this.intervalMs);
    }
  }

  stop() {
    this.isRunning = false;
    if (this.worker) {
      this.worker.postMessage({ command: "stop" });
    }
    if (this.fallbackTimer !== null) {
      clearInterval(this.fallbackTimer);
      this.fallbackTimer = null;
    }
  }

  setIntervalMs(intervalMs) {
    this.intervalMs = Math.max(1, intervalMs);
    if (this.worker) {
      this.worker.postMessage({ command: "setInterval", intervalMs: this.intervalMs });
    } else if (this.isRunning) {
      this.stop();
      this.start();
    }
  }
}

if (typeof window !== "undefined") {
  window.HighRateWorkerTicker = HighRateWorkerTicker;
}
if (typeof module !== "undefined" && module.exports) {
  module.exports = { HighRateWorkerTicker };
}
