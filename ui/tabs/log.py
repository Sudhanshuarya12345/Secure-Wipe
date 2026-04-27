import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import logging
import time
from core.wipe_engine import WipeProgress

class UILogHandler(logging.Handler):
    """Route python logging directly to the Tkinter text widget."""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.config(state='normal')
        self.text_widget.insert('end', msg + '\n')
        self.text_widget.see('end')
        self.text_widget.config(state='disabled')


class LogTab(ttk.Frame):
    """Execution status, logging, and trigger UI."""
    def __init__(self, parent, start_callback):
        super().__init__(parent)
        self.start_callback = start_callback
        self._setup_ui()
        
        # Route core logs to UI
        self.log_handler = UILogHandler(self.log_text)
        self.log_handler.setLevel(logging.INFO)
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(self.log_handler)

    def _setup_ui(self):
        # Top controls
        top_frame = ttk.Frame(self)
        top_frame.pack(fill='x', padx=10, pady=5)
        
        self.btn_start = ttk.Button(top_frame, text="START WIPE", style='Danger.TButton', command=self.start_callback, state='disabled')
        self.btn_start.pack(side='right')

        # Status text and Progress bar removed (now exclusively in Drive Selection tab)

        # Log text
        self.log_text = scrolledtext.ScrolledText(self, state='disabled', height=20, bg='black', fg='lightgreen', font=('Consolas', 9))
        self.log_text.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Bottom controls
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(btn_frame, text="Clear Log", command=self.clear_log).pack(side='left', padx=5)
        ttk.Button(btn_frame, text="Save Log", command=self.save_log).pack(side='left', padx=5)

    def set_ready_state(self, is_ready):
        self.btn_start.config(state='normal' if is_ready else 'disabled')

    def log_message(self, message):
        self.log_text.config(state='normal')
        self.log_text.insert('end', message + '\n')
        self.log_text.see('end')
        self.log_text.config(state='disabled')

    def clear_log(self):
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, 'end')
        self.log_text.config(state='disabled')
        
    def save_log(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=f"securewipe_log_{time.strftime('%Y%m%d_%H%M%S')}.txt",
            title="Save Log",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if filepath:
            try:
                with open(filepath, 'w') as f:
                    f.write(self.log_text.get(1.0, 'end'))
                messagebox.showinfo("Success", f"Log saved successfully to {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save log:\n{e}")

    def on_wipe_complete(self, result):
        if result.success:
            self.log_message(f"\n--- WIPE COMPLETED SUCCESSFULLY ---")
            self.log_message(f"Claim Level: {result.claim_level}")
            messagebox.showinfo("Success", f"Data wipe completed successfully!\n\n{result.claim_statement}")
        else:
            self.log_message(f"\n--- WIPE COMPLETED WITH WARNINGS/ERRORS ---")
            for w in result.warnings:
                self.log_message(f"WARNING: {w}")
            messagebox.showwarning("Completed with Warnings", "Wipe completed but encountered warnings. Review the log.")

    def on_wipe_error(self, err_msg):
        self.log_message(f"\nFATAL ERROR: {err_msg}")
        messagebox.showerror("Wipe Failed", f"An error occurred during execution:\n{err_msg}")
