#!/usr/bin/env python3
"""
Hot Axle Monitoring System - Raspberry Pi Controller (HDMI MONITOR VERSION)
Displays train as linked list with real-time temperature monitoring
Auto-detects configuration:
  - 2 coaches: C0 → C1
  - 3 coaches: C0 → C1 → C2 or C0 → C1 → C3
  - 4 coaches: C0 → C1 → C3 → C2
Optimized for HDMI Display (1920x1080 or 1280x720)
"""

import serial
import time
import tkinter as tk
from tkinter import ttk
import threading
import sys
import os

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
        self.config_label = None
        
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
            time.sleep(3)
            
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()
            
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
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                if not self.serial_port or not self.serial_port.is_open:
                    print(f"  Serial port closed")
                    return None
                
                self.serial_port.reset_input_buffer()
                self.serial_port.reset_output_buffer()
                
                cmd_bytes = f"{command}\n".encode('utf-8')
                self.serial_port.write(cmd_bytes)
                self.serial_port.flush()
                
                time.sleep(0.25)
                
                if self.serial_port.in_waiting:
                    response = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    
                    if response and response != "ERROR":
                        return response
                    elif response == "ERROR":
                        if attempt < max_retries - 1:
                            time.sleep(0.1)
                            continue
                        return None
                else:
                    if attempt < max_retries - 1:
                        time.sleep(0.1)
                        continue
                    return None
                    
            except (OSError, IOError) as e:
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
        
        for coach_id in [0, 1, 2, 3]:
            print(f"Probing Coach {coach_id}...", end=" ")
            response = self.send_command(f"TEMP,{coach_id}")
            
            if response and response != "ERROR":
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
        
        self.coaches.clear()
        
        has_c0 = 0 in self.detected_coaches
        has_c1 = 1 in self.detected_coaches
        has_c2 = 2 in self.detected_coaches
        has_c3 = 3 in self.detected_coaches
        
        if has_c0 and has_c1 and not has_c2 and not has_c3:
            print("Configuration: C0 → C1 (2 coaches)")
            print()
            
            node0 = CoachNode(coach_id=0, left_id=-1, right_id=1)
            self.coaches[0] = node0
            print(f"  ✓ Coach 0: NULL ← [C0] → C1")
            
            node1 = CoachNode(coach_id=1, left_id=0, right_id=-1)
            self.coaches[1] = node1
            print(f"  ✓ Coach 1: C0 ← [C1] → NULL")
            
            self.train_order = [0, 1]
        
        elif has_c0 and has_c1 and has_c2 and not has_c3:
            print("Configuration: C0 → C1 → C2 (3 coaches)")
            print()
            
            node0 = CoachNode(coach_id=0, left_id=-1, right_id=1)
            self.coaches[0] = node0
            print(f"  ✓ Coach 0: NULL ← [C0] → C1")
            
            node1 = CoachNode(coach_id=1, left_id=0, right_id=2)
            self.coaches[1] = node1
            print(f"  ✓ Coach 1: C0 ← [C1] → C2")
            
            node2 = CoachNode(coach_id=2, left_id=1, right_id=-1)
            self.coaches[2] = node2
            print(f"  ✓ Coach 2: C1 ← [C2] → NULL")
            
            self.train_order = [0, 1, 2]
        
        elif has_c0 and has_c1 and has_c3 and not has_c2:
            print("Configuration: C0 → C1 → C3 (3 coaches with C3)")
            print()
            
            node0 = CoachNode(coach_id=0, left_id=-1, right_id=1)
            self.coaches[0] = node0
            print(f"  ✓ Coach 0: NULL ← [C0] → C1")
            
            node1 = CoachNode(coach_id=1, left_id=0, right_id=3)
            self.coaches[1] = node1
            print(f"  ✓ Coach 1: C0 ← [C1] → C3")
            
            node3 = CoachNode(coach_id=3, left_id=1, right_id=-1)
            self.coaches[3] = node3
            print(f"  ✓ Coach 3: C1 ← [C3] → NULL")
            
            self.train_order = [0, 1, 3]
        
        elif has_c0 and has_c1 and has_c2 and has_c3:
            print("Configuration: C0 → C1 → C3 → C2 (4 coaches)")
            print()
            
            node0 = CoachNode(coach_id=0, left_id=-1, right_id=1)
            self.coaches[0] = node0
            print(f"  ✓ Coach 0: NULL ← [C0] → C1")
            
            node1 = CoachNode(coach_id=1, left_id=0, right_id=3)
            self.coaches[1] = node1
            print(f"  ✓ Coach 1: C0 ← [C1] → C3")
            
            node3 = CoachNode(coach_id=3, left_id=1, right_id=2)
            self.coaches[3] = node3
            print(f"  ✓ Coach 3: C1 ← [C3] → C2 ⭐ NEW COACH")
            
            node2 = CoachNode(coach_id=2, left_id=3, right_id=-1)
            self.coaches[2] = node2
            print(f"  ✓ Coach 2: C3 ← [C2] → NULL")
            
            self.train_order = [0, 1, 3, 2]
        
        else:
            print(f"⚠ Unusual configuration detected: {sorted(self.detected_coaches)}")
            print("Building minimal train with detected coaches...")
            print()
            
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
        
        self.build_linked_list()
        self.mapped = True
        
        return True
    
    def build_linked_list(self):
        """Build linked list structure from topology"""
        print("🔗 Building linked list structure...")
        
        self.head = self.coaches[0]
        print(f"  ✓ Head coach: C0")
        
        for i in range(len(self.train_order) - 1):
            current_id = self.train_order[i]
            next_id = self.train_order[i + 1]
            self.coaches[current_id].next = self.coaches[next_id]
        
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
                        if len(parts) >= 4:
                            temp = float(parts[3])
                            self.coaches[coach_id].temperature = temp
                            print(f"✓ C{coach_id}: {temp:.1f}°C")
                        else:
                            print(f"⚠ C{coach_id}: Invalid format")
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
        """Create visualization GUI for HDMI Monitor (Full HD or HD)"""
        self.root = tk.Tk()
        self.root.title("Hot Axle Monitoring System - Linked List Visualization")
        
        # Full HD resolution
        self.root.geometry("1920x1080")

        # --- FIX: Linux/Raspberry Pi compatible maximize ---
        # 'zoomed' is Windows-only; use attributes('-zoomed', True) on Linux
        try:
            self.root.attributes('-zoomed', True)   # Works on Linux / Raspberry Pi OS
        except tk.TclError:
            try:
                self.root.state('zoomed')           # Fallback for Windows
            except tk.TclError:
                self.root.geometry("1920x1080")     # Last resort: fixed size
        # ---------------------------------------------------
        
        self.root.configure(bg='#0a0a0a')
        
        # Header frame
        header_frame = tk.Frame(self.root, bg='#0066CC', height=100)
        header_frame.pack(fill=tk.X, side=tk.TOP)
        header_frame.pack_propagate(False)
        
        # Main title
        title = tk.Label(
            header_frame,
            text="🚆 DISTRIBUTED HOT AXLE MONITORING SYSTEM",
            font=("Arial", 32, "bold"),
            bg='#0066CC',
            fg='white'
        )
        title.pack(pady=10)
        
        # Subtitle
        subtitle = tk.Label(
            header_frame,
            text="Real-Time Linked List Based Railway Safety Monitoring",
            font=("Arial", 18),
            bg='#0066CC',
            fg='#E0E0E0'
        )
        subtitle.pack()
        
        # Status frame
        status_frame = tk.Frame(self.root, bg='#1a1a1a', height=80)
        status_frame.pack(fill=tk.X, side=tk.TOP)
        status_frame.pack_propagate(False)
        
        # Configuration label
        self.config_label = tk.Label(
            status_frame,
            text="Configuration: Detecting...",
            font=("Arial", 16, "bold"),
            bg='#1a1a1a',
            fg='#00FF00'
        )
        self.config_label.pack(pady=5)
        
        # Status label
        self.status_label = tk.Label(
            status_frame,
            text="Status: Initializing...",
            font=("Arial", 14),
            bg='#1a1a1a',
            fg='#FFFFFF'
        )
        self.status_label.pack(pady=5)
        
        # Canvas frame with border
        canvas_frame = tk.Frame(self.root, bg='#2a2a2a', padx=20, pady=20)
        canvas_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        
        # Main canvas for linked list
        self.canvas = tk.Canvas(
            canvas_frame,
            bg='#0d0d0d',
            highlightthickness=3,
            highlightbackground='#0066CC'
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Legend frame
        legend_frame = tk.Frame(self.root, bg='#1a1a1a', height=60)
        legend_frame.pack(fill=tk.X, side=tk.BOTTOM)
        legend_frame.pack_propagate(False)
        
        tk.Label(
            legend_frame,
            text="Temperature Status:",
            font=("Arial", 14, "bold"),
            bg='#1a1a1a',
            fg='white'
        ).pack(side=tk.LEFT, padx=20)
        
        legends = [
            ("#00FF00", "Normal (<30°C)"),
            ("#FFD700", "Warning (30-40°C)"),
            ("#FF0000", "Critical (>40°C)"),
            ("#555555", "No Data")
        ]
        
        for color, text in legends:
            tk.Label(
                legend_frame,
                text="■",
                fg=color,
                bg='#1a1a1a',
                font=("Arial", 24)
            ).pack(side=tk.LEFT, padx=5)
            tk.Label(
                legend_frame,
                text=text,
                fg="white",
                bg='#1a1a1a',
                font=("Arial", 12)
            ).pack(side=tk.LEFT, padx=10)
    
    def draw_train(self):
        """Draw train as linked list - FULL HD OPTIMIZED"""
        if not self.mapped:
            self.canvas.create_text(
                960, 400,
                text="Train topology not mapped yet...",
                font=("Arial", 24),
                fill='white'
            )
            return
        
        self.canvas.delete("all")
        
        # Get canvas dimensions
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # If canvas not yet rendered, use default
        if canvas_width <= 1:
            canvas_width = 1880
            canvas_height = 800
        
        num_coaches = len(self.train_order)
        if num_coaches == 0:
            return
        
        # Dynamic layout based on number of coaches
        if num_coaches == 4:
            node_width = 280
            node_height = 200
            spacing = 350
        elif num_coaches == 3:
            node_width = 320
            node_height = 220
            spacing = 420
        else:  # 2 coaches
            node_width = 380
            node_height = 240
            spacing = 500
        
        # Center horizontally
        total_width = (num_coaches * node_width) + ((num_coaches - 1) * (spacing - node_width))
        start_x = (canvas_width - total_width) // 2
        y = canvas_height // 2
        
        # Draw each coach
        for i, coach_id in enumerate(self.train_order):
            node = self.coaches[coach_id]
            x = start_x + (i * spacing)
            
            temp = node.temperature
            color = self.get_temp_color(temp)
            status = self.get_temp_status(temp)
            
            # Highlight C3 with yellow outline if present
            outline_color = 'yellow' if coach_id == 3 else 'white'
            outline_width = 5 if coach_id == 3 else 3
            
            # Node rectangle with shadow
            self.canvas.create_rectangle(
                x + 5, y - node_height//2 + 5,
                x + node_width + 5, y + node_height//2 + 5,
                fill='#000000',
                outline=''
            )
            
            # Main node rectangle
            self.canvas.create_rectangle(
                x, y - node_height//2,
                x + node_width, y + node_height//2,
                fill=color,
                outline=outline_color,
                width=outline_width
            )
            
            # Coach label
            self.canvas.create_text(
                x + node_width//2, y - 70,
                text=f"COACH {coach_id}",
                font=("Arial", 28, "bold"),
                fill='black'
            )
            
            # Temperature
            temp_text = f"{temp:.1f}°C" if temp is not None else "---"
            self.canvas.create_text(
                x + node_width//2, y - 20,
                text=temp_text,
                font=("Arial", 36, "bold"),
                fill='black'
            )
            
            # Status
            self.canvas.create_text(
                x + node_width//2, y + 30,
                text=status,
                font=("Arial", 18, "bold"),
                fill='black'
            )
            
            # Left pointer
            if node.left_id != -1:
                self.canvas.create_text(
                    x + 20, y + 75,
                    text=f"← {node.left_id}",
                    font=("Arial", 14),
                    fill='#AAAAAA'
                )
            else:
                self.canvas.create_text(
                    x + 20, y + 75,
                    text="← NULL",
                    font=("Arial", 14),
                    fill='#666666'
                )
            
            # Right pointer
            if node.right_id != -1:
                self.canvas.create_text(
                    x + node_width - 20, y + 75,
                    text=f"{node.right_id} →",
                    font=("Arial", 14),
                    fill='#AAAAAA'
                )
            else:
                self.canvas.create_text(
                    x + node_width - 20, y + 75,
                    text="NULL →",
                    font=("Arial", 14),
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
                    width=8
                )
                
                self.canvas.create_text(
                    (arrow_start_x + arrow_end_x) // 2, y - 30,
                    text="next",
                    font=("Arial", 14, "italic"),
                    fill='#00FF00'
                )
        
        # Update configuration and status labels
        critical_count = sum(1 for id in self.train_order 
                           if self.coaches[id].temperature and 
                           self.coaches[id].temperature >= 40)
        
        # Configuration text
        if num_coaches == 2:
            config_text = "Configuration: 2-Coach System (C0 → C1)"
        elif num_coaches == 3:
            if 3 in self.train_order and 2 not in self.train_order:
                config_text = "Configuration: 3-Coach System with C3 (C0 → C1 → C3)"
            else:
                config_text = "Configuration: 3-Coach System (C0 → C1 → C2)"
        elif num_coaches == 4:
            config_text = "Configuration: 4-Coach System with C3 Inserted (C0 → C1 → C3 → C2)"
        else:
            config_text = f"Configuration: {num_coaches}-Coach System"
        
        self.config_label.config(text=config_text)
        
        # Status text
        if critical_count > 0:
            status_text = f"⚠ ALERT: {critical_count} coach(es) in CRITICAL HOT AXLE condition!"
            status_color = "#FF0000"
        else:
            status_text = f"✓ All {num_coaches} coaches operating normally - No hot axle detected"
            status_color = "#00FF00"
        
        self.status_label.config(text=status_text, fg=status_color)
    
    def monitoring_loop(self):
        """Background monitoring thread"""
        print("\n🔄 Starting temperature monitoring loop...\n")
        cycle = 0
        while self.running:
            if self.mapped:
                cycle += 1
                print(f"--- Cycle {cycle} ---")
                self.update_temperatures()
                self.root.after(0, self.draw_train)
                print()
            time.sleep(1)
    
    def run(self):
        """Main application"""
        print("=" * 60)
        print("🚆 HOT AXLE MONITORING SYSTEM - RASPBERRY PI")
        print("=" * 60)
        print()
        
        if not self.connect():
            print("\n❌ STARTUP FAILED - Cannot connect to gateway")
            return
        
        print("⏳ Waiting for coaches to complete neighbor discovery (5s)...")
        time.sleep(5)
        
        if not self.detect_coaches():
            print("\n❌ STARTUP FAILED - No coaches detected")
            return
        
        if not self.create_dynamic_topology():
            print("\n❌ STARTUP FAILED - Topology creation failed")
            return
        
        print("🖥  Launching GUI...\n")
        self.create_gui()
        
        self.running = True
        monitor_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        monitor_thread.start()
        
        # Wait for canvas to render before first draw
        self.root.after(500, self.draw_train)
        
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("\nShutting down...")
        
        self.running = False
        if self.serial_port:
            self.serial_port.close()
        print("✓ Shutdown complete")

if __name__ == "__main__":
    port = '/dev/ttyUSB0'
    if len(sys.argv) > 1:
        port = sys.argv[1]
    
    monitor = TrainMonitor(port=port, baudrate=9600)
    monitor.run()