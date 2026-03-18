#!/usr/bin/env python3
"""
Hot Axle Monitoring System - Raspberry Pi Controller (DYNAMIC DETECTION)
Displays train as linked list with real-time temperature monitoring
Auto-detects configuration:
  - 3 coaches: C0 → C1 → C2
  - 4 coaches: C0 → C1 → C3 → C2
Optimized for 3.5" TFT Display (480x320)
"""

import serial
import time
import tkinter as tk
from tkinter import ttk
import threading
import sys
import os

# Set display for TFT screen
os.environ['DISPLAY'] = ':0'

class CoachNode:
    """Represents a coach in the linked list"""
    def __init__(self, coach_id, left_id, right_id):
        self.coach_id = coach_id
        self.left_id = left_id
        self.right_id = right_id
        self.temperature = None
        self.next = None

class TrainMonitor:
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600):
        # Serial connection to Gateway Arduino
        self.serial_port = None
        self.port = port
        self.baudrate = baudrate
        
        # Train data structures - DYNAMIC
        self.coaches = {}
        self.head = None
        self.train_order = []
        self.detected_coaches = set()
        
        # GUI
        self.root = None
        self.canvas = None
        self.status_label = None
        
        # Control
        self.running = False
        self.mapped = False
        
    def connect(self):
        """Connect to Arduino gateway via USB"""
        try:
            print(f"Connecting to {self.port}...")
            self.serial_port = serial.Serial(
                self.port, 
                self.baudrate, 
                timeout=3,
                write_timeout=3
            )
            time.sleep(3)  # Wait for Arduino reset
            
            # Flush buffers
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()
            
            # Wait for READY signal
            print("Waiting for READY signal...")
            start_time = time.time()
            ready_found = False
            
            while time.time() - start_time < 15:
                if self.serial_port.in_waiting:
                    try:
                        line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                        print(f"  Received: '{line}'")
                        if line == "READY":
                            ready_found = True
                            break
                    except Exception as e:
                        print(f"  Read error: {e}")
                time.sleep(0.1)
            
            if ready_found:
                print("✓ Gateway connected and ready\n")
                return True
            else:
                print("✗ Gateway did not send READY signal\n")
                return False
            
        except serial.SerialException as e:
            print(f"✗ Serial connection failed: {e}")
            print(f"  Try: sudo chmod 666 {self.port}")
            return False
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
    
    def send_command(self, command):
        """Send command and get response with robust error handling"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Check if port is still open
                if not self.serial_port or not self.serial_port.is_open:
                    print(f"  Serial port closed, attempting reconnect...")
                    return None
                
                # Flush stale input before request
                self.serial_port.reset_input_buffer()
                
                # Send command
                cmd_bytes = f"{command}\n".encode('utf-8')
                self.serial_port.write(cmd_bytes)
                self.serial_port.flush()
                
                # Accept only real TEMP packets and ignore READY noise.
                deadline = time.time() + 2.0
                while time.time() < deadline:
                    if self.serial_port.in_waiting:
                        response = self.serial_port.readline().decode('utf-8', errors='ignore').strip()

                        if not response or response == "READY":
                            continue
                        if response == "ERROR":
                            break
                        if response.startswith("TEMP,"):
                            return response

                    time.sleep(0.03)

                if attempt < max_retries - 1:
                    time.sleep(0.15)
                    continue
                return None
                    
            except (OSError, IOError) as e:
                # I/O error - serial connection issue
                print(f"  I/O Error: {e}")
                return None
            except UnicodeDecodeError as e:
                if attempt < max_retries - 1:
                    time.sleep(0.1)
                    continue
                return None
            except Exception as e:
                print(f"  Unexpected error: {type(e).__name__}: {e}")
                return None
        
        return None
    
    def detect_coaches(self):
        """Detect which coaches are physically present"""
        print("=" * 60)
        print("🔍 DETECTING COACH PRESENCE")
        print("=" * 60)
        print()
        
        self.detected_coaches.clear()
        
        # Current setup: C0, C1, C2, C3
        for coach_id in [0, 1, 2, 3]:
            print(f"Probing Coach {coach_id}...", end=" ")
            response = self.send_command(f"TEMP,{coach_id}")
            
            if response and response.startswith("TEMP,"):
                self.detected_coaches.add(coach_id)
                print(f"✓ DETECTED")
            else:
                print(f"✗ Not found")
        
        print()
        print(f"Detected coaches: {sorted(self.detected_coaches)}")
        print()
        
        return len(self.detected_coaches) > 0
    
    def create_dynamic_topology(self):
        """Create train topology based on detected coaches"""
        print("=" * 60)
        print("🔗 CREATING TRAIN TOPOLOGY")
        print("=" * 60)
        print()
        
        num_coaches = len(self.detected_coaches)
        
        if num_coaches == 0:
            print("✗ No coaches detected!")
            return False
        
        # Clear previous topology
        self.coaches.clear()
        
        # Determine configuration based on which coaches are present
        has_c0 = 0 in self.detected_coaches
        has_c1 = 1 in self.detected_coaches
        has_c2 = 2 in self.detected_coaches
        has_c3 = 3 in self.detected_coaches
        
        # CASE 1: Only C0 and C1 present (2 coaches)
        if has_c0 and has_c1 and not has_c2 and not has_c3:
            print("Configuration: C0 → C1 (2 coaches)")
            print()
            
            # Create Coach 0
            node0 = CoachNode(coach_id=0, left_id=-1, right_id=1)
            self.coaches[0] = node0
            print(f"  ✓ Coach 0: NULL ← [C0] → C1")
            
            # Create Coach 1
            node1 = CoachNode(coach_id=1, left_id=0, right_id=-1)
            self.coaches[1] = node1
            print(f"  ✓ Coach 1: C0 ← [C1] → NULL")
            
            self.train_order = [0, 1]
        
        # CASE 2: C0, C1, C2 present (3 coaches, no C3)
        elif has_c0 and has_c1 and has_c2 and not has_c3:
            print("Configuration: C0 → C1 → C2 (3 coaches)")
            print()
            
            # Create Coach 0
            node0 = CoachNode(coach_id=0, left_id=-1, right_id=1)
            self.coaches[0] = node0
            print(f"  ✓ Coach 0: NULL ← [C0] → C1")
            
            # Create Coach 1
            node1 = CoachNode(coach_id=1, left_id=0, right_id=2)
            self.coaches[1] = node1
            print(f"  ✓ Coach 1: C0 ← [C1] → C2")
            
            # Create Coach 2
            node2 = CoachNode(coach_id=2, left_id=1, right_id=-1)
            self.coaches[2] = node2
            print(f"  ✓ Coach 2: C1 ← [C2] → NULL")
            
            self.train_order = [0, 1, 2]
        
        # CASE 2b: C0, C1, C3 present (3 coaches, with C3 instead of C2)
        elif has_c0 and has_c1 and has_c3 and not has_c2:
            print("Configuration: C0 → C1 → C3 (3 coaches with C3)")
            print()
            
            # Create Coach 0
            node0 = CoachNode(coach_id=0, left_id=-1, right_id=1)
            self.coaches[0] = node0
            print(f"  ✓ Coach 0: NULL ← [C0] → C1")
            
            # Create Coach 1
            node1 = CoachNode(coach_id=1, left_id=0, right_id=3)
            self.coaches[1] = node1
            print(f"  ✓ Coach 1: C0 ← [C1] → C3")
            
            # Create Coach 3
            node3 = CoachNode(coach_id=3, left_id=1, right_id=-1)
            self.coaches[3] = node3
            print(f"  ✓ Coach 3: C1 ← [C3] → NULL")
            
            self.train_order = [0, 1, 3]
        
        # CASE 3: All coaches present including C3 (4 coaches)
        elif has_c0 and has_c1 and has_c2 and has_c3:
            print("Configuration: C0 → C1 → C3 → C2 (4 coaches)")
            print()
            
            # Create Coach 0
            node0 = CoachNode(coach_id=0, left_id=-1, right_id=1)
            self.coaches[0] = node0
            print(f"  ✓ Coach 0: NULL ← [C0] → C1")
            
            # Create Coach 1
            node1 = CoachNode(coach_id=1, left_id=0, right_id=3)
            self.coaches[1] = node1
            print(f"  ✓ Coach 1: C0 ← [C1] → C3")
            
            # Create Coach 3 (NEW - inserted between C1 and C2)
            node3 = CoachNode(coach_id=3, left_id=1, right_id=2)
            self.coaches[3] = node3
            print(f"  ✓ Coach 3: C1 ← [C3] → C2 ⭐ NEW COACH")
            
            # Create Coach 2
            node2 = CoachNode(coach_id=2, left_id=3, right_id=-1)
            self.coaches[2] = node2
            print(f"  ✓ Coach 2: C3 ← [C2] → NULL")
            
            self.train_order = [0, 1, 3, 2]
        
        # CASE 4: Other combinations (fallback - minimal train)
        else:
            print(f"⚠ Unusual configuration detected: {sorted(self.detected_coaches)}")
            print("Building minimal train with detected coaches...")
            print()
            
            # Build a simple chain with whatever we have
            detected_list = sorted(self.detected_coaches)
            for i, coach_id in enumerate(detected_list):
                left_id = detected_list[i-1] if i > 0 else -1
                right_id = detected_list[i+1] if i < len(detected_list)-1 else -1
                
                node = CoachNode(coach_id=coach_id, left_id=left_id, right_id=right_id)
                self.coaches[coach_id] = node
                
                left_str = f"C{left_id}" if left_id != -1 else "NULL"
                right_str = f"C{right_id}" if right_id != -1 else "NULL"
                print(f"  ✓ Coach {coach_id}: {left_str} ← [C{coach_id}] → {right_str}")
            
            self.train_order = detected_list
        
        print()
        print("=" * 60)
        print(f"TOPOLOGY COMPLETE: {len(self.coaches)} coaches configured")
        print(f"Train order: {' → '.join([f'C{id}' for id in self.train_order])}")
        print("=" * 60)
        print()
        
        # Build linked list
        self.build_linked_list()
        self.mapped = True
        
        return True
    
    def build_linked_list(self):
        """Build linked list structure from topology"""
        print("🔗 Building linked list structure...")
        
        # Set head
        self.head = self.coaches[0]
        print(f"  ✓ Head coach: C0")
        
        # Link nodes according to train_order
        for i in range(len(self.train_order) - 1):
            current_id = self.train_order[i]
            next_id = self.train_order[i + 1]
            self.coaches[current_id].next = self.coaches[next_id]
        
        # Last coach points to None
        last_id = self.train_order[-1]
        self.coaches[last_id].next = None
        
        print(f"  ✓ Linked list built: {len(self.coaches)} coaches")
        print(f"  ✓ Train order: {' → '.join([f'C{id}' for id in self.train_order])}\n")
    
    def update_temperatures(self):
        """Continuously update temperatures from all coaches"""
        for coach_id in self.train_order:
            try:
                response = self.send_command(f"TEMP,{coach_id}")
                
                if response and response != "ERROR":
                    try:
                        parts = response.split(',')
                        if len(parts) >= 5:
                            temp = float(parts[4])
                            self.coaches[coach_id].temperature = temp
                            print(f"✓ C{coach_id}: {temp:.1f}°C")
                        else:
                            print(f"⚠ C{coach_id}: Invalid format - {response}")
                    except (ValueError, IndexError) as e:
                        print(f"⚠ C{coach_id}: Parse error - {e}")
                else:
                    print(f"⚠ C{coach_id}: No response")
            except Exception as e:
                print(f"⚠ C{coach_id}: Communication error - {e}")
                continue
    
    def get_temp_color(self, temp):
        """Determine color based on temperature"""
        if temp is None:
            return "#555555"
        elif temp < 30:
            return "#00FF00"
        elif temp < 40:
            return "#FFD700"
        else:
            return "#FF0000"
    
    def get_temp_status(self, temp):
        """Get status text for temperature"""
        if temp is None:
            return "NO DATA"
        elif temp < 30:
            return "NORMAL"
        elif temp < 40:
            return "WARNING"
        else:
            return "CRITICAL"
    
    def create_gui(self):
        """Create visualization GUI for 3.5 inch TFT Display"""
        self.root = tk.Tk()
        self.root.title("Hot Axle Monitor")
        
        # 3.5" TFT Display Resolution (typically 480x320)
        self.root.geometry("480x320")
        
        # Fullscreen for TFT display
        self.root.attributes('-fullscreen', True)
        
        # Set display to framebuffer if available
        self.root.configure(bg='#1a1a1a')
        
        # Title - Compact for small screen
        title = tk.Label(
            self.root,
            text="HOT AXLE MONITOR",
            font=("Arial", 11, "bold"),
            bg='#1a1a1a',
            fg='#00FF00'
        )
        title.pack(pady=3)
        
        # Status - Compact
        self.status_label = tk.Label(
            self.root,
            text="Status: Initializing...",
            font=("Arial", 8, "bold"),
            bg='#1a1a1a',
            fg='#00FF00'
        )
        self.status_label.pack(pady=2)
        
        # Canvas - Sized for 480x320 display
        self.canvas = tk.Canvas(
            self.root,
            width=470,
            height=240,
            bg='#0d0d0d',
            highlightthickness=1,
            highlightbackground='#333333'
        )
        self.canvas.pack(pady=3)
        
        # Legend - Compact
        legend_frame = tk.Frame(self.root, bg='#1a1a1a')
        legend_frame.pack(pady=2)
        
        legends = [
            ("#00FF00", "Normal"),
            ("#FFD700", "Warn"),
            ("#FF0000", "Crit"),
            ("#555555", "N/A")
        ]
        
        for color, text in legends:
            tk.Label(
                legend_frame,
                text="■",
                fg=color,
                bg='#1a1a1a',
                font=("Arial", 10)
            ).pack(side=tk.LEFT, padx=2)
            tk.Label(
                legend_frame,
                text=text,
                fg="white",
                bg='#1a1a1a',
                font=("Arial", 7)
            ).pack(side=tk.LEFT, padx=3)
    
    def draw_train(self):
        """Draw train as linked list - Optimized for 480x320 TFT - DYNAMIC LAYOUT"""
        if not self.mapped:
            self.canvas.create_text(
                235, 120,
                text="Train not mapped yet...",
                font=("Arial", 10),
                fill='white'
            )
            return
        
        self.canvas.delete("all")
        
        num_coaches = len(self.train_order)
        if num_coaches == 0:
            return
        
        # Dynamic layout based on number of coaches
        if num_coaches == 4:
            # 4 coaches - tightest spacing
            node_width = 70
            node_height = 75
            spacing = 95
            start_x = 15
            font_size_temp = 9
            font_size_label = 8
        elif num_coaches == 3:
            # 3 coaches - medium spacing
            node_width = 90
            node_height = 80
            spacing = 120
            start_x = 40
            font_size_temp = 10
            font_size_label = 9
        else:  # 2 coaches
            # 2 coaches - most spacing
            node_width = 110
            node_height = 90
            spacing = 140
            start_x = 60
            font_size_temp = 12
            font_size_label = 10
        
        y = 120
        
        # Draw each coach
        for i, coach_id in enumerate(self.train_order):
            node = self.coaches[coach_id]
            x = start_x + (i * spacing)
            
            temp = node.temperature
            color = self.get_temp_color(temp)
            status = self.get_temp_status(temp)
            
            # Highlight C3 with yellow outline if present
            outline_color = 'yellow' if coach_id == 3 else 'white'
            outline_width = 3 if coach_id == 3 else 2
            
            # Node rectangle
            self.canvas.create_rectangle(
                x, y - node_height//2,
                x + node_width, y + node_height//2,
                fill=color,
                outline=outline_color,
                width=outline_width
            )
            
            # Coach label
            self.canvas.create_text(
                x + node_width//2, y - 28,
                text=f"C{coach_id}",
                font=("Arial", font_size_label, "bold"),
                fill='black'
            )
            
            # Temperature
            temp_text = f"{temp:.1f}°" if temp is not None else "---"
            self.canvas.create_text(
                x + node_width//2, y - 5,
                text=temp_text,
                font=("Arial", font_size_temp, "bold"),
                fill='black'
            )
            
            # Status
            status_short = status[:4]
            self.canvas.create_text(
                x + node_width//2, y + 16,
                text=status_short,
                font=("Arial", 6, "bold"),
                fill='black'
            )
            
            # Left pointer
            if node.left_id != -1:
                self.canvas.create_text(
                    x + 8, y + 33,
                    text=f"←{node.left_id}",
                    font=("Arial", 6),
                    fill='#AAAAAA'
                )
            else:
                self.canvas.create_text(
                    x + 8, y + 33,
                    text="←X",
                    font=("Arial", 6),
                    fill='#666666'
                )
            
            # Right pointer
            if node.right_id != -1:
                self.canvas.create_text(
                    x + node_width - 8, y + 33,
                    text=f"{node.right_id}→",
                    font=("Arial", 6),
                    fill='#AAAAAA'
                )
            else:
                self.canvas.create_text(
                    x + node_width - 8, y + 33,
                    text="X→",
                    font=("Arial", 6),
                    fill='#666666'
                )
            
            # Arrow to next
            if i < num_coaches - 1:
                arrow_start_x = x + node_width
                arrow_end_x = x + spacing
                
                self.canvas.create_line(
                    arrow_start_x, y,
                    arrow_end_x, y,
                    arrow=tk.LAST,
                    fill='#00FF00',
                    width=3
                )
                
                self.canvas.create_text(
                    (arrow_start_x + arrow_end_x) // 2, y - 10,
                    text="next",
                    font=("Arial", 5, "italic"),
                    fill='#888888'
                )
        
        # Update status - More compact
        critical_count = sum(1 for id in self.train_order 
                           if self.coaches[id].temperature and 
                           self.coaches[id].temperature >= 40)
        
        if critical_count > 0:
            status_text = f"⚠ ALERT: {critical_count} CRITICAL!"
            status_color = "#FF0000"
        else:
            # Display configuration type
            if num_coaches == 2:
                config_text = "2-Coach"
            elif num_coaches == 3:
                # Check if it's C0-C1-C3 or C0-C1-C2
                if 3 in self.train_order and 2 not in self.train_order:
                    config_text = "3-Coach (C3)"
                else:
                    config_text = "3-Coach"
            elif num_coaches == 4:
                config_text = "4-Coach (+C3)"
            else:
                config_text = f"{num_coaches}-Coach"
            
            status_text = f"{config_text} | All OK"
            status_color = "#00FF00"
        
        self.status_label.config(text=status_text, fg=status_color)
    
    def monitoring_loop(self):
        """Background monitoring thread - FASTER UPDATE"""
        print("\n🔄 Starting temperature monitoring loop...\n")
        cycle = 0
        while self.running:
            if self.mapped:
                cycle += 1
                print(f"--- Cycle {cycle} ---")
                self.update_temperatures()
                self.root.after(0, self.draw_train)
                print()
            time.sleep(1)  # Faster - 1 second update interval
    
    def run(self):
        """Main application"""
        print("=" * 60)
        print("🚆 HOT AXLE MONITORING SYSTEM - RASPBERRY PI")
        print("=" * 60)
        print()
        
        # Connect
        if not self.connect():
            print("\n❌ STARTUP FAILED - Cannot connect to gateway")
            return
        
        # Wait for neighbor discovery
        print("⏳ Waiting for coaches to complete neighbor discovery (5s)...")
        time.sleep(5)
        
        # Detect which coaches are present
        if not self.detect_coaches():
            print("\n❌ STARTUP FAILED - No coaches detected")
            return
        
        # Create dynamic topology based on detection
        if not self.create_dynamic_topology():
            print("\n❌ STARTUP FAILED - Topology creation failed")
            return
        
        # Create GUI
        print("🖥  Launching GUI...\n")
        self.create_gui()
        
        # Start monitoring
        self.running = True
        monitor_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        monitor_thread.start()
        
        # Initial draw
        self.draw_train()
        
        # Start GUI
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("\nShutting down...")
        
        # Cleanup
        self.running = False
        if self.serial_port:
            self.serial_port.close()
        print("✓ Shutdown complete")

if __name__ == "__main__":
    # Check for port argument
    port = '/dev/ttyUSB0'
    if len(sys.argv) > 1:
        port = sys.argv[1]
    
    monitor = TrainMonitor(port=port, baudrate=9600)
    monitor.run()