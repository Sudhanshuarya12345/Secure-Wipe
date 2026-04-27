import tkinter as tk
from tkinter import ttk

from core.drive_manager import detect_device_profile, get_sector_geometry
from firmware.capabilities import detect_firmware_capabilities

class AdvancedSecurityTab(ttk.Frame):
    """Displays hardware capabilities and preflight status."""
    def __init__(self, parent):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        # Profile Frame
        prof_frame = ttk.LabelFrame(self, text="Device Profile")
        prof_frame.pack(fill='x', padx=10, pady=5)
        
        self.lbl_type = ttk.Label(prof_frame, text="Device Type: Unknown")
        self.lbl_type.pack(anchor='w', padx=5, pady=2)
        self.lbl_transport = ttk.Label(prof_frame, text="Transport: Unknown")
        self.lbl_transport.pack(anchor='w', padx=5, pady=2)

        # Firmware Capabilities Frame
        fw_frame = ttk.LabelFrame(self, text="Firmware Capabilities")
        fw_frame.pack(fill='x', padx=10, pady=5)
        
        self.lbl_ata = ttk.Label(fw_frame, text="ATA Secure Erase: Unknown")
        self.lbl_ata.pack(anchor='w', padx=5, pady=2)
        self.lbl_nvme_san = ttk.Label(fw_frame, text="NVMe Sanitize: Unknown")
        self.lbl_nvme_san.pack(anchor='w', padx=5, pady=2)
        self.lbl_nvme_fmt = ttk.Label(fw_frame, text="NVMe Format: Unknown")
        self.lbl_nvme_fmt.pack(anchor='w', padx=5, pady=2)
        self.lbl_crypto = ttk.Label(fw_frame, text="Crypto Erase Supported: Unknown")
        self.lbl_crypto.pack(anchor='w', padx=5, pady=2)
        self.lbl_frozen = ttk.Label(fw_frame, text="Security Frozen: Unknown")
        self.lbl_frozen.pack(anchor='w', padx=5, pady=2)

        # Hidden Regions Frame
        hr_frame = ttk.LabelFrame(self, text="Hidden Regions (HPA/DCO)")
        hr_frame.pack(fill='x', padx=10, pady=5)
        
        self.lbl_hpa = ttk.Label(hr_frame, text="HPA Present: Unknown")
        self.lbl_hpa.pack(anchor='w', padx=5, pady=2)
        self.lbl_dco = ttk.Label(hr_frame, text="DCO Restricted: Unknown")
        self.lbl_dco.pack(anchor='w', padx=5, pady=2)
        self.lbl_sectors = ttk.Label(hr_frame, text="Sectors (Current/Native): Unknown")
        self.lbl_sectors.pack(anchor='w', padx=5, pady=2)

    def update_capabilities(self, disk_path):
        if not disk_path:
            self.lbl_type.config(text="Device Type: Unknown")
            self.lbl_transport.config(text="Transport: Unknown")
            self.lbl_ata.config(text="ATA Secure Erase: Unknown")
            self.lbl_nvme_san.config(text="NVMe Sanitize: Unknown")
            self.lbl_nvme_fmt.config(text="NVMe Format: Unknown")
            self.lbl_crypto.config(text="Crypto Erase Supported: Unknown")
            self.lbl_frozen.config(text="Security Frozen: Unknown")
            self.lbl_hpa.config(text="HPA Present: Unknown")
            self.lbl_dco.config(text="DCO Restricted: Unknown")
            self.lbl_sectors.config(text="Sectors: Unknown")
            return

        # Show loading state
        self.lbl_type.config(text="Device Type: Detecting...")
        self.lbl_transport.config(text="Transport: Detecting...")
        
        def _fetch_caps():
            try:
                profile = detect_device_profile(disk_path)
                caps = detect_firmware_capabilities(disk_path, profile)
                geo = get_sector_geometry(disk_path)

                def _apply():
                    self.lbl_type.config(text=f"Device Type: {profile.get('device_type', 'Unknown')}")
                    self.lbl_transport.config(text=f"Transport: {profile.get('transport', 'Unknown').upper()}")
                    
                    self.lbl_ata.config(text=f"ATA Secure Erase: {'Yes' if caps.get('secure_erase') else 'No'}")
                    self.lbl_nvme_san.config(text=f"NVMe Sanitize: {'Yes' if caps.get('nvme_sanitize') else 'No'}")
                    self.lbl_nvme_fmt.config(text=f"NVMe Format: {'Yes' if caps.get('nvme_format') else 'No'}")
                    self.lbl_crypto.config(text=f"Crypto Erase Supported: {'Yes' if caps.get('crypto_erase_supported') else 'No'}")
                    self.lbl_frozen.config(text=f"Security Frozen: {'Yes' if caps.get('security_frozen') else 'No'}")
                    
                    self.lbl_hpa.config(text=f"HPA Present: {'Yes' if geo.get('hpa_present') else 'No'}")
                    self.lbl_dco.config(text=f"DCO Restricted: {'Yes' if geo.get('dco_restricted') else 'No'}")
                    self.lbl_sectors.config(text=f"Sectors (Current/Native): {geo.get('current_sectors', 'Unknown')} / {geo.get('native_sectors', 'Unknown')}")

                self.after(0, _apply)
            except Exception as e:
                self.after(0, lambda: self.lbl_type.config(text=f"Error reading capabilities: {e}"))

        import threading
        threading.Thread(target=_fetch_caps, daemon=True).start()
