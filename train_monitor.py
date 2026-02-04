#!/usr/bin/env python3
"""
Hot Axle Monitoring System - Raspberry Pi Controller (HARDCODED MAP)
Displays train as linked list with real-time temperature monitoring
Hardcoded topology: C0 → C1 → C2
"""

import serial
import time
import tkinter as tk
from tkinter import ttk
import threading
import sys

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
        
        # Train data structures - HARDCODED TOPOLOGY
        self.coaches = {}
        self.head = None
        self.train_order = [0, 1, 2]  # C0 → C1 → C2
        
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
        max_retries = 2  # Reduced retries to avoid hanging
        
        for attempt in range(max_retries):
            try:
                # Check if port is still open
                if not self.serial_port or not self.serial_port.is_open:
                    print(f"  Serial port closed, attempting reconnect...")
                    return None
                
                # Flush buffers
                self.serial_port.reset_input_buffer()
                self.serial_port.reset_output_buffer()
                
                # Send command
                cmd_bytes = f"{command}\n".encode('utf-8')
                self.serial_port.write(cmd_bytes)
                self.serial_port.flush()
                
                # Wait for response with shorter timeout
                time.sleep(0.3)
                
                if self.serial_port.in_waiting:
                    # Read response with error handling
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
                # I/O error - serial connection issue
                print(f"  I/O Error: {e} - Check USB connection")
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
    
    def create_hardcoded_topology(self):
        """Create hardcoded train topology: C0 → C1 → C2"""
        print("=" * 60)
        print("🔍 CREATING HARDCODED TRAIN TOPOLOGY")
        print("=" * 60)
        print()
        print("Hardcoded Configuration: C0 → C1 → C2")
        print()
        
        # Create Coach 0 (Head)
        node0 = CoachNode(coach_id=0, left_id=-1, right_id=1)
        self.coaches[0] = node0
        print(f"  ✓ Coach 0: NULL ← [C0] → C1")
        
        # Create Coach 1 (Middle)
        node1 = CoachNode(coach_id=1, left_id=0, right_id=2)
        self.coaches[1] = node1
        print(f"  ✓ Coach 1: C0 ← [C1] → C2")
        
        # Create Coach 2 (Tail)
        node2 = CoachNode(coach_id=2, left_id=1, right_id=-1)
        self.coaches[2] = node2
        print(f"  ✓ Coach 2: C1 ← [C2] → NULL")
        
        print()
        print("=" * 60)
        print(f"TOPOLOGY COMPLETE: {len(self.coaches)} coaches configured")
        print("=" * 60)
        print()
        
        # Build linked list
        self.build_linked_list()
        self.mapped = True
        
        return True
    
    def build_linked_list(self):
        """Build linked list structure from hardcoded topology"""
        print("🔗 Building linked list structure...")
        
        # Set head
        self.head = self.coaches[0]
        print(f"  ✓ Head coach: C0")
        
        # Link nodes
        self.coaches[0].next = self.coaches[1]
        self.coaches[1].next = self.coaches[2]
        self.coaches[2].next = None
        
        print(f"  ✓ Linked list built: {len(self.coaches)} coaches")
        print(f"  ✓ Train order: C0 → C1 → C2\n")
    
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
                            print(f"⚠ C{coach_id}: Invalid format - {response}")
                    except (ValueError, IndexError) as e:
                        print(f"⚠ C{coach_id}: Parse error - {e}")
                else:
                    print(f"⚠ C{coach_id}: No response")
            except Exception as e:
                print(f"⚠ C{coach_id}: Communication error - {e}")
                # Don't break the loop, try next coach
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
        """Create visualization GUI"""
        self.root = tk.Tk()
        self.root.title("🚆 Hot Axle Monitoring - Linked List View")
        self.root.geometry("900x650")
        self.root.configure(bg='#1a1a1a')
        
        # Title
        title = tk.Label(
            self.root,
            text="🚆 DISTRIBUTED HOT AXLE MONITORING SYSTEM",
            font=("Arial", 18, "bold"),
            bg='#1a1a1a',
            fg='#00FF00'
        )
        title.pack(pady=15)
        
        # Subtitle
        subtitle = tk.Label(
            self.root,
            text="Linked List Based Real-Time Temperature Monitoring",
            font=("Arial", 11),
            bg='#1a1a1a',
            fg='#888888'
        )
        subtitle.pack()
        
        # Status
        self.status_label = tk.Label(
            self.root,
            text="Status: Initializing...",
            font=("Arial", 11, "bold"),
            bg='#1a1a1a',
            fg='#00FF00'
        )
        self.status_label.pack(pady=5)
        
        # Canvas
        self.canvas = tk.Canvas(
            self.root,
            width=880,
            height=450,
            bg='#0d0d0d',
            highlightthickness=2,
            highlightbackground='#333333'
        )
        self.canvas.pack(pady=10)
        
        # Legend
        legend_frame = tk.Frame(self.root, bg='#1a1a1a')
        legend_frame.pack(pady=5)
        
        legends = [
            ("#00FF00", "Normal (<30°C)"),
            ("#FFD700", "Warning (30-40°C)"),
            ("#FF0000", "Critical (>40°C)"),
            ("#555555", "No Data")
        ]
        
        for color, text in legends:
            tk.Label(
                legend_frame,
                text="◼",
                fg=color,
                bg='#1a1a1a',
                font=("Arial", 16)
            ).pack(side=tk.LEFT, padx=3)
            tk.Label(
                legend_frame,
                text=text,
                fg="white",
                bg='#1a1a1a',
                font=("Arial", 10)
            ).pack(side=tk.LEFT, padx=8)
    
    def draw_train(self):
        """Draw train as linked list"""
        if not self.mapped:
            self.canvas.create_text(
                440, 225,
                text="Train not mapped yet...",
                font=("Arial", 14),
                fill='white'
            )
            return
        
        self.canvas.delete("all")
        
        # Debug: Show we're drawing
        print(f"[GUI] Drawing {len(self.train_order)} coaches")
        
        num_coaches = len(self.train_order)
        if num_coaches == 0:
            return
        
        # Calculate layout
        node_width = 140
        node_height = 120
        spacing = 180
        start_x = 100
        y = 220
        
        # Draw each coach
        for i, coach_id in enumerate(self.train_order):
            node = self.coaches[coach_id]
            x = start_x + (i * spacing)
            
            temp = node.temperature
            color = self.get_temp_color(temp)
            status = self.get_temp_status(temp)
            
            print(f"[GUI] C{coach_id}: Temp={temp}, Color={color}")
            
            # Node rectangle
            self.canvas.create_rectangle(
                x, y - node_height//2,
                x + node_width, y + node_height//2,
                fill=color,
                outline='white',
                width=3
            )
            
            # Coach label
            self.canvas.create_text(
                x + node_width//2, y - 40,
                text=f"COACH {coach_id}",
                font=("Arial", 13, "bold"),
                fill='black'
            )
            
            # Temperature
            temp_text = f"{temp:.1f}°C" if temp is not None else "---"
            self.canvas.create_text(
                x + node_width//2, y - 5,
                text=temp_text,
                font=("Arial", 16, "bold"),
                fill='black'
            )
            
            # Status
            self.canvas.create_text(
                x + node_width//2, y + 20,
                text=status,
                font=("Arial", 9, "bold"),
                fill='black'
            )
            
            # Left pointer
            left_text = f"← {node.left_id}" if node.left_id != -1 else "← NULL"
            self.canvas.create_text(
                x + 15, y + 45,
                text=left_text,
                font=("Arial", 9),
                fill='#AAAAAA'
            )
            
            # Right pointer
            right_text = f"{node.right_id} →" if node.right_id != -1 else "NULL →"
            self.canvas.create_text(
                x + node_width - 15, y + 45,
                text=right_text,
                font=("Arial", 9),
                fill='#AAAAAA'
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
                    width=4
                )
                
                self.canvas.create_text(
                    (arrow_start_x + arrow_end_x) // 2, y - 15,
                    text="next",
                    font=("Arial", 8, "italic"),
                    fill='#888888'
                )
        
        # Update status
        critical_count = sum(1 for id in self.train_order 
                           if self.coaches[id].temperature and 
                           self.coaches[id].temperature >= 40)
        
        if critical_count > 0:
            status_text = f"⚠ ALERT: {critical_count} coach(es) in CRITICAL state!"
            status_color = "#FF0000"
        else:
            status_text = f"✓ Monitoring {num_coaches} coaches - All systems normal"
            status_color = "#00FF00"
        
        self.status_label.config(text=status_text, fg=status_color)
        print(f"[GUI] Status: {status_text}\n")
    
    def monitoring_loop(self):
        """Background monitoring thread"""
        print("\n🔄 Starting temperature monitoring loop...\n")
        cycle = 0
        while self.running:
            if self.mapped:
                cycle += 1
                print(f"--- Monitoring Cycle {cycle} ---")
                self.update_temperatures()
                self.root.after(0, self.draw_train)
                print()
            time.sleep(2)
    
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
        
        # Create hardcoded topology (skip real discovery)
        if not self.create_hardcoded_topology():
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