#!/usr/bin/env python3
"""
Hot Axle Monitoring System - Raspberry Pi Controller
Displays train as linked list with real-time temperature monitoring
"""

import serial
import time
import tkinter as tk
from tkinter import ttk
import threading

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
        
        # Train data structures
        self.coaches = {}  # Dictionary to store all coach nodes
        self.head = None   # Head of linked list (first coach)
        self.train_order = []  # Ordered list of coach IDs
        
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
            self.serial_port = serial.Serial(self.port, self.baudrate, timeout=2)
            time.sleep(2)  # Wait for Arduino to reset
            
            # Wait for READY signal
            start_time = time.time()
            while time.time() - start_time < 10:
                if self.serial_port.in_waiting:
                    line = self.serial_port.readline().decode().strip()
                    if line == "READY":
                        print("✓ Gateway connected and ready")
                        return True
            
            print("✗ Gateway did not send READY signal")
            return False
            
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
    
    def send_command(self, command):
        """Send command to Arduino and get response"""
        try:
            self.serial_port.write(f"{command}\n".encode())
            time.sleep(0.3)  # Wait for processing
            
            if self.serial_port.in_waiting:
                response = self.serial_port.readline().decode().strip()
                return response
            return None
            
        except Exception as e:
            print(f"Error sending command: {e}")
            return None
    
    def discover_train(self):
        """Phase 1: Discover all coaches and build map"""
        print("\n🔍 Discovering train topology...")
        
        # Request map bundles from coaches 0-3
        for coach_id in range(4):
            response = self.send_command(f"MAP,{coach_id}")
            
            if response and response != "ERROR":
                parts = response.split(',')
                if len(parts) == 3:
                    left_id = int(parts[0])
                    current_id = int(parts[1])
                    right_id = int(parts[2])
                    
                    # Create coach node
                    node = CoachNode(current_id, left_id, right_id)
                    self.coaches[current_id] = node
                    
                    print(f"  Coach {current_id}: Left={left_id}, Right={right_id}")
        
        # Build linked list
        self.build_linked_list()
        self.mapped = True
        print(f"✓ Train mapped: {len(self.coaches)} coaches detected")
        print(f"  Train order: {' → '.join(map(str, self.train_order))}")
    
    def build_linked_list(self):
        """Reconstruct linked list from discovered coaches"""
        # Find head (coach with left = -1)
        for coach_id, node in self.coaches.items():
            if node.left_id == -1:
                self.head = node
                break
        
        if not self.head:
            print("✗ No head coach found!")
            return
        
        # Traverse and link nodes
        current = self.head
        self.train_order = []
        
        while current:
            self.train_order.append(current.coach_id)
            
            # Link to next coach
            if current.right_id != -1 and current.right_id in self.coaches:
                current.next = self.coaches[current.right_id]
                current = current.next
            else:
                break
    
    def update_temperatures(self):
        """Phase 2: Continuously update temperatures"""
        for coach_id in self.train_order:
            response = self.send_command(f"TEMP,{coach_id}")
            
            if response and response != "ERROR":
                parts = response.split(',')
                if len(parts) >= 4:
                    try:
                        temp = float(parts[3])
                        self.coaches[coach_id].temperature = temp
                    except ValueError:
                        pass
    
    def get_temp_color(self, temp):
        """Determine color based on temperature thresholds"""
        if temp is None:
            return "gray"
        elif temp < 30:
            return "#00FF00"  # Green - Normal
        elif temp < 40:
            return "#FFD700"  # Yellow - Warning
        else:
            return "#FF0000"  # Red - Critical (Hot Axle)
    
    def create_gui(self):
        """Create visualization GUI"""
        self.root = tk.Tk()
        self.root.title("🚆 Hot Axle Monitoring - Linked List View")
        self.root.geometry("800x600")
        self.root.configure(bg='#1a1a1a')
        
        # Title
        title = tk.Label(
            self.root,
            text="🚆 DISTRIBUTED HOT AXLE MONITORING SYSTEM",
            font=("Arial", 16, "bold"),
            bg='#1a1a1a',
            fg='white'
        )
        title.pack(pady=10)
        
        # Status
        self.status_label = tk.Label(
            self.root,
            text="Status: Initializing...",
            font=("Arial", 10),
            bg='#1a1a1a',
            fg='#00FF00'
        )
        self.status_label.pack()
        
        # Canvas for train visualization
        self.canvas = tk.Canvas(
            self.root,
            width=780,
            height=500,
            bg='#0d0d0d',
            highlightthickness=0
        )
        self.canvas.pack(pady=10)
        
        # Legend
        legend_frame = tk.Frame(self.root, bg='#1a1a1a')
        legend_frame.pack()
        
        tk.Label(legend_frame, text="◼", fg="#00FF00", bg='#1a1a1a', font=("Arial", 14)).pack(side=tk.LEFT, padx=5)
        tk.Label(legend_frame, text="Normal (<30°C)", fg="white", bg='#1a1a1a').pack(side=tk.LEFT, padx=5)
        
        tk.Label(legend_frame, text="◼", fg="#FFD700", bg='#1a1a1a', font=("Arial", 14)).pack(side=tk.LEFT, padx=5)
        tk.Label(legend_frame, text="Warning (30-40°C)", fg="white", bg='#1a1a1a').pack(side=tk.LEFT, padx=5)
        
        tk.Label(legend_frame, text="◼", fg="#FF0000", bg='#1a1a1a', font=("Arial", 14)).pack(side=tk.LEFT, padx=5)
        tk.Label(legend_frame, text="Critical (>40°C)", fg="white", bg='#1a1a1a').pack(side=tk.LEFT, padx=5)
    
    def draw_train(self):
        """Draw train as linked list on canvas"""
        if not self.mapped:
            return
        
        self.canvas.delete("all")
        
        # Calculate positions
        num_coaches = len(self.train_order)
        spacing = 150
        start_x = 50
        y = 250
        
        # Draw each coach node
        for i, coach_id in enumerate(self.train_order):
            node = self.coaches[coach_id]
            x = start_x + (i * spacing)
            
            # Coach box
            temp = node.temperature
            color = self.get_temp_color(temp)
            
            # Draw node box
            self.canvas.create_rectangle(
                x, y - 50, x + 100, y + 50,
                fill=color,
                outline='white',
                width=2
            )
            
            # Coach ID
            self.canvas.create_text(
                x + 50, y - 30,
                text=f"Coach {coach_id}",
                font=("Arial", 12, "bold"),
                fill='black'
            )
            
            # Temperature
            temp_text = f"{temp:.1f}°C" if temp is not None else "---"
            self.canvas.create_text(
                x + 50, y,
                text=temp_text,
                font=("Arial", 14, "bold"),
                fill='black'
            )
            
            # Left pointer (if not head)
            if node.left_id != -1:
                self.canvas.create_text(
                    x + 10, y + 30,
                    text=f"← {node.left_id}",
                    font=("Arial", 9),
                    fill='white'
                )
            else:
                self.canvas.create_text(
                    x + 10, y + 30,
                    text="← NULL",
                    font=("Arial", 9),
                    fill='#888888'
                )
            
            # Right pointer (if not tail)
            if node.right_id != -1:
                self.canvas.create_text(
                    x + 90, y + 30,
                    text=f"{node.right_id} →",
                    font=("Arial", 9),
                    fill='white'
                )
            else:
                self.canvas.create_text(
                    x + 90, y + 30,
                    text="NULL →",
                    font=("Arial", 9),
                    fill='#888888'
                )
            
            # Draw arrow to next node
            if i < num_coaches - 1:
                self.canvas.create_line(
                    x + 100, y,
                    x + 150, y,
                    arrow=tk.LAST,
                    fill='white',
                    width=3
                )
        
        # Update status
        self.status_label.config(text=f"Status: Monitoring {num_coaches} coaches")
    
    def monitoring_loop(self):
        """Background thread for continuous monitoring"""
        while self.running:
            if self.mapped:
                self.update_temperatures()
                self.root.after(0, self.draw_train)
            time.sleep(2)  # Update every 2 seconds
    
    def run(self):
        """Main application loop"""
        # Connect to gateway
        if not self.connect():
            print("Failed to connect to gateway")
            return
        
        # Wait for coaches to complete neighbor discovery
        print("Waiting for coaches to complete setup (5 seconds)...")
        time.sleep(5)
        
        # Discover train topology
        self.discover_train()
        
        # Create GUI
        self.create_gui()
        
        # Start monitoring thread
        self.running = True
        monitor_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        monitor_thread.start()
        
        # Initial draw
        self.draw_train()
        
        # Start GUI
        self.root.mainloop()
        
        # Cleanup
        self.running = False
        if self.serial_port:
            self.serial_port.close()

if __name__ == "__main__":
    print("=" * 60)
    print("🚆 HOT AXLE MONITORING SYSTEM - RASPBERRY PI")
    print("=" * 60)
    
    # Configure serial port (change if needed)
    monitor = TrainMonitor(port='/dev/ttyUSB0', baudrate=9600)
    monitor.run()