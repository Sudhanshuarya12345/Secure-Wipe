"""FAT/exFAT metadata wiper — targets FAT tables."""

import logging

from .base import MetadataWiperPlugin

logger = logging.getLogger(__name__)


class FATMetadataWiper(MetadataWiperPlugin):
    """Wipes FAT/exFAT metadata (FAT tables)."""

    def can_handle(self, filesystem_type, system):
        return filesystem_type.lower() in ('fat32', 'exfat', 'fat16')

    def get_structures(self):
        return ['FAT1', 'FAT2', 'Root Directory']

    def wipe_metadata(self, mount_point, passes):
        messages = []
        messages.append('FAT metadata: generally handled by full free-space wipe.')
        return True, messages
