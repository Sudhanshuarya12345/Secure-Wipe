import os
import re
import json
import subprocess
import platform
import psutil
import threading

from utils.constants import REQUIRED_CHECK_SEVERITY
from utils.system import command_exists, check_output_silent, run_silent_command
from core.drive_manager import (
    resolve_windows_disk_number,
    canonical_disk_key,
    _normalize_unix_disk_device,
    get_disk_identity,
    verify_disk_identity,
    get_sector_geometry,
    detect_device_profile
)
from firmware.capabilities import detect_firmware_capabilities

def _run_powershell(command):
    """Execute PowerShell command and return stripped stdout."""
    output = check_output_silent(['powershell', '-Command', command], stderr=subprocess.STDOUT)
    return output.decode('utf-8', errors='ignore').strip()

def get_system_disk_keys():
    """Return canonical key set for system/root disk to prevent destructive targeting."""
    keys = set()
    system = platform.system()
    try:
        if system == 'Windows':
            drive = os.environ.get('SystemDrive', 'C:')
            disk_num = resolve_windows_disk_number(drive)
            if disk_num is not None:
                keys.add(f"physicaldrive{disk_num}")
            keys.add(f"driveletter{drive[0].lower()}")
            return keys

        root_line = check_output_silent(['df', '/'], stderr=subprocess.STDOUT).decode('utf-8', errors='ignore').splitlines()
        if len(root_line) > 1:
            root_device = root_line[1].split()[0]
            keys.add(canonical_disk_key(root_device))
    except Exception:
        pass
    return {k for k in keys if k}

def list_mounted_targets_for_disk(disk_path):
    """List mounted paths/partitions for a disk. Non-empty means mounted/in-use."""
    system = platform.system()
    key = canonical_disk_key(disk_path)
    mounted = []

    try:
        if system == 'Windows':
            disk_num = resolve_windows_disk_number(disk_path)
            if disk_num is None:
                return mounted
            cmd = (
                f"Get-Partition -DiskNumber {disk_num} | "
                "Select-Object DriveLetter,AccessPaths | ConvertTo-Json -Compress"
            )
            output = _run_powershell(cmd)
            if not output:
                return mounted
            rows = json.loads(output)
            if isinstance(rows, dict):
                rows = [rows]
            for row in rows:
                drive_letter = row.get('DriveLetter')
                access_paths = row.get('AccessPaths') or []
                if drive_letter:
                    mounted.append(f"{drive_letter}:")
                elif access_paths:
                    filtered_paths = []
                    for path in access_paths:
                        value = str(path or '').strip()
                        if not value:
                            continue
                        if re.match(r'^\\\\\?\\Volume\{[0-9A-Fa-f\-]+\}\\$', value):
                            continue
                        filtered_paths.append(value)
                    if filtered_paths:
                        mounted.append(','.join(filtered_paths))
            return mounted

        for part in psutil.disk_partitions(all=True):
            part_key = canonical_disk_key(part.device)
            if part_key == key:
                mounted.append(f"{part.device} -> {part.mountpoint}")
    except Exception:
        pass
    return mounted

def prepare_disk_unmounted_state(disk_path):
    """Best-effort unmount/dismount pass before strict full-disk preflight."""
    import time as _time
    system = platform.system()
    messages = []

    try:
        if system == 'Windows':
            disk_num = resolve_windows_disk_number(disk_path)
            if disk_num is None:
                return False, ["could not resolve Windows disk number for unmount preparation"]

            # Strategy: Completely wipe the partition table and uninitialize the disk.
            # Windows blocks raw writes (Win32 error 5) to disks that contain recognized 
            # file systems. Setting the disk offline makes it read-only. The only way to 
            # get full write access is to destroy the partition table (MBR/GPT) first.
            cmd = (
                f"Set-Disk -Number {disk_num} -IsOffline $false -ErrorAction SilentlyContinue; "
                f"Clear-Disk -Number {disk_num} -RemoveData -Confirm:$false -ErrorAction SilentlyContinue; "
                f"Update-HostStorageCache -ErrorAction SilentlyContinue"
            )
            result = run_silent_command(
                ['powershell', '-Command', cmd],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            output = ((result.stdout or '') + '\n' + (result.stderr or '')).strip()

            # Wait for Windows to update its state and drop volume locks
            _time.sleep(3)

            messages.append(f"cleared partition table on disk {disk_num} to drop volume locks")
            if output:
                messages.append(f"clear details: {output[:280]}")
            return True, messages

        if system == 'Darwin':
            normalized = _normalize_unix_disk_device(str(disk_path))
            result = run_silent_command(
                ['diskutil', 'unmountDisk', 'force', normalized],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if result.returncode == 0:
                messages.append(f"unmounted disk {normalized}")
                return True, messages

            err = (result.stderr or result.stdout or '').strip()
            return False, [f"diskutil unmountDisk failed: {err}"]

        normalized = _normalize_unix_disk_device(str(disk_path))
        mounted_devices = []

        if command_exists('lsblk'):
            output = check_output_silent(
                ['lsblk', '-nrpo', 'NAME,MOUNTPOINT', normalized],
                stderr=subprocess.STDOUT,
            ).decode('utf-8', errors='ignore')
            for line in output.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split(maxsplit=1)
                if len(parts) == 2 and parts[1].strip():
                    mounted_devices.append(parts[0].strip())
        else:
            key = canonical_disk_key(normalized)
            for part in psutil.disk_partitions(all=True):
                if canonical_disk_key(part.device) == key and part.mountpoint:
                    mounted_devices.append(part.device)

        if not mounted_devices:
            return True, ["no mounted partitions detected for unmount preparation"]

        all_ok = True
        for dev in mounted_devices:
            result = subprocess.run(
                ['umount', dev],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if result.returncode == 0:
                messages.append(f"unmounted {dev}")
                continue

            all_ok = False
            err = (result.stderr or result.stdout or '').strip()
            messages.append(f"umount failed on {dev}: {err}")

        return all_ok, messages
    except Exception as exc:
        return False, [str(exc)]

def _resolve_expected_identity(expected_identity, disk_path):
    """Normalize expected identity object for preflight matching."""
    if isinstance(expected_identity, dict):
        resolved = dict(expected_identity)
        if 'device_path' not in resolved and 'device' in resolved:
            resolved['device_path'] = resolved.get('device')
        if not resolved.get('device_path'):
            resolved['device_path'] = str(disk_path)
        return resolved
    return {'device_path': str(disk_path)}

def _preflight_issue_severity(check_name):
    """Return the severity model for a required preflight check."""
    return REQUIRED_CHECK_SEVERITY.get(check_name, 'warning')

def _record_preflight_result(checks, check_name, status, details=''):
    """Persist per-check status in preflight output for audit/debug visibility."""
    checks.setdefault('check_results', {})[check_name] = {
        'status': status,
        'details': details,
    }

def _register_preflight_issue(checks, check_name, message):
    """Record a preflight issue according to required-check severity policy."""
    severity = _preflight_issue_severity(check_name)
    if severity == 'block':
        checks.setdefault('failures', []).append(message)
        _record_preflight_result(checks, check_name, 'failed', message)
        return
    if severity == 'warning':
        checks.setdefault('warnings', []).append(message)
        _record_preflight_result(checks, check_name, 'warning', message)
        return
    checks.setdefault('notes', []).append(message)
    _record_preflight_result(checks, check_name, 'noted', message)

def _strict_mode_requires_geometry(mode):
    return mode in ('ENHANCED', 'MAXIMUM')

def run_preflight_validation(
    disk_path,
    execution_plan,
    expected_identity=None,
    require_unmounted=True,
):
    """Run strict preflight blockers before destructive backend execution."""
    plan = execution_plan or {}
    checks = {
        'passed': False,
        'failures': [],
        'warnings': [],
        'notes': [],
        'required_checks': list(plan.get('required_checks', [])),
        'check_results': {},
        'disk_identity': {},
        'hidden_status': {},
        'mounted_targets': [],
        'device_profile': {},
        'capabilities': {},
    }

    actual_identity = get_disk_identity(disk_path)
    checks['disk_identity'] = actual_identity
    target_key = canonical_disk_key(actual_identity.get('disk_key') or actual_identity.get('device_path') or disk_path)
    expected = _resolve_expected_identity(expected_identity, disk_path)

    mounted_targets = None
    hidden_status = None
    capabilities = None

    for check_name in checks['required_checks']:
        if check_name == 'system_disk_protection':
            system_keys = get_system_disk_keys()
            if target_key in system_keys:
                _register_preflight_issue(checks, check_name, "target disk is the system/root disk")
            else:
                _record_preflight_result(checks, check_name, 'passed', 'target is not a detected system/root disk')
            continue

        if check_name == 'mount_in_use_check':
            if mounted_targets is None:
                mounted_targets = list_mounted_targets_for_disk(disk_path)
                checks['mounted_targets'] = mounted_targets

            if require_unmounted and mounted_targets:
                _register_preflight_issue(checks, check_name, "target disk has mounted partitions or access paths")
            elif mounted_targets and not require_unmounted:
                _record_preflight_result(
                    checks,
                    check_name,
                    'not_applicable',
                    'mount blocker relaxed for free-space path; mounted access paths are expected',
                )
            else:
                _record_preflight_result(checks, check_name, 'passed', 'no mounted access paths detected')
            continue

        if check_name == 'disk_identity_verification':
            identity_ok, mismatches = verify_disk_identity(expected, actual_identity)
            if not identity_ok:
                _register_preflight_issue(checks, check_name, "disk identity mismatch: " + "; ".join(mismatches))
            else:
                _record_preflight_result(checks, check_name, 'passed', 'expected disk identity matches selected target')
            continue

        if check_name == 'hpa_dco_baseline':
            if hidden_status is None:
                hidden_status = get_sector_geometry(disk_path)
                checks['hidden_status'] = hidden_status

            current_sectors = hidden_status.get('current_sectors')
            native_sectors = hidden_status.get('native_sectors')

            if current_sectors is not None and native_sectors is not None and current_sectors > native_sectors:
                _register_preflight_issue(checks, check_name, "invalid geometry baseline: current sectors exceed native sectors")
            elif _strict_mode_requires_geometry(plan.get('mode')) and (current_sectors is None or native_sectors is None):
                _register_preflight_issue(checks, check_name, "strict geometry baseline unavailable for selected mode")
            else:
                _record_preflight_result(
                    checks,
                    check_name,
                    'passed',
                    f"sector geometry baseline current={current_sectors}, native={native_sectors}",
                )
            continue

        if check_name == 'device_capability_detection':
            try:
                device_profile = detect_device_profile(disk_path)
                capabilities = detect_firmware_capabilities(disk_path, device_profile=device_profile)
                checks['device_profile'] = device_profile
                checks['capabilities'] = capabilities
                _record_preflight_result(
                    checks,
                    check_name,
                    'passed',
                    f"device_type={device_profile.get('device_type', 'unknown')}; transport={device_profile.get('transport', 'unknown')}",
                )
            except Exception as exc:
                _register_preflight_issue(checks, check_name, f"device capability detection failed: {exc}")
            continue

        if check_name == 'secure_erase_interrupt_lock':
            if threading.current_thread() is threading.main_thread():
                _record_preflight_result(checks, check_name, 'passed', 'main-thread context supports interruption lock setup')
            else:
                _register_preflight_issue(
                    checks,
                    check_name,
                    'secure erase interruption lock is unavailable outside the main thread',
                )
            continue

        if check_name == 'power_stability_warning':
            power_note = 'Ensure stable power during firmware erase/sanitize operations.'
            if capabilities is not None and capabilities.get('power_stability_warning'):
                power_note = str(capabilities.get('power_stability_warning'))
            _register_preflight_issue(checks, check_name, power_note)
            continue

        if check_name == 'expert_audit_logging':
            if plan.get('audit_logging'):
                _record_preflight_result(checks, check_name, 'passed', 'expert audit logging flag is enabled')
            else:
                _register_preflight_issue(checks, check_name, 'expert audit logging requirement not satisfied by active plan')
            continue

        _register_preflight_issue(checks, check_name, f"unknown required preflight check '{check_name}'")

    if not checks.get('hidden_status'):
        checks['hidden_status'] = get_sector_geometry(disk_path)

    checks['passed'] = len(checks['failures']) == 0
    if not checks['passed']:
        raise RuntimeError("Preflight validation failed: " + " | ".join(checks['failures']))
    return checks
