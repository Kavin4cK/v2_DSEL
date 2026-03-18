#!/usr/bin/env python3
"""
Hot Axle Monitoring System - Raspberry Pi (3.5in TFT)
Real-time temperature sensing and visualization for each detected coach.

Gateway protocol:
  request:  TEMP,<id>
  response: TEMP,<id>,<left>,<right>,<temp>
"""

import os
import serial
import sys
import threading
import time
import tkinter as tk

# Use Pi display by default when running without desktop session.
os.environ.setdefault("DISPLAY", ":0")


class CoachNode:
    """Linked-list node representing a coach."""

    def __init__(self, coach_id, left_id=-1, right_id=-1):
        self.coach_id = coach_id
        self.left_id = left_id
        self.right_id = right_id
        self.temperature = None
        self.next = None


class TrainMonitor:
    def __init__(self, port="/dev/ttyUSB0", baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.serial_port = None

        self.coaches = {}
        self.train_order = []
        self.detected_coaches = set()
        self.head = None

        self.root = None
        self.canvas = None
        self.status_label = None
        self.meta_label = None

        self.running = False
        self.mapped = False
        self.last_update_ts = None

    def connect(self):
        """Connect to gateway and wait for READY."""
        try:
            print(f"Connecting to {self.port}...")
            self.serial_port = serial.Serial(
                self.port,
                self.baudrate,
                timeout=3,
                write_timeout=3,
            )
            time.sleep(2)
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()

            print("Waiting for READY signal...")
            start = time.time()
            while time.time() - start < 15:
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode("utf-8", errors="ignore").strip()
                    print(f"  RX: {line}")
                    if line == "READY":
                        print("Connected.\n")
                        return True
                time.sleep(0.1)

            print("No READY received.\n")
            return False
        except Exception as exc:
            print(f"Connection failed: {exc}")
            return False

    def send_command(self, command):
        """Send command and return non-error response line."""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                if not self.serial_port or not self.serial_port.is_open:
                    return None

                self.serial_port.reset_input_buffer()
                self.serial_port.reset_output_buffer()
                self.serial_port.write(f"{command}\n".encode("utf-8"))
                self.serial_port.flush()

                time.sleep(0.2)
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode("utf-8", errors="ignore").strip()
                    if line and line != "ERROR":
                        return line

                if attempt < (max_retries - 1):
                    time.sleep(0.1)
            except Exception:
                return None
        return None

    def parse_temp_response(self, response):
        """Parse TEMP response in both strict and legacy forms."""
        try:
            parts = [part.strip() for part in response.split(",")]
            if len(parts) < 4 or parts[0] != "TEMP":
                return None

            coach_id = int(parts[1])
            if len(parts) >= 5:
                left_id = int(parts[2])
                right_id = int(parts[3])
                temperature = float(parts[4])
            else:
                left_id = -1
                right_id = -1
                temperature = float(parts[3])

            return {
                "coach_id": coach_id,
                "left_id": left_id,
                "right_id": right_id,
                "temperature": temperature,
            }
        except (ValueError, IndexError):
            return None

    def detect_coaches(self):
        """Probe coach IDs 0..4 and cache metadata from gateway replies."""
        print("=" * 60)
        print("DETECTING COACHES")
        print("=" * 60)

        detected_info = {}
        self.detected_coaches.clear()

        for coach_id in range(5):
            print(f"Probing C{coach_id}... ", end="", flush=True)
            response = self.send_command(f"TEMP,{coach_id}")
            parsed = self.parse_temp_response(response) if response else None

            if parsed:
                detected_info[coach_id] = parsed
                self.detected_coaches.add(coach_id)
                print(f"OK ({parsed['temperature']:.1f} C)")
            else:
                print("not found")

        print(f"Detected: {sorted(self.detected_coaches)}\n")
        return detected_info

    def create_dynamic_topology(self, detected_info):
        """Build linked list using reported left/right pointers with safe fallback."""
        if not detected_info:
            print("No coaches detected.")
            return False

        self.coaches.clear()
        self.train_order = []

        for coach_id, info in detected_info.items():
            node = CoachNode(coach_id, info["left_id"], info["right_id"])
            node.temperature = info["temperature"]
            self.coaches[coach_id] = node

        if 0 in detected_info:
            start_id = 0
        else:
            left_end = [cid for cid, info in detected_info.items() if info["left_id"] == -1]
            start_id = min(left_end) if left_end else min(detected_info.keys())

        visited = set()
        current_id = start_id
        while current_id in detected_info and current_id not in visited:
            visited.add(current_id)
            self.train_order.append(current_id)
            next_id = detected_info[current_id]["right_id"]
            if next_id not in detected_info:
                break
            current_id = next_id

        for coach_id in sorted(detected_info.keys()):
            if coach_id not in visited:
                self.train_order.append(coach_id)

        for idx, coach_id in enumerate(self.train_order):
            next_id = self.train_order[idx + 1] if idx + 1 < len(self.train_order) else None
            self.coaches[coach_id].next = self.coaches[next_id] if next_id is not None else None

        self.head = self.coaches[self.train_order[0]] if self.train_order else None
        self.mapped = bool(self.train_order)

        chain = " -> ".join(f"C{coach_id}" for coach_id in self.train_order)
        print(f"Topology built: {chain}\n")
        return self.mapped

    def update_temperatures(self):
        """Poll every detected coach and refresh temperatures."""
        for coach_id in self.train_order:
            response = self.send_command(f"TEMP,{coach_id}")
            parsed = self.parse_temp_response(response) if response else None
            if not parsed:
                self.coaches[coach_id].temperature = None
                print(f"  C{coach_id}: no response")
                continue

            self.coaches[coach_id].left_id = parsed["left_id"]
            self.coaches[coach_id].right_id = parsed["right_id"]
            self.coaches[coach_id].temperature = parsed["temperature"]
            print(f"  C{coach_id}: {parsed['temperature']:.1f} C")

        self.last_update_ts = time.strftime("%H:%M:%S")

    @staticmethod
    def get_temp_color(temp):
        if temp is None:
            return "#555555"
        if temp < 30:
            return "#00FF00"
        if temp < 40:
            return "#FFD700"
        return "#FF0000"

    @staticmethod
    def get_temp_status(temp):
        if temp is None:
            return "N/A"
        if temp < 30:
            return "NORM"
        if temp < 40:
            return "WARN"
        return "CRIT"

    def create_gui(self):
        """Create 480x320 fullscreen UI for Raspberry Pi 3.5in display."""
        self.root = tk.Tk()
        self.root.title("Hot Axle Monitor")
        self.root.geometry("480x320")
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg="#141414")
        self.root.protocol("WM_DELETE_WINDOW", self.stop)

        tk.Label(
            self.root,
            text="HOT AXLE MONITOR",
            font=("Arial", 12, "bold"),
            bg="#141414",
            fg="#00FFAA",
        ).pack(pady=2)

        self.status_label = tk.Label(
            self.root,
            text="Initializing...",
            font=("Arial", 8, "bold"),
            bg="#141414",
            fg="#00FF00",
        )
        self.status_label.pack(pady=1)

        self.meta_label = tk.Label(
            self.root,
            text="",
            font=("Arial", 7),
            bg="#141414",
            fg="#C0C0C0",
        )
        self.meta_label.pack(pady=1)

        self.canvas = tk.Canvas(
            self.root,
            width=470,
            height=232,
            bg="#0B0B0B",
            highlightthickness=1,
            highlightbackground="#2F2F2F",
        )
        self.canvas.pack(pady=2)

        legend = tk.Frame(self.root, bg="#141414")
        legend.pack(pady=1)
        for color, text in [
            ("#00FF00", "Normal"),
            ("#FFD700", "Warn"),
            ("#FF0000", "Crit"),
            ("#555555", "NoData"),
        ]:
            tk.Label(legend, text="■", fg=color, bg="#141414", font=("Arial", 9)).pack(side=tk.LEFT, padx=1)
            tk.Label(legend, text=text, fg="white", bg="#141414", font=("Arial", 7)).pack(side=tk.LEFT, padx=3)

    def draw_train(self):
        if not self.mapped or not self.train_order:
            self.canvas.delete("all")
            self.canvas.create_text(235, 115, text="No mapped coaches", fill="white", font=("Arial", 12, "bold"))
            return

        self.canvas.delete("all")
        coach_count = len(self.train_order)

        if coach_count >= 5:
            node_width, node_height, gap = 64, 84, 10
        elif coach_count == 4:
            node_width, node_height, gap = 76, 86, 12
        elif coach_count == 3:
            node_width, node_height, gap = 92, 90, 16
        else:
            node_width, node_height, gap = 112, 94, 18

        total_width = coach_count * node_width + (coach_count - 1) * gap
        start_x = max(6, (470 - total_width) // 2)
        center_y = 118

        for idx, coach_id in enumerate(self.train_order):
            node = self.coaches[coach_id]
            x = start_x + idx * (node_width + gap)
            temp = node.temperature

            self.canvas.create_rectangle(
                x,
                center_y - node_height // 2,
                x + node_width,
                center_y + node_height // 2,
                fill=self.get_temp_color(temp),
                outline="white",
                width=2,
            )

            self.canvas.create_text(
                x + node_width // 2,
                center_y - node_height // 2 + 12,
                text=f"C{coach_id}",
                font=("Arial", 9, "bold"),
                fill="black",
            )

            temperature_text = f"{temp:.1f} C" if temp is not None else "---"
            self.canvas.create_text(
                x + node_width // 2,
                center_y - 2,
                text=temperature_text,
                font=("Arial", 11, "bold"),
                fill="black",
            )

            self.canvas.create_text(
                x + node_width // 2,
                center_y + node_height // 2 - 12,
                text=self.get_temp_status(temp),
                font=("Arial", 7, "bold"),
                fill="black",
            )

            if idx < coach_count - 1:
                arrow_start = x + node_width
                arrow_end = arrow_start + gap
                self.canvas.create_line(
                    arrow_start,
                    center_y,
                    arrow_end,
                    center_y,
                    fill="#00FFAA",
                    width=3,
                    arrow=tk.LAST,
                )

        critical = [
            coach_id
            for coach_id in self.train_order
            if self.coaches[coach_id].temperature is not None and self.coaches[coach_id].temperature >= 40
        ]

        if critical:
            msg = "CRITICAL: " + " ".join(f"C{coach_id}" for coach_id in critical)
            color = "#FF3333"
        else:
            msg = "All detected coaches in safe range"
            color = "#00FF00"

        self.status_label.config(text=msg, fg=color)
        chain = " -> ".join(f"C{coach_id}" for coach_id in self.train_order)
        updated = self.last_update_ts if self.last_update_ts else "--:--:--"
        self.meta_label.config(text=f"Detected: {coach_count} | {chain} | Updated: {updated}")

    def monitoring_loop(self):
        print("Starting monitoring loop...\n")
        cycle = 0
        while self.running:
            cycle += 1
            print(f"--- Cycle {cycle} ---")
            self.update_temperatures()
            if self.root:
                self.root.after(0, self.draw_train)
            print()
            time.sleep(1)

    def stop(self):
        self.running = False
        if self.root:
            self.root.destroy()

    def run(self):
        print("=" * 58)
        print("HOT AXLE MONITORING SYSTEM - RASPBERRY PI (3.5in TFT)")
        print("=" * 58)

        if not self.connect():
            print("Startup failed: gateway connection issue.")
            return

        print("Waiting 5s for neighbor discovery...")
        time.sleep(5)

        detected_info = self.detect_coaches()
        if not self.create_dynamic_topology(detected_info):
            print("Startup failed: no coach topology available.")
            return

        self.create_gui()
        self.draw_train()

        self.running = True
        monitor_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        monitor_thread.start()

        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            print("Shutdown complete.")


if __name__ == "__main__":
    serial_port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
    monitor = TrainMonitor(port=serial_port, baudrate=9600)
    monitor.run()