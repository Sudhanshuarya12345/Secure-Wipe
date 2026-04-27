"""Cross-platform raw disk I/O abstraction layer.

This module is a leaf dependency; it must NOT import from core/, firmware/, 
metadata/, or ui/. Only utils/ imports are allowed.
"""

import os
import re
import platform
import errno
import logging

from utils.constants import DEFAULT_WIPE_BLOCK_SIZE

logger = logging.getLogger(__name__)


def normalize_pattern(pattern):
    """Normalize user-provided pattern name."""
    pattern = str(pattern or '').lower().strip()
    return pattern if pattern in ('random', 'zeroes', 'ones', 'all') else 'random'


def resolve_wipe_block_size(block_size):
    """Resolve raw block size to a safe integer value."""
    try:
        bs = int(block_size)
        if bs <= 0:
            return DEFAULT_WIPE_BLOCK_SIZE
        return bs
    except (ValueError, TypeError):
        return DEFAULT_WIPE_BLOCK_SIZE


def resolve_raw_disk_path(disk_path):
    """Resolve platform-specific raw device path."""
    path = str(disk_path)
    if platform.system() == 'Windows':
        if path.startswith('\\\\.\\PhysicalDrive'):
            return path
        disk_num_match = re.search(r'(\d+)$', path)
        if disk_num_match:
            return f"\\\\.\\PhysicalDrive{disk_num_match.group(1)}"
    return path


def _get_disk_size_windows(handle):
    """Get the size of a raw disk on Windows using DeviceIoControl."""
    try:
        import ctypes
        import ctypes.wintypes as wintypes
        import struct

        IOCTL_DISK_GET_LENGTH_INFO = 0x0007405C
        out_buf = ctypes.create_string_buffer(8)
        bytes_returned = wintypes.DWORD(0)

        result = ctypes.windll.kernel32.DeviceIoControl(
            handle,
            IOCTL_DISK_GET_LENGTH_INFO,
            None, 0,
            out_buf, 8,
            ctypes.byref(bytes_returned),
            None,
        )
        if result:
            return struct.unpack('<Q', out_buf.raw)[0]
    except Exception as exc:
        logger.debug("DeviceIoControl GET_LENGTH_INFO failed: %s", exc)
    return None


def _lock_volume_windows(handle):
    """Send FSCTL_LOCK_VOLUME to a Windows disk handle.

    Returns:
        Tuple[bool, int]: (success, win32_error_code)
    """
    try:
        import ctypes
        import ctypes.wintypes as wintypes

        FSCTL_LOCK_VOLUME = 0x00090018
        bytes_returned = wintypes.DWORD(0)
        result = ctypes.windll.kernel32.DeviceIoControl(
            handle, FSCTL_LOCK_VOLUME,
            None, 0, None, 0,
            ctypes.byref(bytes_returned), None,
        )
        if result:
            return True, 0
        return False, ctypes.GetLastError()
    except Exception:
        return False, -1


def _dismount_volume_windows(handle):
    """Send FSCTL_DISMOUNT_VOLUME to a Windows disk handle.

    Returns:
        Tuple[bool, int]: (success, win32_error_code)
    """
    try:
        import ctypes
        import ctypes.wintypes as wintypes

        FSCTL_DISMOUNT_VOLUME = 0x00090020
        bytes_returned = wintypes.DWORD(0)
        result = ctypes.windll.kernel32.DeviceIoControl(
            handle, FSCTL_DISMOUNT_VOLUME,
            None, 0, None, 0,
            ctypes.byref(bytes_returned), None,
        )
        if result:
            return True, 0
        return False, ctypes.GetLastError()
    except Exception:
        return False, -1


def _build_block(mode, block_size):
    """Build a single data block for the given pattern mode."""
    if mode == 'random':
        return os.urandom(block_size)
    elif mode == 'ones':
        return b'\xFF' * block_size
    else:
        return b'\x00' * block_size


def _write_to_raw_disk_windows_once(raw_path, mode, block_size, progress_callback=None, cancel_event=None):
    """Execute one Windows raw-write attempt with a fixed block size.

    Returns:
        Tuple[bool, str, int, int]:
            - success flag
            - detail string
            - total bytes written
            - last Win32 error code
    """
    import ctypes
    import ctypes.wintypes as wintypes

    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    FILE_FLAG_NO_BUFFERING = 0x20000000
    FILE_FLAG_WRITE_THROUGH = 0x80000000
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    CreateFileW = ctypes.windll.kernel32.CreateFileW
    CreateFileW.restype = wintypes.HANDLE
    WriteFile = ctypes.windll.kernel32.WriteFile
    CloseHandle = ctypes.windll.kernel32.CloseHandle
    SetFilePointer = ctypes.windll.kernel32.SetFilePointer

    handle = CreateFileW(
        raw_path,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        FILE_FLAG_WRITE_THROUGH | FILE_FLAG_NO_BUFFERING,
        None,
    )

    if handle == INVALID_HANDLE_VALUE or handle is None:
        err_code = ctypes.GetLastError()
        raise PermissionError(
            f"Cannot open {raw_path} for writing (Win32 error {err_code}). "
            "Ensure you are running as Administrator."
        )

    try:
        # Lock and dismount are best-effort, but we keep their status for diagnostics.
        lock_ok, lock_err = _lock_volume_windows(handle)
        dismount_ok, dismount_err = _dismount_volume_windows(handle)
        if not lock_ok:
            logger.debug("FSCTL_LOCK_VOLUME failed on %s (err=%s)", raw_path, lock_err)
        if not dismount_ok:
            logger.debug("FSCTL_DISMOUNT_VOLUME failed on %s (err=%s)", raw_path, dismount_err)

        # Get disk size so we know when to stop
        disk_size = _get_disk_size_windows(handle)
        logger.info("Disk %s size: %s bytes", raw_path, disk_size)

        # Seek to start
        SetFilePointer(handle, 0, None, 0)

        # Ensure block_size is sector-aligned (512 bytes minimum)
        SECTOR_SIZE = 512
        block_size = max(SECTOR_SIZE, (int(block_size) // SECTOR_SIZE) * SECTOR_SIZE)

        static_block = None
        if mode in ('zeroes', 'ones'):
            static_block = _build_block(mode, block_size)

        bytes_written_total = 0
        last_error_code = 0
        reached_end = False

        # Report initial 0% progress
        if progress_callback:
            progress_callback(bytes_written_total, disk_size or 0)

        while True:
            if cancel_event and cancel_event.is_set():
                logger.info("Write to %s aborted by user at offset %s", raw_path, bytes_written_total)
                return False, "Aborted by user", bytes_written_total, 0
                
            # If we know the disk size, stop when we've written enough
            if disk_size is not None and bytes_written_total >= disk_size:
                break

            # If near the end of disk, shrink to fit and align down to sector size.
            write_len = block_size
            if disk_size is not None:
                remaining = disk_size - bytes_written_total
                if remaining <= 0:
                    reached_end = True
                    break

                if remaining < write_len:
                    write_len = remaining

                write_len = (int(write_len) // SECTOR_SIZE) * SECTOR_SIZE
                if write_len <= 0:
                    reached_end = True
                    break

            if mode == 'random':
                data = os.urandom(write_len)
            elif write_len == block_size and static_block is not None:
                data = static_block
            else:
                data = _build_block(mode, write_len)

            write_buf = ctypes.create_string_buffer(data)
            c_bytes_written = wintypes.DWORD(0)

            success = WriteFile(
                handle,
                write_buf,
                write_len,
                ctypes.byref(c_bytes_written),
                None,
            )

            if not success or c_bytes_written.value == 0:
                last_error_code = ctypes.GetLastError()

                # If we cannot read disk size, these are commonly end-of-device conditions.
                if disk_size is None and last_error_code in (0, 23, 87, 112) and bytes_written_total > 0:
                    reached_end = True
                    break

                detail = (
                    f"WriteFile failed at offset {bytes_written_total} on {raw_path} "
                    f"(Win32 error {last_error_code})."
                )
                if bytes_written_total == 0 and (not lock_ok or not dismount_ok):
                    detail += (
                        f" Volume lock/dismount may have failed "
                        f"(lock_ok={lock_ok}, lock_err={lock_err}, "
                        f"dismount_ok={dismount_ok}, dismount_err={dismount_err})."
                    )
                if last_error_code in (21, 1117):
                    detail += " Device became unavailable or reported an I/O error."
                logger.warning(detail)
                return False, detail, bytes_written_total, last_error_code

            bytes_written_total += c_bytes_written.value

            import time
            current_time = time.time()
            # Throttle UI updates to max 5 times a second (every 0.2s)
            if progress_callback and (current_time - getattr(_write_to_raw_disk_windows_once, 'last_update', 0) > 0.2):
                progress_callback(bytes_written_total, disk_size or 0)
                _write_to_raw_disk_windows_once.last_update = current_time

            # Log progress every ~256 MB
            if bytes_written_total % (block_size * 32) == 0:
                if disk_size:
                    pct = (bytes_written_total / disk_size) * 100
                    logger.info("Overwrite progress: %.1f%% (%d bytes)", pct, bytes_written_total)

        # Ensure we always send the final progress update when the loop breaks
        if progress_callback:
            progress_callback(bytes_written_total, disk_size or 0)

        logger.info(
            "Overwrite attempt complete: %d bytes written to %s (last_err=%d, reached_end=%s)",
            bytes_written_total,
            raw_path,
            last_error_code,
            reached_end,
        )

        if bytes_written_total <= 0:
            detail = f"WriteFile returned 0 bytes on {raw_path} (Win32 error: {last_error_code})"
            if not lock_ok or not dismount_ok:
                detail += (
                    f"; lock_ok={lock_ok}, lock_err={lock_err}, "
                    f"dismount_ok={dismount_ok}, dismount_err={dismount_err}"
                )
            return False, detail, bytes_written_total, last_error_code

        if disk_size is not None:
            # Allow up to one sector of tail slack when disk size is not sector-aligned.
            expected_min = max(0, int(disk_size) - SECTOR_SIZE)
            if bytes_written_total < expected_min:
                detail = (
                    f"Short raw write on {raw_path}: wrote {bytes_written_total} bytes, "
                    f"expected about {disk_size} bytes."
                )
                return False, detail, bytes_written_total, last_error_code

        return True, '', bytes_written_total, last_error_code

    finally:
        CloseHandle(handle)


def _write_to_raw_disk_windows(raw_path, mode, block_size, progress_callback=None, cancel_event=None):
    """Windows-specific raw disk write with retry on zero-byte starts.

    Some removable USB controllers reject very large initial writes. We retry
    with smaller aligned block sizes only when no data was written.
    """
    sector = 512
    candidate_sizes = []
    for size in (block_size, 1024 * 1024, 512 * 1024, 128 * 1024, 64 * 1024):
        aligned = max(sector, (int(size) // sector) * sector)
        if aligned not in candidate_sizes:
            candidate_sizes.append(aligned)

    last_detail = ''
    last_error_code = 0
    for idx, candidate in enumerate(candidate_sizes):
        if idx > 0:
            logger.warning(
                "Retrying raw write on %s with smaller block size=%d bytes",
                raw_path,
                candidate,
            )

        success, detail, bytes_written, err_code = _write_to_raw_disk_windows_once(raw_path, mode, candidate, progress_callback, cancel_event)
        if success:
            return True, ''

        last_detail = detail
        last_error_code = err_code

        # Retry only if nothing was written and the failure looks like size/parameter/startup issue.
        if bytes_written > 0:
            return False, detail
        if err_code not in (0, 87):
            return False, detail

    if not last_detail:
        last_detail = f"WriteFile returned 0 bytes on {raw_path} (Win32 error: {last_error_code})"
    return False, last_detail


def _write_to_raw_disk_unix(raw_path, mode, block_size, progress_callback=None, cancel_event=None):
    """Unix/macOS raw disk write using standard file I/O.
    
    On Unix, /dev/sdX devices can be opened with standard open() in 'r+b' mode.
    """
    try:
        with open(raw_path, 'r+b') as f:
            data = _build_block(mode, block_size) if mode in ('zeroes', 'ones') else None
            bytes_written_total = 0

            while True:
                if cancel_event and cancel_event.is_set():
                    return False

                try:
                    if mode == 'random':
                        data = os.urandom(block_size)
                    f.write(data)
                    bytes_written_total += block_size
                except OSError as e:
                    if e.errno in (errno.ENOSPC, errno.EFBIG, errno.EIO, errno.EINVAL):
                        break
                    raise

                if progress_callback:
                    progress_callback(bytes_written_total, None)

                if f.tell() % (block_size * 32) == 0:
                    f.flush()

            try:
                f.flush()
                os.fsync(f.fileno())
            except Exception:
                pass

        return True
    except Exception as e:
        logger.warning("Raw disk wipe failed on %s: %s", raw_path, e)
        return False


def write_to_raw_disk(disk_path, pattern='random', block_size=DEFAULT_WIPE_BLOCK_SIZE, progress_callback=None, cancel_event=None):
    """Write directly to a raw device until full.
    
    Returns:
        Tuple of (success: bool, detail: str).
        On success, detail is empty. On failure, detail describes the error.
    """
    block_size = resolve_wipe_block_size(block_size)
    mode = normalize_pattern(pattern)
    if mode == 'all':
        mode = 'random'

    raw_path = resolve_raw_disk_path(disk_path)
    logger.info("Starting raw disk write to %s (pattern=%s, block_size=%d)", raw_path, mode, block_size)

    try:
        if platform.system() == 'Windows':
            return _write_to_raw_disk_windows(raw_path, mode, block_size, progress_callback, cancel_event)
        else:
            result = _write_to_raw_disk_unix(raw_path, mode, block_size, progress_callback, cancel_event)
            return (result, '') if result else (False, f'Write failed on {raw_path}')
    except PermissionError as e:
        msg = (
            f"Permission denied writing to {raw_path}: {e}\n"
            "You must run this application as Administrator.\n"
            "Right-click the terminal/app → 'Run as administrator'"
        )
        logger.error(msg)
        return False, msg
    except Exception as e:
        msg = f"Raw disk wipe failed on {raw_path}: {e}"
        logger.error(msg)
        return False, msg
