import os
import re
import time
import tempfile
import subprocess
import platform
import psutil

from utils.system import check_output_silent
from core.drive_manager import (
    resolve_windows_disk_number,
    canonical_disk_key,
    _normalize_unix_disk_device,
    get_sector_geometry
)

def _run_powershell(command):
    """Execute PowerShell command and return stripped stdout."""
    output = check_output_silent(['powershell', '-Command', command], stderr=subprocess.STDOUT)
    return output.decode('utf-8', errors='ignore').strip()

def evaluate_final_status(report):
    """Compute SAFE/SAFE_WITH_WARNINGS/UNSAFE from verification outcomes."""
    if report.get('final_sector_check') != 'PASS' or report.get('reusability_test') != 'PASS':
        return 'UNSAFE'
    if report.get('warnings'):
        return 'SAFE_WITH_WARNINGS'
    return 'SAFE'

def add_report_step(report, operation_name, status, before=None, after=None, details=None):
    """Append operation step state to audit report."""
    step = {
        'operation_name': operation_name,
        'status': status,
        'before': before,
        'after': after,
        'details': details,
    }
    report.setdefault('operations_executed', []).append(step)

def run_reusability_test(disk_path):
    """Mandatory reusability validation: partition, filesystem, and mount usability."""
    system = platform.system()
    details = []

    try:
        if system == 'Windows':
            disk_num = resolve_windows_disk_number(disk_path)
            if disk_num is None:
                return False, ["could not resolve disk number"]

            part_count = 0
            part_count_out = ''
            for _ in range(20):
                part_count_out = _run_powershell(
                    f"(Get-Partition -DiskNumber {disk_num} | Measure-Object).Count"
                )
                part_count_match = re.search(r'(\d+)', part_count_out)
                part_count = int(part_count_match.group(1)) if part_count_match else 0
                if part_count > 0:
                    break
                time.sleep(1)

            if part_count <= 0:
                return False, ["partition creation check failed (no partition became visible)"]
            details.append(f"partition_count={part_count}")

            drive = None
            drive_out = ''
            for _ in range(20):
                drive_out = _run_powershell(
                    f"(Get-Partition -DiskNumber {disk_num} | Where-Object {{$_.DriveLetter}} | "
                    "Select-Object -First 1 -ExpandProperty DriveLetter)"
                )
                drive_match = re.search(r'([A-Za-z])', drive_out)
                if drive_match:
                    drive = drive_match.group(1).upper()
                    break
                time.sleep(1)

            if not drive:
                return False, ["mount/drive-letter check failed (no drive letter became available)"]
            root = f"{drive}:\\"

            probe_file = os.path.join(root, '.securewipe_reuse_probe.tmp')
            probe_ok = False
            probe_error = None
            for _ in range(5):
                try:
                    with open(probe_file, 'w', encoding='utf-8') as f:
                        f.write('securewipe-reuse-probe')
                    os.remove(probe_file)
                    probe_ok = True
                    break
                except Exception as exc:
                    probe_error = str(exc)
                    time.sleep(1)

            if not probe_ok:
                return False, [f"mount write-probe failed on {root}: {probe_error}"]

            details.append(f"mount_probe={root}")
            return True, details

        if system == 'Linux':
            normalized = _normalize_unix_disk_device(str(disk_path))
            output = subprocess.check_output(['lsblk', '-nrpo', 'NAME,FSTYPE,MOUNTPOINT', normalized], stderr=subprocess.STDOUT).decode('utf-8', errors='ignore').strip()
            if not output:
                return False, ["lsblk returned no partition info"]

            partition_rows = []
            for line in output.splitlines():
                parts = [p for p in line.split(' ') if p != '']
                if not parts:
                    continue
                name = parts[0]
                if name == normalized:
                    continue
                fstype = parts[1] if len(parts) > 1 else ''
                mountpoint = parts[2] if len(parts) > 2 else ''
                partition_rows.append((name, fstype, mountpoint))

            if not partition_rows:
                return False, ["partition creation check failed"]

            partition, fstype, mountpoint = partition_rows[0]
            if not fstype:
                return False, ["filesystem check failed"]
            details.append(f"filesystem={fstype}")

            mounted_here = False
            temp_mount = None
            mount_target = mountpoint
            if not mount_target:
                temp_mount = tempfile.mkdtemp(prefix='securewipe_mount_')
                mount_result = subprocess.run(['mount', partition, temp_mount], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if mount_result.returncode != 0:
                    try:
                        os.rmdir(temp_mount)
                    except Exception:
                        pass
                    return False, [f"mount check failed: {mount_result.stderr.strip()}"]
                mounted_here = True
                mount_target = temp_mount

            probe_file = os.path.join(mount_target, '.securewipe_reuse_probe.tmp')
            with open(probe_file, 'w', encoding='utf-8') as f:
                f.write('securewipe-reuse-probe')
            os.remove(probe_file)
            details.append(f"mount_probe={mount_target}")

            if mounted_here and temp_mount:
                subprocess.run(['umount', temp_mount], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    os.rmdir(temp_mount)
                except Exception:
                    pass
            return True, details

        disk_key = canonical_disk_key(disk_path)
        candidates = [p for p in psutil.disk_partitions(all=True) if canonical_disk_key(p.device) == disk_key]
        if not candidates:
            return False, ["partition/mount check failed"]
        mountpoint = candidates[0].mountpoint
        probe_file = os.path.join(mountpoint, '.securewipe_reuse_probe.tmp')
        with open(probe_file, 'w', encoding='utf-8') as f:
            f.write('securewipe-reuse-probe')
        os.remove(probe_file)
        details.append(f"mount_probe={mountpoint}")
        return True, details
    except Exception as exc:
        return False, [str(exc)]

def run_postflight_validation(disk_path, execution_plan, report, require_hpa_clear=False):
    """Run strict postflight checks and update structured report state."""
    plan = execution_plan or {}
    geometry = get_sector_geometry(disk_path)
    current_sectors = geometry.get('current_sectors')
    native_sectors = geometry.get('native_sectors')

    if current_sectors is not None and native_sectors is not None and current_sectors == native_sectors:
        report['final_sector_check'] = 'PASS'
    else:
        report['final_sector_check'] = 'FAIL'
        report.setdefault('warnings', []).append('final sector geometry validation failed')
    add_report_step(
        report,
        'postflight_geometry_validation',
        'success' if report['final_sector_check'] == 'PASS' else 'failed',
        after={
            'current_sectors': current_sectors,
            'native_sectors': native_sectors,
            'hpa_present': geometry.get('hpa_present'),
            'dco_restricted': geometry.get('dco_restricted'),
        },
    )

    hpa_present = bool(geometry.get('hpa_present'))
    dco_present = bool(geometry.get('dco_restricted'))
    report['hpa_detected'] = report.get('hpa_detected', False) or hpa_present
    report['hpa_status'] = 'present' if hpa_present else 'not_detected'
    report['dco_status'] = 'restricted' if dco_present else 'not_restricted'

    if require_hpa_clear and hpa_present:
        report.setdefault('warnings', []).append('HPA still detected after wipe')
        report['final_sector_check'] = 'FAIL'

    if plan.get('mode') != 'MAXIMUM' and dco_present:
        report.setdefault('warnings', []).append('DCO restriction still present; DCO modification is blocked by mode policy')

    reusable, reuse_details = run_reusability_test(disk_path)
    report['reusability_test'] = 'PASS' if reusable else 'FAIL'
    report['reusability_status'] = 'REUSABLE' if reusable else 'NOT_REUSABLE'
    if not reusable:
        report.setdefault('warnings', []).append('reusability test failed: ' + '; '.join(reuse_details))
    add_report_step(
        report,
        'postflight_reusability_test',
        'success' if reusable else 'failed',
        details='; '.join(reuse_details),
    )

    report['final_status'] = evaluate_final_status(report)
    return report
