"""NVMe sanitize and format operations.

This module must NOT import from core/ — it is a leaf dependency.
Only utils/ imports are allowed.
"""

import re
import subprocess
import platform
import signal
import threading
import logging

from utils.system import command_exists, run_silent_command, check_output_silent

logger = logging.getLogger(__name__)


def _normalize_nvme_device(device_path):
    """Strip partition suffix from NVMe device path (e.g. nvme0n1p2 -> nvme0n1).
    
    This is a local copy to avoid importing from core.drive_manager
    which would violate the firmware -> core dependency rule.
    """
    path = str(device_path or '').strip()
    if not path:
        return path
    # nvme0n1p2 -> nvme0n1
    path = re.sub(r'(nvme\d+n\d+)p\d+$', r'\1', path)
    # mmcblk0p1 -> mmcblk0
    path = re.sub(r'(mmcblk\d+)p\d+$', r'\1', path)
    # sda1 -> sda
    path = re.sub(r'(sd[a-z]+)\d+$', r'\1', path)
    return path


def run_nvme_sanitize(disk_path, sanitize_action='block'):
    """Run NVMe sanitize command with selected action."""
    messages = []
    if platform.system() != 'Linux':
        messages.append('NVMe sanitize is only supported on Linux in this build.')
        return False, messages

    if not command_exists('nvme'):
        messages.append('nvme-cli not found; NVMe sanitize unavailable.')
        return False, messages

    action_map = {
        'block': '2',
        'overwrite': '3',
        'crypto': '4',
    }
    action_code = action_map.get(str(sanitize_action or '').lower(), '2')
    normalized = _normalize_nvme_device(str(disk_path))
    cmd = ['nvme', 'sanitize', normalized, f'--sanact={action_code}']

    try:
        result = run_silent_command(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            messages.append(f'NVMe sanitize command accepted ({sanitize_action}).')
            return True, messages
        err = (result.stderr or result.stdout or '').strip()
        messages.append(f'NVMe sanitize failed: {err}')
        return False, messages
    except Exception as exc:
        messages.append(f'NVMe sanitize error: {exc}')
        return False, messages


def run_nvme_format(disk_path, ses='1'):
    """Run NVMe format command with secure erase setting (SES)."""
    messages = []
    if platform.system() != 'Linux':
        messages.append('NVMe format is only supported on Linux in this build.')
        return False, messages

    if not command_exists('nvme'):
        messages.append('nvme-cli not found; NVMe format unavailable.')
        return False, messages

    normalized = _normalize_nvme_device(str(disk_path))
    cmd = ['nvme', 'format', normalized, f'--ses={ses}']

    try:
        result = run_silent_command(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            messages.append(f'NVMe format command completed (SES={ses}).')
            return True, messages
        err = (result.stderr or result.stdout or '').strip()
        messages.append(f'NVMe format failed: {err}')
        return False, messages
    except Exception as exc:
        messages.append(f'NVMe format error: {exc}')
        return False, messages


def run_nvme_sanitize_with_interrupt_lock(disk_path, sanitize_action='block'):
    """Run NVMe sanitize with interruption lock in main-thread contexts."""
    in_main_thread = threading.current_thread() is threading.main_thread()
    original_handler = None

    def locked_handler(_sig, _frame):
        logger.warning('NVMe sanitize is running; interruption is blocked until a safe checkpoint.')

    try:
        if in_main_thread:
            original_handler = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, locked_handler)
        return run_nvme_sanitize(disk_path, sanitize_action=sanitize_action)
    finally:
        if in_main_thread and original_handler is not None:
            signal.signal(signal.SIGINT, original_handler)


def run_nvme_format_with_interrupt_lock(disk_path, ses='1'):
    """Run NVMe format with interruption lock in main-thread contexts."""
    in_main_thread = threading.current_thread() is threading.main_thread()
    original_handler = None

    def locked_handler(_sig, _frame):
        logger.warning('NVMe format is running; interruption is blocked until a safe checkpoint.')

    try:
        if in_main_thread:
            original_handler = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, locked_handler)
        return run_nvme_format(disk_path, ses=ses)
    finally:
        if in_main_thread and original_handler is not None:
            signal.signal(signal.SIGINT, original_handler)
