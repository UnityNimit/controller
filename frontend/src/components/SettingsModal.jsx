import React from 'react';

/**
 * SettingsModal: Minimalist cyber-physical layout switcher & hardware telemetry dock.
 * Features dual architecture selection, slot assignment, and zero-gyro calibration.
 */
export default function SettingsModal({
  isOpen,
  onClose,
  preset,
  onSelectPreset,
  gyroEnabled,
  onToggleGyro,
  onZeroGyro,
  rawAngle = 0,
  playerSlot = 1,
  onSelectSlot,
  connected = false,
  rtt = 0,
  hapticsEngine
}) {
  if (!isOpen) return null;

  const handlePresetChange = (newPreset) => {
    if (hapticsEngine) hapticsEngine.triggerClick('heavy');
    onSelectPreset(newPreset);
    onClose();
  };

  const handleZeroGyro = () => {
    if (hapticsEngine) hapticsEngine.triggerClick('heavy');
    if (onZeroGyro) onZeroGyro();
  };

  const handleSlotCycle = () => {
    if (hapticsEngine) hapticsEngine.triggerClick('heavy');
    if (onSelectSlot) onSelectSlot();
  };

  return (
    <div className="settings-modal-backdrop" onClick={onClose}>
      <style>{`
        /* ==========================================================================
           SETTINGS MODAL — OBSIDIAN GLASSM нейро ARCHITECTURE
           ========================================================================== */
        .settings-minimal-card {
          width: 90%;
          max-width: 380px;
          background: linear-gradient(180deg, #0d0f15 0%, #06070a 100%);
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 12px;
          padding: 24px 20px;
          box-shadow: 0 24px 60px rgba(0, 0, 0, 0.95), 0 0 1px rgba(255, 255, 255, 0.2);
          display: flex;
          flex-direction: column;
          gap: 16px;
          animation: modalAppear 0.15s cubic-bezier(0.16, 1, 0.3, 1);
        }

        @keyframes modalAppear {
          from {
            opacity: 0;
            transform: scale(0.95);
          }
          to {
            opacity: 1;
            transform: scale(1);
          }
        }

        .settings-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
          padding-bottom: 12px;
        }

        .settings-title {
          font-family: var(--font-hud);
          font-size: 13px;
          font-weight: 800;
          letter-spacing: 0.14em;
          color: #ffffff;
        }

        .settings-close-btn {
          font-family: var(--font-mono);
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 0.08em;
          color: rgba(255, 255, 255, 0.4);
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 4px;
          padding: 3px 8px;
          cursor: pointer;
          transition: all 0.1s ease;
        }

        .settings-close-btn:active {
          background: #ffffff;
          color: #000000;
        }

        /* Dual Hero Architecture Switchers */
        .preset-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
        }

        .preset-choice-tile {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 90px;
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.14);
          border-radius: 8px;
          cursor: pointer;
          touch-action: none;
          transition: all 0.1s ease;
          gap: 4px;
        }

        .preset-choice-tile:hover {
          border-color: rgba(255, 255, 255, 0.35);
          background: rgba(255, 255, 255, 0.06);
        }

        .preset-choice-tile.active {
          background: #ffffff !important;
          border-color: #ffffff !important;
          box-shadow: 0 0 20px rgba(255, 255, 255, 0.5);
        }

        .preset-number {
          font-family: var(--font-hud);
          font-size: 32px;
          font-weight: 900;
          color: #ffffff;
          line-height: 1;
        }

        .preset-choice-tile.active .preset-number {
          color: #000000;
        }

        .preset-tag {
          font-family: var(--font-mono);
          font-size: 8.5px;
          font-weight: 700;
          letter-spacing: 0.12em;
          color: rgba(255, 255, 255, 0.45);
        }

        .preset-choice-tile.active .preset-tag {
          color: rgba(0, 0, 0, 0.7);
        }

        /* Telemetry & Calibration Dock */
        .settings-dock {
          display: flex;
          flex-direction: column;
          gap: 8px;
          background: rgba(0, 0, 0, 0.4);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 6px;
          padding: 10px 12px;
        }

        .dock-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          font-family: var(--font-mono);
          font-size: 9.5px;
          letter-spacing: 0.08em;
        }

        .dock-label {
          color: rgba(255, 255, 255, 0.4);
        }

        .dock-value {
          color: #ffffff;
          font-weight: 700;
        }

        .dock-slot-btn {
          background: rgba(255, 255, 255, 0.08);
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 3px;
          padding: 2px 7px;
          color: #ffffff;
          font-family: var(--font-mono);
          font-size: 9.5px;
          font-weight: 800;
          cursor: pointer;
        }

        .dock-slot-btn:active {
          background: #ffffff;
          color: #000000;
        }

        /* Action Buttons */
        .calibration-btn {
          width: 100%;
          padding: 9px;
          background: rgba(255, 255, 255, 0.06);
          border: 1px solid rgba(255, 255, 255, 0.16);
          border-radius: 5px;
          color: #ffffff;
          font-family: var(--font-mono);
          font-size: 10px;
          font-weight: 800;
          letter-spacing: 0.1em;
          cursor: pointer;
          transition: all 0.08s ease;
        }

        .calibration-btn:active {
          background: #ffffff;
          color: #000000;
          box-shadow: 0 0 14px rgba(255, 255, 255, 0.4);
        }
      `}</style>

      <div className="settings-minimal-card" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="settings-header">
          <span className="settings-title">CONFIG // ARCHITECTURE</span>
          <button className="settings-close-btn" onClick={onClose}>
            ESC
          </button>
        </div>

        {/* Hero Dual Preset Selector */}
        <div className="preset-grid">
          <button
            className={`preset-choice-tile ${preset === 'preset1' ? 'active' : ''}`}
            id="btn-preset-1"
            onClick={() => handlePresetChange('preset1')}
          >
            <span className="preset-number">01</span>
            <span className="preset-tag">SYMMETRICAL</span>
          </button>

          <button
            className={`preset-choice-tile ${preset === 'preset2' ? 'active' : ''}`}
            id="btn-preset-2"
            onClick={() => handlePresetChange('preset2')}
          >
            <span className="preset-number">02</span>
            <span className="preset-tag">ASYMMETRIC</span>
          </button>
        </div>

        {/* Live Hardware Telemetry Dock */}
        <div className="settings-dock">
          <div className="dock-row">
            <span className="dock-label">LINK</span>
            <span className="dock-value">
              {connected ? `ONLINE // ${rtt}ms` : 'DISCONNECTED'}
            </span>
          </div>

          <div className="dock-row">
            <span className="dock-label">SLOT ASSIGNMENT</span>
            <button
              className="dock-slot-btn"
              onClick={handleSlotCycle}
              title="Tap to switch slot"
            >
              PLAYER {playerSlot} ↺
            </button>
          </div>
        </div>

        {/* Gyro Horizon Recalibration Action */}
        <button className="calibration-btn" onClick={handleZeroGyro}>
          CALIBRATE HORIZON // ZERO GYRO
        </button>
      </div>
    </div>
  );
}