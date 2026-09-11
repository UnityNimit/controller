/**
 * Project Controller - 60 FPS HTML5 Canvas Telemetry Heads-Up Display
 * Ultra-Minimalist Industrial Aesthetic. High Contrast, Zero Bloat.
 */

export class CockpitHUD {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d", { alpha: false });
    this.width = 0;
    this.height = 0;

    // Current Display State
    this.telemetry = {
      speed_kmh: 0,
      rpm: 0,
      max_rpm: 8500,
      gear: 0,
      slip_ratio: 0.0,
      g_lat: 0.0,
      g_long: 0.0,
      abs_active: false,
      tcs_active: false
    };

    this.currentSteeringAngle = 0;
    this.playerSlot = 1;
    this.playerColor = "#00ffcc";

    this.resize();
    window.addEventListener("resize", () => this.resize());
  }

  resize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.width = rect.width;
    this.height = rect.height;
    this.canvas.width = Math.floor(rect.width * dpr);
    this.canvas.height = Math.floor(rect.height * dpr);
    this.ctx.scale(dpr, dpr);
  }

  updateTelemetry(telem) {
    if (!telem) return;
    this.telemetry = { ...this.telemetry, ...telem };
  }

  updateSteering(angleDeg) {
    this.currentSteeringAngle = angleDeg;
  }

  setPlayerSlot(slot, color) {
    this.playerSlot = slot;
    this.playerColor = color || "#00ffcc";
  }

  render() {
    const ctx = this.ctx;
    const w = this.width;
    const h = this.height;

    // 1. Clear Frame (Deep Void Black)
    ctx.fillStyle = "#050505";
    ctx.fillRect(0, 0, w, h);

    // Subtle Boundary Grid
    ctx.strokeStyle = "#161616";
    ctx.lineWidth = 1;
    ctx.strokeRect(8, 8, w - 16, h - 16);

    // 2. Segmented Horizontal Tachometer
    this._renderTachometer(ctx, w, h);

    // 3. Main Center Readout: Speed & Gear
    this._renderSpeedAndGear(ctx, w, h);

    // 4. G-Force Crosshair Meter (Bottom Left)
    this._renderGMeter(ctx, w, h);

    // 5. Tire Slip Vector & Status Flags (Bottom Right)
    this._renderSlipAndFlags(ctx, w, h);

    // 6. Steering Deflection Indicator (Bottom Center)
    this._renderSteeringRuler(ctx, w, h);
  }

  _renderTachometer(ctx, w, h) {
    const barW = w - 32;
    const barH = Math.max(8, Math.min(14, Math.floor(h * 0.06)));
    const barX = 16;
    const barY = Math.max(8, Math.floor(h * 0.04));
    const numSegments = 32;
    const segSpacing = 3;
    const segW = (barW - (numSegments - 1) * segSpacing) / numSegments;

    const rpm = this.telemetry.rpm || 0;
    const maxRpm = this.telemetry.max_rpm || 8500;
    const rpmPct = Math.min(1.0, Math.max(0.0, rpm / maxRpm));
    const activeSegments = Math.round(rpmPct * numSegments);

    for (let i = 0; i < numSegments; i++) {
      const segPct = i / numSegments;
      let color = "#1a1a1a"; // off

      if (i < activeSegments) {
        if (segPct > 0.90) {
          // Redline zone (flashes if rev limiter hit)
          const flash = rpmPct > 0.96 && Math.floor(performance.now() / 80) % 2 === 0;
          color = flash ? "#ffffff" : "#ff3333";
        } else if (segPct > 0.72) {
          color = "#ffaa00"; // shift warning
        } else {
          color = "#2f80ed"; // normal power band
        }
      }

      ctx.fillStyle = color;
      ctx.fillRect(barX + i * (segW + segSpacing), barY, segW, barH);
    }

    // RPM Numerical label
    ctx.fillStyle = "#888888";
    ctx.font = "9px monospace";
    ctx.textAlign = "right";
    ctx.fillText(`${Math.round(rpm)} RPM`, barX + barW, barY + barH + 11);
  }

  _renderSpeedAndGear(ctx, w, h) {
    const centerY = h * 0.44;
    const fontSize = Math.max(28, Math.min(56, Math.floor(h * 0.24)));

    // Gear Indicator (Large Bold)
    let gearText = "N";
    if (this.telemetry.gear === -1) gearText = "R";
    else if (this.telemetry.gear === 0) gearText = "N";
    else if (this.telemetry.gear > 0) gearText = `${this.telemetry.gear}`;

    ctx.fillStyle = "#ffffff";
    ctx.font = `bold ${fontSize}px monospace`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(gearText, w * 0.35, centerY);

    ctx.fillStyle = "#666666";
    ctx.font = "9px monospace";
    ctx.fillText("GEAR", w * 0.35, centerY + (fontSize * 0.55));

    // Speed Indicator (Digital Numeric)
    const speed = Math.round(this.telemetry.speed_kmh || 0);
    ctx.fillStyle = "#ededed";
    ctx.font = `bold ${fontSize}px monospace`;
    ctx.fillText(`${speed}`, w * 0.65, centerY);

    ctx.fillStyle = "#666666";
    ctx.font = "9px monospace";
    ctx.fillText("KM/H", w * 0.65, centerY + (fontSize * 0.55));
  }

  _renderGMeter(ctx, w, h) {
    const size = Math.min(80, h * 0.35);
    const cx = 50 + size / 2;
    const cy = h - 50;

    // Outer boundary & crosshair
    ctx.strokeStyle = "#262626";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(cx, cy, size / 2, 0, Math.PI * 2);
    ctx.arc(cx, cy, size / 4, 0, Math.PI * 2);
    ctx.moveTo(cx - size / 2, cy);
    ctx.lineTo(cx + size / 2, cy);
    ctx.moveTo(cx, cy - size / 2);
    ctx.lineTo(cx, cy + size / 2);
    ctx.stroke();

    // G-Force Vector Dot
    const maxG = 2.0;
    const gLat = Math.max(-maxG, Math.min(maxG, this.telemetry.g_lat || 0));
    const gLong = Math.max(-maxG, Math.min(maxG, this.telemetry.g_long || 0));

    const dotX = cx + (gLat / maxG) * (size / 2);
    const dotY = cy - (gLong / maxG) * (size / 2);

    ctx.fillStyle = "#ffcc00";
    ctx.beginPath();
    ctx.arc(dotX, dotY, 4, 0, Math.PI * 2);
    ctx.fill();

    // Label
    ctx.fillStyle = "#666666";
    ctx.font = "9px monospace";
    ctx.textAlign = "center";
    ctx.fillText("G-METER", cx, cy + size / 2 + 14);
  }

  _renderSlipAndFlags(ctx, w, h) {
    const rx = w - 100;
    const ry = h - 85;

    // Status Boxes: ABS / TCS / SLIP
    const drawFlag = (text, active, color, x, y) => {
      ctx.fillStyle = active ? color : "#161616";
      ctx.fillRect(x, y, 42, 18);
      ctx.fillStyle = active ? "#000000" : "#444444";
      ctx.font = "bold 9px monospace";
      ctx.textAlign = "center";
      ctx.fillText(text, x + 21, y + 12);
    };

    const isSlip = (this.telemetry.slip_ratio || 0) > 0.35;
    drawFlag("ABS", this.telemetry.abs_active, "#ffcc00", rx, ry);
    drawFlag("TCS", this.telemetry.tcs_active, "#00ffcc", rx + 48, ry);
    drawFlag("SLIP", isSlip, "#ff3333", rx, ry + 22);

    // Player Slot Badge
    ctx.fillStyle = this.playerColor;
    ctx.fillRect(rx + 48, ry + 22, 42, 18);
    ctx.fillStyle = "#000000";
    ctx.font = "bold 9px monospace";
    ctx.textAlign = "center";
    ctx.fillText(`P${this.playerSlot}`, rx + 48 + 21, ry + 34);
  }

  _renderSteeringRuler(ctx, w, h) {
    const cx = w * 0.5;
    const cy = h - 22;
    const rulerW = 140;

    // Baseline
    ctx.strokeStyle = "#262626";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(cx - rulerW / 2, cy);
    ctx.lineTo(cx + rulerW / 2, cy);
    ctx.stroke();

    // Center Mark
    ctx.strokeStyle = "#666666";
    ctx.beginPath();
    ctx.moveTo(cx, cy - 6);
    ctx.lineTo(cx, cy + 6);
    ctx.stroke();

    // Pointer Dot based on steering angle
    const maxAngle = 35.0;
    const norm = Math.max(-1.0, Math.min(1.0, this.currentSteeringAngle / maxAngle));
    const pointerX = cx + norm * (rulerW / 2);

    ctx.fillStyle = this.playerColor;
    ctx.beginPath();
    ctx.arc(pointerX, cy, 5, 0, Math.PI * 2);
    ctx.fill();

    // Angle label
    ctx.fillStyle = "#888888";
    ctx.font = "10px monospace";
    ctx.textAlign = "center";
    ctx.fillText(`${this.currentSteeringAngle > 0 ? "+" : ""}${this.currentSteeringAngle.toFixed(1)}°`, cx, cy - 10);
  }
}
