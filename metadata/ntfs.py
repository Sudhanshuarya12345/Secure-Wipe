"""NTFS metadata wiper — targets MFT, $LogFile, $Bitmap."""

import subprocess
import logging

from .base import MetadataWiperPlugin

logger = logging.getLogger(__name__)


class NTFSMetadataWiper(MetadataWiperPlugin):
    """Wipes NTFS metadata (MFT) using Windows cipher tool."""

    def can_handle(self, filesystem_type, system):
        return filesystem_type.lower() == 'ntfs' and system == 'Windows'

    def get_structures(self):
        return ['MFT', '$LogFile', '$Bitmap', 'Boot Sector']

    def wipe_metadata(self, mount_point, passes):
        messages = []
        try:
            cmd = ['cipher', '/w:' + mount_point]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                messages.append(f'Successfully wiped NTFS MFT on {mount_point}.')
                return True, messages
            else:
                messages.append(f'Failed to wipe NTFS MFT: {result.stderr.strip() or result.stdout.strip()}')
                return False, messages
        except Exception as e:
            messages.append(f'Error wiping NTFS MFT: {e}')
            return False, messages
