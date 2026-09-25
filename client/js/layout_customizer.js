/**
 * Project Controller - Dedicated Layout 1 Customization Engine
 * Handles drag-and-drop repositioning, corner handle resizing, analog stick travel radius,
 * and localStorage persistence.
 */

class GamepadLayoutCustomizer {
  constructor(options = {}) {
    this.frame = options.frame || null;
    this.getGamepadPoint = options.getGamepadPoint || ((x, y) => ({ x, y }));
    this.triggerHaptic = options.triggerHaptic || (() => {});
    this.onModeChange = options.onModeChange || null;

    this.isCustomizing = false;
    this.config = {};
    this.stickRadius = { left: 40, right: 40 };
    this.activeRadiusPopupStick = null;

    this._activeDrag = null;
    this._initialized = false;
  }

  init(frameEl) {
    if (frameEl) this.frame = frameEl;
    if (!this.frame) {
      this.frame = document.getElementById("gamepad-frame");
    }
    this.loadConfig();
    this._bindEvents();
    this._initialized = true;
  }

  toggleMode() {
    this.isCustomizing = !this.isCustomizing;
    this.triggerHaptic("heavy");

    const frame = this.frame || document.getElementById("gamepad-frame");
    if (frame) {
      frame.classList.toggle("customizing-mode", this.isCustomizing);
    }

    if (this.isCustomizing) {
      this.closeRadiusPopup();
    } else {
      this.closeRadiusPopup();
      this.saveConfig();
    }

    if (this.onModeChange) {
      this.onModeChange(this.isCustomizing);
    }

    return this.isCustomizing;
  }

  _bindEvents() {
    const frame = this.frame || document.getElementById("gamepad-frame");
    if (!frame) return;

    const getCustomElement = (target) => {
      if (!target || !target.closest) return null;
      return target.closest("[data-custom-id]");
    };

    const getResizeHandle = (target) => {
      if (!target || !target.closest) return null;
      return target.closest(".l1-resize-handle");
    };

    frame.addEventListener("pointerdown", (e) => {
      if (!this.isCustomizing) return;
      if (e.target.closest(".l1-custom-hud") || e.target.closest(".l1-radius-popup") || e.target.closest("#btn-settings-logo")) {
        return;
      }

      const resizeHandle = getResizeHandle(e.target);
      if (resizeHandle) {
        e.preventDefault();
        e.stopPropagation();
        const targetId = resizeHandle.dataset.target;
        const targetEl = document.querySelector(`[data-custom-id="${targetId}"]`);
        if (!targetEl) return;

        const cfg = this._getElemConfig(targetId);
        const pt = this.getGamepadPoint(e.clientX, e.clientY);
        this._activeDrag = {
          id: targetId,
          el: targetEl,
          startX: pt.x,
          startY: pt.y,
          origDx: cfg.dx,
          origDy: cfg.dy,
          origScale: cfg.s,
          isResize: true,
          moved: false
        };
        return;
      }

      const customEl = getCustomElement(e.target);
      if (customEl) {
        e.preventDefault();
        e.stopPropagation();
        const targetId = customEl.dataset.customId;
        const cfg = this._getElemConfig(targetId);
        const pt = this.getGamepadPoint(e.clientX, e.clientY);

        this._activeDrag = {
          id: targetId,
          el: customEl,
          startX: pt.x,
          startY: pt.y,
          origDx: cfg.dx,
          origDy: cfg.dy,
          origScale: cfg.s,
          isResize: false,
          moved: false
        };
      }
    }, { passive: false });

    window.addEventListener("pointermove", (e) => {
      if (!this.isCustomizing || !this._activeDrag) return;
      e.preventDefault();

      const pt = this.getGamepadPoint(e.clientX, e.clientY);
      const dx = pt.x - this._activeDrag.startX;
      const dy = pt.y - this._activeDrag.startY;
      if (Math.hypot(dx, dy) > 6) {
        this._activeDrag.moved = true;
      }

      if (this._activeDrag.isResize) {
        const delta = (dx + dy) / 2;
        const isZone = this._activeDrag.id.endsWith("-zone");
        const scaleChange = delta / (isZone ? 140 : 110);
        const minScale = isZone ? 0.35 : 0.60;
        const maxScale = isZone ? 2.50 : 1.85;
        const newScale = Math.max(minScale, Math.min(maxScale, this._activeDrag.origScale + scaleChange));
        this._setElemScale(this._activeDrag.id, newScale);
      } else {
        const newDx = this._activeDrag.origDx + dx;
        const newDy = this._activeDrag.origDy + dy;
        this._setElemTranslate(this._activeDrag.id, newDx, newDy);
      }
    }, { passive: false });

    window.addEventListener("pointerup", () => {
      if (!this.isCustomizing || !this._activeDrag) return;

      if (!this._activeDrag.isResize && !this._activeDrag.moved) {
        if (this._activeDrag.id === "left-stick-anchor") {
          this.openRadiusPopup("left", this._activeDrag.el);
        } else if (this._activeDrag.id === "right-stick-anchor") {
          this.openRadiusPopup("right", this._activeDrag.el);
        }
      }

      this._activeDrag = null;
    });

    // Dedicated Tap-to-Open Slider Listeners for Joysticks
    const setupStickTap = (anchorId, stickSide) => {
      const anchorEl = document.getElementById(anchorId);
      if (!anchorEl) return;
      let downTime = 0;
      let startX = 0, startY = 0;
      anchorEl.addEventListener("pointerdown", (e) => {
        if (!this.isCustomizing) return;
        if (e.target.closest(".l1-resize-handle")) return;
        downTime = performance.now();
        startX = e.clientX;
        startY = e.clientY;
      });
      anchorEl.addEventListener("pointerup", (e) => {
        if (!this.isCustomizing || !downTime) return;
        if (e.target.closest(".l1-resize-handle")) return;
        const dist = Math.hypot(e.clientX - startX, e.clientY - startY);
        const elapsed = performance.now() - downTime;
        downTime = 0;
        if (dist < 12 && elapsed < 450) {
          this.openRadiusPopup(stickSide, anchorEl);
        }
      });
    };
    setupStickTap("left-stick-anchor", "left");
    setupStickTap("right-stick-anchor", "right");

    // Joystick Radius Slider Event
    const slider = document.getElementById("l1-radius-slider");
    if (slider) {
      const handleSliderChange = (e) => {
        const val = parseInt(e.target.value, 10);
        if (this.activeRadiusPopupStick) {
          this.stickRadius[this.activeRadiusPopupStick] = val;
          const valLabel = document.getElementById("l1-radius-val");
          if (valLabel) valLabel.textContent = `${val}px`;

          const previewRing = document.getElementById(`${this.activeRadiusPopupStick}-stick-radius-preview`);
          if (previewRing) {
            previewRing.style.width = `${val * 2}px`;
            previewRing.style.height = `${val * 2}px`;
          }
          this.triggerHaptic("dpad");
        }
      };
      slider.addEventListener("input", handleSliderChange);
      slider.addEventListener("change", handleSliderChange);
    }

    // Close Button on Radius Slider Popup
    const closeBtn = document.getElementById("l1-radius-close-btn");
    if (closeBtn) {
      closeBtn.addEventListener("click", (e) => {
        if (e) { e.preventDefault(); e.stopPropagation(); }
        this.closeRadiusPopup();
      });
    }

    // Reset Defaults Button
    const resetBtn = document.getElementById("l1-reset-btn");
    if (resetBtn) {
      resetBtn.addEventListener("click", (e) => {
        if (e) { e.preventDefault(); e.stopPropagation(); }
        this.resetDefaults();
      });
    }

    // Test Vibration & Haptics Button
    const vibeTestBtn = document.getElementById("l1-test-vibe-btn");
    if (vibeTestBtn) {
      vibeTestBtn.addEventListener("click", (e) => {
        if (e) { e.preventDefault(); e.stopPropagation(); }
        if (window.hapticEngine) {
          window.hapticEngine.testHapticPulse();
        } else if (window.gamepadClient && window.gamepadClient.haptics) {
          window.gamepadClient.haptics.testHapticPulse();
        }
      });
    }
  }

  openRadiusPopup(stick, anchorEl) {
    this.activeRadiusPopupStick = stick;
    const popup = document.getElementById("l1-radius-popup");
    const title = document.getElementById("l1-radius-title");
    const valLabel = document.getElementById("l1-radius-val");
    const slider = document.getElementById("l1-radius-slider");
    if (!popup || !anchorEl) return;

    const currentR = this.stickRadius[stick] || 40;
    if (title) title.textContent = `${stick.toUpperCase()} STICK DRAG RADIUS`;
    if (valLabel) valLabel.textContent = `${currentR}px`;
    if (slider) {
      slider.min = "20";
      slider.max = "85";
      slider.value = currentR;
    }

    const frame = this.frame || document.getElementById("gamepad-frame");
    let localX = anchorEl.offsetLeft;
    let localY = anchorEl.offsetTop;
    let parent = anchorEl.offsetParent;
    while (parent && parent !== frame) {
      localX += parent.offsetLeft;
      localY += parent.offsetTop;
      parent = parent.offsetParent;
    }

    const frameW = frame ? (frame.clientWidth || 907) : 907;
    const frameH = frame ? (frame.clientHeight || 400) : 400;

    let top = localY - 95;
    if (top < 15) top = localY + (anchorEl.clientHeight || 140) + 12;
    top = Math.max(15, Math.min(frameH - 120, top));

    let left = localX - 25;
    if (left + 235 > frameW) left = frameW - 245;
    left = Math.max(15, left);

    popup.style.top = `${top}px`;
    popup.style.left = `${left}px`;
    popup.classList.add("active");
    this.triggerHaptic("normal");
  }

  closeRadiusPopup() {
    this.activeRadiusPopupStick = null;
    const popup = document.getElementById("l1-radius-popup");
    if (popup) popup.classList.remove("active");
  }

  _ensureConfig() {
    if (!this.config) {
      this.config = {};
    }
  }

  _getElemConfig(id) {
    this._ensureConfig();
    if (!this.config[id]) {
      this.config[id] = { dx: 0, dy: 0, s: 1.0 };
    }
    return this.config[id];
  }

  _applyElemTransform(id) {
    const el = document.querySelector(`[data-custom-id="${id}"]`);
    if (!el) return;
    const cfg = this._getElemConfig(id);
    el.style.setProperty("--l1-dx", `${cfg.dx}px`);
    el.style.setProperty("--l1-dy", `${cfg.dy}px`);
    el.style.setProperty("--l1-s", `${cfg.s}`);
    el.style.transform = `translate(var(--l1-dx, ${cfg.dx}px), var(--l1-dy, ${cfg.dy}px)) scale(calc(var(--l1-s, ${cfg.s}) * var(--l1-press, 1)))`;
  }

  _setElemTranslate(id, dx, dy) {
    const cfg = this._getElemConfig(id);
    cfg.dx = Math.round(dx);
    cfg.dy = Math.round(dy);
    this._applyElemTransform(id);
  }

  _setElemScale(id, s) {
    const cfg = this._getElemConfig(id);
    cfg.s = parseFloat(s.toFixed(2));
    this._applyElemTransform(id);
  }

  saveConfig() {
    try {
      const data = {
        elements: this.config || {},
        stickRadius: this.stickRadius || { left: 40, right: 40 }
      };
      localStorage.setItem("controller_layout1_custom_config", JSON.stringify(data));
      this.triggerHaptic("heavy");
    } catch (_) {}
  }

  loadConfig() {
    try {
      const raw = localStorage.getItem("controller_layout1_custom_config");
      if (raw) {
        const data = JSON.parse(raw);
        if (data.elements) {
          this.config = data.elements;
          Object.keys(this.config).forEach((id) => {
            this._applyElemTransform(id);
          });
        }
        if (data.stickRadius) {
          this.stickRadius = {
            left: data.stickRadius.left || 40,
            right: data.stickRadius.right || 40
          };
          const leftRing = document.getElementById("left-stick-radius-preview");
          if (leftRing) {
            leftRing.style.width = `${this.stickRadius.left * 2}px`;
            leftRing.style.height = `${this.stickRadius.left * 2}px`;
          }
          const rightRing = document.getElementById("right-stick-radius-preview");
          if (rightRing) {
            rightRing.style.width = `${this.stickRadius.right * 2}px`;
            rightRing.style.height = `${this.stickRadius.right * 2}px`;
          }
        }
      }
    } catch (_) {}
  }

  resetDefaults() {
    try {
      localStorage.removeItem("controller_layout1_custom_config");
      this.config = {};
      this.stickRadius = { left: 40, right: 40 };

      document.querySelectorAll("[data-custom-id]").forEach((el) => {
        el.style.transform = "";
        el.style.removeProperty("--l1-dx");
        el.style.removeProperty("--l1-dy");
        el.style.removeProperty("--l1-s");
      });

      const leftRing = document.getElementById("left-stick-radius-preview");
      if (leftRing) {
        leftRing.style.width = "80px";
        leftRing.style.height = "80px";
      }
      const rightRing = document.getElementById("right-stick-radius-preview");
      if (rightRing) {
        rightRing.style.width = "80px";
        rightRing.style.height = "80px";
      }

      this.closeRadiusPopup();
      this.triggerHaptic("heavy");
    } catch (_) {}
  }
}

if (typeof window !== "undefined") {
  window.GamepadLayoutCustomizer = GamepadLayoutCustomizer;
}
if (typeof module !== "undefined" && module.exports) {
  module.exports = { GamepadLayoutCustomizer };
}
