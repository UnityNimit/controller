import React, { useRef } from 'react';
import GyroScreen from './GyroScreen';
import VisualizerScreen from './VisualizerScreen';

export default function Preset1({
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
    hapticsEngine,
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
    <div className="preset-container preset-1-layout" id="gamepad-frame">
      <style>{`
        /* ==========================================================================
           PRESET 1 DUAL-DECK ERGONOMIC ENGINE (ZERO-OVERLAP ARCHITECTURE)
           ========================================================================== */
        .wing-deck-top {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          height: 48%;
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 10;
        }

        .wing-deck-divider {
          position: absolute;
          top: 48%;
          left: 8%;
          right: 8%;
          height: 1px;
          background: linear-gradient(90deg, transparent 0%, rgba(255, 255, 255, 0.12) 50%, transparent 100%);
          pointer-events: none;
        }

        .wing-deck-bottom {
          position: absolute;
          bottom: 0;
          left: 0;
          right: 0;
          height: 52%;
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 20;
        }

        /* Tactical D-Pad Crosshair Assembly */
        .tactical-dpad-grid {
          position: relative;
          width: 84px;
          height: 84px;
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          grid-template-rows: repeat(3, 1fr);
          gap: 2px;
        }

        .dpad-btn {
          background: rgba(255, 255, 255, 0.04);
          border: 1px solid rgba(255, 255, 255, 0.14);
          color: rgba(255, 255, 255, 0.7);
          font-family: var(--font-hud);
          font-size: 11px;
          font-weight: 900;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          touch-action: none;
          transition: all 0.06s ease;
        }

        .dpad-btn:active, .dpad-btn.active {
          background: #ffffff !important;
          color: #000000 !important;
          border-color: #ffffff !important;
          box-shadow: 0 0 14px rgba(255, 255, 255, 0.6);
        }

        .dpad-btn-up    { grid-column: 2; grid-row: 1; border-radius: 4px 4px 1px 1px; }
        .dpad-btn-left  { grid-column: 1; grid-row: 2; border-radius: 4px 1px 1px 4px; }
        .dpad-hub-pip   { grid-column: 2; grid-row: 2; background: rgba(0, 0, 0, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 2px; }
        .dpad-btn-right { grid-column: 3; grid-row: 2; border-radius: 1px 4px 4px 1fr; }
        .dpad-btn-down  { grid-column: 2; grid-row: 3; border-radius: 1px 1px 4px 4px; }

        /* Tactical ABXY Diamond Assembly */
        .tactical-abxy-diamond {
          position: relative;
          width: 86px;
          height: 86px;
        }

        .abxy-btn {
          position: absolute;
          width: 27px;
          height: 27px;
          border-radius: 50%;
          background: rgba(255, 255, 255, 0.04);
          border: 1px solid rgba(255, 255, 255, 0.16);
          color: #ffffff;
          font-family: var(--font-hud);
          font-size: 13px;
          font-weight: 900;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          touch-action: none;
          box-shadow: 0 2px 6px rgba(0, 0, 0, 0.5);
          transition: all 0.06s ease;
        }

        .abxy-btn:active, .abxy-btn.active {
          background: #ffffff !important;
          color: #000000 !important;
          border-color: #ffffff !important;
          box-shadow: 0 0 16px rgba(255, 255, 255, 0.7);
          transform: scale(0.94);
        }

        .abxy-btn-y { top: 0; left: 50%; transform: translateX(-50%); }
        .abxy-btn-x { top: 50%; left: 0; transform: translateY(-50%); }
        .abxy-btn-b { top: 50%; right: 0; transform: translateY(-50%); }
        .abxy-btn-a { bottom: 0; left: 50%; transform: translateX(-50%); }

        /* Centered Anchors inside Deck Bottom */
        .wing-deck-bottom .stick-anchor {
          position: relative;
          top: auto;
          left: auto;
          transform: none;
          width: 68px;
          height: 68px;
        }
      `}</style>

      {/* ====================================================================
          1. TOP ROW: LT, LB, P1/PING TELEMETRY, RB, RT
          ==================================================================== */}
      {/* Left Trigger (LT) */}
      <div
        className="gamepad-module"
        id="mod-lt"
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
          <path className="trigger-path" d="M 2,2 L 198,2 L 198,75 L 142,136 L 2,136 Z" />
        </svg>
        <div className="trigger-inner" id="lt-trigger">
          <div className="trigger-level-fill" id="lt-fill" ref={ltFillRef} />
          <span className="mod-label trigger-lbl">LT</span>
        </div>
      </div>

      {/* Left Bumper (LB) */}
      <div className="gamepad-module" id="mod-lb">
        <button
          className="bumper-btn"
          id="btn-lb"
          onPointerDown={(e) => { e.preventDefault(); handleButtonDown('LB'); }}
          onPointerUp={(e) => { e.preventDefault(); handleButtonUp('LB'); }}
          onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('LB'); }}
        >
          LB
        </button>
      </div>

      {/* Center Telemetry Capsule: Slot & Ping */}
      <div
        className="gamepad-module"
        id="mod-slot-ping"
        title="Tap to switch player slot"
        onClick={cyclePreferredSlot}
      >
        <div className="slot-badge-text" id="slot-text">P{playerSlot}</div>
        <div className="ping-badge-text" id="ping-text">{rtt ? `${rtt}ms` : '0ms'}</div>
      </div>

      {/* Right Bumper (RB) */}
      <div className="gamepad-module" id="mod-rb">
        <button
          className="bumper-btn"
          id="btn-rb"
          onPointerDown={(e) => { e.preventDefault(); handleButtonDown('RB'); }}
          onPointerUp={(e) => { e.preventDefault(); handleButtonUp('RB'); }}
          onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('RB'); }}
        >
          RB
        </button>
      </div>

      {/* Right Trigger (RT) */}
      <div
        className="gamepad-module"
        id="mod-rt"
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
          <path className="trigger-path" d="M 2,2 L 198,2 L 198,136 L 58,136 L 2,75 Z" />
        </svg>
        <div className="trigger-inner" id="rt-trigger">
          <div className="trigger-level-fill" id="rt-fill" ref={rtFillRef} />
          <span className="mod-label trigger-lbl">RT</span>
        </div>
      </div>

      {/* ====================================================================
          2. SUB-ROW: BACK, FLIGHT ATTITUDE GYRO HUD, START
          ==================================================================== */}
      <div className="gamepad-module" id="mod-back">
        <button
          className="wedge-btn"
          id="btn-back"
          onPointerDown={(e) => { e.preventDefault(); handleButtonDown('BACK'); }}
          onPointerUp={(e) => { e.preventDefault(); handleButtonUp('BACK'); }}
          onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('BACK'); }}
        >
          BACK
        </button>
      </div>

      <GyroScreen
        gyroEnabled={gyroEnabled}
        rawAngle={rawAngle}
        accel={accel}
        onToggleGyro={toggleGyro}
      />

      <div className="gamepad-module" id="mod-start">
        <button
          className="wedge-btn"
          id="btn-start"
          onPointerDown={(e) => { e.preventDefault(); handleButtonDown('START'); }}
          onPointerUp={(e) => { e.preventDefault(); handleButtonUp('START'); }}
          onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('START'); }}
        >
          START
        </button>
      </div>

      {/* ====================================================================
          3. SETTINGS LOGO CAPSULE (Clean Milled Monolith, Borderless)
          ==================================================================== */}
      <div
        className="gamepad-module"
        id="mod-settings-nut"
        title="Switch Layout Preset"
        onClick={onOpenSettings}
      >
        <button className="nut-btn borderless-logo-btn" id="btn-settings-logo">
          <img src="/logo.png" alt="Settings" className="clean-settings-logo" />
        </button>
      </div>

      {/* ====================================================================
          4. AUDIO SPECTRUM & HAPTIC OSCILLOSCOPE SCREEN
          ==================================================================== */}
      <VisualizerScreen hapticsEngine={hapticsEngine} />

      {/* ====================================================================
          5. LEFT WING: TACTICAL D-PAD (TOP) + LEFT STICK (BOTTOM)
          ==================================================================== */}
      <div className="gamepad-module wing-arena" id="mod-left-wing">
        {/* Upper Action Deck: Precision D-Pad */}
        <div className="wing-deck-top">
          <div className="tactical-dpad-grid" id="left-dpad-cluster">
            <button
              className="dpad-btn dpad-btn-up"
              id="dpad-up"
              onPointerDown={(e) => { e.preventDefault(); handleButtonDown('DPAD_UP'); }}
              onPointerUp={(e) => { e.preventDefault(); handleButtonUp('DPAD_UP'); }}
              onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('DPAD_UP'); }}
            >
              ▲
            </button>
            <button
              className="dpad-btn dpad-btn-left"
              id="dpad-left"
              onPointerDown={(e) => { e.preventDefault(); handleButtonDown('DPAD_LEFT'); }}
              onPointerUp={(e) => { e.preventDefault(); handleButtonUp('DPAD_LEFT'); }}
              onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('DPAD_LEFT'); }}
            >
              ◀
            </button>
            <div className="dpad-hub-pip" />
            <button
              className="dpad-btn dpad-btn-right"
              id="dpad-right"
              onPointerDown={(e) => { e.preventDefault(); handleButtonDown('DPAD_RIGHT'); }}
              onPointerUp={(e) => { e.preventDefault(); handleButtonUp('DPAD_RIGHT'); }}
              onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('DPAD_RIGHT'); }}
            >
              ▶
            </button>
            <button
              className="dpad-btn dpad-btn-down"
              id="dpad-down"
              onPointerDown={(e) => { e.preventDefault(); handleButtonDown('DPAD_DOWN'); }}
              onPointerUp={(e) => { e.preventDefault(); handleButtonUp('DPAD_DOWN'); }}
              onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('DPAD_DOWN'); }}
            >
              ▼
            </button>
          </div>
        </div>

        <div className="wing-deck-divider" />

        {/* Lower Sweep Deck: Milled Left Thumbstick Well */}
        <div className="wing-deck-bottom">
          <div
            className="stick-anchor"
            id="left-stick-anchor"
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
            <div className="stick-base-ring" id="left-stick-base" ref={leftBaseRef}>
              <div className="stick-puck-puck red-puck" id="left-stick-puck" ref={leftPuckRef}>
                <div className="puck-center-pip" />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ====================================================================
          6. RIGHT WING: ABXY DIAMOND (TOP) + RIGHT STICK (BOTTOM)
          ==================================================================== */}
      <div className="gamepad-module wing-arena" id="mod-right-wing">
        {/* Upper Action Deck: Precision ABXY Diamond */}
        <div className="wing-deck-top">
          <div className="tactical-abxy-diamond" id="right-abxy-cluster">
            <button
              className="abxy-btn abxy-btn-y"
              id="btn-y"
              onPointerDown={(e) => { e.preventDefault(); handleButtonDown('Y'); }}
              onPointerUp={(e) => { e.preventDefault(); handleButtonUp('Y'); }}
              onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('Y'); }}
            >
              Y
            </button>
            <button
              className="abxy-btn abxy-btn-x"
              id="btn-x"
              onPointerDown={(e) => { e.preventDefault(); handleButtonDown('X'); }}
              onPointerUp={(e) => { e.preventDefault(); handleButtonUp('X'); }}
              onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('X'); }}
            >
              X
            </button>
            <button
              className="abxy-btn abxy-btn-b"
              id="btn-b"
              onPointerDown={(e) => { e.preventDefault(); handleButtonDown('B'); }}
              onPointerUp={(e) => { e.preventDefault(); handleButtonUp('B'); }}
              onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('B'); }}
            >
              B
            </button>
            <button
              className="abxy-btn abxy-btn-a"
              id="btn-a"
              onPointerDown={(e) => { e.preventDefault(); handleButtonDown('A'); }}
              onPointerUp={(e) => { e.preventDefault(); handleButtonUp('A'); }}
              onPointerCancel={(e) => { e.preventDefault(); handleButtonUp('A'); }}
            >
              A
            </button>
          </div>
        </div>

        <div className="wing-deck-divider" />

        {/* Lower Sweep Deck: Milled Right Thumbstick Well with RS Click */}
        <div className="wing-deck-bottom">
          <div
            className="stick-anchor"
            id="right-stick-anchor"
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
            <div className="stick-base-ring" id="right-stick-base" ref={rightBaseRef}>
              <div className="stick-puck-puck red-puck" id="right-stick-puck" ref={rightPuckRef}>
                <div className="puck-center-pip" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}