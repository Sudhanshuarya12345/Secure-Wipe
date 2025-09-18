#!/usr/bin/env python3
"""
Secure Wipe GUI - Comprehensive GUI interface for the Secure Wipe secure data wiping tool
Copyright 2025 REDD - MIT License

Features all capabilities from the CLI version in an intuitive graphical interface:
- Drive selection with detailed information
- Free space wiping with multiple patterns and passes
- Full disk formatting with advanced security features
- Real-time progress tracking with time estimates
- Advanced security options (HPA/DCO removal, SMART clearing, etc.)
- Comprehensive logging and status reporting
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import queue
import sys
import os
import time
import platform
import subprocess
from pathlib import Path
import argparse
import errno
import re

# Import the original Secure Wipe functions
sys.path.insert(0, os.path.dirname(__file__))
from securewipe import (
    ensure_venv, get_physical_drives, wipe_free_space, format_disk,
    format_size, SELECTED_DISK_INFO, check_hpa_dco, remove_hpa_dco, 
    clear_smart_data, secure_erase_enhanced, estimate_operation_time,
    format_time_human_readable, find_writable_path_for_volume, 
    get_free_space, is_path_writable, parse_size, 
    clear_drive_cache, handle_remapped_sectors, estimate_write_speed
)

class SecureWipeGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Secure Wipe v1.5 - Secure Data Wiping Tool")
        self.root.geometry("900x750")
        self.root.resizable(False, False)
        
        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Variables
        self.drives = []
        self.selected_drive = None
        self.operation_running = False
        self.operation_thread = None
        self.progress_queue = queue.Queue()
        
        # Settings variables
        self.passes_var = tk.IntVar(value=3)
        self.pattern_var = tk.StringVar(value="all")
        self.block_size_var = tk.StringVar(value="1MB")
        self.verify_var = tk.BooleanVar(value=False)
        self.filesystem_var = tk.StringVar(value="exfat")
        self.label_var = tk.StringVar(value="")
        
        # Advanced security options
        self.remove_hpa_dco_var = tk.BooleanVar(value=True)
        self.clear_smart_var = tk.BooleanVar(value=True)
        self.enhanced_erase_var = tk.BooleanVar(value=True)
        self.clear_cache_var = tk.BooleanVar(value=True)
        self.handle_remapped_var = tk.BooleanVar(value=True)
        
        # Benchmark and estimation options
        self.show_detailed_progress_var = tk.BooleanVar(value=True)
        
        # Operation mode
        self.operation_mode_var = tk.StringVar(value="freespace")
        
        # Current operation details
        self.current_time_estimate = None
        self.operation_start_time = None
        
        # Log settings
        self.autoscroll_enabled = True
        
        self.create_widgets()
        self.refresh_drives()
        self.root.after(100, self.check_progress_queue)
        
        # Set window icon and additional properties
        try:
            self.root.iconname("Secure Wipe")
        except:
            pass
        
    def create_widgets(self):
        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Drive Selection Tab
        self.create_drive_tab()
        
        # Settings Tab
        self.create_settings_tab()
        
        # Advanced Security Tab
        self.create_advanced_tab()
        
        # Log Tab
        self.create_log_tab()
        
        # Status bar at bottom
        self.create_status_bar()
        
    def create_drive_tab(self):
        # Drive Selection Frame
        drive_frame = ttk.Frame(self.notebook)
        self.notebook.add(drive_frame, text="Drive Selection")
        
        # Title
        title_label = ttk.Label(drive_frame, text="Secure Wipe - Secure Data Wiping Tool", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Refresh button
        refresh_frame = ttk.Frame(drive_frame)
        refresh_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(refresh_frame, text="🔄 Refresh Drives", 
                  command=self.refresh_drives).pack(side=tk.LEFT)
        
        # Drive list
        list_frame = ttk.LabelFrame(drive_frame, text="Available Drives")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Treeview for drives with more detailed columns
        columns = ("Device", "Name", "Size", "Free", "Mount", "Type", "Status")
        self.drive_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=10)
        
        # Configure column widths and headings
        column_widths = {"Device": 100, "Name": 150, "Size": 80, "Free": 80, "Mount": 120, "Type": 60, "Status": 80}
        for col in columns:
            self.drive_tree.heading(col, text=col)
            self.drive_tree.column(col, width=column_widths.get(col, 100))
        
        # Scrollbar for treeview
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.drive_tree.yview)
        self.drive_tree.configure(yscrollcommand=scrollbar.set)
        
        self.drive_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.drive_tree.bind('<<TreeviewSelect>>', self.on_drive_select)
        
        # Drive details frame
        details_frame = ttk.LabelFrame(drive_frame, text="Selected Drive Details")
        details_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.drive_details_text = tk.Text(details_frame, height=4, wrap=tk.WORD, state=tk.DISABLED)
        self.drive_details_text.pack(fill=tk.X, padx=5, pady=5)
        
        # Operation buttons
        button_frame = ttk.Frame(drive_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Left side buttons
        left_buttons = ttk.Frame(button_frame)
        left_buttons.pack(side=tk.LEFT)
        
        self.format_btn = ttk.Button(left_buttons, text="Complete secure wipe", 
                                    command=self.format_disk_gui, state=tk.DISABLED)
        self.format_btn.pack(side=tk.LEFT, padx=5)
        
        self.wipe_btn = ttk.Button(left_buttons, text="Free Space Wipe", 
                                  command=self.wipe_free_space_gui, state=tk.DISABLED)
        self.wipe_btn.pack(side=tk.LEFT, padx=5)
        
        
        # Right side buttons
        right_buttons = ttk.Frame(button_frame)
        right_buttons.pack(side=tk.RIGHT)
        
        self.stop_btn = ttk.Button(right_buttons, text=" Stop Operation", 
                                  command=self.stop_operation, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.RIGHT, padx=5)
        
        # Generate Certificate button (enabled only after successful operation)
        self.certificate_btn = ttk.Button(right_buttons, text=" Generate Certificate",
                                         command=self.open_certificate_ui, state=tk.DISABLED)
        self.certificate_btn.pack(side=tk.RIGHT, padx=5)
        
        # Progress frame
        progress_frame = ttk.LabelFrame(drive_frame, text="Operation Progress")
        progress_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Status and progress info
        status_frame = ttk.Frame(progress_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.progress_var = tk.StringVar(value="Ready")
        self.progress_label = ttk.Label(status_frame, textvariable=self.progress_var, font=('Arial', 10, 'bold'))
        self.progress_label.pack(anchor=tk.W)
        
        # Time estimate display
        self.time_estimate_var = tk.StringVar(value="")
        self.time_estimate_label = ttk.Label(status_frame, textvariable=self.time_estimate_var, 
                                           font=('Arial', 9), foreground='blue')
        self.time_estimate_label.pack(anchor=tk.W, pady=(2, 0))
        
        # Speed and data info
        self.speed_info_var = tk.StringVar(value="")
        self.speed_info_label = ttk.Label(status_frame, textvariable=self.speed_info_var, 
                                         font=('Arial', 9), foreground='green')
        self.speed_info_label.pack(anchor=tk.W, pady=(2, 0))
        
        # Progress bars
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, padx=10, pady=5)
        
        # Pass progress (for multi-pass operations)
        pass_frame = ttk.Frame(progress_frame)
        pass_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        self.pass_progress_var = tk.StringVar(value="")
        self.pass_progress_label = ttk.Label(pass_frame, textvariable=self.pass_progress_var, 
                                           font=('Arial', 8))
        self.pass_progress_label.pack(side=tk.LEFT)
        
        self.pass_progress_bar = ttk.Progressbar(pass_frame, mode='determinate', length=200)
        self.pass_progress_bar.pack(side=tk.RIGHT, padx=(10, 0))
        
    def create_settings_tab(self):
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text="Settings")
        
        # Wiping Settings
        wipe_frame = ttk.LabelFrame(settings_frame, text="Wiping Settings")
        wipe_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Passes
        ttk.Label(wipe_frame, text="Number of Passes:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        passes_spin = ttk.Spinbox(wipe_frame, from_=1, to=10, textvariable=self.passes_var, width=10)
        passes_spin.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Pattern
        ttk.Label(wipe_frame, text="Wiping Pattern:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        pattern_combo = ttk.Combobox(wipe_frame, textvariable=self.pattern_var, 
                                   values=["all", "random", "zeroes", "ones", "ticks", "haha"], 
                                   state="readonly", width=15)
        pattern_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Pattern description
        pattern_desc_label = ttk.Label(wipe_frame, text="", font=('Arial', 8), foreground='gray')
        pattern_desc_label.grid(row=1, column=2, sticky=tk.W, padx=10, pady=5)
        
        def update_pattern_description(*args):
            descriptions = {
                "all": "Random + zeroes + ones (recommended)",
                "random": "Random data pattern",
                "zeroes": "All zeros (0x00)",
                "ones": "All ones (0xFF)",
                "ticks": "Custom pattern (3===D)",
                "haha": "Custom pattern (haha-)"
            }
            pattern_desc_label.config(text=descriptions.get(self.pattern_var.get(), ""))
        
        self.pattern_var.trace('w', update_pattern_description)
        update_pattern_description()  # Set initial description
        
        # Block Size
        ttk.Label(wipe_frame, text="Block Size:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        block_combo = ttk.Combobox(wipe_frame, textvariable=self.block_size_var,
                                 values=["512KB", "1MB", "2MB", "4MB", "8MB"], 
                                 state="readonly", width=15)
        block_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Verify
        verify_check = ttk.Checkbutton(wipe_frame, text="Verify after wiping", 
                                     variable=self.verify_var)
        verify_check.grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        
        # Format Settings
        format_frame = ttk.LabelFrame(settings_frame, text="Format Settings")
        format_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Filesystem
        ttk.Label(format_frame, text="Filesystem:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        
        import platform
        fs_options = ["exfat", "fat32", "ntfs"]
        if platform.system() == 'Darwin':
            fs_options.extend(["apfs", "hfs+"])
        elif platform.system() == 'Linux':
            fs_options.extend(["ext4", "ext3", "ext2"])
            
        fs_combo = ttk.Combobox(format_frame, textvariable=self.filesystem_var,
                              values=fs_options, state="readonly", width=15)
        fs_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Label
        ttk.Label(format_frame, text="Volume Label:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        label_entry = ttk.Entry(format_frame, textvariable=self.label_var, width=20)
        label_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
    def create_advanced_tab(self):
        advanced_frame = ttk.Frame(self.notebook)
        self.notebook.add(advanced_frame, text="Advanced Security")
        
        # Security Features
        security_frame = ttk.LabelFrame(advanced_frame, text="Advanced Security Features")
        security_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Checkbutton(security_frame, text="Remove HPA/DCO (Hidden Protected Areas)", 
                       variable=self.remove_hpa_dco_var).pack(anchor=tk.W, padx=5, pady=2)
        
        ttk.Checkbutton(security_frame, text="Clear SMART data and logs", 
                       variable=self.clear_smart_var).pack(anchor=tk.W, padx=5, pady=2)
        
        ttk.Checkbutton(security_frame, text="Enhanced Secure Erase (if supported)", 
                       variable=self.enhanced_erase_var).pack(anchor=tk.W, padx=5, pady=2)
        
        # Information
        info_frame = ttk.LabelFrame(advanced_frame, text="Security Information")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        info_text = """Advanced Security Features:

• HPA/DCO Removal: Removes Hidden Protected Areas and Device Configuration Overlay that may contain hidden data.

• SMART Data Clearing: Clears drive's Self-Monitoring, Analysis and Reporting Technology logs that may contain usage history.

• Enhanced Secure Erase: Uses hardware-level secure erase commands when available for maximum security.

• Multi-pass Wiping: Overwrites data multiple times with different patterns to prevent data recovery.

• DoD Compliance: Follows Department of Defense standards for secure data destruction.

Note: Some features may require administrative privileges and are platform-dependent."""
        
        info_label = ttk.Label(info_frame, text=info_text, justify=tk.LEFT, wraplength=750)
        info_label.pack(padx=10, pady=10)
        
    def create_log_tab(self):
        log_frame = ttk.Frame(self.notebook)
        self.notebook.add(log_frame, text="Log")
        
        # Log display
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=25)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Clear log button
        ttk.Button(log_frame, text="Clear Log", command=self.clear_log).pack(pady=5)
        ttk.Button(log_frame, text="Save Log", command=self.save_log).pack(pady=5)
        
    def strip_ansi_codes(self, text):
        """Remove ANSI color codes from text for GUI display"""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)
    
    def log_message(self, message, level="INFO"):
        """Add message to log with timestamp and level"""
        timestamp = time.strftime("%H:%M:%S")
        # Strip any ANSI codes that might be in the message
        clean_message = self.strip_ansi_codes(str(message))
        
        # Color coding based on level
        level_colors = {
            "INFO": "black",
            "SUCCESS": "green", 
            "WARNING": "orange",
            "ERROR": "red"
        }
        color = level_colors.get(level, "black")
        
        # Insert message with color
        self.log_text.insert(tk.END, f"[{timestamp}] [{level}] {clean_message}\n")
        
        # Apply color to the last line
        line_start = self.log_text.index("end-2c linestart")
        line_end = self.log_text.index("end-2c lineend")
        self.log_text.tag_add(level, line_start, line_end)
        self.log_text.tag_config(level, foreground=color)
        
        if self.autoscroll_enabled:
            self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def clear_log(self):
        """Clear the log display"""
        self.log_text.delete(1.0, tk.END)
        self.log_message("Log cleared", "INFO")
    
    def save_log(self):
        """Save log to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Save Log File"
        )
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(self.log_text.get(1.0, tk.END))
                self.log_message(f"Log saved to {filename}", "SUCCESS")
            except Exception as e:
                self.log_message(f"Error saving log: {e}", "ERROR")
    
    def toggle_autoscroll(self):
        """Toggle auto-scroll for log"""
        self.autoscroll_enabled = not self.autoscroll_enabled
        status = "enabled" if self.autoscroll_enabled else "disabled"
        self.log_message(f"Auto-scroll {status}", "INFO")
    
    def filter_log(self, event=None):
        """Filter log messages by level"""
        # This is a placeholder - full implementation would filter existing messages
        filter_level = self.log_filter_var.get()
        self.log_message(f"Log filter set to: {filter_level}", "INFO")
    
    def refresh_drives(self):
        """Refresh the list of available drives"""
        try:
            self.log_message("Refreshing drive list...")
            self.drives = get_physical_drives()
            
            # Clear existing items
            for item in self.drive_tree.get_children():
                self.drive_tree.delete(item)
                
            # Add drives to tree
            for drive in self.drives:
                self.drive_tree.insert("", tk.END, values=(
                    drive['device'],
                    drive['name'],
                    drive['size_human'],
                    format_size(drive['free']),
                    drive['mountpoint'],
                    drive['fstype']
                ))
                
            self.log_message(f"Found {len(self.drives)} drives", "SUCCESS")
            
            # Update status bar
            self.status_var.set(f"Found {len(self.drives)} drives")
            
        except Exception as e:
            self.log_message(f"Error refreshing drives: {e}")
            messagebox.showerror("Error", f"Failed to refresh drives: {e}")
            
    def on_drive_select(self, event):
        """Handle drive selection"""
        selection = self.drive_tree.selection()
        if selection:
            item = self.drive_tree.item(selection[0])
            device = item['values'][0]
            
            # Find the selected drive
            for drive in self.drives:
                if drive['device'] == device:
                    self.selected_drive = drive
                    break
                    
            # Enable buttons
            self.wipe_btn.config(state=tk.NORMAL)
            self.format_btn.config(state=tk.NORMAL)
            
            # Update drive details
            self.update_drive_details()
            
            self.log_message(f"Selected drive: {device}", "INFO")
    
    def update_drive_details(self):
        """Update the drive details display"""
        if not self.selected_drive:
            return
            
        details = f"""Device: {self.selected_drive['device']}
Name: {self.selected_drive['name']}
Size: {self.selected_drive['size_human']}
Free Space: {format_size(self.selected_drive['free'])}
Mount Point: {self.selected_drive['mountpoint']}
Filesystem: {self.selected_drive['fstype']}"""
        
        self.drive_details_text.config(state=tk.NORMAL)
        self.drive_details_text.delete(1.0, tk.END)
        self.drive_details_text.insert(1.0, details)
        self.drive_details_text.config(state=tk.DISABLED)
            
    def get_block_size_bytes(self):
        """Convert block size string to bytes using Secure wipe's parse_size function"""
        size_str = self.block_size_var.get()
        return parse_size(size_str) or 1048576  # Default to 1MB if parsing fails
        
    def wipe_free_space_gui(self):
        """Start free space wiping operation"""
        if not self.selected_drive:
            messagebox.showwarning("Warning", "Please select a drive first")
            return
            
        if self.operation_running:
            messagebox.showwarning("Warning", "An operation is already running")
            return
        
        # Get time estimate
        try:
            free_space = self.selected_drive['free']
            passes = self.passes_var.get()
            time_estimate = estimate_operation_time(free_space, passes, include_benchmark=False, path=None)
            
            # Confirmation dialog with time estimate
            drive_info = f"Drive: {self.selected_drive['device']}\n"
            drive_info += f"Name: {self.selected_drive['name']}\n"
            drive_info += f"Free Space: {format_size(self.selected_drive['free'])}\n"
            drive_info += f"Passes: {self.passes_var.get()}\n"
            drive_info += f"Pattern: {self.pattern_var.get()}\n\n"
            drive_info += f"Estimated Time: {time_estimate['estimated_human']}\n"
            drive_info += f"Expected Completion: {time_estimate['completion_time']}"
            
            if not messagebox.askyesno("Confirm Free Space Wipe", 
                                      f"Wipe free space on the following drive?\n\n{drive_info}"):
                return
                
            # Store time estimate for progress display
            self.current_time_estimate = time_estimate
            
        except Exception as e:
            self.log_message(f"Warning: Could not calculate time estimate: {e}")
            # Fallback to original confirmation without time estimate
            drive_info = f"Drive: {self.selected_drive['device']}\n"
            drive_info += f"Name: {self.selected_drive['name']}\n"
            drive_info += f"Free Space: {format_size(self.selected_drive['free'])}\n"
            drive_info += f"Passes: {self.passes_var.get()}\n"
            drive_info += f"Pattern: {self.pattern_var.get()}"
            
            if not messagebox.askyesno("Confirm Free Space Wipe", 
                                      f"Wipe free space on the following drive?\n\n{drive_info}"):
                return
                
            self.current_time_estimate = None
            
        self.start_operation("wipe")
        
    def format_disk_gui(self):
        """Start disk formatting operation"""
        if not self.selected_drive:
            messagebox.showwarning("Warning", "Please select a drive first")
            return
            
        if self.operation_running:
            messagebox.showwarning("Warning", "An operation is already running")
            return
        
        # Get time estimate for full disk operation
        try:
            disk_size = self.selected_drive.get('size', 500 * 1024 * 1024 * 1024)  # Fallback to 500GB
            passes = self.passes_var.get()
            time_estimate = estimate_operation_time(disk_size, passes, include_benchmark=False, path=None)
            
            # Strong warning for format operation with time estimate
            drive_info = f"Drive: {self.selected_drive['device']}\n"
            drive_info += f"Name: {self.selected_drive['name']}\n"
            drive_info += f"Size: {self.selected_drive['size_human']}\n"
            drive_info += f"Filesystem: {self.filesystem_var.get().upper()}\n"
            if self.label_var.get():
                drive_info += f"Label: {self.label_var.get()}\n"
            drive_info += f"\nEstimated Time: {time_estimate['estimated_human']}\n"
            drive_info += f"Expected Completion: {time_estimate['completion_time']}"
            
            # Store time estimate for progress display
            self.current_time_estimate = time_estimate
            
        except Exception as e:
            self.log_message(f"Warning: Could not calculate time estimate: {e}")
            # Fallback without time estimate
            drive_info = f"Drive: {self.selected_drive['device']}\n"
            drive_info += f"Name: {self.selected_drive['name']}\n"
            drive_info += f"Size: {self.selected_drive['size_human']}\n"
            drive_info += f"Filesystem: {self.filesystem_var.get().upper()}\n"
            if self.label_var.get():
                drive_info += f"Label: {self.label_var.get()}\n"
            
            self.current_time_estimate = None
            
        warning = "⚠️ WARNING: COMPLETE DISK FORMAT ⚠️\n\n"
        warning += "This operation will PERMANENTLY ERASE ALL DATA on the selected disk!\n\n"
        warning += drive_info + "\n"
        warning += "This action CANNOT be undone!\n\n"
        warning += "Are you absolutely sure you want to continue?"
        
        if not messagebox.askyesno("⚠️ DESTRUCTIVE OPERATION WARNING", warning):
            return
            
        # Second confirmation
        if not messagebox.askyesno("Final Confirmation", 
                                  "Last chance! This will destroy all data on the disk.\n\nProceed with format?"):
            return
            
        self.start_operation("format")
        
    def start_operation(self, operation_type):
        """Start the selected operation in a separate thread"""
        self.operation_running = True
        self.operation_type = operation_type
        self.operation_start_time = time.time()
        
        # Update UI
        self.wipe_btn.config(state=tk.DISABLED)
        self.format_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.certificate_btn.config(state=tk.DISABLED)
        
        self.progress_var.set(f"Starting {operation_type} operation...")
        
        # Display time estimate if available
        if hasattr(self, 'current_time_estimate') and self.current_time_estimate:
            self.time_estimate_var.set(f"Estimated time: {self.current_time_estimate['estimated_human']} | "
                                     f"Expected completion: {self.current_time_estimate['completion_time']}")
        else:
            self.time_estimate_var.set("Calculating time estimate...")
        
        self.progress_bar.config(mode='indeterminate')
        self.progress_bar.start()
        
        # Start operation thread
        if operation_type == "wipe":
            self.operation_thread = threading.Thread(target=self.wipe_thread)
        else:  # format
            self.operation_thread = threading.Thread(target=self.format_thread)
            
        self.operation_thread.daemon = True
        self.operation_thread.start()
        
    def wipe_thread(self):
        """Thread function for wiping free space"""
        try:
            # Get parameters
            passes = self.passes_var.get()
            pattern = self.pattern_var.get()
            block_size = self.get_block_size_bytes()
            verify = self.verify_var.get()
            mount_point = self.selected_drive['mountpoint']
            
            self.progress_queue.put(("log", f"Starting free space wipe on {mount_point}"))
            self.progress_queue.put(("log", f"Passes: {passes}, Pattern: {pattern}, Block size: {format_size(block_size)}"))
            
            # Get free space and time estimate
            try:
                free_space = get_free_space(mount_point)
                time_estimate = estimate_operation_time(free_space, passes, include_benchmark=False, path=mount_point)
                self.progress_queue.put(("log", f"Free space: {format_size(free_space)}"))
                self.progress_queue.put(("log", f"Estimated time: {time_estimate['estimated_human']}"))
            except Exception as e:
                self.progress_queue.put(("log", f"Warning: Could not estimate time: {e}"))
            
            # Call the core wiping logic directly without confirmations
            self.perform_free_space_wipe(mount_point, passes, pattern, block_size, verify)
            
            self.progress_queue.put(("complete", "Free space wiping completed successfully!"))
            
        except Exception as e:
            self.progress_queue.put(("error", f"Error during wiping: {e}"))
            
    # def format_thread(self):
    #     """Thread function for formatting disk"""
    #     try:
    #         # Get parameters
    #         disk_path = self.selected_drive['device']
    #         filesystem = self.filesystem_var.get()
    #         label = self.label_var.get() if self.label_var.get() else None
    #         passes = self.passes_var.get()
    #         pattern = self.pattern_var.get()
    #         verify = self.verify_var.get()
            
    #         self.progress_queue.put(("log", f"Starting disk format: {disk_path}"))
    #         self.progress_queue.put(("log", f"Filesystem: {filesystem}, Label: {label or 'None'}"))
    #         self.progress_queue.put(("log", f"Passes: {passes}, Pattern: {pattern}"))
            
    #         # Call the core formatting logic directly without confirmations
    #         self.perform_disk_format(disk_path, filesystem, label, passes, pattern, verify)
            
    #         self.progress_queue.put(("complete", "Disk formatting completed successfully!"))
            
    #     except Exception as e:
    #         self.progress_queue.put(("error", f"Error during formatting: {e}"))
    def format_thread(self):
        try:
            # Gather parameters
            disk_path = self.selected_drive['device']
            filesystem = self.filesystem_var.get()
            label = self.label_var.get() or None
            passes = self.passes_var.get()
            pattern = self.pattern_var.get()
            verify = self.verify_var.get()

            # Use the wrapper that resolves platform-specific targets and calls core formatter
            self.perform_disk_format(
                disk_path,
                filesystem,
                label,
                passes,
                pattern,
                verify
            )

            self.progress_queue.put(("complete", "Disk formatting completed successfully!"))
        except Exception as e:
            self.progress_queue.put(("error", f"Error during formatting: {e}"))

    def stop_operation(self):
        """Stop the current operation"""
        if self.operation_running and self.operation_thread:
            # Send interrupt signal to the thread (this is a simplified approach)
            self.progress_queue.put(("status", "Stopping operation..."))
            self.log_message("Stop requested - operation may take a moment to terminate safely")
            
            # In a real implementation, you'd need to implement proper thread cancellation
            # For now, we'll just mark it as stopped
            self.operation_running = False
            self.finish_operation()
            
    def finish_operation(self):
        """Clean up after operation completion"""
        self.operation_running = False
        
        # Update UI
        self.wipe_btn.config(state=tk.NORMAL if self.selected_drive else tk.DISABLED)
        self.format_btn.config(state=tk.NORMAL if self.selected_drive else tk.DISABLED)
        # Some builds may not define benchmark button; guard access
        if hasattr(self, 'benchmark_btn'):
            self.benchmark_btn.config(state=tk.NORMAL if self.selected_drive else tk.DISABLED)
        self.stop_btn.config(state=tk.DISABLED)
# ---------------------------------------------------------------------------------
        # self.certificate_btn.config(state=tk.NORMAL)
        
        self.progress_bar.stop()
        self.progress_bar.config(mode='determinate')
        self.progress_bar['value'] = 0
        self.progress_var.set("Ready")
        try:
            self.status_var.set("Ready")
        except Exception:
            pass
        
        # Clear time estimate display
        self.time_estimate_var.set("")
        self.speed_info_var.set("")
        self.pass_progress_var.set("")
        self.pass_progress_bar['value'] = 0
        
        # Refresh drives to update free space
        self.refresh_drives()
        
    def update_progress_with_time(self, elapsed_time):
        """Update progress display with elapsed time information"""
        if hasattr(self, 'current_time_estimate') and self.current_time_estimate:
            elapsed_str = format_time_human_readable(elapsed_time, abbreviated=True)
            remaining_estimate = max(0, self.current_time_estimate['estimated_seconds'] - elapsed_time)
            remaining_str = format_time_human_readable(remaining_estimate, abbreviated=True)
            
            self.time_estimate_var.set(f"Elapsed: {elapsed_str} | Remaining: ~{remaining_str}")
    
    def check_progress_queue(self):
        """Check for progress updates from worker threads"""
        try:
            while True:
                msg_type, message = self.progress_queue.get_nowait()
                
                if msg_type == "status":
                    self.progress_var.set(message)
                elif msg_type == "log":
                    self.log_message(message)
                elif msg_type == "progress":
                    # # message should be a percentage (0-100)
                    # self.progress_bar.config(mode='determinate')
                    # self.progress_bar['value'] = message
                    self.progress_bar.config(mode='determinate')
                    # Convert string like "45% - Formatting simulation" to numeric 45
                    if isinstance(message, str):
                        if "%" in message:
                            try:
                                percent = float(message.split("%")[0])
                            except ValueError:
                                percent = 0
                        else:
                            try:
                                percent = float(message)
                            except ValueError:
                                percent = 0
                        self.progress_bar['value'] = percent
                        self.progress_var.set(message)   # show text in label
                    else:
                        self.progress_bar['value'] = float(message)
                elif msg_type == "pass_start":
                    # message: (current_pass, total_passes)
                    try:
                        current_pass, total_passes = message
                        self.pass_progress_var.set(f"Pass {current_pass}/{total_passes}")
                        self.pass_progress_bar['value'] = 0
                    except Exception:
                        pass
                elif msg_type == "pass_progress":
                    try:
                        self.pass_progress_bar['value'] = float(message)
                    except Exception:
                        pass
                elif msg_type == "speed":
                    # message: formatted speed/time string
                    self.speed_info_var.set(message)
                elif msg_type == "time_update":
                    # message should be elapsed time in seconds
                    self.update_progress_with_time(message)
                elif msg_type == "complete":
                    self.log_message(message)
                    self.progress_var.set(message)
                    # Ensure status/progress are reset before popup
                    self.finish_operation()
                    messagebox.showinfo("Success", message)
                    # Enable certificate button on success
                    print("Operation complete, trying to enabling certificate button")
                    try:
                        time.sleep(1)
                        self.certificate_btn.config(state=tk.NORMAL)
# ---------------------------------------------------------------------------------------------
                    except Exception:
                        print("Failed to enable certificate button")
                        pass
                elif msg_type == "error":
                    self.log_message(f"ERROR: {message}")
                    self.progress_var.set("Error occurred")
                    # Ensure status/progress are reset before popup
                    self.finish_operation()
                    messagebox.showerror("Error", message)
                    # Keep certificate disabled on error
                    try:
                        self.certificate_btn.config(state=tk.DISABLED)
                    except Exception:
                        pass
                    self.finish_operation()
                    
        except queue.Empty:
            pass
            
        # Schedule next check
        self.root.after(100, self.check_progress_queue)

    def benchmark_drive_speed(self):
        """Run drive speed benchmark"""
        if not self.selected_drive:
            messagebox.showwarning("Warning", "Please select a drive first")
            return
            
        if self.operation_running:
            messagebox.showwarning("Warning", "An operation is already running")
            return
        
        # Run benchmark in thread
        def benchmark_thread():
            try:
                mount_point = self.selected_drive['mountpoint']
                
                self.log_message(f"Starting speed benchmark on {mount_point}", "INFO")
                
                speed = benchmark_write_speed(mount_point, test_size=50*1024*1024)  # 50MB test
                
                if speed:
                    speed_mb = speed / (1024 * 1024)
                    self.log_message(f"Benchmark complete: {speed_mb:.2f} MB/s", "SUCCESS")
                    messagebox.showinfo("Benchmark Complete", f"Write Speed: {speed_mb:.2f} MB/s")
                else:
                    self.log_message("Benchmark failed", "ERROR")
                    
            except Exception as e:
                self.log_message(f"Benchmark error: {e}", "ERROR")
        
        thread = threading.Thread(target=benchmark_thread)
        thread.daemon = True
        thread.start()


    def create_performance_tab(self):
        """Create benchmark and performance tab"""
        perf_frame = ttk.Frame(self.notebook)
        self.notebook.add(perf_frame, text="Performance")
        
        # Benchmark settings
        benchmark_frame = ttk.LabelFrame(perf_frame, text="Benchmark Settings")
        benchmark_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Checkbutton(benchmark_frame, text="Enable automatic speed benchmarking", 
                       variable=self.enable_benchmark_var).pack(anchor=tk.W, padx=5, pady=2)
        
        ttk.Label(benchmark_frame, text="Runs a quick write speed test before operations for better time estimates", 
                 font=('Arial', 8), foreground='gray').pack(anchor=tk.W, padx=20, pady=(0, 5))

    def create_status_bar(self):
        """Create status bar at bottom of window"""
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=2)
        
        # Status label
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(self.status_bar, textvariable=self.status_var)
        self.status_label.pack(side=tk.LEFT)
        
        # System info
        system_info = f"Platform: {platform.system()} | Python: {platform.python_version()}"
        ttk.Label(self.status_bar, text=system_info, font=('Arial', 8)).pack(side=tk.RIGHT)

    def apply_preset(self, preset_type):
        """Apply preset configuration"""
        presets = {
            "quick": {"passes": 1, "pattern": "random", "verify": False},
            "standard": {"passes": 3, "pattern": "all", "verify": False},
            "secure": {"passes": 7, "pattern": "all", "verify": True},
            "dod": {"passes": 3, "pattern": "all", "verify": True}  # DoD 5220.22-M
        }
        
        if preset_type in presets:
            preset = presets[preset_type]
            self.passes_var.set(preset["passes"])
            self.pattern_var.set(preset["pattern"])
            self.verify_var.set(preset["verify"])
            
            self.log_message(f"Applied {preset_type.title()} preset", "INFO")
            
            # Show confirmation
            messagebox.showinfo("Preset Applied", 
                              f"Applied {preset_type.title()} preset:\n"
                              f"Passes: {preset['passes']}\n"
                              f"Pattern: {preset['pattern']}\n"
                              f"Verify: {preset['verify']}")

    def perform_free_space_wipe(self, root_path, passes, pattern, block_size, verify):
        """Perform free space wiping without confirmations"""
        import tempfile
        import os
        
        fname = os.path.join(root_path, '.securewipe_free_space.tmp')
        
        try:
            for p in range(passes):
                if pattern == 'zeroes':
                    mode = 'zeroes'
                elif pattern == 'ones':
                    mode = 'ones'
                elif pattern == 'random':
                    mode = 'random'
                elif pattern == 'ticks':
                    mode = 'ticks'
                elif pattern == 'haha':
                    mode = 'haha'
                else:  # 'all' - default with first pass being random
                    if p == 0:
                        mode = 'random'
                    else:
                        mode = {1: 'zeroes', 2: 'ones'}.get(p % 3, 'random')
                
                self.progress_queue.put(("log", f"Pass {p+1}/{passes}: filling free space with {mode}"))
                self.progress_queue.put(("pass_start", (p+1, passes)))
                
                # Get free space for this pass
                free_space = get_free_space(root_path)
                if free_space <= 0:
                    self.progress_queue.put(("log", "No free space available to wipe"))
                    break
                
                # Generate pattern data
                if mode == 'zeroes':
                    data = b'\x00' * block_size
                elif mode == 'ones':
                    data = b'\xFF' * block_size
                elif mode == 'ticks':
                    pattern_bytes = b'3===D'
                    data = (pattern_bytes * (block_size // len(pattern_bytes) + 1))[:block_size]
                elif mode == 'haha':
                    pattern_bytes = b'haha-'
                    data = (pattern_bytes * (block_size // len(pattern_bytes) + 1))[:block_size]
                else:  # random
                    data = os.urandom(block_size)
                
                # Write data to fill free space
                written = 0
                with open(fname, 'wb') as f:
                    while True:
                        try:
                            # Write a chunk
                            if mode == 'random':
                                chunk = os.urandom(block_size)
                                f.write(chunk)
                            else:
                                f.write(data)
                            written += block_size
                        except OSError as e:
                            # Stop on no space left on device
                            if hasattr(e, 'errno') and e.errno in (errno.ENOSPC, errno.EFBIG):
                                break
                            else:
                                raise
                        
                        # Calculate progress against initial free space
                        progress = min(100.0, (written / free_space) * 100.0) if free_space > 0 else 0.0
                        self.progress_queue.put(("progress", f"{progress:.1f}% - {format_size(min(written, free_space))}/{format_size(free_space)}"))
                        self.progress_queue.put(("pass_progress", progress))
                        
                        # Update speed/time approximately twice per second
                        elapsed = max(1e-6, time.time() - self.operation_start_time)
                        speed_bps = written / elapsed
                        speed_str = f"Speed: {format_size(int(speed_bps))}/s"
                        self.progress_queue.put(("speed", speed_str))
                        self.progress_queue.put(("time_update", elapsed))
                
                # Verify if requested
                if verify:
                    self.progress_queue.put(("log", f"Verifying pass {p+1}"))
                    # Simple verification - check file size
                    if os.path.getsize(fname) != written:
                        raise Exception(f"Verification failed for pass {p+1}")
                
                # Clean up temp file
                try:
                    os.remove(fname)
                except:
                    pass
                    
        except Exception as e:
            # Clean up on error
            try:
                os.remove(fname)
            except:
                pass
            raise e
    
    def perform_disk_format(self, disk_path, filesystem, label, passes, pattern, verify):
        """Perform real disk formatting using core format_disk without CLI confirmations"""
        try:
            system = platform.system()
            target = disk_path
            # On Windows, map selected drive letter to physical disk number expected by core format_disk
            if system == 'Windows':
                try:
                    # If disk_path looks like a drive letter, resolve to disk number
                    drive_letter = None
                    if len(disk_path) >= 2 and disk_path[1] == ':':
                        drive_letter = disk_path[0]
                    elif self.selected_drive and self.selected_drive.get('mountpoint'):
                        mp = self.selected_drive['mountpoint']
                        if len(mp) >= 2 and mp[1] == ':':
                            drive_letter = mp[0]
                    if drive_letter:
                        ps_cmd = f"(Get-Partition -DriveLetter {drive_letter} | Get-Disk).Number"
                        result = subprocess.check_output(['powershell', '-Command', ps_cmd], stderr=subprocess.STDOUT).decode('utf-8').strip()
                        # Disk number should be an integer on its own line
                        num_match = re.search(r"(\d+)", result)
                        if num_match:
                            # Pass numeric disk id; core will handle mountpoint resolution
                            target = num_match.group(1)
                except Exception as e:
                    self.progress_queue.put(("log", f"Warning: Could not resolve disk number automatically: {e}"))
            
            # Progress start
            self.progress_queue.put(("status", f"Formatting started: {target} ({filesystem.upper()})"))
            self.progress_bar = self.progress_bar  # keep reference
            # Call core formatting (no_confirm=True to suppress CLI dialogs)
            format_disk(target, filesystem=filesystem, label=label, no_confirm=True, passes=passes, pattern=pattern, verify=verify)
            
        except Exception as e:
            raise e

    def open_certificate_ui(self):
        """Launch the certificate generator UI in a separate process."""
        try:
            # Print/log product key if available
            try:
                if hasattr(self, 'product_key') and self.product_key:
                    print(f"Product Key: {self.product_key}")
                    
                    
                    
                    
                    
                    
                    
                    self.log_message(f"Product Key: {self.product_key}")
            except Exception:
                pass
            script_path = os.path.join(os.path.dirname(__file__), 'generateCert.py')
            subprocess.Popen([sys.executable, script_path])
            self.log_message("Opened certificate generator", "SUCCESS")
        except Exception as e:
            self.log_message(f"Failed to open certificate UI: {e}", "ERROR")

def main():
    # Ensure virtual environment is set up
    try:
        ensure_venv()
    except Exception as e:
        print(f"Error setting up virtual environment: {e}")
        return
        
    # Create and run GUI
    root = tk.Tk()
    app = SecureWipeGUI(root)
    # Attach product key if provided via environment
    try:
        pk = os.environ.get('SECUREWIPE_PRODUCT_KEY')
        if pk:
            setattr(app, 'product_key', pk)
    except Exception:
        pass
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", type=str, help="User details")
    parser.add_argument("--product_key", type=str, help="Product key passed from login")
    parser.add_argument("--elevated", action="store_true", help="Internal flag to indicate elevated relaunch")
    args = parser.parse_args()
    if args.user:
        print(args.user)

    # On Windows, auto-relaunch with elevation if not already elevated
    try:
        if platform.system() == 'Windows':
            import ctypes
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
            if not is_admin and not args.elevated:
                # Relaunch with UAC elevation
                params_list = []
                if args.user:
                    params_list.append(f'--user "{args.user}"')
                if args.product_key:
                    params_list.append(f'--product_key "{args.product_key}"')
                params_list.append('--elevated')
                params = ' '.join(params_list).strip()
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{__file__}" {params}', None, 1)
                sys.exit(0)
    except Exception:
        # If elevation check fails, continue; core will still guard and show error
        pass
    
    # Optionally make product_key available to GUI if needed later
    if args.product_key:
        os.environ['SECUREWIPE_PRODUCT_KEY'] = args.product_key
    
    main()
    
    