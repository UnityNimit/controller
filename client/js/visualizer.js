/**
 * Project Controller - Dedicated Visualizer & Canvas Rendering Engine
 * Manages HUD canvases, high-framerate horizon lines, telemetry overlays, and visual effects.
 */

class GamepadVisualizerRenderer {
  constructor(options = {}) {
    this.gyroCanvas = options.gyroCanvas || null;
    this.visualizerCanvas = options.visualizerCanvas || null;
    this.gyroHorizonLine = options.gyroHorizonLine || null;
    this.l2DividerLine = options.l2DividerLine || null;
    this.getGyroSensor = options.getGyroSensor || null;

    this._animFrame = null;
    this._running = false;
  }

  start() {
    if (this._running) return;
    this._running = true;

    const render = () => {
      if (!this._running) return;
      this.renderFrame();
      this._animFrame = requestAnimationFrame(render);
    };
    this._animFrame = requestAnimationFrame(render);
  }

  stop() {
    this._running = false;
    if (this._animFrame) {
      cancelAnimationFrame(this._animFrame);
      this._animFrame = null;
    }
  }

  renderFrame() {
    const gyro = this.getGyroSensor ? this.getGyroSensor() : null;
    if (gyro && typeof gyro.renderHorizonLines === "function") {
      gyro.renderHorizonLines(this.gyroHorizonLine);
    }
    this.renderGyroCanvas();
    this.renderVisualizerCanvas();
  }

  renderGyroCanvas() {
    const canvas = this.gyroCanvas || document.getElementById("gyro-canvas");
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

  renderVisualizerCanvas() {
    const canvas = this.visualizerCanvas || document.getElementById("visualizer-canvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
}

if (typeof window !== "undefined") {
  window.GamepadVisualizerRenderer = GamepadVisualizerRenderer;
}
if (typeof module !== "undefined" && module.exports) {
  module.exports = { GamepadVisualizerRenderer };
}
