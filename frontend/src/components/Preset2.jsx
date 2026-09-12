import React, { useRef } from 'react';
import GyroScreen from './GyroScreen';

export default function Preset2({
  gamepad,
  onOpenSettings
}) {
  const {
    playerSlot,
    rtt,
    gyroEnabled,
    rawAngle,
    accel,
    toggleGyro,
    cyclePreferredSlot,
    handleButtonDown,
    handleButtonUp,
    handleTriggerDown,
    handleTriggerUp,
    updateLeftStickFromPointer,
    releaseLeftStick,
    updateRightStickFromPointer,
    releaseRightStick
  } = gamepad;

  const leftBaseRef = useRef(null);
  const leftPuckRef = useRef(null);
  const rightBaseRef = useRef(null);
  const rightPuckRef = useRef(null);
  const ltFillRef = useRef(null);
  const rtFillRef = useRef(null);

  return (
    <div className="preset-container preset-2-layout" id="gamepad-frame">
      <style>{`
        /* ==========================================================================
           PRESET 2: TACTICAL ASYMMETRIC ENGINE & INTERLOCKING POLYGONS
           ========================================================================== */
        
        /* Left Wing Asymmetric Split: Primary Stick Top + Tactical D-Pad Bottom */
        .p2-left-deck-top {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          height: 60%;
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 20;
        }

        .p2-left-deck-bottom {
          position: absolute;
          bottom: 0;
          left: 0;
          right: 0;
          height: 40%;
          display: flex;
          align-items: center;
          justify-content: center;
          border-top: 1px solid rgba(255, 255, 255, 0.08);
          background: rgba(0, 0, 0, 0.35);
          z-index: 10;
        }

        .p2-stick-anchor {
          position: relative;
          width: 72px;
          height: 72px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .p2-tactical-dpad {
          display: flex;
          gap: 6px;
          align-items: center;
          justify-content: center;
        }

        .p2-dpad-mini-btn {
          width: 28px;
          height: 24px;
          background: rgba(255, 255, 255, 0.04);
          border: 1px solid rgba(255, 255, 255, 0.14);
          border-radius: 3px;
          color: rgba(255, 255, 255, 0.7);
          font-family: var(--font-hud);
          font-size: 10px;
          font-weight: 900;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          touch-action: none;
          transition: all 0.06s ease;
        }

        .p2-dpad-mini-btn:active, .p2-dpad-mini-btn.active {
          background: #ffffff !important;
          color: #000000 !important;
          border-color: #ffffff !important;
          box-shadow: 0 0 12px rgba(255, 255, 255, 0.7);
        }

        /* Mid-Right Standalone Thumbstick Module */
        .mid-right-stick-module {
          left: 63.5%;
          top: 48.0%;
          width: 72px;
          height: 72px;
          z-index: 22;
          background: var(--obsidian-plate);
          border: 1px solid rgba(255, 255, 255, 0.14);
          border-radius: 50%;
          box-shadow: inset 0 2px 10px rgba(0, 0, 0, 0.85);
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .mid-right-stick-module .stick-anchor {
          position: relative;
          width: 68px;
          height: 68px;
        }

        /* Precision Interlocking Polygon Cluster */
        .tactical-right-cluster {
          left: 74.5%;
          top: 43.0%;
          width: 24.5%;
          height: 54.5%;
          position: absolute;
          z-index: 20;
        }

        .poly-btn-wrap {
          position: absolute;
          touch-action: none;
          cursor: pointer;
        }

        .poly-btn {
          width: 100%;
          height: 100%;
          background: transparent;
          border: none;
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          touch-action: none;
          cursor: pointer;
        }

        .poly-svg {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          pointer-events: none;
        }

        .poly-shape {
          fill: #0a0c10;
          stroke: rgba(255, 255, 255, 0.16);
          stroke-width: 1.5;
          vector-effect: non-scaling-stroke;
          transition: all 0.08s ease;
        }

        .poly-btn:active .poly-shape, .poly-btn.active .poly-shape {
          fill: #ffffff !important;
          stroke: #ffffff !important;
          filter: drop-shadow(0 0 12px rgba(255, 255, 255, 0.8));
        }

        .poly-label {
          position: relative;
          z-index: 2;
          font-family: var(--font-hud);
          font-size: 18px;
          font-weight: 900;
          color: #ffffff;
          pointer-events: none;
          transition: color 0.08s ease;
        }

        .poly-btn:active .poly-label, .poly-btn.active .poly-label {
          color: #000000 !important;
        }

        /* Interlocking Modular Placement */
        .poly-wrap-y {
          top: 2%;
          left: 2%;
          width: 66%;
          height: 46%;
        }

        .poly-wrap-x {
          bottom: 2%;
          left: 2%;
          width: 32%;
          height: 48%;
        }

        .poly-wrap-a {
          bottom: 2%;
          left: 36%;
          width: 32%;
          height: 48%;
        }

        .poly-wrap-b {
          top: 2%;
          right: 2%;
          width: 28%;
          height: 96%;
        }
      `}</style>

      {/* ====================================================================
          1. TOP ROW: 45° CHAMFERED LT, LB, LOGO + P1/PING, RB, CHAMFERED RT
          ==================================================================== */}
      {/* 45° Chamfered Left Trigger (LT) */}
      <div
        className="gamepad-module"
        id="mod-lt-p2"
        onPointerDown={(e) => {
          e.preventDefault();
          handleTriggerDown('LT');
          if (ltFillRef.current) ltFillRef.current.style.height = '100%';
        }}
        onPointerUp={(e) => {
          e.preventDefault();
          handleTriggerUp('LT');
          if (ltFillRef.current) ltFillRef.current.style.height = '0%';
        }}
        onPointerCancel={(e) => {
          e.preventDefault();
          handleTriggerUp('LT');
          if (ltFillRef.current) ltFillRef.current.style.height = '0%';
        }}
      >
        <svg className="trigger-svg" viewBox="0 0 200 138" preserveAspectRatio="none">
          <path className="trigger-path" d="M 2,2 L 198,2 L 198,75 L 140,136 L 2,136 Z" />
        </svg>
        <div className="trigger-inner" id="lt-trigger-p2">
          <div className="trigger-level-fill" id="lt-fill-p2" ref={ltFillRef} />
          <span className="mod-label trigger-lbl">LT</span>
        </div>
      </div>

      {/* Left Bumper (LB) */}
      <div className="gamepad-module" id="mod-lb-p2">
        <button
          className="bumper-btn"
          id="btn-lb-p2"
          onPointerDown={(e) => { e.preventDefault(); handleButtonDown('LB'); }}
          onPointerUp={(e) => { e.preventDefault(); handleButtonUp('LB'); }}
          onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('LB'); }}
        >
          LB
        </button>
      </div>

      {/* Top Center Telemetry & Settings Stack */}
      <div className="gamepad-module tactical-center-badge-stack" id="mod-slot-ping-p2">
        <button
          className="nut-btn borderless-logo-btn"
          id="btn-settings-logo-p2"
          title="Switch Layout Preset"
          onClick={onOpenSettings}
        >
          <img src="/logo.png" alt="Settings" className="clean-settings-logo" />
        </button>
        <div
          className="tactical-sub-badge"
          id="tactical-sub-badge-p2"
          onClick={cyclePreferredSlot}
          title="Tap to switch slot"
        >
          <span className="slot-badge-text" id="slot-text-p2">P{playerSlot}</span>
          <span className="ping-badge-text" id="ping-text-p2">{rtt ? `${rtt}ms` : '0ms'}</span>
        </div>
      </div>

      {/* Right Bumper (RB) */}
      <div className="gamepad-module" id="mod-rb-p2">
        <button
          className="bumper-btn"
          id="btn-rb-p2"
          onPointerDown={(e) => { e.preventDefault(); handleButtonDown('RB'); }}
          onPointerUp={(e) => { e.preventDefault(); handleButtonUp('RB'); }}
          onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('RB'); }}
        >
          RB
        </button>
      </div>

      {/* 45° Chamfered Right Trigger (RT) */}
      <div
        className="gamepad-module"
        id="mod-rt-p2"
        onPointerDown={(e) => {
          e.preventDefault();
          handleTriggerDown('RT');
          if (rtFillRef.current) rtFillRef.current.style.height = '100%';
        }}
        onPointerUp={(e) => {
          e.preventDefault();
          handleTriggerUp('RT');
          if (rtFillRef.current) rtFillRef.current.style.height = '0%';
        }}
        onPointerCancel={(e) => {
          e.preventDefault();
          handleTriggerUp('RT');
          if (rtFillRef.current) rtFillRef.current.style.height = '0%';
        }}
      >
        <svg className="trigger-svg" viewBox="0 0 200 138" preserveAspectRatio="none">
          <path className="trigger-path" d="M 2,2 L 198,2 L 198,136 L 60,136 L 2,75 Z" />
        </svg>
        <div className="trigger-inner" id="rt-trigger-p2">
          <div className="trigger-level-fill" id="rt-fill-p2" ref={rtFillRef} />
          <span className="mod-label trigger-lbl">RT</span>
        </div>
      </div>

      {/* ====================================================================
          2. SUB-ROW: ANGLED WEDGES (BACK & START)
          ==================================================================== */}
      <div className="gamepad-module tactical-back-module" id="mod-back-p2">
        <button
          className="wedge-btn angled-back-btn"
          id="btn-back-p2"
          onPointerDown={(e) => { e.preventDefault(); handleButtonDown('BACK'); }}
          onPointerUp={(e) => { e.preventDefault(); handleButtonUp('BACK'); }}
          onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('BACK'); }}
        >
          BACK
        </button>
      </div>

      <div className="gamepad-module tactical-start-module" id="mod-start-p2">
        <button
          className="wedge-btn angled-start-btn"
          id="btn-start-p2"
          onPointerDown={(e) => { e.preventDefault(); handleButtonDown('START'); }}
          onPointerUp={(e) => { e.preventDefault(); handleButtonUp('START'); }}
          onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('START'); }}
        >
          START
        </button>
      </div>

      {/* ====================================================================
          3. CENTER: PANORAMIC GYRO FLIGHT ATTITUDE HUD
          ==================================================================== */}
      <GyroScreen
        className="tactical-center-gyro"
        gyroEnabled={gyroEnabled}
        rawAngle={rawAngle}
        accel={accel}
        onToggleGyro={toggleGyro}
      />

      {/* ====================================================================
          4. LEFT WING: ASYMMETRIC STICK (TOP) + TACTICAL SUB-DPAD (BOTTOM)
          ==================================================================== */}
      <div className="gamepad-module tactical-left-thumb-zone" id="mod-left-wing-p2">
        {/* Upper Zone: Primary Ergonomic Thumbstick */}
        <div className="p2-left-deck-top">
          <div
            className="p2-stick-anchor"
            id="left-stick-anchor-p2"
            onPointerDown={(e) => {
              e.preventDefault();
              updateLeftStickFromPointer(e.clientX, e.clientY, leftBaseRef.current, leftPuckRef.current);
            }}
            onPointerMove={(e) => {
              if (e.buttons > 0) {
                e.preventDefault();
                updateLeftStickFromPointer(e.clientX, e.clientY, leftBaseRef.current, leftPuckRef.current);
              }
            }}
            onPointerUp={(e) => {
              e.preventDefault();
              releaseLeftStick(leftPuckRef.current);
            }}
            onPointerCancel={(e) => {
              e.preventDefault();
              releaseLeftStick(leftPuckRef.current);
            }}
          >
            <div className="stick-base-ring tactical-base-ring" id="left-stick-base-p2" ref={leftBaseRef}>
              <div className="stick-puck-puck red-puck" id="left-stick-puck-p2" ref={leftPuckRef}>
                <div className="puck-center-pip" />
              </div>
            </div>
          </div>
        </div>

        {/* Lower Zone: Tactical Sub-Deck D-Pad */}
        <div className="p2-left-deck-bottom">
          <div className="p2-tactical-dpad">
            <button
              className="p2-dpad-mini-btn"
              id="dpad-left-p2"
              onPointerDown={(e) => { e.preventDefault(); handleButtonDown('DPAD_LEFT'); }}
              onPointerUp={(e) => { e.preventDefault(); handleButtonUp('DPAD_LEFT'); }}
              onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('DPAD_LEFT'); }}
            >
              ◀
            </button>
            <button
              className="p2-dpad-mini-btn"
              id="dpad-up-p2"
              onPointerDown={(e) => { e.preventDefault(); handleButtonDown('DPAD_UP'); }}
              onPointerUp={(e) => { e.preventDefault(); handleButtonUp('DPAD_UP'); }}
              onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('DPAD_UP'); }}
            >
              ▲
            </button>
            <button
              className="p2-dpad-mini-btn"
              id="dpad-down-p2"
              onPointerDown={(e) => { e.preventDefault(); handleButtonDown('DPAD_DOWN'); }}
              onPointerUp={(e) => { e.preventDefault(); handleButtonUp('DPAD_DOWN'); }}
              onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('DPAD_DOWN'); }}
            >
              ▼
            </button>
            <button
              className="p2-dpad-mini-btn"
              id="dpad-right-p2"
              onPointerDown={(e) => { e.preventDefault(); handleButtonDown('DPAD_RIGHT'); }}
              onPointerUp={(e) => { e.preventDefault(); handleButtonUp('DPAD_RIGHT'); }}
              onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('DPAD_RIGHT'); }}
            >
              ▶
            </button>
          </div>
        </div>
      </div>

      {/* ====================================================================
          5. OFFSET MID-RIGHT THUMBSTICK (GENEROUS CLEARANCE, ZERO CLASH)
          ==================================================================== */}
      <div className="gamepad-module mid-right-stick-module" id="mod-right-stick-p2">
        <div
          className="stick-anchor"
          id="right-stick-anchor-p2"
          onPointerDown={(e) => {
            e.preventDefault();
            updateRightStickFromPointer(e.clientX, e.clientY, rightBaseRef.current, rightPuckRef.current);
          }}
          onPointerMove={(e) => {
            if (e.buttons > 0) {
              e.preventDefault();
              updateRightStickFromPointer(e.clientX, e.clientY, rightBaseRef.current, rightPuckRef.current);
            }
          }}
          onPointerUp={(e) => {
            e.preventDefault();
            releaseRightStick(rightPuckRef.current);
          }}
          onPointerCancel={(e) => {
            e.preventDefault();
            releaseRightStick(rightPuckRef.current);
          }}
        >
          <div className="stick-base-ring tactical-base-ring" id="right-stick-base-p2" ref={rightBaseRef}>
            <div className="stick-puck-puck red-puck" id="right-stick-puck-p2" ref={rightPuckRef}>
              <div className="puck-center-pip" />
            </div>
          </div>
        </div>
      </div>

      {/* ====================================================================
          6. INTERLOCKING POLYGON ACTION CLUSTER (Y, X, A, B)
          ==================================================================== */}
      <div className="gamepad-module tactical-right-cluster" id="mod-right-wing-p2">
        {/* Y Button: Top Angled Facet */}
        <div className="poly-btn-wrap poly-wrap-y">
          <button
            className="poly-btn"
            id="btn-y-p2"
            data-btn="Y"
            onPointerDown={(e) => { e.preventDefault(); handleButtonDown('Y'); }}
            onPointerUp={(e) => { e.preventDefault(); handleButtonUp('Y'); }}
            onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('Y'); }}
          >
            <svg className="poly-svg" viewBox="0 0 100 80" preserveAspectRatio="none">
              <polygon points="25,4 96,4 96,76 4,76" className="poly-shape" />
            </svg>
            <span className="poly-label letter-y">Y</span>
          </button>
        </div>

        {/* X Button: Bottom-Left Facet */}
        <div className="poly-btn-wrap poly-wrap-x">
          <button
            className="poly-btn"
            id="btn-x-p2"
            data-btn="X"
            onPointerDown={(e) => { e.preventDefault(); handleButtonDown('X'); }}
            onPointerUp={(e) => { e.preventDefault(); handleButtonUp('X'); }}
            onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('X'); }}
          >
            <svg className="poly-svg" viewBox="0 0 80 80" preserveAspectRatio="none">
              <polygon points="4,4 76,4 76,76 20,76" className="poly-shape" />
            </svg>
            <span className="poly-label letter-x">X</span>
          </button>
        </div>

        {/* A Button: Bottom-Mid Facet */}
        <div className="poly-btn-wrap poly-wrap-a">
          <button
            className="poly-btn"
            id="btn-a-p2"
            data-btn="A"
            onPointerDown={(e) => { e.preventDefault(); handleButtonDown('A'); }}
            onPointerUp={(e) => { e.preventDefault(); handleButtonUp('A'); }}
            onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('A'); }}
          >
            <svg className="poly-svg" viewBox="0 0 80 80" preserveAspectRatio="none">
              <polygon points="4,4 76,4 76,56 56,76 4,76" className="poly-shape" />
            </svg>
            <span className="poly-label letter-a">A</span>
          </button>
        </div>

        {/* B Button: Elongated Right Flank Plate */}
        <div className="poly-btn-wrap poly-wrap-b">
          <button
            className="poly-btn"
            id="btn-b-p2"
            data-btn="B"
            onPointerDown={(e) => { e.preventDefault(); handleButtonDown('B'); }}
            onPointerUp={(e) => { e.preventDefault(); handleButtonUp('B'); }}
            onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('B'); }}
          >
            <svg className="poly-svg" viewBox="0 0 60 180" preserveAspectRatio="none">
              <polygon points="4,4 56,4 56,176 35,176 4,75" className="poly-shape" />
            </svg>
            <span className="poly-label letter-b">B</span>
          </button>
        </div>
      </div>
    </div>
  );
}