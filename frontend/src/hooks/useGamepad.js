import { useState, useEffect, useRef, useCallback } from 'react';
import { SecurityClient } from '../utils/security_client';
import { HapticEngine } from '../utils/haptics';

/**
 * useGamepad: Ultra-low latency 120Hz cyber-physical gamepad input pipeline.
 * Features zero-render stick polling, multi-touch arbitration, and IMU telemetry.
 */
export function useGamepad() {
  const [connected, setConnected] = useState(false);
  const [playerSlot, setPlayerSlot] = useState(1);
  const [rtt, setRtt] = useState(0);
  const [preset, setPresetState] = useState(() => {
    return localStorage.getItem('controller_preset') || 'preset1';
  });
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [engaged, setEngaged] = useState(false);
  const [gyroEnabled, setGyroEnabled] = useState(false);
  const [rawAngle, setRawAngle] = useState(0.0);
  const [accel, setAccel] = useState({ x: 0, y: 0, z: 9.8 });
  const [isRotated, setIsRotated] = useState(false);
  const [hapticsEnabled, setHapticsEnabled] = useState(true);

  // Non-rendering mutable refs for 0ms latency input execution
  const wsRef = useRef(null);
  const seqRef = useRef(0);
  const securityRef = useRef(new SecurityClient());
  const hapticsRef = useRef(new HapticEngine());
  const zeroOffsetRef = useRef(0.0);

  const buttonsRef = useRef({
    A: false,
    B: false,
    X: false,
    Y: false,
    LB: false,
    RB: false,
    RS: false,
    LS: false,
    START: false,
    BACK: false,
    DPAD_UP: false,
    DPAD_DOWN: false,
    DPAD_LEFT: false,
    DPAD_RIGHT: false
  });

  const analogRef = useRef({
    throttle: 0.0,
    brake: 0.0,
    stickX: 0,
    stickY: 0,
    rightStickX: 0,
    rightStickY: 0
  });

  const pointerRegistries = useRef({
    leftStickPointerId: null,
    leftStickActive: false,
    rightStickPointerId: null,
    rightStickActive: false,
    rightStickMoved: false,
    rightStickStartTime: 0
  });

  const isRotatedRef = useRef(false);
  const gyroEnabledRef = useRef(false);
  const rawAngleRef = useRef(0.0);
  const accelRef = useRef({ x: 0, y: 0, z: 9.8 });
  const rttRef = useRef(0);

  // Layout preset switcher with instant physical haptic feedback
  const setPreset = useCallback((newPreset) => {
    setPresetState(newPreset);
    localStorage.setItem('controller_preset', newPreset);
    hapticsRef.current.triggerClick('heavy');
  }, []);

  // Send input packet over WebSocket immediately
  const sendInputNow = useCallback((isCritical = false) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    const now = performance.now();
    seqRef.current++;

    const reg = pointerRegistries.current;
    const manualStickActive =
      reg.leftStickActive ||
      Math.abs(analogRef.current.stickX) > 400 ||
      Math.abs(analogRef.current.stickY) > 400;

    const effectiveGyro = gyroEnabledRef.current && !manualStickActive;
    const effectiveAngle = effectiveGyro
      ? rawAngleRef.current - zeroOffsetRef.current
      : 0.0;
    const effectiveStickX = effectiveGyro ? 0 : analogRef.current.stickX;

    const packet = {
      type: 'INPUT',
      seq: seqRef.current,
      ts: now,
      gyro_enabled: effectiveGyro,
      angle: effectiveAngle,
      stick_x: effectiveStickX,
      stick_y: analogRef.current.stickY,
      right_stick_x: analogRef.current.rightStickX,
      right_stick_y: analogRef.current.rightStickY,
      throttle: analogRef.current.throttle,
      brake: analogRef.current.brake,
      accel: accelRef.current,
      rtt: rttRef.current || 0,
      buttons: { ...buttonsRef.current }
    };

    try {
      ws.send(JSON.stringify(packet));
    } catch (_) {}
  }, []);

  // Coordinate transformation for forced-landscape mobile orientations
  const getGamepadPoint = useCallback((clientX, clientY) => {
    if (isRotatedRef.current) {
      return {
        x: clientY,
        y: window.innerWidth - clientX
      };
    }
    return { x: clientX, y: clientY };
  }, []);

  const getGamepadCenter = useCallback(
    (element) => {
      if (!element) return { x: 0, y: 0 };
      const rect = element.getBoundingClientRect();
      const screenCenterX = rect.left + rect.width / 2;
      const screenCenterY = rect.top + rect.height / 2;
      return getGamepadPoint(screenCenterX, screenCenterY);
    },
    [getGamepadPoint]
  );

  // Viewport orientation detection
  const checkOrientation = useCallback(() => {
    const isPortrait =
      typeof window !== 'undefined' && window.innerHeight > window.innerWidth;
    setIsRotated(isPortrait);
    isRotatedRef.current = isPortrait;
    if (typeof document !== 'undefined' && document.body) {
      document.body.classList.toggle('forced-landscape-portrait', isPortrait);
    }
  }, []);

  useEffect(() => {
    checkOrientation();
    window.addEventListener('resize', checkOrientation);
    window.addEventListener('orientationchange', checkOrientation);
    return () => {
      window.removeEventListener('resize', checkOrientation);
      window.removeEventListener('orientationchange', checkOrientation);
    };
  }, [checkOrientation]);

  // Gyro toggling & zero-calibration
  const toggleGyro = useCallback(() => {
    const next = !gyroEnabledRef.current;
    gyroEnabledRef.current = next;
    setGyroEnabled(next);
    hapticsRef.current.triggerClick('normal');
    sendInputNow(true);
  }, [sendInputNow]);

  const zeroGyro = useCallback(() => {
    const angle = rawAngleRef.current;
    zeroOffsetRef.current = angle;
    hapticsRef.current.triggerClick('heavy');
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'CALIBRATE', angle }));
    }
  }, []);

  // Cycle player slot (P1 -> P2 -> P3 -> P4)
  const cyclePreferredSlot = useCallback(() => {
    const nextSlot = (playerSlot % 4) + 1;
    setPlayerSlot(nextSlot);
    localStorage.setItem('controller_preferred_slot', nextSlot.toString());
    hapticsRef.current.triggerClick('heavy');
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }
  }, [playerSlot]);

  // WebSocket connection & cryptographic challenge-response
  const connect = useCallback(() => {
    if (typeof window === 'undefined') return;
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host || '127.0.0.1:8080';
    const url = `${proto}//${host}/ws`;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        // Connected to gateway
      };

      ws.onmessage = async (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'AUTH_CHALLENGE') {
            const authResponse = await securityRef.current.solveChallenge(
              msg.nonce,
              msg.timestamp
            );
            const prefSlot = localStorage.getItem('controller_preferred_slot');
            if (prefSlot) {
              authResponse.preferred_slot = parseInt(prefSlot, 10);
            }
            ws.send(JSON.stringify(authResponse));
          } else if (msg.type === 'AUTH_SUCCESS') {
            setConnected(true);
            setPlayerSlot(msg.player_slot);
            sendInputNow(true);
          } else if (msg.type === 'SLOT_REASSIGNED') {
            setPlayerSlot(msg.player_slot);
            hapticsRef.current.triggerClick('heavy');
          } else if (msg.type === 'RUMBLE') {
            hapticsRef.current.handleRumble(msg.large, msg.small);
          } else if (msg.type === 'TELEMETRY') {
            if (msg.haptics?.slip_rumble) hapticsRef.current.triggerSlip();
            if (msg.haptics?.impact_spike) hapticsRef.current.triggerImpact();
            if (msg.haptics?.redline_alert) hapticsRef.current.triggerRedline();
          } else if (msg.type === 'PONG') {
            const now = performance.now();
            const calculatedRtt = Math.round(now - msg.ts);
            rttRef.current = calculatedRtt;
            setRtt(calculatedRtt);
          }
        } catch (_) {}
      };

      ws.onclose = () => {
        setConnected(false);
        setRtt(0);
        rttRef.current = 0;
        setTimeout(() => {
          if (engaged) connect();
        }, 1500);
      };
    } catch (_) {}
  }, [engaged, sendInputNow]);

  // Motion sensor tracking (IMU)
  const attachMotionSensors = useCallback(() => {
    if (typeof window === 'undefined') return;

    window.addEventListener(
      'deviceorientation',
      (e) => {
        const orientation =
          window.orientation ||
          (window.screen.orientation ? window.screen.orientation.angle : 0);
        let angle = 0;
        if (orientation === 90) {
          angle = -e.beta;
        } else if (orientation === -90) {
          angle = e.beta;
        } else {
          angle = e.gamma || 0;
        }
        rawAngleRef.current = angle;
        setRawAngle(angle);
      },
      { passive: true }
    );

    window.addEventListener(
      'devicemotion',
      (e) => {
        if (e.accelerationIncludingGravity) {
          const nextAccel = {
            x: e.accelerationIncludingGravity.x || 0,
            y: e.accelerationIncludingGravity.y || 0,
            z: e.accelerationIncludingGravity.z || 9.8
          };
          accelRef.current = nextAccel;
          setAccel(nextAccel);
        }
      },
      { passive: true }
    );
  }, []);

  // Full-screen, orientation lock & sensor engagement
  const engage = useCallback(async () => {
    setEngaged(true);

    const el = document.documentElement;
    try {
      if (!document.fullscreenElement && !document.webkitFullscreenElement) {
        if (el.requestFullscreen) {
          await el.requestFullscreen().catch(() => {});
        } else if (el.webkitRequestFullscreen) {
          el.webkitRequestFullscreen();
        }
      }
    } catch (_) {}
    window.scrollTo(0, 1);

    try {
      if (window.screen.orientation && window.screen.orientation.lock) {
        await window.screen.orientation.lock('landscape').catch(() => {});
      }
    } catch (_) {}
    checkOrientation();

    if (
      typeof DeviceOrientationEvent !== 'undefined' &&
      typeof DeviceOrientationEvent.requestPermission === 'function'
    ) {
      try {
        await DeviceOrientationEvent.requestPermission();
      } catch (_) {}
    }

    try {
      if ('wakeLock' in navigator) {
        await navigator.wakeLock.request('screen');
      }
    } catch (_) {}

    hapticsRef.current.initAudio();
    attachMotionSensors();
    connect();
  }, [attachMotionSensors, checkOrientation, connect]);

  // High-frequency 120Hz polling loop
  useEffect(() => {
    if (!engaged) return;
    let lastPing = performance.now();
    const interval = setInterval(() => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;

      const now = performance.now();
      const reg = pointerRegistries.current;
      if (
        reg.leftStickActive ||
        reg.rightStickActive ||
        analogRef.current.throttle > 0 ||
        analogRef.current.brake > 0 ||
        gyroEnabledRef.current
      ) {
        sendInputNow();
      }

      if (now - lastPing >= 1000) {
        lastPing = now;
        ws.send(JSON.stringify({ type: 'PING', ts: now }));
      }
    }, 1000 / 120);

    return () => clearInterval(interval);
  }, [engaged, sendInputNow]);

  // Instant pointer button actuation
  const handleButtonDown = useCallback(
    (key) => {
      buttonsRef.current[key] = true;
      hapticsRef.current.triggerClick(
        key.startsWith('DPAD') ? 'dpad' : 'normal'
      );
      sendInputNow(true);
    },
    [sendInputNow]
  );

  const handleButtonUp = useCallback(
    (key) => {
      buttonsRef.current[key] = false;
      sendInputNow(true);
    },
    [sendInputNow]
  );

  // Linear trigger controls
  const handleTriggerDown = useCallback(
    (triggerKey) => {
      if (triggerKey === 'LT') {
        analogRef.current.brake = 1.0;
      } else {
        analogRef.current.throttle = 1.0;
      }
      hapticsRef.current.triggerClick('heavy');
      sendInputNow(true);
    },
    [sendInputNow]
  );

  const handleTriggerUp = useCallback(
    (triggerKey) => {
      if (triggerKey === 'LT') {
        analogRef.current.brake = 0.0;
      } else {
        analogRef.current.throttle = 0.0;
      }
      sendInputNow(true);
      setTimeout(() => sendInputNow(true), 16);
    },
    [sendInputNow]
  );

  // Left Thumbstick engine (sub-pixel radial deadzone & clamping)
  const updateLeftStickFromPointer = useCallback(
    (clientX, clientY, baseEl, puckEl) => {
      pointerRegistries.current.leftStickActive = true;
      const pt = getGamepadPoint(clientX, clientY);
      const center = getGamepadCenter(baseEl);
      const dx = pt.x - center.x;
      const dy = pt.y - center.y;
      const maxRadius = 32;
      const dist = Math.hypot(dx, dy);

      let visualDx = dx;
      let visualDy = dy;
      if (dist > maxRadius) {
        visualDx = (dx / dist) * maxRadius;
        visualDy = (dy / dist) * maxRadius;
      }

      if (puckEl) {
        puckEl.style.transform = `translate3d(${visualDx}px, ${visualDy}px, 0)`;
      }

      const deadzone = 0.08;
      const normDist = Math.min(1.0, dist / maxRadius);

      if (normDist < deadzone) {
        analogRef.current.stickX = 0;
        analogRef.current.stickY = 0;
      } else {
        const linearScale = (normDist - deadzone) / (1.0 - deadzone);
        const angleRad = Math.atan2(-dy, dx);
        analogRef.current.stickX = Math.round(
          Math.cos(angleRad) * linearScale * 32767
        );
        analogRef.current.stickY = Math.round(
          Math.sin(angleRad) * linearScale * 32767
        );
      }
      sendInputNow();
    },
    [getGamepadCenter, getGamepadPoint, sendInputNow]
  );

  const releaseLeftStick = useCallback(
    (puckEl) => {
      pointerRegistries.current.leftStickActive = false;
      pointerRegistries.current.leftStickPointerId = null;
      analogRef.current.stickX = 0;
      analogRef.current.stickY = 0;
      if (puckEl) {
        puckEl.style.transform = 'translate3d(0px, 0px, 0)';
      }
      sendInputNow(true);
      setTimeout(() => sendInputNow(true), 16);
    },
    [sendInputNow]
  );

  // Right Thumbstick engine (tap-to-RS click & radial aim)
  const updateRightStickFromPointer = useCallback(
    (clientX, clientY, baseEl, puckEl) => {
      if (!pointerRegistries.current.rightStickActive) {
        pointerRegistries.current.rightStickActive = true;
        pointerRegistries.current.rightStickMoved = false;
        pointerRegistries.current.rightStickStartTime = performance.now();
      }

      const pt = getGamepadPoint(clientX, clientY);
      const center = getGamepadCenter(baseEl);
      const dx = pt.x - center.x;
      const dy = pt.y - center.y;
      const maxRadius = 32;
      const dist = Math.hypot(dx, dy);

      if (dist > 5) {
        pointerRegistries.current.rightStickMoved = true;
      }

      let visualDx = dx;
      let visualDy = dy;
      if (dist > maxRadius) {
        visualDx = (dx / dist) * maxRadius;
        visualDy = (dy / dist) * maxRadius;
      }

      if (puckEl) {
        puckEl.style.transform = `translate3d(${visualDx}px, ${visualDy}px, 0)`;
      }

      const deadzone = 0.06;
      const normDist = Math.min(1.0, dist / maxRadius);

      if (normDist < deadzone) {
        analogRef.current.rightStickX = 0;
        analogRef.current.rightStickY = 0;
      } else {
        const linearScale = (normDist - deadzone) / (1.0 - deadzone);
        const angleRad = Math.atan2(-dy, dx);
        analogRef.current.rightStickX = Math.round(
          Math.cos(angleRad) * linearScale * 32767
        );
        analogRef.current.rightStickY = Math.round(
          Math.sin(angleRad) * linearScale * 32767
        );
      }
      sendInputNow();
    },
    [getGamepadCenter, getGamepadPoint, sendInputNow]
  );

  const releaseRightStick = useCallback(
    (puckEl) => {
      const duration =
        performance.now() - pointerRegistries.current.rightStickStartTime;
      if (!pointerRegistries.current.rightStickMoved && duration < 250) {
        // Tap without drag triggers Right Stick (RS / R3) click
        buttonsRef.current.RS = true;
        hapticsRef.current.triggerClick('heavy');
        sendInputNow(true);
        setTimeout(() => {
          buttonsRef.current.RS = false;
          sendInputNow(true);
        }, 80);
      }

      pointerRegistries.current.rightStickActive = false;
      pointerRegistries.current.rightStickPointerId = null;
      analogRef.current.rightStickX = 0;
      analogRef.current.rightStickY = 0;
      if (puckEl) {
        puckEl.style.transform = 'translate3d(0px, 0px, 0)';
      }
      sendInputNow(true);
      setTimeout(() => sendInputNow(true), 16);
    },
    [sendInputNow]
  );

  // Global blur / visibility change reset
  useEffect(() => {
    const handleReset = () => {
      for (const k in buttonsRef.current) buttonsRef.current[k] = false;
      analogRef.current.throttle = 0;
      analogRef.current.brake = 0;
      analogRef.current.stickX = 0;
      analogRef.current.stickY = 0;
      analogRef.current.rightStickX = 0;
      analogRef.current.rightStickY = 0;
      pointerRegistries.current.leftStickActive = false;
      pointerRegistries.current.rightStickActive = false;
      sendInputNow(true);
    };

    window.addEventListener('blur', handleReset);
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) handleReset();
    });
    return () => {
      window.removeEventListener('blur', handleReset);
    };
  }, [sendInputNow]);

  return {
    connected,
    playerSlot,
    rtt,
    preset,
    setPreset,
    settingsOpen,
    setSettingsOpen,
    engaged,
    engage,
    gyroEnabled,
    rawAngle,
    accel,
    toggleGyro,
    zeroGyro,
    cyclePreferredSlot,
    hapticsEngine: hapticsRef.current,
    hapticsEnabled,
    setHapticsEnabled,
    pointerRegistries,
    buttonsRef,
    analogRef,
    handleButtonDown,
    handleButtonUp,
    handleTriggerDown,
    handleTriggerUp,
    updateLeftStickFromPointer,
    releaseLeftStick,
    updateRightStickFromPointer,
    releaseRightStick,
    sendInputNow
  };
}