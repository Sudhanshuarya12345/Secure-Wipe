"""Cross-platform raw disk I/O abstraction."""
from .disk_access import resolve_raw_disk_path, write_to_raw_disk

__all__ = ['resolve_raw_disk_path', 'write_to_raw_disk']
