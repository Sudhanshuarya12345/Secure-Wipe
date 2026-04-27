"""Filesystem metadata wiping plugin system."""
from .registry import get_metadata_wiper, wipe_filesystem_metadata

__all__ = ['get_metadata_wiper', 'wipe_filesystem_metadata']
