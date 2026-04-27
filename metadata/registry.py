import platform

from .ntfs import NTFSMetadataWiper
from .ext4 import Ext4MetadataWiper
from .fat import FATMetadataWiper

_PLUGINS = [
    NTFSMetadataWiper(),
    Ext4MetadataWiper(),
    FATMetadataWiper(),
]

def get_metadata_wiper(filesystem_type, system):
    """Get the appropriate metadata wiper for the filesystem."""
    for plugin in _PLUGINS:
        if plugin.can_handle(filesystem_type, system):
            return plugin
    return None

def wipe_filesystem_metadata(mount_point, filesystem_type, passes=1):
    """Entry point to wipe metadata on a specific mount point."""
    system = platform.system()
    wiper = get_metadata_wiper(filesystem_type, system)
    
    if wiper:
        return wiper.wipe_metadata(mount_point, passes)
    
    # Return True since metadata wiping is optional/best-effort if no plugin exists.
    return True, []
