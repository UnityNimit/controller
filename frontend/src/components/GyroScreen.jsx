import React, { useEffect, useRef } from 'react';

/**
 * GyroScreen: High-precision aerospace Primary Flight Display (PFD) HUD.
 * Renders pitch ladder, roll line, bank arc, and collimated reticle at 60fps.
 */
export default function GyroScreen({
  gyroEnabled = false,
  rawAngle = 0.0,
  accel = { x: 0, y: 0, z: 9.8 },
  onToggleGyro,
  className = '',
  style = {}
}) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const stateRef = useRef({ gyroEnabled, rawAngle, accel });

  useEffect(() => {
    stateRef.current = { gyroEnabled, rawAngle, accel };
  }, [gyroEnabled, rawAngle, accel]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext('2d', { alpha: false });
    let animId;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 3);
      const rect = container.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        canvas.width = Math.round(rect.width * dpr);
        canvas.height = Math.round(rect.height * dpr);
      }
    };

    resize();
    window.addEventListener('resize', resize);

    const render = () => {
      const rect = container.getBoundingClientRect();
      const w = rect.width;
      const h = rect.height;
      const dpr = Math.min(window.devicePixelRatio || 1, 3);

      if (w > 0 && h > 0 && ctx) {
        // High-DPI subpixel matrix reset
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        // Deep OLED Obsidian Well
        ctx.fillStyle = '#030406';
        ctx.fillRect(0, 0, w, h);

        const { gyroEnabled: isEnabled, rawAngle: angle, accel: acc } = stateRef.current;
        const cx = w / 2;
        const cy = h / 2;

        const rollRad = ((angle || 0) * Math.PI) / 180.0;
        const pitchOffset = Math.max(-h * 0.36, Math.min(h * 0.36, (acc.y || 0) * 3.8));

        // 1. ROTATING HORIZON & PITCH LADDER
        ctx.save();
        ctx.translate(cx, cy + pitchOffset);
        ctx.rotate(rollRad);

        // Main Horizon Line with Center Reticle Gap
        ctx.strokeStyle = isEnabled ? '#ffffff' : 'rgba(255, 255, 255, 0.55)';
        ctx.lineWidth = 1.5;
        if (isEnabled) {
          ctx.shadowColor = '#ffffff';
          ctx.shadowBlur = 6;
        }

        const horizonGap = w * 0.14;
        ctx.beginPath();
        ctx.moveTo(-w * 0.75, 0);
        ctx.lineTo(-horizonGap, 0);
        ctx.moveTo(horizonGap, 0);
        ctx.lineTo(w * 0.75, 0);
        ctx.stroke();

        // Calibrated Pitch Ladder (±10°, ±20°)
        const pitchStep = h * 0.18;
        ctx.lineWidth = 1;
        ctx.font = '8px "SF Mono", monospace';
        ctx.fillStyle = isEnabled ? '#ffffff' : 'rgba(255, 255, 255, 0.45)';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        for (let i = -2; i <= 2; i++) {
          if (i === 0) continue;
          const py = i * pitchStep;
          const rungWidth = (w * 0.18) / (Math.abs(i) === 2 ? 1.4 : 1.0);
          const rungGap = w * 0.08;

          // Broken Rung Lines
          ctx.beginPath();
          ctx.moveTo(-rungWidth, py);
          ctx.lineTo(-rungGap, py);
          ctx.moveTo(rungGap, py);
          ctx.lineTo(rungWidth, py);

          // Altitude Pitch Marker Feet
          const footLen = i > 0 ? -3 : 3;
          ctx.moveTo(-rungWidth, py);
          ctx.lineTo(-rungWidth, py + footLen);
          ctx.moveTo(rungWidth, py);
          ctx.lineTo(rungWidth, py + footLen);
          ctx.stroke();

          // Degree Labels
          const degTag = `${Math.abs(i * 10)}`;
          ctx.fillText(degTag, -rungWidth - 9, py);
          ctx.fillText(degTag, rungWidth + 9, py);
        }

        ctx.restore();

        // 2. FIXED TOP BANK ARC & INDEX TICKS
        ctx.save();
        const bankRadius = Math.min(cx, cy) * 0.82;
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(cx, cy, bankRadius, -Math.PI * 0.8, -Math.PI * 0.2);
        ctx.stroke();

        // Bank Index Tick Marks (0°, ±10°, ±20°, ±30°, ±45°, ±60°)
        const bankTicks = [-60, -45, -30, -20, -10, 0, 10, 20, 30, 45, 60];
        for (const deg of bankTicks) {
          const rad = (deg - 90) * (Math.PI / 180.0);
          const innerR = deg === 0 || Math.abs(deg) === 30 || Math.abs(deg) === 60 ? bankRadius - 5 : bankRadius - 3;
          ctx.beginPath();
          ctx.moveTo(cx + innerR * Math.cos(rad), cy + innerR * Math.sin(rad));
          ctx.lineTo(cx + bankRadius * Math.cos(rad), cy + bankRadius * Math.sin(rad));
          ctx.stroke();
        }

        // Sky Pointer (Roll Inverted Triangle)
        const rollPointerAngle = -rollRad - Math.PI / 2;
        const pointerDist = bankRadius - 2;
        const px = cx + pointerDist * Math.cos(rollPointerAngle);
        const py = cy + pointerDist * Math.sin(rollPointerAngle);

        ctx.fillStyle = isEnabled ? '#ffffff' : 'rgba(255, 255, 255, 0.6)';
        ctx.beginPath();
        ctx.arc(px, py, 2.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();

        // 3. FIXED CENTRAL COLLIMATED RETICLE [- · -]
        ctx.save();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1.5;
        if (isEnabled) {
          ctx.shadowColor = '#ffffff';
          ctx.shadowBlur = 7;
        }

        const wingSpan = Math.min(w * 0.08, 16);
        const wingDrop = 4;

        // Left Wing Reticle
        ctx.beginPath();
        ctx.moveTo(cx - wingSpan * 1.5, cy);
        ctx.lineTo(cx - wingSpan * 0.4, cy);
        ctx.lineTo(cx - wingSpan * 0.4, cy + wingDrop);
        ctx.stroke();

        // Right Wing Reticle
        ctx.beginPath();
        ctx.moveTo(cx + wingSpan * 1.5, cy);
        ctx.lineTo(cx + wingSpan * 0.4, cy);
        ctx.lineTo(cx + wingSpan * 0.4, cy + wingDrop);
        ctx.stroke();

        // Central Optical Laser Pip
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(cx, cy, 2, 0, Math.PI * 2);
        ctx.fill();

        ctx.restore();
      }

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animId);
    };
  }, []);

  const formattedAngle = `${rawAngle >= 0 ? '+' : ''}${rawAngle.toFixed(1)}°`;
  const gForce = (Math.hypot(accel.x || 0, accel.y || 0, accel.z || 9.8) / 9.8).toFixed(2);

  return (
    <div
      ref={containerRef}
      id="mod-gyro"
      className={`gamepad-module screen-panel ${className}`}
      onClick={onToggleGyro}
      title="Tap to toggle Gyro steering"
      style={{
        cursor: 'pointer',
        ...style
      }}
    >
      <style>{`
        #mod-gyro {
          position: absolute;
          background: #030406;
          border: 1px solid rgba(255, 255, 255, 0.14);
          border-radius: 4px;
          overflow: hidden;
        }

        #gyro-canvas {
          width: 100%;
          height: 100%;
          display: block;
        }

        .gyro-hud-top-left {
          position: absolute;
          top: 6px;
          left: 7px;
          font-family: var(--font-mono);
          font-size: 9px;
          font-weight: 800;
          color: rgba(255, 255, 255, 0.4);
          letter-spacing: 0.12em;
          pointer-events: none;
        }

        .gyro-hud-top-right {
          position: absolute;
          top: 5px;
          right: 6px;
          pointer-events: none;
        }

        .gyro-hud-bottom {
          position: absolute;
          bottom: 5px;
          left: 7px;
          right: 7px;
          display: flex;
          justify-content: space-between;
          font-family: var(--font-mono);
          font-size: 8.5px;
          font-weight: 700;
          color: rgba(255, 255, 255, 0.35);
          letter-spacing: 0.08em;
          pointer-events: none;
        }

        .gyro-status-capsule {
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 2px 5px;
          background: rgba(0, 0, 0, 0.75);
          border: 1px solid rgba(255, 255, 255, 0.18);
          border-radius: 3px;
          font-family: var(--font-mono);
          font-size: 9px;
          font-weight: 700;
          letter-spacing: 0.08em;
          color: #ffffff;
        }

        .gyro-status-capsule.active {
          border-color: #ffffff;
          box-shadow: 0 0 10px rgba(255, 255, 255, 0.35);
        }

        .gyro-pip {
          width: 5px;
          height: 5px;
          border-radius: 50%;
          background: rgba(255, 255, 255, 0.3);
        }

        .gyro-status-capsule.active .gyro-pip {
          background: #ffffff;
          box-shadow: 0 0 6px #ffffff;
        }
      `}</style>

      <canvas id="gyro-canvas" ref={canvasRef} />

      {/* Military HUD Micro-Telemetry Overlays */}
      <div className="gyro-hud-top-left">PFD // ATT</div>

      <div className="gyro-hud-top-right">
        <div className={`gyro-status-capsule ${gyroEnabled ? 'active' : ''}`}>
          <div className="gyro-pip" />
          <span>{gyroEnabled ? `GYRO ${formattedAngle}` : formattedAngle}</span>
        </div>
      </div>

      <div className="gyro-hud-bottom">
        <span>G: {gForce}</span>
        <span>ROLL: {formattedAngle}</span>
      </div>
    </div>
  );
}