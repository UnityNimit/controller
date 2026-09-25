/**
 * Project Controller - High-Frequency Mobile Touch Digitizer Ingestion Engine (Pillar 3)
 * Unleashes the full hardware scanning capability of smartphone touchscreens (120Hz – 480Hz+ digitizers).
 * Uses 'pointerrawupdate' to bypass mobile browser VSYNC / frame render clamping,
 * and extracts all sub-millisecond micro-samples via 'getCoalescedEvents()'.
 */

class TouchDigitizerEngine {
  constructor(options = {}) {
    this.target = options.target || (typeof window !== "undefined" ? window : null);
    this.onSample = options.onSample || null;
    this.onDown = options.onDown || null;
    this.onUp = options.onUp || null;
    this.onCancel = options.onCancel || null;

    // Feature detection
    this.hasPointerRawUpdate = false;
    if (typeof window !== "undefined") {
      this.hasPointerRawUpdate = ("onpointerrawupdate" in window) ||
                                 ("onpointerrawupdate" in document.documentElement);
    }

    this.isRunning = false;
    this._lastSampleTime = new Map(); // pointerId -> timestamp
    this._sampleCounter = 0;
    this._sampleRate = 0;
    this._coalescedCount = 0;
    this._lastRateCalcTime = 0;

    // Bound listeners
    this._onPointerRawUpdateBound = this._handleRawUpdate.bind(this);
    this._onPointerMoveBound = this._handlePointerMove.bind(this);
    this._onPointerDownBound = this._handlePointerDown.bind(this);
    this._onPointerUpBound = this._handlePointerUp.bind(this);
    this._onPointerCancelBound = this._handlePointerCancel.bind(this);
  }

  get isRawUpdateSupported() {
    return this.hasPointerRawUpdate;
  }

  get sampleRateHz() {
    return this._sampleRate;
  }

  get totalCoalescedEvents() {
    return this._coalescedCount;
  }

  start() {
    if (this.isRunning || !this.target) return;
    this.isRunning = true;
    this._lastRateCalcTime = performance.now();

    const opts = { passive: false };

    // 1. Hook pointerrawupdate if supported (Blink/Chromium/Edge/Android WebView)
    if (this.hasPointerRawUpdate) {
      this.target.addEventListener("pointerrawupdate", this._onPointerRawUpdateBound, opts);
    }

    // 2. Hook pointermove as fallback (WebKit/Safari) or complementary stream
    this.target.addEventListener("pointermove", this._onPointerMoveBound, opts);

    // 3. Pointer lifecycle events
    this.target.addEventListener("pointerdown", this._onPointerDownBound, opts);
    this.target.addEventListener("pointerup", this._onPointerUpBound, { passive: true });
    this.target.addEventListener("pointercancel", this._onPointerCancelBound, { passive: true });
  }

  stop() {
    if (!this.isRunning || !this.target) return;
    this.isRunning = false;

    if (this.hasPointerRawUpdate) {
      this.target.removeEventListener("pointerrawupdate", this._onPointerRawUpdateBound);
    }
    this.target.removeEventListener("pointermove", this._onPointerMoveBound);
    this.target.removeEventListener("pointerdown", this._onPointerDownBound);
    this.target.removeEventListener("pointerup", this._onPointerUpBound);
    this.target.removeEventListener("pointercancel", this._onPointerCancelBound);
    this._lastSampleTime.clear();
  }

  _handleRawUpdate(e) {
    if (!this.isRunning) return;
    this._extractAndDispatch(e, true);
  }

  _handlePointerMove(e) {
    if (!this.isRunning) return;
    // If pointerrawupdate is active and fired recently for this pointer, skip duplicate move
    if (this.hasPointerRawUpdate) {
      const lastT = this._lastSampleTime.get(e.pointerId);
      if (lastT !== undefined && (e.timeStamp - lastT) < 0.25) {
        return;
      }
    }
    this._extractAndDispatch(e, false);
  }

  _extractAndDispatch(e, isRaw) {
    // Unpack coalesced events if available
    let coalesced = null;
    try {
      if (typeof e.getCoalescedEvents === "function") {
        coalesced = e.getCoalescedEvents();
      }
    } catch (_) {
      coalesced = null;
    }

    if (coalesced && coalesced.length > 0) {
      this._coalescedCount += (coalesced.length - 1);
      for (let i = 0; i < coalesced.length; i++) {
        const ce = coalesced[i];
        this._dispatchSample(ce, isRaw, true, e);
      }
    } else {
      this._dispatchSample(e, isRaw, false, e);
    }
  }

  _dispatchSample(eventObj, isRaw, isCoalesced, rootEvent) {
    const pId = eventObj.pointerId;
    const t = eventObj.timeStamp || performance.now();
    this._lastSampleTime.set(pId, t);
    this._sampleCounter++;

    // Rolling rate calculation (1 Hz update)
    const now = performance.now();
    if (now - this._lastRateCalcTime >= 1000) {
      this._sampleRate = Math.round((this._sampleCounter * 1000) / (now - this._lastRateCalcTime));
      this._sampleCounter = 0;
      this._lastRateCalcTime = now;
    }

    if (this.onSample) {
      this.onSample({
        pointerId: pId,
        clientX: eventObj.clientX,
        clientY: eventObj.clientY,
        pressure: (eventObj.pressure && eventObj.pressure > 0.01) ? eventObj.pressure : 1.0,
        timeStamp: t,
        pointerType: eventObj.pointerType || "touch",
        isRaw: isRaw,
        isCoalesced: isCoalesced,
        originalEvent: rootEvent,
        preventDefault: () => {
          try { if (rootEvent && rootEvent.preventDefault) rootEvent.preventDefault(); } catch (_) {}
        }
      });
    }
  }

  _handlePointerDown(e) {
    if (!this.isRunning) return;
    const t = e.timeStamp || performance.now();
    this._lastSampleTime.set(e.pointerId, t);

    if (this.onDown) {
      this.onDown({
        pointerId: e.pointerId,
        clientX: e.clientX,
        clientY: e.clientY,
        pressure: (e.pressure && e.pressure > 0.01) ? e.pressure : 1.0,
        timeStamp: t,
        pointerType: e.pointerType || "touch",
        originalEvent: e,
        preventDefault: () => {
          try { if (e && e.preventDefault) e.preventDefault(); } catch (_) {}
        }
      });
    }
  }

  _handlePointerUp(e) {
    if (!this.isRunning) return;
    this._lastSampleTime.delete(e.pointerId);

    if (this.onUp) {
      this.onUp({
        pointerId: e.pointerId,
        clientX: e.clientX,
        clientY: e.clientY,
        timeStamp: e.timeStamp || performance.now(),
        pointerType: e.pointerType || "touch",
        originalEvent: e
      });
    }
  }

  _handlePointerCancel(e) {
    if (!this.isRunning) return;
    this._lastSampleTime.delete(e.pointerId);

    if (this.onCancel) {
      this.onCancel({
        pointerId: e.pointerId,
        clientX: e.clientX,
        clientY: e.clientY,
        timeStamp: e.timeStamp || performance.now(),
        pointerType: e.pointerType || "touch",
        originalEvent: e
      });
    }
  }
}

if (typeof window !== "undefined") {
  window.TouchDigitizerEngine = TouchDigitizerEngine;
}
if (typeof module !== "undefined" && module.exports) {
  module.exports = { TouchDigitizerEngine };
}
