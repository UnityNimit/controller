import React from 'react';
import GameControllerIcon from './GameControllerIcon';

/**
 * EngageModal: Minimalist cyber-physical launch portal.
 * Unlocks WebAudio context, requests Fullscreen, landscape orientation, and IMU sensors.
 */
export default function EngageModal({
  isOpen,
  onEngage
}) {
  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" id="engage-modal">
      <style>{`
        /* ==========================================================================
           ENGAGE MODAL — OBSIDIAN AEROSPACE LAUNCH PORTAL
           ========================================================================== */
        .modal-card {
          width: 88%;
          max-width: 400px;
          background: linear-gradient(180deg, #0e1117 0%, #050608 100%);
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 14px;
          padding: 34px 26px;
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          box-shadow: 0 30px 80px rgba(0, 0, 0, 0.98), 0 0 1px rgba(255, 255, 255, 0.2);
          animation: engageAppear 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }

        @keyframes engageAppear {
          from {
            opacity: 0;
            transform: scale(0.94);
          }
          to {
            opacity: 1;
            transform: scale(1);
          }
        }

        /* Recessed CNC Icon Well with Breathing Phosphor Halo */
        .modal-logo-well {
          position: relative;
          width: 88px;
          height: 88px;
          border-radius: 50%;
          background: radial-gradient(circle, #131620 0%, #06070a 100%);
          border: 1px solid rgba(255, 255, 255, 0.16);
          box-shadow: inset 0 2px 10px rgba(0, 0, 0, 0.9), 0 8px 24px rgba(0, 0, 0, 0.6);
          display: flex;
          align-items: center;
          justify-content: center;
          margin-bottom: 20px;
        }

        .modal-logo-well::after {
          content: "";
          position: absolute;
          width: 100%;
          height: 100%;
          border-radius: 50%;
          border: 1px solid rgba(255, 255, 255, 0.3);
          animation: pulseRing 2.4s cubic-bezier(0.2, 0.8, 0.2, 1) infinite;
          pointer-events: none;
        }

        @keyframes pulseRing {
          0% {
            transform: scale(0.96);
            opacity: 0.6;
          }
          50% {
            transform: scale(1.12);
            opacity: 0;
          }
          100% {
            transform: scale(0.96);
            opacity: 0;
          }
        }

        .modal-title {
          font-family: var(--font-hud);
          font-size: 22px;
          font-weight: 900;
          letter-spacing: 0.16em;
          color: #ffffff;
          margin-bottom: 6px;
        }

        .modal-subtitle {
          font-family: var(--font-mono);
          font-size: 9px;
          font-weight: 700;
          letter-spacing: 0.14em;
          color: rgba(255, 255, 255, 0.45);
          margin-bottom: 22px;
        }

        /* Pre-Flight Telemetry Checklist */
        .preflight-checklist {
          width: 100%;
          display: flex;
          flex-direction: column;
          gap: 6px;
          background: rgba(0, 0, 0, 0.45);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 6px;
          padding: 10px 14px;
          margin-bottom: 24px;
        }

        .checklist-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          font-family: var(--font-mono);
          font-size: 8.5px;
          letter-spacing: 0.08em;
        }

        .checklist-label {
          color: rgba(255, 255, 255, 0.4);
        }

        .checklist-status {
          display: flex;
          align-items: center;
          gap: 5px;
          color: #ffffff;
          font-weight: 700;
        }

        .status-dot {
          width: 5px;
          height: 5px;
          border-radius: 50%;
          background: #ffffff;
          box-shadow: 0 0 6px #ffffff;
        }

        /* Hero Initiation Button */
        .engage-primary-btn {
          width: 100%;
          padding: 15px;
          background: #ffffff;
          border: none;
          border-radius: 6px;
          color: #000000;
          font-family: var(--font-hud);
          font-size: 14px;
          font-weight: 900;
          letter-spacing: 0.16em;
          cursor: pointer;
          box-shadow: 0 0 24px rgba(255, 255, 255, 0.45);
          transition: transform 0.08s ease, box-shadow 0.08s ease, filter 0.08s ease;
        }

        .engage-primary-btn:hover {
          box-shadow: 0 0 32px rgba(255, 255, 255, 0.75);
        }

        .engage-primary-btn:active {
          transform: scale(0.97);
          filter: brightness(0.9);
        }
      `}</style>

      <div className="modal-card">
        {/* Recessed CNC Logo Well */}
        <div className="modal-logo-well">
          <GameControllerIcon size={44} active={true} />
        </div>

        {/* Branding */}
        <div className="modal-title">CONTROLLER</div>
        <div className="modal-subtitle">LOW LATENCY CYBER-PHYSICAL GAMEPAD // V1.0</div>

        {/* Pre-Flight Telemetry Checklist */}
        <div className="preflight-checklist">
          <div className="checklist-item">
            <span className="checklist-label">DSP HAPTIC AUDIO</span>
            <span className="checklist-status">
              <span className="status-dot" />
              ARMED
            </span>
          </div>
          <div className="checklist-item">
            <span className="checklist-label">MOTION SENSORS (IMU)</span>
            <span className="checklist-status">
              <span className="status-dot" />
              60 FPS
            </span>
          </div>
          <div className="checklist-item">
            <span className="checklist-label">POLLING ARCHITECTURE</span>
            <span className="checklist-status">
              <span className="status-dot" />
              120Hz ULTRA-LOW
            </span>
          </div>
        </div>

        {/* Hero Engagement Button */}
        <button
          className="engage-primary-btn"
          id="engage-btn"
          onClick={onEngage}
        >
          INITIALIZE // ENGAGE
        </button>
      </div>
    </div>
  );
}