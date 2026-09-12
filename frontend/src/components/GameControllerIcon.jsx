import React from 'react';

/**
 * GameControllerIcon: Precision vector SVG icon of a modern game controller.
 * Monochromatic esports styling with clean lines, D-pad, action buttons, and analog sticks.
 */
export default function GameControllerIcon({ className = '', size = 28, active = false }) {
  return (
    <svg
      className={`game-controller-icon ${active ? 'active' : ''} ${className}`}
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{
        display: 'inline-block',
        verticalAlign: 'middle',
        transition: 'all 0.15s cubic-bezier(0.2, 0.8, 0.2, 1)'
      }}
    >
      {/* Gamepad Outer Shell */}
      <path
        d="M 12 12 
           C 16 12, 18 15, 24 15 
           C 30 15, 32 12, 36 12 
           C 42 12, 45 16, 44 26 
           C 43.3 33, 40 40, 36 40 
           C 32.5 40, 31 34, 29 34 
           C 27 34, 26 36, 24 36 
           C 22 36, 21 34, 19 34 
           C 17 34, 15.5 40, 12 40 
           C 8 40, 4.7 33, 4 26 
           C 3 16, 6 12, 12 12 Z"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill={active ? 'rgba(255, 255, 255, 0.18)' : 'rgba(255, 255, 255, 0.04)'}
      />

      {/* Shoulder Triggers / Bumpers Hints */}
      <path
        d="M 11 10 C 13 8, 17 8, 19 9"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path
        d="M 29 9 C 31 8, 35 8, 37 10"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />

      {/* D-Pad (Left Side) */}
      <path
        d="M 14 18 V 26 M 10 22 H 18"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
      />

      {/* ABXY Action Buttons (Right Side 4-pip diamond) */}
      <circle cx="34" cy="18.5" r="1.3" fill="currentColor" />
      <circle cx="37.5" cy="22" r="1.3" fill="currentColor" />
      <circle cx="30.5" cy="22" r="1.3" fill="currentColor" />
      <circle cx="34" cy="25.5" r="1.3" fill="currentColor" />

      {/* Dual Analog Thumbsticks */}
      <circle
        cx="19"
        cy="28.5"
        r="2.8"
        stroke="currentColor"
        strokeWidth="1.8"
        fill={active ? 'currentColor' : 'none'}
      />
      <circle
        cx="29"
        cy="28.5"
        r="2.8"
        stroke="currentColor"
        strokeWidth="1.8"
        fill={active ? 'currentColor' : 'none'}
      />

      {/* Center Home / Select Pips */}
      <circle cx="21.5" cy="20" r="0.9" fill="currentColor" />
      <circle cx="26.5" cy="20" r="0.9" fill="currentColor" />
    </svg>
  );
}
