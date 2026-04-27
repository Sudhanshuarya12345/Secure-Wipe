import tkinter as tk
from tkinter import ttk

from core.drive_manager import get_physical_drives, get_disk_identity
from core.wipe_engine import WipeProgress
import logging

logger = logging.getLogger(__name__)

class DriveSelectionTab(ttk.Frame):
    """Drive selection UI perfectly matching the legacy screenshot."""
    def __init__(self, parent, callbacks):
        """
        callbacks dict expects:
        - on_drive_select: func(disk_path, identity)
        - on_complete_wipe: func()
        - on_free_space_wipe: func()
        - on_stop_operation: func()
        - on_generate_cert: func()
        """
        super().__init__(parent)
        self.callbacks = callbacks
        self._setup_ui()
        self.refresh_drives()

    def _setup_ui(self):
        # Title
        title_label = ttk.Label(self, text="Secure Wipe - Secure Data Wiping Tool", font=('Arial', 16, 'bold'))
        title_label.pack(pady=10)
        
        # Refresh button
        refresh_frame = ttk.Frame(self)
        refresh_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(refresh_frame, text="🔄 Refresh Drives", command=self.refresh_drives).pack(side=tk.LEFT)
        
        # Drive list
        list_frame = ttk.LabelFrame(self, text="Available Drives")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        columns = ("Device", "Name", "Size", "Free", "Mount", "Type", "Status")
        self.drive_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
        
        column_widths = {"Device": 60, "Name": 150, "Size": 80, "Free": 80, "Mount": 120, "Type": 60, "Status": 80}
        for col in columns:
            self.drive_tree.heading(col, text=col)
            self.drive_tree.column(col, width=column_widths.get(col, 100))
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.drive_tree.yview)
        self.drive_tree.configure(yscrollcommand=scrollbar.set)
        
        self.drive_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.drive_tree.bind('<<TreeviewSelect>>', self._on_select)
        
        # Drive details frame
        details_frame = ttk.LabelFrame(self, text="Selected Drive Details")
        details_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.drive_details_text = tk.Text(details_frame, height=4, wrap=tk.WORD, state=tk.DISABLED)
        self.drive_details_text.pack(fill=tk.X, padx=5, pady=5)
        
        # Operation buttons
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        left_buttons = ttk.Frame(button_frame)
        left_buttons.pack(side=tk.LEFT)
        
        self.format_btn = ttk.Button(left_buttons, text="Complete secure wipe", command=self.callbacks['on_complete_wipe'], state=tk.DISABLED)
        self.format_btn.pack(side=tk.LEFT, padx=5)
        
        self.wipe_btn = ttk.Button(left_buttons, text="Free Space Wipe", command=self.callbacks['on_free_space_wipe'], state=tk.DISABLED)
        self.wipe_btn.pack(side=tk.LEFT, padx=5)
        
        right_buttons = ttk.Frame(button_frame)
        right_buttons.pack(side=tk.RIGHT)
        
        self.certificate_btn = ttk.Button(right_buttons, text="Generate Certificate", command=self.callbacks['on_generate_cert'], state=tk.DISABLED)
        self.certificate_btn.pack(side=tk.RIGHT, padx=5)

        self.stop_btn = ttk.Button(right_buttons, text="Stop Operation", command=self.callbacks['on_stop_operation'], state=tk.DISABLED)
        self.stop_btn.pack(side=tk.RIGHT, padx=5)
        
        # Progress frame
        progress_frame = ttk.LabelFrame(self, text="Operation Progress")
        progress_frame.pack(fill=tk.X, padx=10, pady=5)
        
        status_frame = ttk.Frame(progress_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.progress_var = tk.StringVar(value="Ready")
        self.progress_label = ttk.Label(status_frame, textvariable=self.progress_var, font=('Arial', 10, 'bold'))
        self.progress_label.pack(anchor=tk.W)
        
        self.time_estimate_var = tk.StringVar(value="")
        ttk.Label(status_frame, textvariable=self.time_estimate_var, font=('Arial', 9), foreground='blue').pack(anchor=tk.W, pady=(2, 0))
        
        self.speed_info_var = tk.StringVar(value="")
        ttk.Label(status_frame, textvariable=self.speed_info_var, font=('Arial', 9), foreground='green').pack(anchor=tk.W, pady=(2, 0))
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, padx=10, pady=5)
        
        pass_frame = ttk.Frame(progress_frame)
        pass_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
        
        self.pass_progress_var = tk.StringVar(value="")
        ttk.Label(pass_frame, textvariable=self.pass_progress_var, font=('Arial', 8)).pack(side=tk.LEFT)
        
        self.pass_progress_bar = ttk.Progressbar(pass_frame, mode='determinate', length=200)
        self.pass_progress_bar.pack(side=tk.RIGHT, padx=(10, 0))

    def refresh_drives(self):
        logger.info("USER ACTION: Refreshing drive list...")
        from utils.formatting import format_size
        for item in self.drive_tree.get_children():
            self.drive_tree.delete(item)
            
        drives = get_physical_drives()
        for drive in drives:
            free_val = drive.get('free', 0)
            free_display = format_size(free_val) if isinstance(free_val, (int, float)) and free_val > 0 else ''
            status = drive.get('status', 'Online')

            self.drive_tree.insert('', 'end', values=(
                drive.get('device', ''),
                drive.get('name', 'Unknown'),
                drive.get('size_human', ''),
                free_display,
                drive.get('mountpoint', ''),
                drive.get('fstype', ''),
                status
            ))

    def _on_select(self, event):
        selection = self.drive_tree.selection()
        if not selection:
            self.format_btn.config(state=tk.DISABLED)
            self.wipe_btn.config(state=tk.DISABLED)
            self.drive_details_text.config(state=tk.NORMAL)
            self.drive_details_text.delete(1.0, tk.END)
            self.drive_details_text.config(state=tk.DISABLED)
            self.callbacks['on_drive_select'](None, None)
            return
            
        item = self.drive_tree.item(selection[0])
        device_path = item['values'][0]
        model_cached = item['values'][1]
        size_cached = item['values'][2]
        
        # Update UI instantly with cached values
        self.drive_details_text.config(state=tk.NORMAL)
        self.drive_details_text.delete(1.0, tk.END)
        self.drive_details_text.insert(tk.END, f"Device Path: {device_path}\nModel: {model_cached}\nSize: {size_cached}\n(Fetching deep identity...)")
        self.drive_details_text.config(state=tk.DISABLED)

        # Disable buttons temporarily while we fetch deep identity to prevent race conditions
        self.format_btn.config(state=tk.DISABLED)
        self.wipe_btn.config(state=tk.DISABLED)

        def _fetch_identity_bg():
            identity = get_disk_identity(device_path)
            
            def _apply():
                # Ensure the selection hasn't changed while we were fetching
                current_selection = self.drive_tree.selection()
                if not current_selection or self.drive_tree.item(current_selection[0])['values'][0] != device_path:
                    return

                self.drive_details_text.config(state=tk.NORMAL)
                self.drive_details_text.delete(1.0, tk.END)
                self.drive_details_text.insert(tk.END, f"Device Path: {device_path}\nModel: {identity.get('model')}\nSize: {identity.get('size_human')}")
                self.drive_details_text.config(state=tk.DISABLED)

                if not getattr(self, 'operation_in_progress', False):
                    self.format_btn.config(state=tk.NORMAL)
                    self.wipe_btn.config(state=tk.NORMAL)
                self.callbacks['on_drive_select'](device_path, identity)

            self.after(0, _apply)

        import threading
        threading.Thread(target=_fetch_identity_bg, daemon=True).start()

    def set_operation_state(self, is_running):
        state = tk.DISABLED if is_running else tk.NORMAL
        self.format_btn.config(state=state)
        self.wipe_btn.config(state=state)
        self.stop_btn.config(state=tk.NORMAL if is_running else tk.DISABLED)
        if is_running:
            self._wipe_start_time = None
            self._last_step = None

    def update_progress(self, p: WipeProgress):
        self.progress_var.set(f"Step {p.step_index}/{p.total_steps}: {p.current_step}")
        
        overall_pct = (p.bytes_done / max(p.total_bytes, 1)) * 100
        self.progress_bar['value'] = overall_pct
        
        import time
        if not getattr(self, '_wipe_start_time', None) or getattr(self, '_last_step', None) != p.current_step:
            self._wipe_start_time = time.time()
            self._last_eta_update = 0
            self._eta_str = "Calculating ETA..."
            self._last_step = p.current_step
            self._start_bytes = p.bytes_done

        now = time.time()
        elapsed = now - self._wipe_start_time
        
        if p.bytes_done > getattr(self, '_start_bytes', 0) and elapsed > 5 and (now - getattr(self, '_last_eta_update', 0) > 1):
            bytes_written_this_step = p.bytes_done - self._start_bytes
            rate = bytes_written_this_step / elapsed
            bytes_left = max(p.total_bytes - p.bytes_done, 0)
            seconds_left = bytes_left / rate if rate > 0 else 0
            
            from utils.formatting import format_time_human_readable
            self._eta_str = format_time_human_readable(seconds_left)
            self._last_eta_update = now
            
        eta_display = f" | ETA: {self._eta_str}" if 0 < overall_pct < 100 and p.current_step == 'overwrite_passes' else ""
        
        self.pass_progress_var.set(f"Pass {p.current_pass}/{p.total_passes} | Pattern: {p.pattern_name} | {overall_pct:.1f}%{eta_display}")
        self.pass_progress_bar['value'] = overall_pct

    def set_status(self, status):
        self.progress_var.set(status)
