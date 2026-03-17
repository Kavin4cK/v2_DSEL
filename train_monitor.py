#!/usr/bin/env python3
"""
============================================================
 HOT AXLE MONITORING SYSTEM — Raspberry Pi
 3.5" SPI TFT (ILI9486)  480x320
============================================================
 How it works:
   1. On startup: probe TEMP,0 through TEMP,4
      Collect every ID that replies without ERROR
   2. Sort responders ascending → build linked list
   3. Poll each in order, update temps, refresh GUI
   4. Missing coaches are simply not shown
   5. Re-probes every 30s to detect newly added coaches

 Pi sends    → "TEMP,<id>\n"
 Gateway replies:
   success   → "<left>,<id>,<right>,<temp>\n"
   error     → "ERROR\n"
============================================================
"""

import serial
import threading
import time
import sys
import tkinter as tk
from tkinter import font as tkfont

# ── Config ───────────────────────────────────────────────────
DISPLAY_W    = 480
DISPLAY_H    = 320
DEFAULT_PORT = "/dev/ttyUSB0"
BAUDRATE     = 9600
ALL_IDS      = [0, 1, 2, 3, 4]
PROBE_EVERY  = 30       # re-probe for new coaches every N seconds
POLL_DELAY   = 0.3      # seconds between each coach query

TEMP_NORMAL  = 30.0
TEMP_WARNING = 40.0

# ── Colours ──────────────────────────────────────────────────
BG          = "#0A0A0F"
PANEL_BG    = "#12121A"
HEADER_BG   = "#0D1B2A"
ACCENT      = "#1E90FF"
COL_NORMAL  = "#00E676"
COL_WARN    = "#FFD600"
COL_CRIT    = "#FF1744"
COL_NODATA  = "#555566"
COL_DK      = "#0A0A0F"
COL_LT      = "#E0E0E0"
COL_DIM     = "#445566"
COL_ARROW   = "#1E90FF"
COL_GW      = "#7B61FF"   # gateway node accent colour

# ─────────────────────────────────────────────────────────────
class CoachNode:
    def __init__(self, coach_id, left_id, right_id):
        self.coach_id    = coach_id
        self.left_id     = left_id
        self.right_id    = right_id
        self.temperature = None
        self.status      = "WAITING"
        self.next        = None

    def update_temp(self, temp: float | None):
        self.temperature = temp
        if temp is None:
            self.status = "ERROR"
        elif temp < TEMP_NORMAL:
            self.status = "NORMAL"
        elif temp < TEMP_WARNING:
            self.status = "WARNING"
        else:
            self.status = "CRITICAL"

    @property
    def color(self):
        return {
            "NORMAL":   COL_NORMAL,
            "WARNING":  COL_WARN,
            "CRITICAL": COL_CRIT,
            "WAITING":  COL_NODATA,
            "ERROR":    COL_NODATA,
        }.get(self.status, COL_NODATA)

    @property
    def temp_str(self):
        if self.temperature is None:
            return "---"
        return f"{self.temperature:.1f}\u00b0"

# ─────────────────────────────────────────────────────────────
class TrainMonitor(threading.Thread):
    """
    Background thread:
      - Maintains serial connection to gateway
      - Probes which coaches are present
      - Continuously polls temps and updates node list
    """
    def __init__(self, port: str):
        super().__init__(daemon=True)
        self.port       = port
        self._ser       = None
        self._lock      = threading.Lock()
        self._nodes     = []          # sorted list of CoachNode
        self.status_msg = "Connecting..."
        self.connected  = False
        self._last_probe = 0.0

    # ── Public read ──────────────────────────────────────────
    def get_nodes(self) -> list[CoachNode]:
        with self._lock:
            return list(self._nodes)

    # ── Thread entry ─────────────────────────────────────────
    def run(self):
        while True:
            try:
                self._connect()
                self._main_loop()
            except Exception as e:
                self.connected  = False
                self.status_msg = f"Reconnecting... ({e})"
                try:
                    if self._ser:
                        self._ser.close()
                except Exception:
                    pass
                time.sleep(3)

    # ── Connect ──────────────────────────────────────────────
    def _connect(self):
        self.status_msg = f"Connecting to {self.port}..."
        self._ser = serial.Serial(self.port, BAUDRATE, timeout=2)
        time.sleep(2)
        self._ser.reset_input_buffer()

        self.status_msg = "Waiting for READY..."
        deadline = time.time() + 15
        while time.time() < deadline:
            raw = self._ser.readline()
            if raw:
                line = raw.decode("utf-8", errors="ignore").strip()
                if line == "READY":
                    self.connected  = True
                    self.status_msg = "Probing coaches..."
                    return
        raise ConnectionError("Gateway did not send READY")

    # ── Main poll loop ───────────────────────────────────────
    def _main_loop(self):
        while True:
            now = time.time()

            # Re-probe periodically
            if now - self._last_probe >= PROBE_EVERY:
                self._probe_coaches()
                self._last_probe = time.time()

            # Poll each active coach
            nodes = self.get_nodes()
            if not nodes:
                self.status_msg = "No coaches responding"
                time.sleep(1)
                continue

            for node in nodes:
                self._poll_temp(node)
                time.sleep(POLL_DELAY)

    # ── Probe which coaches exist ────────────────────────────
    def _probe_coaches(self):
        self.status_msg = "Probing coaches..."
        found = []

        for cid in ALL_IDS:
            reply = self._send_temp_request(cid)
            if reply is None:
                continue
            left_id, curr_id, right_id, temp = reply
            node = CoachNode(curr_id, left_id, right_id)
            node.update_temp(temp)
            found.append(node)
            time.sleep(0.1)

        # Sort ascending by ID and rebuild linked list
        found.sort(key=lambda n: n.coach_id)
        for i, node in enumerate(found):
            node.next = found[i + 1] if i + 1 < len(found) else None

        with self._lock:
            self._nodes = found

        ids = [f"C{n.coach_id}" for n in found]
        self.status_msg = f"Active: {' → '.join(ids)}" if ids else "No coaches found"

    # ── Poll one coach temperature ───────────────────────────
    def _poll_temp(self, node: CoachNode):
        reply = self._send_temp_request(node.coach_id)
        if reply is None:
            return
        _, _, _, temp = reply
        node.update_temp(temp)

    # ── Send TEMP,<id> and parse reply ───────────────────────
    def _send_temp_request(self, coach_id: int):
        """
        Returns (left_id, curr_id, right_id, temp) or None on failure.
        """
        try:
            self._ser.reset_input_buffer()
            self._ser.write(f"TEMP,{coach_id}\n".encode())
            self._ser.flush()

            raw = self._ser.readline()
            if not raw:
                return None

            line = raw.decode("utf-8", errors="ignore").strip()
            if not line or line == "ERROR":
                return None

            parts = line.split(",")
            if len(parts) != 4:
                return None

            left_id  = int(parts[0])
            curr_id  = int(parts[1])
            right_id = int(parts[2])
            temp     = float(parts[3])
            return (left_id, curr_id, right_id, temp)

        except Exception:
            return None


# ─────────────────────────────────────────────────────────────
class HotAxleGUI:
    REFRESH_MS = 800

    def __init__(self, monitor: TrainMonitor):
        self.monitor = monitor

        self.root = tk.Tk()
        self.root.title("Hot Axle Monitor")
        self.root.geometry(f"{DISPLAY_W}x{DISPLAY_H}+0+0")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.root.overrideredirect(True)     # borderless fullscreen on Pi
        try:
            self.root.attributes("-zoomed", True)
        except Exception:
            pass

        self._fonts()
        self._build()
        self.root.after(self.REFRESH_MS, self._refresh)

    # ── Fonts ────────────────────────────────────────────────
    def _fonts(self):
        self.f_hdr    = tkfont.Font(family="DejaVu Sans",      size=10, weight="bold")
        self.f_sub    = tkfont.Font(family="DejaVu Sans",      size=7)
        self.f_id     = tkfont.Font(family="DejaVu Sans Mono", size=9,  weight="bold")
        self.f_temp   = tkfont.Font(family="DejaVu Sans Mono", size=16, weight="bold")
        self.f_status = tkfont.Font(family="DejaVu Sans",      size=7,  weight="bold")
        self.f_ptr    = tkfont.Font(family="DejaVu Sans Mono", size=6)
        self.f_leg    = tkfont.Font(family="DejaVu Sans",      size=7)

    # ── Static layout ────────────────────────────────────────
    def _build(self):
        # Header  480 × 36
        hdr = tk.Frame(self.root, bg=HEADER_BG, height=36)
        hdr.place(x=0, y=0, width=DISPLAY_W)
        tk.Label(hdr, text="HOT AXLE MONITORING SYSTEM",
                 font=self.f_hdr, bg=HEADER_BG, fg=ACCENT).place(x=8, y=3)
        tk.Label(hdr, text="Hardcoded topology  |  auto-sorted ascending",
                 font=self.f_sub, bg=HEADER_BG, fg=COL_DIM).place(x=10, y=20)
        self.lbl_clock = tk.Label(hdr, text="", font=self.f_sub,
                                  bg=HEADER_BG, fg=COL_DIM)
        self.lbl_clock.place(x=388, y=3)

        # Canvas  480 × 232
        self.cv = tk.Canvas(self.root, width=DISPLAY_W, height=232,
                            bg=PANEL_BG, highlightthickness=0)
        self.cv.place(x=0, y=36)

        # Footer  480 × 52
        ftr = tk.Frame(self.root, bg=HEADER_BG, height=52)
        ftr.place(x=0, y=268, width=DISPLAY_W)

        lx = 6
        for col, txt in [(COL_NORMAL, "Normal <30°"),
                         (COL_WARN,   "Warning 30-40°"),
                         (COL_CRIT,   "Critical >40°"),
                         (COL_NODATA, "No data")]:
            tk.Label(ftr, text="●", fg=col, bg=HEADER_BG,
                     font=self.f_leg).place(x=lx, y=4)
            tk.Label(ftr, text=txt, fg=COL_LT, bg=HEADER_BG,
                     font=self.f_leg).place(x=lx + 13, y=4)
            lx += 118

        self.lbl_alert = tk.Label(ftr, text="", font=self.f_leg,
                                  bg=HEADER_BG, fg=COL_LT,
                                  wraplength=464, justify="left")
        self.lbl_alert.place(x=6, y=24)

    # ── Refresh loop ─────────────────────────────────────────
    def _refresh(self):
        self._draw_canvas()
        self._draw_footer()
        self.lbl_clock.config(text=time.strftime("%H:%M:%S"))
        self.root.after(self.REFRESH_MS, self._refresh)

    # ── Canvas ───────────────────────────────────────────────
    def _draw_canvas(self):
        self.cv.delete("all")
        nodes = self.monitor.get_nodes()

        if not nodes:
            self.cv.create_text(
                DISPLAY_W // 2, 116,
                text=self.monitor.status_msg,
                font=self.f_id, fill=COL_DIM
            )
            return

        n      = len(nodes)
        NW     = min(74, (DISPLAY_W - 20) // n - 10)
        NH     = 112
        GAP    = max(8, (DISPLAY_W - 10 - n * NW) // max(n - 1, 1))
        TOTAL  = n * NW + max(n - 1, 0) * GAP
        sx     = (DISPLAY_W - TOTAL) // 2
        cy     = 116

        for i, node in enumerate(nodes):
            nx  = sx + i * (NW + GAP)
            col = node.color
            is_gw = (node.coach_id == 0)

            # Shadow
            self.cv.create_rectangle(
                nx+3, cy-NH//2+3, nx+NW+3, cy+NH//2+3,
                fill="#000000", outline="")

            # Box
            outline_col = COL_GW if is_gw else "white"
            self.cv.create_rectangle(
                nx, cy-NH//2, nx+NW, cy+NH//2,
                fill=col, outline=outline_col, width=2)

            cx = nx + NW // 2

            # ID label
            label = f"C{node.coach_id}" + (" GW" if is_gw else "")
            self.cv.create_text(cx, cy - NH//2 + 12,
                text=label, font=self.f_id, fill=COL_DK)

            # Divider
            self.cv.create_line(
                nx+4, cy-NH//2+22, nx+NW-4, cy-NH//2+22,
                fill=COL_DK)

            # Temperature (big)
            self.cv.create_text(cx, cy - 6,
                text=node.temp_str, font=self.f_temp, fill=COL_DK)

            # Status text
            self.cv.create_text(cx, cy + NH//2 - 22,
                text=node.status, font=self.f_status, fill=COL_DK)

            # Pointer labels  ←left   right→
            l_lbl = f"←{node.left_id}"  if node.left_id  >= 0 else "←NULL"
            r_lbl = f"{node.right_id}→" if node.right_id >= 0 else "NULL→"
            self.cv.create_text(nx + 4, cy + NH//2 - 9,
                text=l_lbl, font=self.f_ptr, fill="#333344", anchor="w")
            self.cv.create_text(nx + NW - 4, cy + NH//2 - 9,
                text=r_lbl, font=self.f_ptr, fill="#333344", anchor="e")

            # Arrow  →  to next node
            if i < n - 1:
                ax = nx + NW
                ex = ax + GAP
                self.cv.create_line(ax, cy, ex, cy,
                    arrow=tk.LAST, fill=COL_ARROW, width=2)
                self.cv.create_text((ax + ex) // 2, cy - 10,
                    text="next", font=self.f_ptr, fill=COL_ARROW)

    # ── Footer alert ─────────────────────────────────────────
    def _draw_footer(self):
        nodes    = self.monitor.get_nodes()
        critical = [n for n in nodes if n.status == "CRITICAL"]
        warning  = [n for n in nodes if n.status == "WARNING"]

        if critical:
            ids = " ".join(f"C{n.coach_id}" for n in critical)
            txt = f"⚠  CRITICAL HOT AXLE — {ids}"
            fg  = COL_CRIT
        elif warning:
            ids = " ".join(f"C{n.coach_id}" for n in warning)
            txt = f"⚠  Warning — {ids} elevated"
            fg  = COL_WARN
        elif nodes:
            active = " → ".join(f"C{n.coach_id}" for n in nodes)
            txt = f"✔  All normal  |  {active}"
            fg  = COL_NORMAL
        else:
            txt = self.monitor.status_msg
            fg  = COL_DIM

        self.lbl_alert.config(text=txt, fg=fg)

    def run(self):
        self.root.mainloop()


# ── Entry point ──────────────────────────────────────────────
if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORT

    print("=" * 50)
    print("  HOT AXLE MONITOR — Raspberry Pi")
    print(f"  Port    : {port}  @  {BAUDRATE} baud")
    print(f"  Coaches : C0–C4 (missing ones auto-skipped)")
    print(f"  Display : 480×320 SPI TFT")
    print("=" * 50)

    monitor = TrainMonitor(port)
    monitor.start()

    gui = HotAxleGUI(monitor)
    gui.run()