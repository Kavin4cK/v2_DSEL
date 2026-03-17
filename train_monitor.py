#!/usr/bin/env python3
"""
============================================================
 HOT AXLE MONITORING SYSTEM — Raspberry Pi
 3.5" SPI TFT (ILI9486)  480 × 320
============================================================

 Architecture:
   Pi sends "TEMP,<id>"  to gateway over USB serial
   Gateway sets CTRL pins (D6/D7/D8) → coach ID
   Target coach reads sensor (blocks 800ms) → ready
   Gateway waits 900ms → reads 7 bytes via I2C (SDA/SCL)
   Gateway replies to Pi: "<left>,<id>,<right>,<temp>"

 Startup:
   Probe TEMP,0 through TEMP,4
   Any that reply without ERROR → add to active list
   Sort ascending → display as linked list

 Runtime:
   Poll each active coach in order, update temperatures
   Re-probe every 30s to catch newly connected coaches

 Missing coaches → simply not shown (no box, no error)
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
REPROBE_SECS = 30
SERIAL_TIMEOUT = 3.0    # seconds — must be > CONV_WAIT (0.9s) + margin

TEMP_NORMAL  = 30.0
TEMP_WARNING = 40.0

# ── Palette ──────────────────────────────────────────────────
C_BG      = "#0A0A0F"
C_PANEL   = "#12121A"
C_HEADER  = "#0D1B2A"
C_ACCENT  = "#1E90FF"
C_NORMAL  = "#00E676"
C_WARN    = "#FFD600"
C_CRIT    = "#FF1744"
C_NODATA  = "#444455"
C_DK      = "#0A0A0F"
C_LT      = "#E0E0E0"
C_DIM     = "#334455"
C_ARROW   = "#1E90FF"
C_GW      = "#A78BFA"   # purple tint for gateway node border


# ─────────────────────────────────────────────────────────────
class CoachNode:
    """One node in the sorted linked list."""

    def __init__(self, coach_id: int, left_id: int, right_id: int):
        self.coach_id    = coach_id
        self.left_id     = left_id     # -1 = NULL
        self.right_id    = right_id    # -1 = NULL
        self.temperature: float | None = None
        self.status      = "WAITING"
        self.next: "CoachNode | None" = None

    def set_temp(self, temp: float):
        self.temperature = temp
        if temp < TEMP_NORMAL:
            self.status = "NORMAL"
        elif temp < TEMP_WARNING:
            self.status = "WARNING"
        else:
            self.status = "CRITICAL"

    def set_error(self):
        self.temperature = None
        self.status      = "ERROR"

    @property
    def fill_color(self) -> str:
        return {
            "NORMAL":   C_NORMAL,
            "WARNING":  C_WARN,
            "CRITICAL": C_CRIT,
            "WAITING":  C_NODATA,
            "ERROR":    C_NODATA,
        }.get(self.status, C_NODATA)

    @property
    def temp_str(self) -> str:
        if self.temperature is None:
            return "---"
        return f"{self.temperature:.1f}\u00b0C"


# ─────────────────────────────────────────────────────────────
class TrainMonitor(threading.Thread):
    """
    Background thread — owns the serial connection.
    Probes coaches, polls temperatures, updates node list.
    Thread-safe reads via get_nodes() / get_status().
    """

    def __init__(self, port: str):
        super().__init__(daemon=True)
        self._port       = port
        self._ser        = None
        self._lock       = threading.Lock()
        self._nodes: list[CoachNode] = []
        self._status     = "Connecting..."
        self._last_probe = 0.0

    # ── Public API ───────────────────────────────────────────
    def get_nodes(self) -> list[CoachNode]:
        with self._lock:
            return list(self._nodes)

    def get_status(self) -> str:
        with self._lock:
            return self._status

    def _set_status(self, msg: str):
        with self._lock:
            self._status = msg

    # ── Thread ───────────────────────────────────────────────
    def run(self):
        while True:
            try:
                self._connect()
                self._main_loop()
            except Exception as e:
                self._set_status(f"Reconnecting... ({e})")
                try:
                    if self._ser:
                        self._ser.close()
                except Exception:
                    pass
                time.sleep(3)

    # ── Connect and wait for READY ───────────────────────────
    def _connect(self):
        self._set_status(f"Connecting to {self._port}...")
        self._ser = serial.Serial(
            self._port, BAUDRATE,
            timeout=SERIAL_TIMEOUT
        )
        time.sleep(2)
        self._ser.reset_input_buffer()

        self._set_status("Waiting for gateway READY...")
        deadline = time.time() + 20
        while time.time() < deadline:
            raw = self._ser.readline()
            if raw:
                line = raw.decode("utf-8", errors="ignore").strip()
                if line == "READY":
                    self._set_status("Gateway ready — probing coaches...")
                    return
        raise ConnectionError("Gateway did not send READY within 20s")

    # ── Main loop ────────────────────────────────────────────
    def _main_loop(self):
        while True:
            if time.time() - self._last_probe >= REPROBE_SECS:
                self._probe_all()
                self._last_probe = time.time()

            nodes = self.get_nodes()
            if not nodes:
                self._set_status("No coaches responding — retrying...")
                time.sleep(2)
                continue

            for node in nodes:
                self._poll_one(node)

    # ── Probe all IDs — build the node list ──────────────────
    def _probe_all(self):
        self._set_status("Probing coaches 0–4...")
        found: list[CoachNode] = []

        for cid in ALL_IDS:
            result = self._send_temp(cid)
            if result is None:
                continue
            left_id, curr_id, right_id, temp = result
            node = CoachNode(curr_id, left_id, right_id)
            node.set_temp(temp)
            found.append(node)

        # Sort ascending, rebuild next pointers
        found.sort(key=lambda n: n.coach_id)
        for i, node in enumerate(found):
            node.next = found[i + 1] if i + 1 < len(found) else None

        with self._lock:
            self._nodes = found

        if found:
            chain = " → ".join(f"C{n.coach_id}" for n in found)
            self._set_status(f"Active: {chain}")
        else:
            self._set_status("No coaches found")

    # ── Poll one coach temperature ────────────────────────────
    def _poll_one(self, node: CoachNode):
        result = self._send_temp(node.coach_id)
        if result is not None:
            _, _, _, temp = result
            node.set_temp(temp)
        # If no reply during polling we keep the last known value
        # (coach may still be mid-conversion from previous cycle)

    # ── Send TEMP,<id> → parse reply ─────────────────────────
    def _send_temp(self, coach_id: int):
        """
        Returns (left_id, curr_id, right_id, temp: float) or None.
        left_id / right_id are -1 for NULL.
        """
        try:
            self._ser.reset_input_buffer()
            self._ser.write(f"TEMP,{coach_id}\n".encode())
            self._ser.flush()

            # Timeout must be > CONV_WAIT (900ms) + serial latency
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
        self.root.configure(bg=C_BG)
        self.root.overrideredirect(True)
        try:
            self.root.attributes("-zoomed", True)
        except Exception:
            pass

        self._build_fonts()
        self._build_layout()
        self.root.after(self.REFRESH_MS, self._refresh)

    # ── Fonts ────────────────────────────────────────────────
    def _build_fonts(self):
        self.f_hdr    = tkfont.Font(family="DejaVu Sans",      size=10, weight="bold")
        self.f_sub    = tkfont.Font(family="DejaVu Sans",      size=7)
        self.f_id     = tkfont.Font(family="DejaVu Sans Mono", size=9,  weight="bold")
        self.f_temp   = tkfont.Font(family="DejaVu Sans Mono", size=15, weight="bold")
        self.f_stat   = tkfont.Font(family="DejaVu Sans",      size=7,  weight="bold")
        self.f_ptr    = tkfont.Font(family="DejaVu Sans Mono", size=6)
        self.f_leg    = tkfont.Font(family="DejaVu Sans",      size=7)

    # ── Static layout ────────────────────────────────────────
    def _build_layout(self):
        # ── Header  480 × 36 ─────────────────────────────────
        hdr = tk.Frame(self.root, bg=C_HEADER, height=36)
        hdr.place(x=0, y=0, width=DISPLAY_W)

        tk.Label(hdr, text="HOT AXLE MONITORING SYSTEM",
                 font=self.f_hdr, bg=C_HEADER, fg=C_ACCENT
                 ).place(x=8, y=3)
        tk.Label(hdr, text="Control lines D6/D7/D8  ·  I2C SDA/SCL  ·  auto-sorted",
                 font=self.f_sub, bg=C_HEADER, fg=C_DIM
                 ).place(x=8, y=21)
        self.lbl_clock = tk.Label(hdr, text="", font=self.f_sub,
                                  bg=C_HEADER, fg=C_DIM)
        self.lbl_clock.place(x=388, y=3)

        # ── Canvas  480 × 232 ────────────────────────────────
        self.cv = tk.Canvas(self.root, width=DISPLAY_W, height=232,
                            bg=C_PANEL, highlightthickness=0)
        self.cv.place(x=0, y=36)

        # ── Footer  480 × 52 ─────────────────────────────────
        ftr = tk.Frame(self.root, bg=C_HEADER, height=52)
        ftr.place(x=0, y=268, width=DISPLAY_W)

        lx = 6
        for col, txt in [
            (C_NORMAL, "Normal <30°C"),
            (C_WARN,   "Warning 30–40°C"),
            (C_CRIT,   "Critical >40°C"),
            (C_NODATA, "No data"),
        ]:
            tk.Label(ftr, text="●", fg=col,
                     bg=C_HEADER, font=self.f_leg).place(x=lx, y=4)
            tk.Label(ftr, text=txt, fg=C_LT,
                     bg=C_HEADER, font=self.f_leg).place(x=lx + 13, y=4)
            lx += 118

        self.lbl_alert = tk.Label(
            ftr, text="", font=self.f_leg,
            bg=C_HEADER, fg=C_LT,
            wraplength=464, justify="left"
        )
        self.lbl_alert.place(x=6, y=24)

    # ── Refresh ──────────────────────────────────────────────
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
                text=self.monitor.get_status(),
                font=self.f_id, fill=C_DIM
            )
            return

        n     = len(nodes)
        NW    = min(76, (DISPLAY_W - 20) // n - 10)
        NH    = 116
        GAP   = max(8, (DISPLAY_W - 10 - n * NW) // max(n - 1, 1))
        TOTAL = n * NW + max(n - 1, 0) * GAP
        sx    = (DISPLAY_W - TOTAL) // 2
        cy    = 116

        for i, node in enumerate(nodes):
            nx  = sx + i * (NW + GAP)
            col = node.fill_color
            gw  = (node.coach_id == 0)

            # ── Shadow ───────────────────────────────────────
            self.cv.create_rectangle(
                nx + 3, cy - NH//2 + 3,
                nx + NW + 3, cy + NH//2 + 3,
                fill="#000000", outline=""
            )

            # ── Main box ─────────────────────────────────────
            border = C_GW if gw else "white"
            bwidth = 3    if gw else 2
            self.cv.create_rectangle(
                nx, cy - NH//2, nx + NW, cy + NH//2,
                fill=col, outline=border, width=bwidth
            )

            cx = nx + NW // 2   # horizontal centre

            # ── Coach ID ─────────────────────────────────────
            tag = f"C{node.coach_id}" + (" GW" if gw else "")
            self.cv.create_text(cx, cy - NH//2 + 13,
                text=tag, font=self.f_id, fill=C_DK)

            # ── Divider line ─────────────────────────────────
            self.cv.create_line(
                nx + 4,  cy - NH//2 + 24,
                nx + NW - 4, cy - NH//2 + 24,
                fill=C_DK
            )

            # ── Temperature ──────────────────────────────────
            self.cv.create_text(cx, cy - 4,
                text=node.temp_str, font=self.f_temp, fill=C_DK)

            # ── Status ───────────────────────────────────────
            self.cv.create_text(cx, cy + NH//2 - 22,
                text=node.status, font=self.f_stat, fill=C_DK)

            # ── Pointer labels ───────────────────────────────
            l_lbl = f"\u2190{node.left_id}"  if node.left_id  >= 0 else "\u2190NULL"
            r_lbl = f"{node.right_id}\u2192" if node.right_id >= 0 else "NULL\u2192"
            self.cv.create_text(nx + 4, cy + NH//2 - 9,
                text=l_lbl, font=self.f_ptr, fill="#334455", anchor="w")
            self.cv.create_text(nx + NW - 4, cy + NH//2 - 9,
                text=r_lbl, font=self.f_ptr, fill="#334455", anchor="e")

            # ── Arrow to next ─────────────────────────────────
            if i < n - 1:
                ax = nx + NW
                ex = ax + GAP
                self.cv.create_line(
                    ax, cy, ex, cy,
                    arrow=tk.LAST, fill=C_ARROW, width=2
                )
                self.cv.create_text(
                    (ax + ex) // 2, cy - 10,
                    text="next", font=self.f_ptr, fill=C_ARROW
                )

        # ── NULL terminators ─────────────────────────────────
        self.cv.create_text(sx - 4, cy,
            text="NULL", font=self.f_ptr, fill=C_DIM, anchor="e")
        self.cv.create_text(sx + TOTAL + 4, cy,
            text="NULL", font=self.f_ptr, fill=C_DIM, anchor="w")

    # ── Footer ───────────────────────────────────────────────
    def _draw_footer(self):
        nodes    = self.monitor.get_nodes()
        critical = [n for n in nodes if n.status == "CRITICAL"]
        warning  = [n for n in nodes if n.status == "WARNING"]

        if critical:
            ids = "  ".join(f"C{n.coach_id}" for n in critical)
            txt, fg = f"\u26a0  CRITICAL HOT AXLE — {ids}", C_CRIT
        elif warning:
            ids = "  ".join(f"C{n.coach_id}" for n in warning)
            txt, fg = f"\u26a0  Warning — {ids} elevated", C_WARN
        elif nodes:
            chain = " \u2192 ".join(f"C{n.coach_id}" for n in nodes)
            txt, fg = f"\u2714  All normal  |  {chain}", C_NORMAL
        else:
            txt, fg = self.monitor.get_status(), C_DIM

        self.lbl_alert.config(text=txt, fg=fg)

    def run(self):
        self.root.mainloop()


# ── Entry point ──────────────────────────────────────────────
if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORT

    print("=" * 52)
    print("  HOT AXLE MONITORING SYSTEM — Raspberry Pi")
    print(f"  Port    : {port}  @  {BAUDRATE} baud")
    print(f"  Coaches : C0 (GW) + C1–C4  (missing = auto-skip)")
    print(f"  Display : 480 \u00d7 320  SPI TFT")
    print("=" * 52)

    monitor = TrainMonitor(port)
    monitor.start()

    HotAxleGUI(monitor).run()
