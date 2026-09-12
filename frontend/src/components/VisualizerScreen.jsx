import React, { useEffect, useRef, useState } from 'react';

/**
 * VisualizerScreen: Real-time audio spectrum & haptic oscilloscope instrument.
 * Monochromatic high-contrast spectrum bars with peak-hold caps and laser oscilloscope.
 */
export default function VisualizerScreen({
  hapticsEngine,
  className = '',
  style = {}
}) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const [energyLevel, setEnergyLevel] = useState(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext('2d', { alpha: false });
    let animId;

    const numBars = 26;
    const freqData = new Uint8Array(32);
    const peakBars = new Float32Array(numBars);
    const peakDecay = new Float32Array(numBars);

    let lastEnergyUpdate = 0;

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
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        // Deep OLED Obsidian Well
        ctx.fillStyle = '#030406';
        ctx.fillRect(0, 0, w, h);

        const pulseEnergy = hapticsEngine ? hapticsEngine.getFrequencyData(freqData) : 0;
        const nowMs = performance.now();
        const now = nowMs * 0.003;

        // Throttle UI energy state updates to 15fps for optimal performance
        if (nowMs - lastEnergyUpdate > 66) {
          setEnergyLevel(Math.round(pulseEnergy * 100));
          lastEnergyUpdate = nowMs;
        }

        // 1. SUB-PIXEL CALIBRATION RETICLE GRID
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.035)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        // Horizontal Graticule Lines
        for (let y = 0.25; y <= 0.75; y += 0.25) {
          ctx.moveTo(0, h * y);
          ctx.lineTo(w, h * y);
        }
        // Vertical Graticule Lines
        for (let x = 0.2; x <= 0.8; x += 0.2) {
          ctx.moveTo(w * x, 0);
          ctx.lineTo(w * x, h);
        }
        ctx.stroke();

        // 2. TACTICAL SPECTRUM EQUALIZER BARS
        const gutter = 3;
        const barWidth = Math.max(2, (w - gutter * (numBars + 1)) / numBars);
        const maxBarHeight = h * 0.68;

        for (let i = 0; i < numBars; i++) {
          let rawVal = (freqData[i % freqData.length] || 0) / 255.0;

          // Organic subtle breathing wave during silent standby
          if (rawVal < 0.04) {
            rawVal = 0.05 + 0.04 * Math.sin(now * 1.5 + i * 0.35);
          }

          const energyBoost = pulseEnergy * (0.35 + 0.65 * Math.sin((i / numBars) * Math.PI));
          const normalizedHeight = Math.min(1.0, rawVal + energyBoost);
          const barHeight = Math.max(3, normalizedHeight * maxBarHeight);

          // Gravity Ballistics for Peak-Hold Caps
          if (barHeight >= peakBars[i]) {
            peakBars[i] = barHeight;
            peakDecay[i] = 0.3;
          } else {
            peakDecay[i] = Math.min(2.5, peakDecay[i] + 0.06);
            peakBars[i] = Math.max(3, peakBars[i] - peakDecay[i]);
          }

          const x = gutter + i * (barWidth + gutter);
          const y = h - barHeight - 6;

          // Spectrum Column
          if (normalizedHeight > 0.65) {
            ctx.fillStyle = '#ffffff';
          } else if (normalizedHeight > 0.3) {
            ctx.fillStyle = 'rgba(255, 255, 255, 0.45)';
          } else {
            ctx.fillStyle = 'rgba(255, 255, 255, 0.18)';
          }
          ctx.fillRect(x, y, barWidth, barHeight);

          // Floating Laser Peak Cap
          ctx.fillStyle = '#ffffff';
          const peakY = Math.max(4, h - peakBars[i] - 8);
          ctx.fillRect(x, peakY, barWidth, 1.5);
        }

        // 3. REAL-TIME HAPTIC OSCILLOSCOPE WAVEFORM
        ctx.save();
        const isHighEnergy = pulseEnergy > 0.25;
        ctx.strokeStyle = isHighEnergy ? '#ffffff' : 'rgba(255, 255, 255, 0.4)';
        ctx.lineWidth = isHighEnergy ? 1.8 : 1;

        if (isHighEnergy) {
          ctx.shadowColor = '#ffffff';
          ctx.shadowBlur = 8;
        }

        ctx.beginPath();
        const waveMid = h * 0.42;
        const waveAmp = h * 0.22 * (0.12 + pulseEnergy * 0.88);
        const step = Math.max(2, Math.floor(w / 70));

        for (let x = 0; x <= w; x += step) {
          const progress = x / w;
          const envelope = Math.sin(progress * Math.PI); // Pinched edges
          const angle = progress * Math.PI * 8 + now * 4;
          const wy = waveMid + Math.sin(angle) * waveAmp * envelope;

          if (x === 0) ctx.moveTo(x, wy);
          else ctx.lineTo(x, wy);
        }
        ctx.stroke();
        ctx.restore();
      }

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animId);
    };
  }, [hapticsEngine]);

  return (
    <div
      ref={containerRef}
      id="mod-visualizer"
      className={`gamepad-module screen-panel ${className}`}
      style={style}
    >
      <style>{`
        #mod-visualizer {
          position: absolute;
          background: #030406;
          border: 1px solid rgba(255, 255, 255, 0.14);
          border-radius: 4px;
          overflow: hidden;
        }

        #visualizer-canvas {
          width: 100%;
          height: 100%;
          display: block;
        }

        .vis-hud-top-left {
          position: absolute;
          top: 5px;
          left: 7px;
          font-family: var(--font-mono);
          font-size: 8.5px;
          font-weight: 800;
          color: rgba(255, 255, 255, 0.4);
          letter-spacing: 0.12em;
          pointer-events: none;
        }

        .vis-hud-top-right {
          position: absolute;
          top: 5px;
          right: 6px;
          pointer-events: none;
        }

        .vis-status-capsule {
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 2px 5px;
          background: rgba(0, 0, 0, 0.75);
          border: 1px solid rgba(255, 255, 255, 0.18);
          border-radius: 3px;
          font-family: var(--font-mono);
          font-size: 8.5px;
          font-weight: 700;
          letter-spacing: 0.08em;
          color: #ffffff;
        }

        .vis-status-capsule.active {
          border-color: #ffffff;
          box-shadow: 0 0 10px rgba(255, 255, 255, 0.35);
        }

        .vis-pip {
          width: 5px;
          height: 5px;
          border-radius: 50%;
          background: rgba(255, 255, 255, 0.3);
        }

        .vis-status-capsule.active .vis-pip {
          background: #ffffff;
          box-shadow: 0 0 6px #ffffff;
        }

        .vis-hud-bottom {
          position: absolute;
          bottom: 5px;
          left: 7px;
          right: 7px;
          display: flex;
          justify-content: space-between;
          font-family: var(--font-mono);
          font-size: 8px;
          font-weight: 700;
          color: rgba(255, 255, 255, 0.3);
          letter-spacing: 0.08em;
          pointer-events: none;
        }
      `}</style>

      <canvas id="visualizer-canvas" ref={canvasRef} />

      {/* Cyber-Physical HUD Telemetry Overlays */}
      <div className="vis-hud-top-left">DSP // OSCILLOSCOPE</div>

      <div className="vis-hud-top-right">
        <div className={`vis-status-capsule ${energyLevel > 20 ? 'active' : ''}`}>
          <div className="vis-pip" />
          <span>{energyLevel > 0 ? `HAPTIC ${energyLevel}%` : 'IDLE'}</span>
        </div>
      </div>

      <div className="vis-hud-bottom">
        <span>ACT: L+R DUAL</span>
        <span>RATE: 120Hz</span>
      </div>
    </div>
  );
}