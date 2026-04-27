import subprocess
import platform

from utils.constants import (
    DEVICE_TYPE_HDD,
    DEVICE_TYPE_SATA_SSD,
    DEVICE_TYPE_NVME_SSD
)
from utils.system import command_exists
from core.drive_manager import detect_device_profile

def detect_firmware_capabilities(disk_path, device_profile=None):
    """Detect firmware erase/sanitize capabilities required for strategy fallback."""
    profile = device_profile or detect_device_profile(disk_path)
    capabilities = {
        'supports_secure_erase': False,
        'supports_enhanced_erase': False,
        'supports_nvme_sanitize': False,
        'supports_nvme_format': False,
        'supports_crypto_erase': False,
        'frozen_state': False,
        'power_stability_warning': 'Ensure stable power during firmware erase/sanitize operations.',
        'notes': [],
    }

    system = platform.system()
    device_type = profile.get('device_type')

    try:
        if system == 'Linux':
            if device_type in (DEVICE_TYPE_HDD, DEVICE_TYPE_SATA_SSD):
                if command_exists('hdparm'):
                    output = subprocess.check_output(['hdparm', '-I', str(disk_path)], stderr=subprocess.STDOUT).decode('utf-8', errors='ignore').lower()
                    capabilities['supports_secure_erase'] = ('security erase unit' in output) or ('supported: enhanced erase' in output)
                    capabilities['supports_enhanced_erase'] = 'enhanced security erase' in output
                    capabilities['frozen_state'] = ('frozen' in output) and ('not\tfrozen' not in output) and ('not frozen' not in output)
                    capabilities['supports_crypto_erase'] = ('crypto scramble' in output) or ('sanitize feature set' in output and 'crypto' in output)
                else:
                    capabilities['notes'].append('hdparm not found; ATA secure erase unavailable')

            if device_type == DEVICE_TYPE_NVME_SSD:
                if command_exists('nvme'):
                    output = subprocess.check_output(['nvme', 'id-ctrl', '-H', str(disk_path)], stderr=subprocess.STDOUT).decode('utf-8', errors='ignore').lower()
                    capabilities['supports_nvme_sanitize'] = ('sanitize' in output) and ('not supported' not in output)
                    capabilities['supports_nvme_format'] = True
                    capabilities['supports_crypto_erase'] = ('crypto erase' in output) or ('sanicap' in output and 'crypto' in output)
                else:
                    capabilities['notes'].append('nvme-cli not found; NVMe sanitize unavailable')

        elif system == 'Windows':
            capabilities['notes'].append('Windows path cannot reliably issue firmware sanitize commands in this build; Linux is recommended')

        elif system == 'Darwin':
            capabilities['notes'].append('macOS path has limited firmware sanitize support in this build; Linux is recommended')
    except Exception as exc:
        capabilities['notes'].append(str(exc))

    return capabilities
