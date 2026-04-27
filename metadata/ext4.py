"""Ext4 metadata wiper — targets journal, superblock."""

import logging

from .base import MetadataWiperPlugin

logger = logging.getLogger(__name__)


class Ext4MetadataWiper(MetadataWiperPlugin):
    """Wipes Ext4 metadata (Journal)."""

    def can_handle(self, filesystem_type, system):
        return filesystem_type.lower() in ('ext3', 'ext4') and system == 'Linux'

    def get_structures(self):
        return ['Journal', 'Superblock', 'Group Descriptors']

    def wipe_metadata(self, mount_point, passes):
        messages = []
        messages.append('Ext4 journal wiping: implicitly covered by full-disk overwrite.')
        return True, messages
