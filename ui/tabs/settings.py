import tkinter as tk
from tkinter import ttk
import logging

from core.strategy import build_execution_preview

logger = logging.getLogger(__name__)

class SettingsTab(ttk.Frame):
    """Wipe settings and configuration UI."""
    def __init__(self, parent):
        super().__init__(parent)
        
        self.level_var = tk.StringVar(value="STANDARD")
        self.pattern_var = tk.StringVar(value="all")
        self.passes_var = tk.IntVar(value=3)
        self.fs_var = tk.StringVar(value="exfat")
        self.verify_var = tk.BooleanVar(value=True)

        self._setup_ui()
        self._update_preview()
        
        # Log setting changes
        self.level_var.trace_add('write', lambda *_: logger.info("USER ACTION: Set Wipe Level to %s", self.level_var.get()))
        self.passes_var.trace_add('write', lambda *_: logger.info("USER ACTION: Set Passes to %s", self.passes_var.get()))
        self.pattern_var.trace_add('write', lambda *_: logger.info("USER ACTION: Set Pattern to %s", self.pattern_var.get()))
        self.fs_var.trace_add('write', lambda *_: logger.info("USER ACTION: Set Filesystem to %s", self.fs_var.get()))
        self.verify_var.trace_add('write', lambda *_: logger.info("USER ACTION: Set Verify to %s", self.verify_var.get()))

    def _setup_ui(self):
        # Level selection
        level_frame = ttk.LabelFrame(self, text="Sanitization Depth")
        level_frame.pack(fill='x', padx=10, pady=10)

        levels = [
            ("Standard Wipe", "STANDARD"),
            ("Enhanced Wipe (Recommended for SSD)", "ENHANCED"),
            ("Maximum Wipe (Comprehensive)", "MAXIMUM")
        ]

        for text, mode in levels:
            ttk.Radiobutton(
                level_frame, text=text, variable=self.level_var, 
                value=mode, command=self._update_preview
            ).pack(anchor='w', padx=10, pady=5)

        self.preview_text = tk.Text(level_frame, height=5, wrap='word', state='disabled', bg='#f0f0f0')
        self.preview_text.pack(fill='x', padx=10, pady=5)

        # Options
        opt_frame = ttk.LabelFrame(self, text="Software Overwrite Fallback Options")
        opt_frame.pack(fill='x', padx=10, pady=10)

        ttk.Label(opt_frame, text="Passes:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ttk.Spinbox(opt_frame, from_=1, to=35, textvariable=self.passes_var, width=5).grid(row=0, column=1, padx=5, pady=5, sticky='w')

        ttk.Label(opt_frame, text="Pattern:").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        ttk.Combobox(opt_frame, textvariable=self.pattern_var, values=('all', 'random', 'zeroes', 'ones'), state='readonly', width=10).grid(row=1, column=1, padx=5, pady=5, sticky='w')

        # Reformat
        fmt_frame = ttk.LabelFrame(self, text="Post-Wipe Reformat")
        fmt_frame.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(fmt_frame, text="Filesystem:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ttk.Combobox(fmt_frame, textvariable=self.fs_var, values=('exfat', 'ntfs', 'fat32', 'ext4'), state='readonly', width=10).grid(row=0, column=1, padx=5, pady=5, sticky='w')
        ttk.Checkbutton(fmt_frame, text="Verify sectors after wipe", variable=self.verify_var).grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky='w')

    def _update_preview(self):
        mode = self.level_var.get()
        preview = build_execution_preview(mode)
        desc = preview.get('description', '')
        notes = preview.get('technical_note', '')
        
        self.preview_text.config(state='normal')
        self.preview_text.delete(1.0, 'end')
        self.preview_text.insert('end', f"{desc}\n\nTechnical details: {notes}")
        self.preview_text.config(state='disabled')

    def get_wipe_level(self): return self.level_var.get()
    def get_passes(self): return self.passes_var.get()
    def get_pattern(self): return self.pattern_var.get()
    def get_filesystem(self): return self.fs_var.get()
    def get_verify(self): return self.verify_var.get()
