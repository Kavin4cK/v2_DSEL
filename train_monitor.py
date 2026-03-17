#!/usr/bin/env python3
"""
============================================================
 HOT AXLE MONITORING SYSTEM
 Raspberry Pi Display Controller
============================================================
 Display : 3.5" SPI TFT (ILI9486 / XPT2046)  480×320
 Serial  : Gateway Nano via USB (/dev/ttyUSB0, 9600 baud)

 Protocol from gateway:
   "READY"          → gateway is online
   "TEMP,<id>,<t>"  → coach <id> temperature reading
   "ERROR,<id>"     → coach <id> sensor fault

 Coach display:
   - Only coaches that have reported in are shown
   - Always sorted ascending by ID (1 → 5)
   - Color coding: green / yellow / red / grey
============================================================
"""

import serial
import threading
import time
import sys
import os

import tkinter as tk
from tkinter import font as tkfont

# ── Display Resolution ───────────────────────────────────────
# ILI9486 SPI TFT is 480×320 (landscape)
DISPLAY_W = 480
DISPLAY_H = 320

# ── Temperature Thresholds ───────────────────────────────────
TEMP_NORMAL   = 30.0   # Below this → Normal (green)
TEMP_WARNING  = 40.0   # Below this → Warning (yellow)
                       # At or above → Critical (red)

# ── Serial Config ────────────────────────────────────────────
DEFAULT_PORT = "/dev/ttyUSB0"
BAUDRATE     = 9600

# ── Colours ─────────────────────────────────────────────────
BG          = "#0A0A0F"
PANEL_BG    = "#12121A"
HEADER_BG   = "#0D1B2A"
ACCENT      = "#1E90FF"
COL_NORMAL  = "#00E676"
COL_WARNING = "#FFD600"
COL_CRIT    = "#FF1744"
COL_NODATA  = "#424242"
COL_TEXT_DK = "#0A0A0F"
COL_TEXT_LT = "#E0E0E0"
COL_DIM     = "#555566"
COL_ARROW   = "#1E90FF"

# ─────────────────────────────────────────────────────────────
class CoachNode:
    """Single node in the sorted linked list of coaches."""
    def __init__(self, coach_id: int):
        self.coach_id   = coach_id
        self.temperature: float | None = None
        self.status     = "NO DATA"   # NORMAL / WARNING / CRITICAL / ERROR / NO DATA
        self.last_seen  = 0.0         # epoch time of last update
        self.next: "CoachNode | None" = None

    def update(self, temp: float | None):
        self.temperature = temp
        self.last_seen   = time.time()
        if temp is None:
            self.status = "ERROR"
        elif temp < TEMP_NORMAL:
            self.status = "NORMAL"
        elif temp < TEMP_WARNING:
            self.status = "WARNING"
        else:
            self.status = "CRITICAL"

    @property
    def color(self) -> str:
        return {
            "NORMAL":   COL_NORMAL,
            "WARNING":  COL_WARNING,
            "CRITICAL": COL_CRIT,
            "ERROR":    COL_NODATA,
            "NO DATA":  COL_NODATA,
        }.get(self.status, COL_NODATA)

    @property
    def temp_str(self) -> str:
        if self.temperature is None:
            return "---"
        return f"{self.temperature:.1f}°"

# ─────────────────────────────────────────────────────────────
class CoachLinkedList:
    """
    Sorted singly-linked list of coach nodes.
    Insertion always keeps ascending order by coach_id.
    """
    def __init__(self):
        self.head: CoachNode | None = None
        self._lock = threading.Lock()

    def _insert(self, coach_id: int) -> CoachNode:
        """Insert a new node in sorted position (ascending ID)."""
        new_node = CoachNode(coach_id)
        if self.head is None or self.head.coach_id > coach_id:
            new_node.next = self.head
            self.head = new_node
            return new_node
        curr = self.head
        while curr.next and curr.next.coach_id < coach_id:
            curr = curr.next
        new_node.next = curr.next
        curr.next = new_node
        return new_node

    def get_or_create(self, coach_id: int) -> CoachNode:
        with self._lock:
            curr = self.head
            while curr:
                if curr.coach_id == coach_id:
                    return curr
                curr = curr.next
            return self._insert(coach_id)

    def as_list(self) -> list[CoachNode]:
        with self._lock:
            result, curr = [], self.head
            while curr:
                result.append(curr)
                curr = curr.next
            return result

    def count(self) -> int:
        return len(self.as_list())

# ─────────────────────────────────────────────────────────────
class SerialReader(threading.Thread):
    """
    Background thread — reads gateway serial output and
    updates the shared CoachLinkedList.
    """
    def __init__(self, port: str, coaches: CoachLinkedList,
                 on_ready, on_error):
        super().__init__(daemon=True)
        self.port     = port
        self.coaches  = coaches
        self.on_ready = on_ready
        self.on_error = on_error
        self._ser: serial.Serial | None = None
        self.connected = False

    def run(self):
        while True:
            try:
                self._connect()
                self._read_loop()
            except Exception as e:
                self.connected = False
                self.on_error(f"Serial error: {e}")
                time.sleep(3)

    def _connect(self):
        self.on_error("Connecting to gateway...")
        self._ser = serial.Serial(self.port, BAUDRATE, timeout=2)
        time.sleep(2)
        self._ser.reset_input_buffer()

        deadline = time.time() + 15
        while time.time() < deadline:
            raw = self._ser.readline()
            if raw:
                line = raw.decode("utf-8", errors="ignore").strip()
                if line == "READY":
                    self.connected = True
                    self.on_ready()
                    return
        raise ConnectionError("Gateway did not send READY within 15 s")

    def _read_loop(self):
        while True:
            raw = self._ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            parts = line.split(",")

            if parts[0] == "TEMP" and len(parts) == 3:
                try:
                    cid  = int(parts[1])
                    temp = float(parts[2])
                    node = self.coaches.get_or_create(cid)
                    node.update(temp)
                except ValueError:
                    pass

            elif parts[0] == "ERROR" and len(parts) == 2:
                try:
                    cid  = int(parts[1])
                    node = self.coaches.get_or_create(cid)
                    node.update(None)
                except ValueError:
                    pass

# ─────────────────────────────────────────────────────────────
class HotAxleApp:
    """Main GUI — optimised for 480×320 SPI TFT."""

    REFRESH_MS = 1000   # redraw interval

    def __init__(self, port: str):
        self.coaches    = CoachLinkedList()
        self.sys_status = "Connecting..."
        self.gateway_ok = False

        # ── Root window ──────────────────────────────────────
        self.root = tk.Tk()
        self.root.title("Hot Axle Monitor")
        self.root.geometry(f"{DISPLAY_W}x{DISPLAY_H}+0+0")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.root.overrideredirect(True)   # fullscreen borderless on Pi

        self._build_fonts()
        self._build_ui()

        # ── Serial reader ────────────────────────────────────
        self.reader = SerialReader(
            port    = port,
            coaches = self.coaches,
            on_ready= self._on_gateway_ready,
            on_error= self._on_serial_error,
        )
        self.reader.start()

        # ── Start refresh loop ───────────────────────────────
        self.root.after(self.REFRESH_MS, self._refresh)

    # ── Font setup ───────────────────────────────────────────
    def _build_fonts(self):
        self.f_title    = tkfont.Font(family="DejaVu Sans", size=11, weight="bold")
        self.f_subtitle = tkfont.Font(family="DejaVu Sans", size=7)
        self.f_id       = tkfont.Font(family="DejaVu Sans Mono", size=9,  weight="bold")
        self.f_temp     = tkfont.Font(family="DejaVu Sans Mono", size=16, weight="bold")
        self.f_status   = tkfont.Font(family="DejaVu Sans", size=7, weight="bold")
        self.f_ptr      = tkfont.Font(family="DejaVu Sans Mono", size=6)
        self.f_legend   = tkfont.Font(family="DejaVu Sans", size=7)
        self.f_sys      = tkfont.Font(family="DejaVu Sans", size=7)

    # ── Static UI skeleton ───────────────────────────────────
    def _build_ui(self):
        # ── Header bar (480 × 38) ────────────────────────────
        self.header = tk.Frame(self.root, bg=HEADER_BG,
                               width=DISPLAY_W, height=38)
        self.header.place(x=0, y=0)

        tk.Label(self.header, text="◈  HOT AXLE MONITORING SYSTEM",
                 font=self.f_title, bg=HEADER_BG, fg=ACCENT
                 ).place(x=8, y=4)

        tk.Label(self.header, text="Real-Time I2C Linked-List Railway Safety Monitor",
                 font=self.f_subtitle, bg=HEADER_BG, fg=COL_DIM
                 ).place(x=10, y=22)

        self.lbl_clock = tk.Label(self.header, text="",
                                  font=self.f_subtitle,
                                  bg=HEADER_BG, fg=COL_DIM)
        self.lbl_clock.place(x=390, y=4)

        # ── Canvas for linked-list visualisation (480 × 230) ─
        self.canvas = tk.Canvas(self.root,
                                width=DISPLAY_W, height=230,
                                bg=PANEL_BG, highlightthickness=0)
        self.canvas.place(x=0, y=38)

        # ── Footer bar (480 × 52) ────────────────────────────
        self.footer = tk.Frame(self.root, bg=HEADER_BG,
                               width=DISPLAY_W, height=52)
        self.footer.place(x=0, y=268)

        # Legend dots
        legend_data = [
            (COL_NORMAL,  "Normal <30°C"),
            (COL_WARNING, "Warning 30–40°C"),
            (COL_CRIT,    "Critical >40°C"),
            (COL_NODATA,  "No Data / Error"),
        ]
        lx = 8
        for col, label in legend_data:
            tk.Label(self.footer, text="●", fg=col,
                     bg=HEADER_BG, font=self.f_legend
                     ).place(x=lx, y=4)
            tk.Label(self.footer, text=label, fg=COL_TEXT_LT,
                     bg=HEADER_BG, font=self.f_legend
                     ).place(x=lx + 14, y=4)
            lx += 116

        # System status label
        self.lbl_status = tk.Label(
            self.footer, text="Status: Initialising...",
            font=self.f_sys, bg=HEADER_BG, fg=COL_TEXT_LT,
            wraplength=460, justify="left"
        )
        self.lbl_status.place(x=8, y=26)

    # ── Callbacks ────────────────────────────────────────────
    def _on_gateway_ready(self):
        self.gateway_ok = True
        self.sys_status = "Gateway connected — waiting for coaches..."

    def _on_serial_error(self, msg: str):
        self.gateway_ok = False
        self.sys_status = msg

    # ── Main refresh ─────────────────────────────────────────
    def _refresh(self):
        self._draw_canvas()
        self._update_footer()
        self.lbl_clock.config(text=time.strftime("%H:%M:%S"))
        self.root.after(self.REFRESH_MS, self._refresh)

    # ── Canvas drawing ───────────────────────────────────────
    def _draw_canvas(self):
        self.canvas.delete("all")
        nodes = self.coaches.as_list()   # already sorted ascending

        if not nodes:
            self.canvas.create_text(
                DISPLAY_W // 2, 115,
                text="Waiting for coaches..." if self.gateway_ok
                     else "Gateway not connected",
                font=self.f_id, fill=COL_DIM
            )
            return

        n = len(nodes)

        # ── Layout geometry ──────────────────────────────────
        NODE_W   = min(74, (DISPLAY_W - 20) // n - 14)
        NODE_H   = 110
        ARROW_W  = max(10, (DISPLAY_W - 10 - n * NODE_W) // max(n - 1, 1))
        TOTAL_W  = n * NODE_W + max(n - 1, 0) * ARROW_W
        START_X  = (DISPLAY_W - TOTAL_W) // 2
        CY       = 115   # vertical centre of canvas

        for idx, node in enumerate(nodes):
            nx = START_X + idx * (NODE_W + ARROW_W)
            self._draw_node(nx, CY, NODE_W, NODE_H, node, idx, n)

            # Arrow to next node
            if idx < n - 1:
                ax = nx + NODE_W
                ay = CY
                ex = ax + ARROW_W
                self.canvas.create_line(
                    ax, ay, ex, ay,
                    fill=COL_ARROW, width=2, arrow=tk.LAST
                )
                self.canvas.create_text(
                    ax + ARROW_W // 2, ay - 10,
                    text="next", font=self.f_ptr, fill=COL_ARROW
                )

        # NULL terminators on far left / far right
        lx = START_X - 2
        self.canvas.create_text(lx, CY, text="NULL",
                                font=self.f_ptr, fill=COL_DIM, anchor="e")
        rx = START_X + TOTAL_W + 2
        self.canvas.create_text(rx, CY, text="NULL",
                                font=self.f_ptr, fill=COL_DIM, anchor="w")

    def _draw_node(self, nx: int, cy: int, nw: int, nh: int,
                   node: CoachNode, idx: int, total: int):
        """Draw a single coach node box."""
        top  = cy - nh // 2
        bot  = cy + nh // 2
        col  = node.color

        # Shadow
        self.canvas.create_rectangle(
            nx + 3, top + 3, nx + nw + 3, bot + 3,
            fill="#000000", outline=""
        )

        # Main box
        self.canvas.create_rectangle(
            nx, top, nx + nw, bot,
            fill=col, outline="white", width=2
        )

        cx = nx + nw // 2   # centre-x of node

        # Coach ID label
        self.canvas.create_text(
            cx, top + 14,
            text=f"C{node.coach_id}",
            font=self.f_id, fill=COL_TEXT_DK
        )

        # Divider line
        self.canvas.create_line(
            nx + 4, top + 26, nx + nw - 4, top + 26,
            fill=COL_TEXT_DK, width=1
        )

        # Temperature
        self.canvas.create_text(
            cx, cy - 4,
            text=node.temp_str,
            font=self.f_temp, fill=COL_TEXT_DK
        )

        # Status badge
        self.canvas.create_text(
            cx, bot - 22,
            text=node.status,
            font=self.f_status, fill=COL_TEXT_DK
        )

        # Pointer labels: ← prev | next →
        prev_txt = f"←{nodes_left_id(node, idx)}"
        next_txt = f"{nodes_right_id(node, idx, total)}→"
        self.canvas.create_text(
            nx + 5, bot - 8,
            text=prev_txt, font=self.f_ptr,
            fill="#333333", anchor="w"
        )
        self.canvas.create_text(
            nx + nw - 5, bot - 8,
            text=next_txt, font=self.f_ptr,
            fill="#333333", anchor="e"
        )

    # ── Footer update ─────────────────────────────────────────
    def _update_footer(self):
        nodes = self.coaches.as_list()
        critical = [n for n in nodes if n.status == "CRITICAL"]
        warning  = [n for n in nodes if n.status == "WARNING"]

        if critical:
            ids = ", ".join(f"C{n.coach_id}" for n in critical)
            txt = f"⚠  CRITICAL HOT AXLE — Coach(es): {ids}"
            fg  = COL_CRIT
        elif warning:
            ids = ", ".join(f"C{n.coach_id}" for n in warning)
            txt = f"⚠  Warning — Coach(es): {ids} temperature elevated"
            fg  = COL_WARNING
        elif nodes:
            txt = f"✔  All {len(nodes)} coach(es) normal — No hot axle detected"
            fg  = COL_NORMAL
        else:
            txt = f"   {self.sys_status}"
            fg  = COL_DIM

        self.lbl_status.config(text=txt, fg=fg)

    # ── Run ──────────────────────────────────────────────────
    def run(self):
        self.root.mainloop()


# ── Pointer label helpers ─────────────────────────────────────
def nodes_left_id(node: CoachNode, idx: int) -> str:
    """Label for the left/prev pointer of this node in the list."""
    return "NULL" if idx == 0 else f"C{node.coach_id - 1}"

def nodes_right_id(node: CoachNode, idx: int, total: int) -> str:
    """Label for the right/next pointer of this node in the list."""
    return "NULL" if idx == total - 1 else f"C{node.coach_id + 1}"


# ── Entry point ──────────────────────────────────────────────
if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORT

    if not os.path.exists(port):
        print(f"[WARN] Serial port {port} not found — continuing anyway")

    print("=" * 52)
    print("  HOT AXLE MONITORING SYSTEM  —  Raspberry Pi")
    print("=" * 52)
    print(f"  Display : 480×320 SPI TFT (ILI9486)")
    print(f"  Port    : {port}  @  {BAUDRATE} baud")
    print(f"  Coaches : up to 5  (IDs 1–5, auto-sorted)")
    print("=" * 52)

    app = HotAxleApp(port)
    app.run()
