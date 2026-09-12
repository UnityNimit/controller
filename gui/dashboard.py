"""
Project Controller - Ultra-Minimalist Tactical Telemetry HUD
High-frequency real-time vector oscilloscopes, continuous 60FPS rolling sweep,
live multi-controller visualizer, and dark-mode pairing QR code.
"""

import os
import sys
import time
import queue
import logging
import ctypes
import webbrowser
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
import qrcode

from gui.state_bridge import TelemetryBridge, ControllerSlotState

# Monochrome Tactical Palette (Minimalist High-Contrast Obsidian)
COLOR_BG = "#08090b"            # Deep obsidian canvas
COLOR_CARD = "#0d1015"          # Dark charcoal card surface
COLOR_CARD_BORDER = "#1c2128"   # Crisp subtle border
COLOR_CARD_ACTIVE = "#ffffff"   # High-contrast active card border
COLOR_SURFACE = "#161b22"       # Interactive widget surface
COLOR_SURFACE_HOVER = "#21262d" # Interactive hover surface
COLOR_SURFACE_ACTIVE = "#30363d"# Pressed surface
COLOR_TEXT_PRIMARY = "#f0f6fc"   # Crisp white primary text
COLOR_TEXT_SECONDARY = "#c9d1d9" # Clear secondary text
COLOR_TEXT_MUTED = "#6e7681"     # Muted metadata
COLOR_TEXT_DIM = "#484f58"       # Inactive dim labels

# Monochrome Grayscale Trace Hierarchy
COLOR_WHITE = "#ffffff"         # Primary trace / Active state
COLOR_SILVER = "#d1d5db"        # Secondary trace
COLOR_SLATE = "#9ca3af"         # Tertiary trace
COLOR_PEWTER = "#6b7280"        # Quaternary trace

# Aliases for clean monochrome compatibility
COLOR_CYAN = COLOR_WHITE
COLOR_EMERALD = COLOR_WHITE
COLOR_AMBER = COLOR_SILVER
COLOR_CRIMSON = COLOR_WHITE
COLOR_MAGENTA = COLOR_SLATE
COLOR_PURPLE = COLOR_PEWTER
COLOR_AZURE = COLOR_SILVER


def get_logo_path() -> Optional[Path]:
    """Resolves logo.png across runtime environments (dev workspace, PyInstaller _MEIPASS, or exe dir)."""
    candidates = []
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
        candidates.append(base / "gui" / "logo.png")
        candidates.append(base / "logo.png")
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "gui" / "logo.png")
        candidates.append(exe_dir / "logo.png")

    candidates.append(Path(__file__).resolve().parent / "logo.png")
    candidates.append(Path.cwd() / "gui" / "logo.png")
    candidates.append(Path.cwd() / "logo.png")

    for p in candidates:
        if p.exists() and p.stat().st_size > 0:
            return p
    return None


_LOGO_CACHE: Dict[Tuple[int, int], ctk.CTkImage] = {}


def get_logo_ctk_image(size: Tuple[int, int] = (32, 32)) -> Optional[ctk.CTkImage]:
    """Loads, resizes, and caches logo.png as a CustomTkinter CTkImage."""
    if size in _LOGO_CACHE:
        return _LOGO_CACHE[size]
    p = get_logo_path()
    if not p:
        return None
    try:
        pil_img = Image.open(str(p)).convert("RGBA")
        pil_img = pil_img.resize(size, Image.LANCZOS)
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
        _LOGO_CACHE[size] = ctk_img
        return ctk_img
    except Exception as e:
        logger.debug(f"Failed to load logo image: {e}")
        return None


def get_logo_ico_path() -> Optional[Path]:
    """Resolves logo.ico across runtime environments."""
    candidates = []
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
        candidates.append(base / "gui" / "logo.ico")
        candidates.append(base / "logo.ico")
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "gui" / "logo.ico")
        candidates.append(exe_dir / "logo.ico")

    candidates.append(Path(__file__).resolve().parent / "logo.ico")
    candidates.append(Path.cwd() / "gui" / "logo.ico")
    candidates.append(Path.cwd() / "logo.ico")

    for p in candidates:
        if p.exists() and p.stat().st_size > 0:
            return p
    return None


def set_window_logo_icon(window: tk.Tk) -> None:
    """Sets the native OS window & taskbar icon to logo.ico and logo.png with perfection."""
    # 1. Native Windows Win32 iconbitmap (sets titlebar icon and taskbar icon cleanly)
    ico_p = get_logo_ico_path()
    if ico_p:
        try:
            window.iconbitmap(default=str(ico_p))
        except Exception:
            try:
                window.iconbitmap(str(ico_p))
            except Exception as e:
                logger.debug(f"iconbitmap failed: {e}")

    # 2. iconphoto using PNG as multi-platform high-DPI support
    p = get_logo_path()
    if p:
        try:
            pil_img = Image.open(str(p))
            photo = ImageTk.PhotoImage(pil_img)
            window.iconphoto(False, photo)
            window._logo_photo = photo
        except Exception as e:
            logger.debug(f"Failed to set window icon: {e}")


def should_show_terms_on_startup() -> bool:
    """Checks if the user has opted out of seeing the Terms dialog on startup."""
    try:
        config_path = Path.cwd() / ".controller_config.json"
        if not config_path.exists():
            config_path = Path.home() / ".project_controller_config.json"
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            if data.get("accepted_terms", False) and data.get("dont_show_terms", False):
                return False
    except Exception:
        pass
    return True


def save_terms_preference(dont_show: bool) -> None:
    """Persists the user's terms acceptance and startup modal preference."""
    try:
        config_path = Path.cwd() / ".controller_config.json"
        data = {"accepted_terms": True, "dont_show_terms": dont_show, "version": "1.0.0"}
        config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.debug(f"Could not save terms config: {e}")


def get_bundled_driver_msi() -> Optional[Path]:
    """Locates or downloads the official ViGEmBus installer MSI."""
    candidates = []
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
        candidates.append(base / "ViGEmBusSetup_x64.msi")
        candidates.append(base / "scripts" / "ViGEmBusSetup_x64.msi")
        candidates.append(base / "vgamepad" / "win" / "vigem" / "install" / "x64" / "ViGEmBusSetup_x64.msi")
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "ViGEmBusSetup_x64.msi")
        candidates.append(exe_dir / "scripts" / "ViGEmBusSetup_x64.msi")

    try:
        import vgamepad
        vg_dir = Path(vgamepad.__file__).parent
        candidates.append(vg_dir / "win" / "vigem" / "install" / "x64" / "ViGEmBusSetup_x64.msi")
    except Exception:
        pass

    candidates.append(Path.cwd() / "scripts" / "ViGEmBusSetup_x64.msi")
    candidates.append(Path.cwd() / "ViGEmBusSetup_x64.msi")

    import tempfile
    temp_msi = Path(tempfile.gettempdir()) / "ViGEmBusSetup_x64.msi"
    candidates.append(temp_msi)

    for p in candidates:
        if p.exists() and p.stat().st_size > 100000:
            return p

    # Download official signed release directly to temp if missing from distribution
    try:
        import urllib.request
        url = "https://github.com/nefarius/ViGEmBus/releases/download/v1.22.0/ViGEmBusSetup_x64.msi"
        urllib.request.urlretrieve(url, str(temp_msi))
        if temp_msi.exists() and temp_msi.stat().st_size > 100000:
            return temp_msi
    except Exception:
        pass

    return None


class TermsDialog(ctk.CTkToplevel):
    """
    Sleek Monochrome Terms & Conditions and Community Support Modal Dialog.
    Displays project branding, logo, terms of service, architecture summary,
    GitHub link, and Buy Me a Coffee donation link.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Controller // Terms & Conditions")
        self.geometry("620x540")
        self.minsize(540, 460)
        self.configure(fg_color=COLOR_BG)
        self.transient(parent)
        set_window_logo_icon(self)

        # Center dialog over parent
        try:
            self.update_idletasks()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            px = parent.winfo_x()
            py = parent.winfo_y()
            w = 620
            h = 540
            x = max(0, px + (pw - w) // 2)
            y = max(0, py + (ph - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

        # Header Container
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 6))

        # Centered Logo
        logo_img = get_logo_ctk_image((60, 60))
        if logo_img:
            lbl_logo = ctk.CTkLabel(header, image=logo_img, text="")
            lbl_logo.pack(pady=(0, 4))

        lbl_title = ctk.CTkLabel(
            header,
            text="Controller",
            font=ctk.CTkFont(family="Consolas", size=15, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        lbl_title.pack()

        lbl_sub = ctk.CTkLabel(
            header,
            text="Ultra-Low Latency Cyber-Physical Teleoperation Framework • v1.0.0",
            font=ctk.CTkFont(family="Consolas", size=9),
            text_color=COLOR_TEXT_MUTED
        )
        lbl_sub.pack(pady=(2, 0))

        # Scrollable Terms & Architecture Box
        terms_box = ctk.CTkTextbox(
            self,
            fg_color=COLOR_CARD,
            border_color=COLOR_CARD_BORDER,
            border_width=1,
            text_color=COLOR_TEXT_SECONDARY,
            font=ctk.CTkFont(family="Consolas", size=10),
            corner_radius=6,
            wrap="word"
        )
        terms_box.pack(fill="both", expand=True, padx=20, pady=8)

        terms_content = (
            "=======================================================================\n"
            " CONTROLLER v1.0.0 - TERMS OF USE, DISCLAIMER & ARCHITECTURE\n"
            "=======================================================================\n\n"
            "1. OPEN-SOURCE LICENSE & AS-IS USAGE:\n"
            "   Controller is provided 'AS IS' without warranty of any kind,\n"
            "   express or implied. In no event shall the author or contributors be\n"
            "   liable for any claim, damages, hardware failures, or other liability\n"
            "   arising from the use or misuse of this software.\n\n"
            "2. RECREATIONAL & RESEARCH INTENT:\n"
            "   This software is designed strictly for personal gaming, simulation\n"
            "   teleoperation (e.g. Assetto Corsa, Rocket League, FIFA, Forza, GTA),\n"
            "   and cyber-physical academic research. Non-commercial use only.\n\n"
            "3. KERNEL-LEVEL VIRTUAL GAMEPAD EMULATION:\n"
            "   Virtual Xbox 360 controller hardware interrupts are generated via the\n"
            "   official ViGEmBus kernel driver. Administrative elevation (UAC) is\n"
            "   requested only once during driver installation.\n\n"
            "4. LOCAL PRIVATE NETWORK SAFETY:\n"
            "   All teleoperation streams and sensor telemetry packets are transmitted\n"
            "   strictly within your local private Wi-Fi network with HMAC-SHA256\n"
            "   handshake authentication. Zero telemetric data or telemetry packets\n"
            "   are ever collected or transmitted to external servers or cloud services.\n\n"
            "5. HIGH-PERFORMANCE ARCHITECTURE FEATURES:\n"
            "   - 1000Hz Peak Teleoperation Pipeline with sub-millisecond dispatch\n"
            "   - Esports Hair-Triggers: Instant 100% actuation and strict 0.0 zero-state\n"
            "     release with redundant UDP burst protection (no floating values)\n"
            "   - Adaptive Menu Cadence Engine: Directional flicks (<160ms) emit a calibrated\n"
            "     75ms impulse for crisp 1-step list navigation (FIFA, Steam, Rocket League)\n"
            "   - Closed-Loop Bi-Directional Dual-Motor Force-Feedback Haptics\n"
            "   - 4-Player Local Split-Screen Multiplayer with Atomic Host Slot Swapping\n\n"
            "Thank you for playing and supporting Controller!\n"
        )
        terms_box.insert("1.0", terms_content)
        terms_box.configure(state="disabled")

        # Links & Community Row
        links_frame = ctk.CTkFrame(self, fg_color="transparent")
        links_frame.pack(fill="x", padx=20, pady=(2, 6))

        btn_github = ctk.CTkButton(
            links_frame,
            text="🐙 GITHUB REPO",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            fg_color=COLOR_SURFACE,
            hover_color=COLOR_SURFACE_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_CARD_BORDER,
            border_width=1,
            height=28,
            command=lambda: webbrowser.open("https://github.com/UnityNimit/controller")
        )
        btn_github.pack(side="left", fill="x", expand=True, padx=(0, 6))

        btn_coffee = ctk.CTkButton(
            links_frame,
            text="☕ BUY ME A COFFEE / DONATE",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            fg_color=COLOR_SURFACE,
            hover_color=COLOR_SURFACE_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_CARD_BORDER,
            border_width=1,
            height=28,
            command=lambda: webbrowser.open("https://buymeacoffee.com/unitynimit")
        )
        btn_coffee.pack(side="right", fill="x", expand=True, padx=(6, 0))

        # Bottom Bar: Do not show on startup Checkbox + Accept Button
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=20, pady=(4, 16))

        self.chk_dont_show = ctk.CTkCheckBox(
            bottom_frame,
            text="Do not show on startup",
            font=ctk.CTkFont(family="Consolas", size=9),
            text_color=COLOR_TEXT_MUTED,
            fg_color="#30363d",
            hover_color="#484f58",
            border_color=COLOR_CARD_BORDER,
            checkmark_color="#ffffff"
        )
        self.chk_dont_show.pack(side="left")

        btn_accept = ctk.CTkButton(
            bottom_frame,
            text="ACCEPT & CONTINUE",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            fg_color="#f0f6fc",
            hover_color="#ffffff",
            text_color="#08090b",
            height=30,
            width=160,
            corner_radius=4,
            command=self._on_accept
        )
        btn_accept.pack(side="right")

        self.grab_set()

    def _on_accept(self) -> None:
        dont_show = bool(self.chk_dont_show.get())
        save_terms_preference(dont_show)
        self.grab_release()
        self.destroy()


class MinimalOscilloscope(ctk.CTkFrame):
    """
    High-Performance Continuous-Sweep Oscilloscope.
    Always rolls continuously at 50-60 FPS, with cached coords() updates.
    """
    def __init__(
        self,
        master,
        title: str,
        unit: str = "ms",
        height: int = 115,
        min_val: float = 0.0,
        max_val: float = 50.0,
        grid_steps: int = 3,
        traces: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color=COLOR_CARD, border_color=COLOR_CARD_BORDER, border_width=1, corner_radius=6, **kwargs)
        self.title = title
        self.unit = unit
        self.canvas_height = height
        self.min_val = min_val
        self.max_val = max_val
        self.grid_steps = grid_steps
        self._last_readout: str = ""

        # Top Bar: Title & Value Readout
        self.top_bar = ctk.CTkFrame(self, fg_color="transparent", height=24)
        self.top_bar.pack(fill="x", padx=10, pady=(4, 0))

        self.lbl_title = ctk.CTkLabel(
            self.top_bar,
            text=self.title.upper(),
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            text_color=COLOR_TEXT_SECONDARY
        )
        self.lbl_title.pack(side="left")

        self.lbl_value = ctk.CTkLabel(
            self.top_bar,
            text=f"-- {self.unit}",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            text_color=COLOR_WHITE
        )
        self.lbl_value.pack(side="right")

        # Canvas for High-Speed Waveform Plotting
        self.canvas = tk.Canvas(
            self,
            height=self.canvas_height,
            bg="#050608",
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        self.trace_configs = traces or [{"name": "default", "color": COLOR_WHITE, "min": min_val, "max": max_val}]
        self.trace_lines: Dict[str, int] = {}

        self._init_grid()
        self._init_traces()

    def _init_grid(self) -> None:
        h = self.canvas_height
        for i in range(1, self.grid_steps):
            y = int(h * (i / self.grid_steps))
            self.canvas.create_line(0, y, 2000, y, fill="#12151b", dash=(2, 4), width=1)
            val = self.max_val - (i / self.grid_steps) * (self.max_val - self.min_val)
            self.canvas.create_text(16, y - 5, text=f"{val:.0f}", fill="#383f4f", font=("Consolas", 7))

        if self.min_val < 0 < self.max_val:
            mid_y = int(h * (self.max_val / (self.max_val - self.min_val)))
            self.canvas.create_line(0, mid_y, 2000, mid_y, fill="#1c2128", width=1)

    def _init_traces(self) -> None:
        for cfg in self.trace_configs:
            name = cfg["name"]
            color = cfg.get("color", COLOR_WHITE)
            line_id = self.canvas.create_line(0, self.canvas_height // 2, 0, self.canvas_height // 2, fill=color, width=2)
            self.trace_lines[name] = line_id

    def update_trace(self, name: str, data_points: List[Tuple[float, float]], current_val: Optional[float] = None) -> None:
        line_id = self.trace_lines.get(name)
        if not line_id or len(data_points) < 2:
            return

        cfg = next((c for c in self.trace_configs if c["name"] == name), None)
        min_v = cfg.get("min", self.min_val) if cfg else self.min_val
        max_v = cfg.get("max", self.max_val) if cfg else self.max_val
        v_span = (max_v - min_v) if max_v > min_v else 1.0

        w = self.canvas.winfo_width()
        if w < 50:
            w = 500
        h = self.canvas.winfo_height()
        if h < 30:
            h = self.canvas_height

        pts = []
        count = len(data_points)
        x_step = w / (count - 1) if count > 1 else w

        for idx, (_, val) in enumerate(data_points):
            x = int(idx * x_step)
            norm = (val - min_v) / v_span
            norm = max(0.0, min(1.0, norm))
            y = int(h - (norm * (h - 6)) - 3)
            pts.extend([x, y])

        if len(pts) >= 4:
            self.canvas.coords(line_id, *pts)

        if current_val is not None:
            new_text = f"{current_val:.1f} {self.unit}"
            if new_text != self._last_readout:
                self._last_readout = new_text
                self.lbl_value.configure(text=new_text, text_color=COLOR_TEXT_PRIMARY)


class MinimalStickRadar(ctk.CTkFrame):
    """Clean 2D Vector Crosshair Radar showing real-time thumbstick position."""
    def __init__(self, master, size: int = 46, label: str = "LS", player_color: str = COLOR_WHITE, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.size = size
        self.center = size // 2
        self.radius = (size // 2) - 4
        self.player_color = player_color

        self.canvas = tk.Canvas(
            self,
            width=self.size,
            height=self.size,
            bg="#050608",
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack()

        c = self.center
        r = self.radius
        self.canvas.create_oval(c - r, c - r, c + r, c + r, outline="#21262d", width=1)
        self.canvas.create_line(c - r, c, c + r, c, fill="#1c2128", width=1)
        self.canvas.create_line(c, c - r, c, c + r, fill="#1c2128", width=1)
        self.canvas.create_text(c, c, text=label, fill="#6e7681", font=("Consolas", 7, "bold"))

        self.vec_line = self.canvas.create_line(c, c, c, c, fill=self.player_color, width=2)
        self.dot = self.canvas.create_oval(c - 2, c - 2, c + 2, c + 2, fill=self.player_color, outline="")

    def set_position(self, raw_x: int, raw_y: int) -> None:
        c = self.center
        r = self.radius
        norm_x = max(-1.0, min(1.0, raw_x / 32767.0))
        norm_y = max(-1.0, min(1.0, -raw_y / 32767.0))

        tx = int(c + (norm_x * r))
        ty = int(c + (norm_y * r))
        self.canvas.coords(self.vec_line, c, c, tx, ty)
        self.canvas.coords(self.dot, tx - 2, ty - 2, tx + 2, ty + 2)


class MinimalTriggerMeter(ctk.CTkFrame):
    """Vertical Bars for LT (Brake) and RT (Throttle)."""
    def __init__(self, master, width: int = 28, height: int = 48, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.meter_width = width
        self.meter_height = height

        self.canvas = tk.Canvas(
            self,
            width=self.meter_width,
            height=self.meter_height,
            bg="#050608",
            highlightthickness=0,
            bd=0
        )
        self.canvas.pack()

        bar_w = 8
        lt_x = 3
        rt_x = 15
        top_y = 3
        bot_y = self.meter_height - 11

        self.canvas.create_rectangle(lt_x, top_y, lt_x + bar_w, bot_y, fill="#0e1117", outline="#21262d")
        self.canvas.create_rectangle(rt_x, top_y, rt_x + bar_w, bot_y, fill="#0e1117", outline="#21262d")
        self.canvas.create_text(lt_x + bar_w // 2, bot_y + 6, text="L", fill=COLOR_TEXT_MUTED, font=("Consolas", 6, "bold"))
        self.canvas.create_text(rt_x + bar_w // 2, bot_y + 6, text="R", fill=COLOR_TEXT_MUTED, font=("Consolas", 6, "bold"))

        self.bar_h = bot_y - top_y
        self.bot_y = bot_y
        self.lt_fill = self.canvas.create_rectangle(lt_x, bot_y, lt_x + bar_w, bot_y, fill=COLOR_WHITE, outline="")
        self.rt_fill = self.canvas.create_rectangle(rt_x, bot_y, rt_x + bar_w, bot_y, fill=COLOR_SILVER, outline="")

    def set_triggers(self, throttle: int, brake: int) -> None:
        th_norm = max(0.0, min(1.0, throttle / 255.0))
        br_norm = max(0.0, min(1.0, brake / 255.0))

        lt_h = int(br_norm * self.bar_h)
        rt_h = int(th_norm * self.bar_h)
        self.canvas.coords(self.lt_fill, 3, self.bot_y - lt_h, 3 + 8, self.bot_y)
        self.canvas.coords(self.rt_fill, 15, self.bot_y - rt_h, 15 + 8, self.bot_y)


class MinimalButtonCluster(ctk.CTkFrame):
    """Button Cluster with ABXY diamond, D-Pad, and RS center click."""
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.btn_labels: Dict[str, ctk.CTkLabel] = {}
        self._cached: Dict[str, bool] = {}

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack()

        # Left side: D-Pad 3x3
        dpad_grid = ctk.CTkFrame(container, fg_color="transparent")
        dpad_grid.pack(side="left", padx=(0, 2))
        self.btn_labels["DPAD_UP"] = self._create_btn(dpad_grid, "▲", COLOR_WHITE, 0, 1, size=12, font_size=6)
        self.btn_labels["DPAD_LEFT"] = self._create_btn(dpad_grid, "◀", COLOR_WHITE, 1, 0, size=12, font_size=6)
        self._create_empty(dpad_grid, 1, 1, size=12)
        self.btn_labels["DPAD_RIGHT"] = self._create_btn(dpad_grid, "▶", COLOR_WHITE, 1, 2, size=12, font_size=6)
        self.btn_labels["DPAD_DOWN"] = self._create_btn(dpad_grid, "▼", COLOR_WHITE, 2, 1, size=12, font_size=6)

        # Right side: XYBA Diamond
        action_grid = ctk.CTkFrame(container, fg_color="transparent")
        action_grid.pack(side="right")
        self.btn_labels["Y"] = self._create_btn(action_grid, "Y", COLOR_WHITE, 0, 1, size=12, font_size=6)
        self.btn_labels["X"] = self._create_btn(action_grid, "X", COLOR_WHITE, 1, 0, size=12, font_size=6)
        self.btn_labels["RS"] = self._create_btn(action_grid, "•", COLOR_WHITE, 1, 1, size=12, font_size=6)
        self.btn_labels["B"] = self._create_btn(action_grid, "B", COLOR_WHITE, 1, 2, size=12, font_size=6)
        self.btn_labels["A"] = self._create_btn(action_grid, "A", COLOR_WHITE, 2, 1, size=12, font_size=6)

    def _create_empty(self, parent, r: int, c: int, size: int = 12) -> None:
        lbl = ctk.CTkLabel(parent, text="", width=size, height=size, fg_color="transparent")
        lbl.grid(row=r, column=c, padx=1, pady=1)

    def _create_btn(self, parent, text: str, color: str, r: int, c: int, size: int = 12, font_size: int = 6) -> ctk.CTkLabel:
        lbl = ctk.CTkLabel(
            parent,
            text=text,
            width=size,
            height=size,
            corner_radius=2,
            fg_color="#12151b",
            text_color="#555d6e",
            font=ctk.CTkFont(family="Consolas", size=font_size, weight="bold")
        )
        lbl.grid(row=r, column=c, padx=1, pady=1)
        lbl._neon = color
        return lbl

    def set_states(self, buttons: Dict[str, bool]) -> None:
        for name, lbl in self.btn_labels.items():
            active = bool(buttons.get(name, False))
            if active != self._cached.get(name, False):
                self._cached[name] = active
                if active:
                    lbl.configure(fg_color=COLOR_WHITE, text_color="#08090b")
                else:
                    lbl.configure(fg_color="#12151b", text_color="#555d6e")


class PlayerDeckCard(ctk.CTkFrame):
    """
    Dedicated Tactical Player Cockpit Card.
    Contains player status, identity, swap button, test button,
    hardware crosshairs (LS/RS Radars, Triggers, D-Pad/ABXY),
    and 3 INDIVIDUAL continuous oscilloscopes for THIS specific player.
    """
    def __init__(self, master, slot_index: int, player_color: str, on_test_callback=None, on_swap_callback=None, **kwargs):
        super().__init__(master, fg_color=COLOR_CARD, border_color=COLOR_CARD_BORDER, border_width=1, corner_radius=6, **kwargs)
        self.slot_index = slot_index
        self.player_color = player_color
        self.on_test_callback = on_test_callback
        self.on_swap_callback = on_swap_callback

        self._last_connected: Optional[bool] = None
        self._last_meta_str: str = ""

        # Header Row
        self.header = ctk.CTkFrame(self, fg_color="transparent", height=22)
        self.header.pack(fill="x", padx=6, pady=(4, 1))

        self.lbl_title = ctk.CTkLabel(
            self.header,
            text=f"P{self.slot_index + 1}",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        self.lbl_title.pack(side="left")

        self.lbl_status = ctk.CTkLabel(
            self.header,
            text="WAIT",
            font=ctk.CTkFont(family="Consolas", size=7, weight="bold"),
            text_color=COLOR_TEXT_MUTED,
            fg_color="#161b22",
            corner_radius=3,
            padx=4,
            pady=1
        )
        self.lbl_status.pack(side="left", padx=4)

        self.btn_test = ctk.CTkButton(
            self.header,
            text="TEST",
            width=28,
            height=16,
            font=ctk.CTkFont(family="Consolas", size=7, weight="bold"),
            fg_color=COLOR_SURFACE,
            hover_color=COLOR_SURFACE_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=3,
            command=self._on_test_click
        )
        self.btn_test.pack(side="right", padx=(2, 0))

        self.btn_swap = ctk.CTkButton(
            self.header,
            text="⇄ SWAP",
            width=38,
            height=16,
            font=ctk.CTkFont(family="Consolas", size=7, weight="bold"),
            fg_color=COLOR_SURFACE,
            hover_color=COLOR_SURFACE_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            corner_radius=3,
            command=self._on_swap_click
        )
        self.btn_swap.pack(side="right", padx=2)

        # Telemetry Sub-Bar
        self.lbl_meta = ctk.CTkLabel(
            self,
            text="--",
            font=ctk.CTkFont(family="Consolas", size=8),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_meta.pack(anchor="w", padx=6, pady=(0, 2))

        # Visualizer Row (Radars + Triggers + Buttons)
        self.vis_row = ctk.CTkFrame(self, fg_color="#050608", corner_radius=4)
        self.vis_row.pack(fill="x", padx=4, pady=(0, 4))

        self.radar_ls = MinimalStickRadar(self.vis_row, size=38, label="LS", player_color=COLOR_WHITE)
        self.radar_ls.pack(side="left", padx=1, pady=2)

        self.radar_rs = MinimalStickRadar(self.vis_row, size=38, label="RS", player_color=COLOR_SLATE)
        self.radar_rs.pack(side="left", padx=1, pady=2)

        self.triggers = MinimalTriggerMeter(self.vis_row, width=20, height=40)
        self.triggers.pack(side="left", padx=1, pady=2)

        self.buttons = MinimalButtonCluster(self.vis_row)
        self.buttons.pack(side="right", padx=1, pady=2)

        # 3 Dedicated Mini-Oscilloscopes for THIS Player
        self.osc_container = ctk.CTkFrame(self, fg_color="transparent")
        self.osc_container.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        # 1. Latency / Ping Oscilloscope
        self.osc_latency = MinimalOscilloscope(
            self.osc_container,
            title="Ping / Latency",
            unit="ms",
            height=54,
            min_val=0.0,
            max_val=30.0,
            grid_steps=2,
            traces=[{"name": "latency", "color": COLOR_WHITE, "min": 0.0, "max": 30.0}]
        )
        self.osc_latency.pack(fill="x", pady=(0, 2))

        # 2. Thumbsticks (LS & RS) 4-Trace Oscilloscope
        self.osc_stick = MinimalOscilloscope(
            self.osc_container,
            title="Thumbsticks (LS & RS)",
            unit="val",
            height=70,
            min_val=-32768.0,
            max_val=32767.0,
            grid_steps=3,
            traces=[
                {"name": "stick_x", "color": COLOR_WHITE, "min": -32768.0, "max": 32767.0},
                {"name": "stick_y", "color": COLOR_SILVER, "min": -32768.0, "max": 32767.0},
                {"name": "right_stick_x", "color": COLOR_SLATE, "min": -32768.0, "max": 32767.0},
                {"name": "right_stick_y", "color": COLOR_PEWTER, "min": -32768.0, "max": 32767.0}
            ]
        )
        self.osc_stick.pack(fill="x", pady=(0, 2))

        # 3. Triggers (LT & RT) 2-Trace Oscilloscope
        self.osc_triggers = MinimalOscilloscope(
            self.osc_container,
            title="Triggers (LT & RT)",
            unit="val",
            height=54,
            min_val=0.0,
            max_val=255.0,
            grid_steps=2,
            traces=[
                {"name": "brake", "color": COLOR_WHITE, "min": 0.0, "max": 255.0},
                {"name": "throttle", "color": COLOR_SILVER, "min": 0.0, "max": 255.0}
            ]
        )
        self.osc_triggers.pack(fill="x")

    def _on_test_click(self) -> None:
        if self.on_test_callback:
            self.on_test_callback(self.slot_index)

    def _on_swap_click(self) -> None:
        if self.on_swap_callback:
            # Quick swap with next slot in cyclic pair: 0<->1, 2<->3
            target = self.slot_index + 1 if (self.slot_index % 2 == 0) else self.slot_index - 1
            self.on_swap_callback(self.slot_index, target)

    def update_state(self, slot_data: Dict[str, Any]) -> None:
        connected = bool(slot_data.get("connected", False))

        if connected != self._last_connected:
            self._last_connected = connected
            if connected:
                self.configure(border_color=COLOR_CARD_ACTIVE)
                self.lbl_status.configure(text="LIVE", text_color="#08090b", fg_color=COLOR_WHITE)
            else:
                self.configure(border_color=COLOR_CARD_BORDER)
                self.lbl_status.configure(text="WAIT", text_color=COLOR_TEXT_MUTED, fg_color="#161b22")
                self.lbl_meta.configure(text="--", text_color=COLOR_TEXT_MUTED)
                self._last_meta_str = ""
                self.radar_ls.set_position(0, 0)
                self.radar_rs.set_position(0, 0)
                self.triggers.set_triggers(0, 0)
                self.buttons.set_states({})

        if connected:
            ip = slot_data.get("client_ip", "127.0.0.1")
            rtt = slot_data.get("rtt_ms", 0.0)
            hz = slot_data.get("hz", 0.0)
            pkts = slot_data.get("packets", 0)
            meta_str = f"{ip} • {rtt:.1f}ms • {hz:.0f}Hz • {pkts}p"
            if meta_str != self._last_meta_str:
                self._last_meta_str = meta_str
                self.lbl_meta.configure(text=meta_str, text_color=COLOR_TEXT_PRIMARY)

            self.radar_ls.set_position(slot_data.get("stick_x", 0), slot_data.get("stick_y", 0))
            self.radar_rs.set_position(slot_data.get("right_stick_x", 0), slot_data.get("right_stick_y", 0))
            self.triggers.set_triggers(slot_data.get("throttle", 0), slot_data.get("brake", 0))
            self.buttons.set_states(slot_data.get("buttons", {}))

        # Always update live rolling waveforms for this player
        lat_wave = slot_data.get("latency_wave", [])
        if lat_wave:
            self.osc_latency.update_trace("latency", lat_wave, current_val=slot_data.get("rtt_ms") if connected else None)

        sx_wave = slot_data.get("stick_x_wave", [])
        sy_wave = slot_data.get("stick_y_wave", [])
        rx_wave = slot_data.get("right_stick_x_wave", [])
        ry_wave = slot_data.get("right_stick_y_wave", [])
        if sx_wave:
            self.osc_stick.update_trace("stick_x", sx_wave)
        if sy_wave:
            self.osc_stick.update_trace("stick_y", sy_wave)
        if rx_wave:
            self.osc_stick.update_trace("right_stick_x", rx_wave)
        if ry_wave:
            self.osc_stick.update_trace("right_stick_y", ry_wave)

        th_wave = slot_data.get("throttle_wave", [])
        br_wave = slot_data.get("brake_wave", [])
        if br_wave:
            self.osc_triggers.update_trace("brake", br_wave)
        if th_wave:
            self.osc_triggers.update_trace("throttle", th_wave)


class ControllerDashboard(ctk.CTk):
    """
    Project Controller - Ultra-Minimalist High-Refresh Telemetry Dashboard.
    Zero-Scroll layout with 4 side-by-side controller slots and 3 continuous 50FPS oscilloscopes.
    """
    def __init__(self, bridge: TelemetryBridge, on_close_callback=None):
        super().__init__()
        self.bridge = bridge
        self.on_close_callback = on_close_callback

        # Compact Window Config (Zero-Scroll 4-Player layout)
        self.title("Controller")
        self.geometry("1260x650")
        self.minsize(1020, 520)
        self.configure(fg_color=COLOR_BG)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("dark-blue")
        set_window_logo_icon(self)

        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

        self._last_url = ""
        self._last_uptime_sec = -1
        self._last_hz_str = ""
        self._last_driver_status = ""
        self._tick = 0

        self._build_top_bar()
        self._build_main_layout()
        self._build_bottom_bar()

        # Startup Terms & Conditions Modal Dialog (if not muted)
        if should_show_terms_on_startup():
            self.after(200, self.open_terms_dialog)

        # Start continuous high-frequency 50 FPS render pump
        self.after(20, self._render_loop)

    def open_terms_dialog(self) -> None:
        """Opens the Terms & Conditions and Support modal dialog."""
        try:
            TermsDialog(self)
        except Exception as e:
            logger.debug(f"Could not open terms dialog: {e}")

    def _build_top_bar(self) -> None:
        top = ctk.CTkFrame(self, fg_color=COLOR_CARD, border_color=COLOR_CARD_BORDER, border_width=1, corner_radius=0, height=38)
        top.pack(fill="x", side="top")

        left = ctk.CTkFrame(top, fg_color="transparent")
        left.pack(side="left", padx=10, pady=3)

        # Embedded Logo in Top Header Bar
        logo_img = get_logo_ctk_image((26, 26))
        if logo_img:
            lbl_top_logo = ctk.CTkLabel(left, image=logo_img, text="")
            lbl_top_logo.pack(side="left", padx=(0, 8))

        lbl_brand = ctk.CTkLabel(
            left,
            text="Controller",
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        lbl_brand.pack(side="left")

        right = ctk.CTkFrame(top, fg_color="transparent")
        right.pack(side="right", padx=10, pady=3)

        # About / Terms Button
        btn_about = ctk.CTkButton(
            right,
            text="ℹ️ ABOUT & TERMS",
            font=ctk.CTkFont(family="Consolas", size=9, weight="bold"),
            fg_color=COLOR_SURFACE,
            hover_color=COLOR_SURFACE_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            border_color=COLOR_CARD_BORDER,
            border_width=1,
            height=22,
            command=self.open_terms_dialog
        )
        btn_about.pack(side="left", padx=4)

        # 1-Click Driver Installer Button (shown only if driver missing)
        self.btn_install_driver = ctk.CTkButton(
            right,
            text="⚡ INSTALL DRIVER",
            font=ctk.CTkFont(family="Consolas", size=9, weight="bold"),
            fg_color="#30363d",
            hover_color="#484f58",
            text_color="#ffffff",
            height=22,
            command=self._install_vigem_driver
        )

        self.badge_status = ctk.CTkLabel(
            right,
            text="● ONLINE",
            font=ctk.CTkFont(family="Consolas", size=9, weight="bold"),
            text_color="#08090b",
            fg_color=COLOR_WHITE,
            corner_radius=3,
            padx=6,
            pady=1
        )
        self.badge_status.pack(side="left", padx=4)

        self.badge_driver = ctk.CTkLabel(
            right,
            text="ViGEmBus X360",
            font=ctk.CTkFont(family="Consolas", size=9, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            fg_color=COLOR_SURFACE,
            corner_radius=3,
            padx=6,
            pady=1
        )
        self.badge_driver.pack(side="left", padx=4)

        self.lbl_hz = ctk.CTkLabel(
            right,
            text="0.0 Hz",
            font=ctk.CTkFont(family="Consolas", size=9, weight="bold"),
            text_color=COLOR_WHITE
        )
        self.lbl_hz.pack(side="left", padx=6)

        self.lbl_uptime = ctk.CTkLabel(
            right,
            text="00:00:00",
            font=ctk.CTkFont(family="Consolas", size=9),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_uptime.pack(side="left", padx=6)

    def _build_main_layout(self) -> None:
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=6, pady=4)

        # Left Column: QR & Pairing (Width ~175px)
        col_left = ctk.CTkFrame(body, fg_color=COLOR_CARD, border_color=COLOR_CARD_BORDER, border_width=1, corner_radius=6, width=175)
        col_left.pack(side="left", fill="y", padx=(0, 6))
        col_left.pack_propagate(False)

        # Embedded Logo in Pairing Sidebar
        side_logo = get_logo_ctk_image((48, 48))
        if side_logo:
            lbl_side_logo = ctk.CTkLabel(col_left, image=side_logo, text="")
            lbl_side_logo.pack(pady=(6, 0))

        lbl_qr_title = ctk.CTkLabel(
            col_left,
            text="PHONE PAIRING",
            font=ctk.CTkFont(family="Consolas", size=9, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY
        )
        lbl_qr_title.pack(pady=(2, 2))

        self.qr_container = ctk.CTkLabel(col_left, text="", fg_color="#050608", corner_radius=4)
        self.qr_container.pack(padx=6, pady=2)

        self.lbl_url = ctk.CTkLabel(
            col_left,
            text="https://127.0.0.1:8443",
            font=ctk.CTkFont(family="Consolas", size=8, weight="bold"),
            text_color=COLOR_TEXT_PRIMARY,
            wraplength=165
        )
        self.lbl_url.pack(pady=2)

        btn_copy = ctk.CTkButton(
            col_left,
            text="COPY URL",
            font=ctk.CTkFont(family="Consolas", size=8, weight="bold"),
            fg_color=COLOR_SURFACE,
            hover_color=COLOR_SURFACE_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            height=20,
            command=self._copy_url_to_clipboard
        )
        btn_copy.pack(pady=3)

        # Quick Host Slot Swap Controls
        lbl_swap_title = ctk.CTkLabel(
            col_left,
            text="HOST SLOT SWAP",
            font=ctk.CTkFont(family="Consolas", size=8, weight="bold"),
            text_color=COLOR_TEXT_MUTED
        )
        lbl_swap_title.pack(pady=(6, 2))

        btn_swap_12 = ctk.CTkButton(
            col_left,
            text="⇄ SWAP P1 / P2",
            font=ctk.CTkFont(family="Consolas", size=8, weight="bold"),
            fg_color=COLOR_SURFACE,
            hover_color=COLOR_SURFACE_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            height=20,
            command=lambda: self._on_card_swap(0, 1)
        )
        btn_swap_12.pack(pady=2)

        btn_swap_34 = ctk.CTkButton(
            col_left,
            text="⇄ SWAP P3 / P4",
            font=ctk.CTkFont(family="Consolas", size=8, weight="bold"),
            fg_color=COLOR_SURFACE,
            hover_color=COLOR_SURFACE_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            height=20,
            command=lambda: self._on_card_swap(2, 3)
        )
        btn_swap_34.pack(pady=2)

        # Support & Donation Button in Sidebar
        btn_donate = ctk.CTkButton(
            col_left,
            text="☕ SUPPORT / DONATE",
            font=ctk.CTkFont(family="Consolas", size=8, weight="bold"),
            fg_color=COLOR_SURFACE,
            hover_color=COLOR_SURFACE_HOVER,
            text_color=COLOR_TEXT_PRIMARY,
            height=20,
            command=lambda: webbrowser.open("https://buymeacoffee.com/unitynimit")
        )
        btn_donate.pack(side="bottom", pady=(2, 6))

        lbl_hint = ctk.CTkLabel(
            col_left,
            text="Scan camera to join\n[TEST] wakes testers\n[⇄ SWAP] fixes slots",
            font=ctk.CTkFont(family="Consolas", size=7),
            text_color=COLOR_TEXT_MUTED,
            justify="center"
        )
        lbl_hint.pack(side="bottom", pady=2)

        # Right Area: 4 Dedicated Player Decks in a 4-Column Grid
        col_right = ctk.CTkFrame(body, fg_color="transparent")
        col_right.pack(side="right", fill="both", expand=True)

        decks_frame = ctk.CTkFrame(col_right, fg_color="transparent")
        decks_frame.pack(fill="both", expand=True)
        decks_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="deck_col")
        decks_frame.grid_rowconfigure(0, weight=1)

        self.player_decks: List[PlayerDeckCard] = []
        colors = [COLOR_WHITE, COLOR_SILVER, COLOR_SLATE, COLOR_PEWTER]
        for i in range(4):
            deck = PlayerDeckCard(
                decks_frame,
                slot_index=i,
                player_color=colors[i],
                on_test_callback=self.bridge.pulse_test,
                on_swap_callback=self._on_card_swap
            )
            deck.grid(row=0, column=i, padx=2, sticky="nsew")
            self.player_decks.append(deck)

    def _on_card_swap(self, slot_a: int, slot_b: int) -> None:
        success = self.bridge.swap_slots(slot_a, slot_b)
        if success:
            self.lbl_log.configure(text=f"[*] Swapped Player {slot_a + 1} with Player {slot_b + 1} successfully.")

    def _build_bottom_bar(self) -> None:
        bot = ctk.CTkFrame(self, fg_color=COLOR_CARD, border_color=COLOR_CARD_BORDER, border_width=1, corner_radius=4, height=24)
        bot.pack(fill="x", padx=6, pady=(0, 4))
        bot.pack_propagate(False)

        self.lbl_log = ctk.CTkLabel(
            bot,
            text="[READY] Gateway listening on port 8443 • 4 Native Xbox 360 controllers online • Haptics active",
            font=ctk.CTkFont(family="Consolas", size=8),
            text_color=COLOR_TEXT_MUTED
        )
        self.lbl_log.pack(side="left", padx=8)

    def _update_qr_code(self, url: str) -> None:
        if not url or url == self._last_url:
            return
        self._last_url = url
        try:
            qr = qrcode.QRCode(box_size=3, border=1)
            qr.add_data(url)
            qr.make(fit=True)
            pil_img = qr.make_image(fill_color="#ffffff", back_color="#050608").convert("RGB")
            pil_img = pil_img.resize((120, 120), Image.NEAREST)
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(120, 120))
            self.qr_container.configure(image=ctk_img, text="")
        except Exception as e:
            self.qr_container.configure(text=f"QR: {e}")

    def _install_vigem_driver(self) -> None:
        self.lbl_log.configure(text="[*] Preparing ViGEmBus installer...")

        import tempfile, shutil, subprocess, threading

        def _worker():
            msi_path = get_bundled_driver_msi()
            if not msi_path:
                self.lbl_log.configure(text="[ERROR] ViGEmBus installer could not be found or downloaded.")
                return

            try:
                temp_dir = tempfile.gettempdir()
                dest_msi = os.path.join(temp_dir, "ViGEmBusSetup_x64.msi")
                if str(msi_path) != dest_msi:
                    shutil.copy2(str(msi_path), dest_msi)

                self.lbl_log.configure(text="[*] Installing driver... Please accept the Windows Administrator UAC prompt.")

                cmd = f'Start-Process msiexec.exe -ArgumentList \'/i "{dest_msi}" /passive /norestart\' -Verb RunAs -Wait'
                subprocess.run(
                    ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                    capture_output=True,
                    timeout=120
                )

                time.sleep(1.2)

                upgraded = self.bridge.reinit_driver()
                if upgraded:
                    self.lbl_log.configure(text="[SUCCESS] Official Xbox 360 controller driver installed! Ready for every PC game.")
                    self.badge_driver.configure(text="ViGEmBus X360")
                    self.btn_install_driver.pack_forget()
                else:
                    self.lbl_log.configure(text="[OK] Driver installed! Restart application if controller is not immediately active.")
            except Exception as e:
                self.lbl_log.configure(text=f"[ERROR] Driver installation error: {e}")

        threading.Thread(target=_worker, daemon=True, name="DriverInstallerWorker").start()

    def _copy_url_to_clipboard(self) -> None:
        url = self.bridge.server_url or self.lbl_url.cget("text")
        self.clipboard_clear()
        self.clipboard_append(url)
        self.update()

    def _render_loop(self) -> None:
        """Continuous, ultra-responsive 50 FPS render pump for all 4 player decks."""
        self._tick += 1
        snap = self.bridge.get_snapshot()

        # Update all 4 Player Decks with live telemetry, crosshairs, and individual oscilloscopes
        slots = snap.get("slots", [])
        for i, sdata in enumerate(slots):
            if i < len(self.player_decks):
                self.player_decks[i].update_state(sdata)

        # Slow text updates (~4Hz, every 12 ticks)
        if self._tick % 12 == 0:
            url = snap.get("server_url", "")
            if url and url != self._last_url:
                self.lbl_url.configure(text=url)
                self._update_qr_code(url)

            driver = snap.get("driver_status", "Active")
            if driver != self._last_driver_status:
                self._last_driver_status = driver
                self.badge_driver.configure(text=driver)
                if "Native" not in driver and "X360" not in driver:
                    self.btn_install_driver.pack(side="left", padx=4)
                else:
                    self.btn_install_driver.pack_forget()

            uptime = snap.get("uptime_sec", 0)
            if uptime != self._last_uptime_sec:
                self._last_uptime_sec = uptime
                h, m, s = uptime // 3600, (uptime % 3600) // 60, uptime % 60
                self.lbl_uptime.configure(text=f"{h:02d}:{m:02d}:{s:02d}")

            hz = snap.get("effective_hz", 0.0)
            hz_str = f"{hz:.1f} Hz"
            if hz_str != self._last_hz_str:
                self._last_hz_str = hz_str
                self.lbl_hz.configure(text=hz_str)

        # Log Ticker
        if self._tick % 15 == 0:
            last_entry = None
            while True:
                try:
                    last_entry = self.bridge.log_queue.get_nowait()
                except queue.Empty:
                    break
            if last_entry:
                self.lbl_log.configure(text=f"[{last_entry['timestamp']}] {last_entry['message']}")

        # Next frame in 20ms (~50 FPS)
        self.after(20, self._render_loop)

    def _on_window_close(self) -> None:
        if self.on_close_callback:
            self.on_close_callback()
        self.destroy()
