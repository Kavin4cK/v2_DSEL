#!/usr/bin/env python3
"""
Hot Axle Monitoring System - Raspberry Pi
Based on original working code - just temperature, sorted ascending.

Gateway reply format: "<id>,<temp>\n"
"""

import serial
import time
import tkinter as tk
import threading
import sys
import os

os.environ['DISPLAY'] = ':0'

class CoachNode:
    def __init__(self, coach_id):
        self.coach_id    = coach_id
        self.temperature = None
        self.next        = None

class TrainMonitor:
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200):
        self.serial_port = None
        self.port        = port
        self.baudrate    = baudrate

        self.coaches     = {}   # id -> CoachNode
        self.train_order = []   # sorted ascending

        self.root         = None
        self.canvas       = None
        self.status_label = None

        self.running = False
        self.mapped  = False

    # ── Connect ──────────────────────────────────────────────
    def connect(self):
        try:
            print(f"Connecting to {self.port}...")
            self.serial_port = serial.Serial(
                self.port, self.baudrate,
                timeout=4,        # MUST be > gateway CTRL wait (1000ms)
                write_timeout=3
            )
            time.sleep(2)
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()

            print("Waiting for READY...")
            start = time.time()
            while time.time() - start < 15:
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    print(f"  RX: {line}")
                    if line == "READY":
                        print("✓ Gateway ready\n")
                        return True
                time.sleep(0.1)

            print("✗ No READY received\n")
            return False

        except Exception as e:
            print(f"✗ Connect failed: {e}")
            return False

    # ── Send one command, read one reply ─────────────────────
    def send_command(self, command):
        try:
            self.serial_port.reset_input_buffer()
            self.serial_port.write(f"{command}\n".encode('utf-8'))
            self.serial_port.flush()

            # Read with timeout already set on Serial object (4s)
            line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
            if line and line != "ERROR":
                return line
            return None
        except Exception as e:
            print(f"  TX error: {e}")
            return None

    # ── Probe which coaches are present ──────────────────────
    def detect_coaches(self):
        print("Probing coaches 0-4...")
        detected = []

        for cid in [0, 1, 2, 3, 4]:
            print(f"  C{cid}... ", end="", flush=True)
            resp = self.send_command(f"TEMP,{cid}")
            if resp:
                print(f"FOUND ({resp})")
                detected.append(cid)
            else:
                print("not found")

        print(f"\nDetected: {detected}")
        return detected

    # ── Build sorted linked list ──────────────────────────────
    def build_topology(self, detected):
        detected.sort()   # ascending
        self.coaches.clear()
        self.train_order = detected

        for cid in detected:
            self.coaches[cid] = CoachNode(cid)

        # Link next pointers
        for i in range(len(detected) - 1):
            self.coaches[detected[i]].next = self.coaches[detected[i+1]]

        print(f"Topology: {' → '.join(f'C{i}' for i in detected)}\n")
        self.mapped = True

    # ── Update temperatures ───────────────────────────────────
    def update_temperatures(self):
        for cid in self.train_order:
            resp = self.send_command(f"TEMP,{cid}")
            if resp:
                try:
                    parts = resp.split(',')
                    # Reply format: "<id>,<temp>"
                    if len(parts) == 2:
                        temp = float(parts[1])
                        self.coaches[cid].temperature = temp
                        print(f"  C{cid}: {temp:.1f}°C")
                    else:
                        print(f"  C{cid}: bad reply: {resp}")
                except Exception as e:
                    print(f"  C{cid}: parse error: {e}")
            else:
                print(f"  C{cid}: no response")

    # ── Temperature colour ────────────────────────────────────
    def get_color(self, temp):
        if temp is None:  return "#555555"
        if temp < 30:     return "#00FF00"
        if temp < 40:     return "#FFD700"
        return "#FF0000"

    def get_status(self, temp):
        if temp is None:  return "N/A"
        if temp < 30:     return "NORM"
        if temp < 40:     return "WARN"
        return "CRIT"

    # ── GUI ───────────────────────────────────────────────────
    def create_gui(self):
        self.root = tk.Tk()
        self.root.title("Hot Axle Monitor")
        self.root.geometry("480x320")
        self.root.attributes('-fullscreen', True)
        self.root.configure(bg='#1a1a1a')

        tk.Label(self.root, text="HOT AXLE MONITOR",
                 font=("Arial", 11, "bold"),
                 bg='#1a1a1a', fg='#00FF00').pack(pady=3)

        self.status_label = tk.Label(self.root, text="Starting...",
                 font=("Arial", 8, "bold"),
                 bg='#1a1a1a', fg='#00FF00')
        self.status_label.pack(pady=2)

        self.canvas = tk.Canvas(self.root,
                 width=470, height=240,
                 bg='#0d0d0d',
                 highlightthickness=1,
                 highlightbackground='#333333')
        self.canvas.pack(pady=3)

        leg = tk.Frame(self.root, bg='#1a1a1a')
        leg.pack(pady=2)
        for col, txt in [("#00FF00","Normal"),("#FFD700","Warn"),
                         ("#FF0000","Crit"), ("#555555","N/A")]:
            tk.Label(leg,text="■",fg=col,bg='#1a1a1a',
                     font=("Arial",10)).pack(side=tk.LEFT,padx=2)
            tk.Label(leg,text=txt,fg='white',bg='#1a1a1a',
                     font=("Arial",7)).pack(side=tk.LEFT,padx=3)

    # ── Draw linked list ──────────────────────────────────────
    def draw_train(self):
        if not self.mapped or not self.train_order:
            return

        self.canvas.delete("all")
        n = len(self.train_order)

        # Layout — fits 2-5 coaches on 470px canvas
        node_w = min(80, (460 - (n-1)*14) // n)
        gap    = (460 - n * node_w) // max(n-1, 1)
        start  = (470 - (n*node_w + (n-1)*gap)) // 2
        cy     = 120

        for i, cid in enumerate(self.train_order):
            node = self.coaches[cid]
            x    = start + i*(node_w + gap)
            temp = node.temperature
            col  = self.get_color(temp)
            stat = self.get_status(temp)
            t_str= f"{temp:.1f}\u00b0" if temp is not None else "---"

            # Box
            self.canvas.create_rectangle(
                x, cy-40, x+node_w, cy+42,
                fill=col, outline='white', width=2)

            # Coach ID
            self.canvas.create_text(
                x+node_w//2, cy-26,
                text=f"C{cid}",
                font=("Arial", 9, "bold"), fill='black')

            # Temperature — BIG
            self.canvas.create_text(
                x+node_w//2, cy,
                text=t_str,
                font=("Arial", 13, "bold"), fill='black')

            # Status
            self.canvas.create_text(
                x+node_w//2, cy+24,
                text=stat,
                font=("Arial", 7, "bold"), fill='black')

            # Arrow →
            if i < n-1:
                ax = x+node_w
                ex = ax+gap
                self.canvas.create_line(ax, cy, ex, cy,
                    arrow=tk.LAST, fill='#00FF00', width=3)

        # Status bar
        crits = [cid for cid in self.train_order
                 if self.coaches[cid].temperature
                 and self.coaches[cid].temperature >= 40]
        if crits:
            ids = " ".join(f"C{c}" for c in crits)
            self.status_label.config(
                text=f"⚠ CRITICAL: {ids}", fg="#FF0000")
        else:
            chain = " → ".join(f"C{c}" for c in self.train_order)
            self.status_label.config(
                text=f"OK  |  {chain}", fg="#00FF00")

    # ── Background monitor thread ─────────────────────────────
    def monitoring_loop(self):
        print("Monitoring started\n")
        cycle = 0
        while self.running:
            cycle += 1
            print(f"--- Cycle {cycle} ---")
            self.update_temperatures()
            self.root.after(0, self.draw_train)
            print()
            time.sleep(1)

    # ── Main ─────────────────────────────────────────────────
    def run(self):
        print("=" * 50)
        print("HOT AXLE MONITORING SYSTEM")
        print("=" * 50)

        if not self.connect():
            print("FAILED: cannot connect")
            return

        detected = self.detect_coaches()
        if not detected:
            print("FAILED: no coaches found")
            return

        self.build_topology(detected)
        self.create_gui()

        self.running = True
        t = threading.Thread(target=self.monitoring_loop, daemon=True)
        t.start()

        self.root.after(500, self.draw_train)

        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass

        self.running = False
        if self.serial_port:
            self.serial_port.close()

if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'
    TrainMonitor(port=port, baudrate=115200).run()