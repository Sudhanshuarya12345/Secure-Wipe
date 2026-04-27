import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import queue
import logging
import os
import json
import time

logger = logging.getLogger(__name__)

from core.wipe_engine import WipePipeline, WipeProgress
from audit.certificate import generate_sanitization_certificate
from .tabs.drive_selection import DriveSelectionTab
from .tabs.settings import SettingsTab
from .tabs.advanced_security import AdvancedSecurityTab
from .tabs.log import LogTab

class SecureWipeMainWindow(tk.Tk):
    """Main Application Window for Secure-Wipe Modular Edition."""
    def __init__(self, product_key=""):
        super().__init__()
        self.title("Secure Wipe v1.5 - Secure Data Wiping Tool")
        self.geometry("900x750")
        
        # Configure style
        self.style = ttk.Style()
        if 'clam' in self.style.theme_names():
            self.style.theme_use('clam')
        
        # Shared state
        self.product_key = product_key
        self.selected_disk_path = None
        self.selected_disk_identity = None
        self.last_wipe_result = None
        self.progress_queue = queue.Queue()
        self.wipe_thread = None
        self.cancel_event = threading.Event()
        
        # Create Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Callbacks map
        callbacks = {
            'on_drive_select': self._on_drive_selected,
            'on_complete_wipe': self._on_complete_wipe_requested,
            'on_free_space_wipe': self._on_free_space_wipe_requested,
            'on_stop_operation': self._on_stop_requested,
            'on_generate_cert': self._on_generate_cert_requested
        }

        # Tabs
        self.drive_tab = DriveSelectionTab(self.notebook, callbacks)
        self.settings_tab = SettingsTab(self.notebook)
        self.advanced_tab = AdvancedSecurityTab(self.notebook)
        
        # Create a dummy LogTab but use it strictly for showing output, remove the Start Wipe button in it
        self.log_tab = LogTab(self.notebook, lambda: None)
        self.log_tab.btn_start.pack_forget() # Hide the button, we trigger from Drive Selection tab now
        
        self.notebook.add(self.drive_tab, text="Drive Selection")
        self.notebook.add(self.settings_tab, text="Settings")
        self.notebook.add(self.advanced_tab, text="Advanced Security")
        self.notebook.add(self.log_tab, text="Log")

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._check_queue()

    def _on_drive_selected(self, disk_path, identity):
        self.selected_disk_path = disk_path
        self.selected_disk_identity = identity
        
        if disk_path:
            model = identity.get('model', 'Unknown') if identity else 'Unknown'
            logger.info("USER ACTION: Selected drive %s (Model: %s)", disk_path, model)
            
        self.advanced_tab.update_capabilities(disk_path)

    def _on_complete_wipe_requested(self):
        if not self.selected_disk_path:
            return

        plan_mode = self.settings_tab.get_wipe_level()
        passes = self.settings_tab.get_passes()
        pattern = self.settings_tab.get_pattern()
        verify = self.settings_tab.get_verify()
        filesystem = self.settings_tab.get_filesystem()

        confirm = messagebox.askyesno(
            "Confirm Destructive Operation",
            f"WARNING: You are about to irrevocably destroy all data on:\n\n{self.selected_disk_path}\n\n"
            f"Level: {plan_mode}\n\nAre you absolutely sure you want to proceed?"
        )
        if not confirm:
            logger.info("USER ACTION: Canceled wipe operation on %s", self.selected_disk_path)
            return

        start_msg = f"Starting {plan_mode} wipe on {self.selected_disk_path}"
        self.log_tab.log_message(start_msg)
        logger.info("USER ACTION: %s. Passes: %s, Pattern: %s, Verify: %s, FS: %s", start_msg, passes, pattern, verify, filesystem)
        
        self.drive_tab.set_operation_state(True)
        
        # Switch to log tab to show operations occurring if desired, or stay to see progress bars
        # self.notebook.select(self.log_tab) 

        self.wipe_thread = threading.Thread(
            target=self._run_wipe_pipeline,
            args=(self.selected_disk_path, self.selected_disk_identity, plan_mode, passes, pattern, filesystem, verify),
            daemon=True
        )
        self.wipe_thread.start()

    def _on_free_space_wipe_requested(self):
        messagebox.showinfo("Free Space Wipe", "Free Space Wipe feature will be available in a future update.")

    def _on_stop_requested(self):
        if self.wipe_thread and self.wipe_thread.is_alive():
            confirm = messagebox.askyesno("Stop Wipe", "Are you sure you want to abort the wipe process?\n\nThe drive may be left in an unusable or raw state.")
            if confirm:
                self.cancel_event.set()
                self.log_tab.log_message("USER ACTION: Abort requested. Stopping pipeline...")
                logger.info("USER ACTION: Stop operation requested.")
        else:
            messagebox.showinfo("Stop", "No active wipe operation to stop.")

    def _on_generate_cert_requested(self):
        if not self.last_wipe_result or not self.last_wipe_result.report_path:
            messagebox.showwarning("Certificate", "No successful wipe record found for the current session.")
            return

        try:
            with open(self.last_wipe_result.report_path, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
            
            initial_file = f"Sanitization_Certificate_{report_data.get('report_id', 'result')[:8]}.txt"
            output_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                initialfile=initial_file,
                title="Save Sanitization Certificate",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            
            if output_path:
                generate_sanitization_certificate(report_data, output_path)
                messagebox.showinfo("Success", f"Certificate generated successfully:\n{output_path}")
                logger.info(f"USER ACTION: Generated certificate at {output_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate certificate:\n{e}")
            logger.error(f"Failed to generate certificate: {e}")

    def _run_wipe_pipeline(self, disk_path, identity, plan_mode, passes, pattern, filesystem, verify):
        def progress_callback(progress: WipeProgress):
            self.progress_queue.put(('progress', progress))

        try:
            self.cancel_event.clear()
            pipeline = WipePipeline(
                disk_path=disk_path,
                execution_plan=plan_mode,
                expected_identity=identity,
                callback=progress_callback,
                cancel_event=self.cancel_event
            )
            result = pipeline.execute(
                passes=passes,
                pattern=pattern,
                filesystem=filesystem,
                verify=verify
            )
            self.progress_queue.put(('result', result))
        except Exception as e:
            self.progress_queue.put(('error', str(e)))

    def _check_queue(self):
        try:
            while True:
                msg_type, data = self.progress_queue.get_nowait()
                if msg_type == 'progress':
                    self.drive_tab.update_progress(data)
                elif msg_type == 'result':
                    self.log_tab.on_wipe_complete(data)
                    self.drive_tab.set_operation_state(False)
                    self.drive_tab.set_status("Finished")
                    if data.success:
                        self.last_wipe_result = data
                        self.drive_tab.certificate_btn.config(state=tk.NORMAL)
                elif msg_type == 'error':
                    self.log_tab.on_wipe_error(data)
                    self.drive_tab.set_operation_state(False)
                    self.drive_tab.set_status("FAILED")
        except queue.Empty:
            pass
        finally:
            self.after(100, self._check_queue)

    def _on_close(self):
        if self.wipe_thread and self.wipe_thread.is_alive():
            messagebox.showwarning("Warning", "Cannot close while a wipe is in progress.")
            return
        self.destroy()

def start_ui(product_key=""):
    app = SecureWipeMainWindow(product_key=product_key)
    app.mainloop()

def main():
    start_ui()

if __name__ == '__main__':
    main()
