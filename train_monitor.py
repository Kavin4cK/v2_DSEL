#!/usr/bin/env python3
"""
Hot Axle Monitoring System - Raspberry Pi
Detects present coaches, sorts ascending, shows real-time temperature.
Supports: C0-C1-C3-C4 or C0-C1-C2-C3-C4 (any combination)
"""

import serial
import time
import tkinter as tk
import threading
import sys
import os

os.environ['DISPLAY'] = ':0'

class CoachNode:
    def __init__(self, coach_id, left_id, right_id):
        self.coach_id    = coach_id
        self.left_id     = left_id
        self.right_id    = right_id
        self.temperature = None
        self.next        = None

class TrainMonitor:
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600):
        self.serial_port  = None
        self.port         = port
        self.baudrate     = baudrate
        self.coaches      = {}
        self.train_order  = []
        self.root         = None
        self.canvas       = None
        self.status_label = None
        self.running      = False
        self.mapped       = False

    def connect(self):
        try:
            print(f"Connecting to {self.port}...")
            self.serial_port = serial.Serial(
                self.port, self.baudrate,
                timeout=5, write_timeout=3
            )
            time.sleep(2)
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()

            print("Waiting for READY...")
            start = time.time()
            while time.time() - start < 20:
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    print(f"  RX: {line}")
                    if line == "READY":
                        print("✓ Connected\n")
                        return True
                time.sleep(0.1)

            print("✗ No READY\n")
            return False
        except Exception as e:
            print(f"✗ {e}")
            return False

    def send_command(self, command):
        try:
            self.serial_port.reset_input_buffer()
            self.serial_port.write(f"{command}\n".encode())
            self.serial_port.flush()
            line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
            if line and line != "ERROR":
                return line
            return None
        except Exception as e:
            print(f"  TX error: {e}")
            return None

    def detect_coaches(self):
        print("Probing coaches...")
        detected = []
        for cid in [0, 1, 2, 3, 4]:
            print(f"  C{cid}... ", end="", flush=True)
            resp = self.send_command(f"TEMP,{cid}")
            if resp:
                print(f"FOUND ({resp})")
                detected.append((cid, resp))
            else:
                print("not found")
        return detected

    def build_topology(self, detected):
        detected.sort(key=lambda x: x[0])
        self.coaches.clear()
        self.train_order = []

        for cid, resp in detected:
            try:
                parts = resp.split(',')
                # Format: TEMP,id,left,right,temp
                if len(parts) == 5:
                    left  = int(parts[2])
                    right = int(parts[3])
                    temp  = float(parts[4])
                else:
                    # fallback
                    i = [x[0] for x in detected].index(cid)
                    left  = detected[i-1][0] if i > 0 else -1
                    right = detected[i+1][0] if i+1 < len(detected) else -1
                    temp  = 0.0

                node = CoachNode(cid, left, right)
                node.temperature = temp
                self.coaches[cid] = node
                self.train_order.append(cid)
            except Exception as e:
                print(f"  Parse error C{cid}: {e}")

        # Link next pointers
        for i in range(len(self.train_order) - 1):
            self.coaches[self.train_order[i]].next = self.coaches[self.train_order[i+1]]

        print(f"Order: {' → '.join(f'C{c}' for c in self.train_order)}\n")
        self.mapped = True

    def update_temperatures(self):
        for cid in self.train_order:
            resp = self.send_command(f"TEMP,{cid}")
            if resp:
                try:
                    parts = resp.split(',')
                    if len(parts) == 5:
                        self.coaches[cid].temperature = float(parts[4])
                        print(f"  C{cid}: {self.coaches[cid].temperature:.1f}°C")
                except Exception as e:
                    print(f"  C{cid} parse error: {e}")
            else:
                print(f"  C{cid}: no response")

    def get_color(self, temp):
        if temp is None: return "#555555"
        if temp < 30:    return "#00FF00"
        if temp < 40:    return "#FFD700"
        return "#FF0000"

    def get_status(self, temp):
        if temp is None: return "N/A"
        if temp < 30:    return "NORM"
        if temp < 40:    return "WARN"
        return "CRIT"

    def create_gui(self):
        self.root = tk.Tk()
        self.root.title("Hot Axle Monitor")
        self.root.geometry("480x320")
        self.root.attributes('-fullscreen', True)
        self.root.configure(bg='#1a1a1a')

        tk.Label(self.root, text="HOT AXLE MONITOR",
                 font=("Arial", 11, "bold"),
                 bg='#1a1a1a', fg='#00FF00').pack(pady=3)

        self.status_label = tk.Label(self.root,
                 text="Initializing...",
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
                         ("#FF0000","Crit"),("#555555","N/A")]:
            tk.Label(leg, text="■", fg=col,
                     bg='#1a1a1a', font=("Arial",10)).pack(side=tk.LEFT, padx=2)
            tk.Label(leg, text=txt, fg='white',
                     bg='#1a1a1a', font=("Arial",7)).pack(side=tk.LEFT, padx=3)

    def draw_train(self):
        if not self.mapped or not self.train_order:
            return

        self.canvas.delete("all")
        n = len(self.train_order)

        if n >= 5:
            nw, nh, gap, sx = 60, 75, 14, 8
        elif n == 4:
            nw, nh, gap, sx = 72, 80, 16, 12
        elif n == 3:
            nw, nh, gap, sx = 90, 85, 20, 40
        else:
            nw, nh, gap, sx = 110, 90, 24, 60

        spacing = nw + gap
        cy = 120

        for i, cid in enumerate(self.train_order):
            node = self.coaches[cid]
            x    = sx + i * spacing
            temp = node.temperature
            col  = self.get_color(temp)
            stat = self.get_status(temp)
            tstr = f"{temp:.1f}\u00b0" if temp is not None else "---"

            # Box
            self.canvas.create_rectangle(
                x, cy-nh//2, x+nw, cy+nh//2,
                fill=col, outline='white', width=2)

            # Coach ID
            self.canvas.create_text(x+nw//2, cy-nh//2+12,
                text=f"C{cid}",
                font=("Arial", 9, "bold"), fill='black')

            # Divider
            self.canvas.create_line(
                x+4, cy-nh//2+22, x+nw-4, cy-nh//2+22,
                fill='black')

            # Temperature
            self.canvas.create_text(x+nw//2, cy-2,
                text=tstr,
                font=("Arial", 13, "bold"), fill='black')

            # Status
            self.canvas.create_text(x+nw//2, cy+nh//2-14,
                text=stat,
                font=("Arial", 7, "bold"), fill='black')

            # Arrow to next
            if i < n - 1:
                ax = x + nw
                ex = ax + gap
                self.canvas.create_line(ax, cy, ex, cy,
                    arrow=tk.LAST, fill='#00FF00', width=3)

        # Status bar
        crits = [c for c in self.train_order
                 if self.coaches[c].temperature
                 and self.coaches[c].temperature >= 40]
        if crits:
            self.status_label.config(
                text=f"CRITICAL: {' '.join(f'C{c}' for c in crits)}",
                fg="#FF0000")
        else:
            chain = " → ".join(f"C{c}" for c in self.train_order)
            self.status_label.config(
                text=f"OK | {chain}", fg="#00FF00")

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

        self.root.after(200, self.draw_train)

        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass

        self.running = False
        if self.serial_port:
            self.serial_port.close()

if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'
    TrainMonitor(port=port, baudrate=9600).run()