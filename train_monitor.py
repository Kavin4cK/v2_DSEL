#!/usr/bin/env python3
"""
Hot Axle Monitoring System - Raspberry Pi
Original working UI - probes C0-C4, shows whatever responds, sorted ascending.
Gateway reply format: "TEMP,<id>,<left>,<right>,<temp>"
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
        self.serial_port = None
        self.port        = port
        self.baudrate    = baudrate
        self.coaches     = {}
        self.head        = None
        self.train_order = []
        self.root        = None
        self.canvas      = None
        self.status_label= None
        self.running     = False
        self.mapped      = False

    def connect(self):
        try:
            print(f"Connecting to {self.port}...")
            self.serial_port = serial.Serial(
                self.port, self.baudrate,
                timeout=5,        # must be > bus timeout (2s) + sensor read time
                write_timeout=3
            )
            time.sleep(3)
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()

            print("Waiting for READY signal...")
            start_time = time.time()
            while time.time() - start_time < 15:
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    print(f"  Received: '{line}'")
                    if line == "READY":
                        print("✓ Gateway connected and ready\n")
                        return True
                time.sleep(0.1)

            print("✗ No READY signal received\n")
            return False

        except Exception as e:
            print(f"✗ Connect failed: {e}")
            return False

    def send_command(self, command):
        try:
            if not self.serial_port or not self.serial_port.is_open:
                return None
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()
            self.serial_port.write(f"{command}\n".encode('utf-8'))
            self.serial_port.flush()

            # Read with timeout set on serial object (5s)
            line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
            if line and line != "ERROR":
                return line
            return None
        except Exception as e:
            print(f"  TX error: {e}")
            return None

    def detect_coaches(self):
        print("=" * 50)
        print("DETECTING COACHES")
        print("=" * 50)
        detected = []

        for coach_id in [0, 1, 2, 3, 4]:
            print(f"  Probing C{coach_id}... ", end="", flush=True)
            response = self.send_command(f"TEMP,{coach_id}")
            if response:
                print(f"FOUND  ({response})")
                detected.append(coach_id)
            else:
                print("not found")

        print(f"\nDetected: {detected}\n")
        return detected

    def build_topology(self, detected):
        detected.sort()
        self.coaches.clear()
        self.train_order = detected

        for cid in detected:
            # Get left/right from first probe response
            resp = self.send_command(f"TEMP,{cid}")
            if resp:
                parts = resp.split(',')
                # Format: TEMP,id,left,right,temp
                if len(parts) == 5 and parts[0] == 'TEMP':
                    left  = int(parts[2])
                    right = int(parts[3])
                    self.coaches[cid] = CoachNode(cid, left, right)
                    continue
            # Fallback: build from sorted list
            i = detected.index(cid)
            left  = detected[i-1] if i > 0 else -1
            right = detected[i+1] if i < len(detected)-1 else -1
            self.coaches[cid] = CoachNode(cid, left, right)

        # Link next pointers ascending
        for i in range(len(detected) - 1):
            self.coaches[detected[i]].next = self.coaches[detected[i+1]]
        if detected:
            self.head = self.coaches[detected[0]]

        print(f"Topology: {' → '.join(f'C{i}' for i in detected)}\n")
        self.mapped = True

    def update_temperatures(self):
        for cid in self.train_order:
            resp = self.send_command(f"TEMP,{cid}")
            if resp:
                try:
                    parts = resp.split(',')
                    # Format: TEMP,id,left,right,temp
                    if len(parts) == 5 and parts[0] == 'TEMP':
                        temp = float(parts[4])
                        self.coaches[cid].temperature = temp
                        print(f"  C{cid}: {temp:.1f}°C")
                    else:
                        print(f"  C{cid}: bad reply: {resp}")
                except Exception as e:
                    print(f"  C{cid}: parse error {e} — {resp}")
            else:
                print(f"  C{cid}: no response")

    def get_temp_color(self, temp):
        if temp is None: return "#555555"
        if temp < 30:    return "#00FF00"
        if temp < 40:    return "#FFD700"
        return "#FF0000"

    def get_temp_status(self, temp):
        if temp is None: return "NO DATA"
        if temp < 30:    return "NORMAL"
        if temp < 40:    return "WARNING"
        return "CRITICAL"

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
                 text="Status: Initializing...",
                 font=("Arial", 8, "bold"),
                 bg='#1a1a1a', fg='#00FF00')
        self.status_label.pack(pady=2)

        self.canvas = tk.Canvas(self.root,
                 width=470, height=240,
                 bg='#0d0d0d',
                 highlightthickness=1,
                 highlightbackground='#333333')
        self.canvas.pack(pady=3)

        legend_frame = tk.Frame(self.root, bg='#1a1a1a')
        legend_frame.pack(pady=2)
        for color, text in [("#00FF00","Normal"),("#FFD700","Warn"),
                            ("#FF0000","Crit"),("#555555","N/A")]:
            tk.Label(legend_frame, text="■", fg=color,
                     bg='#1a1a1a', font=("Arial", 10)).pack(side=tk.LEFT, padx=2)
            tk.Label(legend_frame, text=text, fg="white",
                     bg='#1a1a1a', font=("Arial", 7)).pack(side=tk.LEFT, padx=3)

    def draw_train(self):
        if not self.mapped or not self.train_order:
            return

        self.canvas.delete("all")
        n = len(self.train_order)

        # Layout sizes based on coach count
        if n >= 5:
            nw, nh, spacing, start_x, ft, fl = 60, 70, 82, 10, 8, 7
        elif n == 4:
            nw, nh, spacing, start_x, ft, fl = 70, 75, 95, 15, 9, 8
        elif n == 3:
            nw, nh, spacing, start_x, ft, fl = 90, 80, 120, 40, 10, 9
        else:
            nw, nh, spacing, start_x, ft, fl = 110, 90, 140, 60, 12, 10

        y = 120

        for i, cid in enumerate(self.train_order):
            node = self.coaches[cid]
            x    = start_x + i * spacing
            temp = node.temperature
            col  = self.get_temp_color(temp)
            stat = self.get_temp_status(temp)
            tstr = f"{temp:.1f}\u00b0" if temp is not None else "---"

            # Box
            self.canvas.create_rectangle(
                x, y - nh//2, x + nw, y + nh//2,
                fill=col, outline='white', width=2)

            # Coach ID
            self.canvas.create_text(x + nw//2, y - nh//2 + 12,
                text=f"C{cid}", font=("Arial", fl, "bold"), fill='black')

            # Temperature
            self.canvas.create_text(x + nw//2, y - 4,
                text=tstr, font=("Arial", ft, "bold"), fill='black')

            # Status
            self.canvas.create_text(x + nw//2, y + nh//2 - 16,
                text=stat[:4], font=("Arial", 6, "bold"), fill='black')

            # Pointer labels
            lptr = f"\u2190{node.left_id}"  if node.left_id  >= 0 else "\u2190X"
            rptr = f"{node.right_id}\u2192" if node.right_id >= 0 else "X\u2192"
            self.canvas.create_text(x + 6, y + nh//2 - 5,
                text=lptr, font=("Arial", 6), fill='#AAAAAA', anchor='w')
            self.canvas.create_text(x + nw - 6, y + nh//2 - 5,
                text=rptr, font=("Arial", 6), fill='#AAAAAA', anchor='e')

            # Arrow to next
            if i < n - 1:
                ax = x + nw
                ex = start_x + (i+1) * spacing
                self.canvas.create_line(ax, y, ex, y,
                    arrow=tk.LAST, fill='#00FF00', width=3)
                self.canvas.create_text((ax+ex)//2, y - 10,
                    text="next", font=("Arial", 5, "italic"), fill='#888888')

        # Status bar
        crits = [c for c in self.train_order
                 if self.coaches[c].temperature and self.coaches[c].temperature >= 40]
        if crits:
            self.status_label.config(
                text=f"⚠ CRITICAL: {' '.join(f'C{c}' for c in crits)}",
                fg="#FF0000")
        else:
            chain = " → ".join(f"C{c}" for c in self.train_order)
            self.status_label.config(text=f"OK | {chain}", fg="#00FF00")

    def monitoring_loop(self):
        print("\nMonitoring started\n")
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
