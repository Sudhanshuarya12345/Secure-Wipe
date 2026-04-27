"""Base class for filesystem-specific metadata wipers.

Metadata wipers are plugins — they must NOT import from core/.
Only utils/ and diskio/ imports are allowed.
"""

from abc import ABC, abstractmethod


class MetadataWiperPlugin(ABC):
    """Plugin interface for filesystem-specific metadata destruction."""

    @abstractmethod
    def can_handle(self, filesystem_type, system):
        """Return True if this plugin can wipe metadata for the given filesystem and OS."""
        ...

    @abstractmethod
    def wipe_metadata(self, mount_point, passes):
        """Perform metadata wiping on the mounted filesystem.

        Args:
            mount_point (str): The path where the filesystem is mounted.
            passes (int): Number of overwrite passes to apply to metadata.

        Returns:
            tuple: (success (bool), messages (list of str))
        """
        ...

    def get_structures(self):
        """Return human-readable list of structures this wiper targets.

        Example: ['MFT', '$LogFile', '$Bitmap', 'Boot Sector']
        Used for audit logging and UI preview.
        """
        return []
