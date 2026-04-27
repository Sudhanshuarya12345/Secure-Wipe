import os
import re
import json
import subprocess
import platform
import psutil

from utils.constants import (
    DEVICE_TYPE_HDD,
    DEVICE_TYPE_SATA_SSD,
    DEVICE_TYPE_NVME_SSD
)
from utils.formatting import format_size, get_friendly_fs_type
from utils.system import check_output_silent

def _run_powershell(command):
    """Execute PowerShell command and return stripped stdout."""
    output = check_output_silent(['powershell', '-Command', command], stderr=subprocess.STDOUT)
    return output.decode('utf-8', errors='ignore').strip()

def _normalize_unix_disk_device(device_path):
    """Normalize Linux/macOS disk names (strip partition suffix)."""
    path = str(device_path or '').strip()
    if not path:
        return path

    path = re.sub(r'p\d+$', '', path)
    path = re.sub(r'(?<!n)\d+$', '', path)
    return path

def resolve_windows_disk_number(disk_path):
    """Resolve disk number from PhysicalDrive path, numeric id, or drive letter."""
    raw = str(disk_path or '').strip()
    if not raw:
        return None

    if re.fullmatch(r'\d+', raw):
        return int(raw)

    match = re.search(r'physicaldrive\s*(\d+)', raw, re.IGNORECASE)
    if match:
        return int(match.group(1))

    if len(raw) >= 2 and raw[1] == ':':
        drive = raw[0]
        cmd = f"(Get-Partition -DriveLetter {drive} | Get-Disk).Number"
        try:
            output = _run_powershell(cmd)
            number_match = re.search(r'(\d+)', output)
            if number_match:
                return int(number_match.group(1))
        except Exception:
            return None
    return None

def resolve_disk_from_mount_path(target_path):
    """Best-effort resolve of a filesystem path/mountpoint to its backing disk."""
    raw = str(target_path or '').strip()
    if not raw:
        return None

    system = platform.system()
    if system == 'Windows':
        disk_num = resolve_windows_disk_number(raw)
        if disk_num is not None:
            return f"\\\\.\\PhysicalDrive{disk_num}"

        if len(raw) >= 2 and raw[1] == ':':
            disk_num = resolve_windows_disk_number(raw[:2])
            if disk_num is not None:
                return f"\\\\.\\PhysicalDrive{disk_num}"
        return None

    if raw.startswith('/dev/'):
        return _normalize_unix_disk_device(raw)

    try:
        output = check_output_silent(['df', raw], stderr=subprocess.STDOUT).decode('utf-8', errors='ignore')
        lines = output.strip().splitlines()
        if len(lines) > 1:
            source = lines[1].split()[0]
            if source.startswith('/dev/'):
                return _normalize_unix_disk_device(source)
    except Exception:
        return None

    return None

def canonical_disk_key(disk_path):
    """Build canonical key for cross-checking selected disk identity."""
    raw = str(disk_path or '').strip()
    if not raw:
        return ''

    system = platform.system()
    if system == 'Windows':
        match = re.search(r'physicaldrive\s*(\d+)', raw, re.IGNORECASE)
        if match:
            return f"physicaldrive{match.group(1)}"
        if re.fullmatch(r'\d+', raw):
            return f"physicaldrive{raw}"
        if len(raw) >= 2 and raw[1] == ':':
            disk_num = resolve_windows_disk_number(raw[:2])
            if disk_num is not None:
                return f"physicaldrive{disk_num}"
            return f"driveletter{raw[0].lower()}"

        resolved = resolve_disk_from_mount_path(raw)
        if resolved:
            return canonical_disk_key(resolved)
        return raw.lower()

    resolved = resolve_disk_from_mount_path(raw)
    if resolved:
        normalized = _normalize_unix_disk_device(resolved)
        return os.path.basename(normalized).lower()

    normalized = _normalize_unix_disk_device(raw)
    return os.path.basename(normalized).lower()

def get_disk_identity(disk_path):
    """Get normalized identity for strict preflight disk verification."""
    identity = {
        'device_path': str(disk_path),
        'disk_key': canonical_disk_key(disk_path),
        'model': 'Unknown',
        'size_bytes': 0,
        'size_human': 'Unknown',
    }

    system = platform.system()
    try:
        if system == 'Windows':
            disk_num = resolve_windows_disk_number(disk_path)
            if disk_num is not None:
                cmd = (
                    f"Get-Disk -Number {disk_num} | "
                    "Select-Object Number,FriendlyName,SerialNumber,Size | "
                    "ConvertTo-Json -Compress"
                )
                output = _run_powershell(cmd)
                data = json.loads(output) if output else {}
                size_bytes = int(data.get('Size', 0) or 0)
                identity.update({
                    'device_path': f"\\\\.\\PhysicalDrive{disk_num}",
                    'disk_key': f"physicaldrive{disk_num}",
                    'model': str(data.get('FriendlyName') or 'Unknown').strip() or 'Unknown',
                    'serial': str(data.get('SerialNumber') or '').strip(),
                    'size_bytes': size_bytes,
                    'size_human': format_size(size_bytes),
                })
                return identity

        if system == 'Linux':
            normalized = _normalize_unix_disk_device(str(disk_path))
            output = subprocess.check_output(['lsblk', '-bdno', 'SIZE,MODEL', normalized], stderr=subprocess.STDOUT).decode('utf-8', errors='ignore').strip()
            if output:
                parts = output.split(maxsplit=1)
                size_bytes = int(parts[0]) if parts else 0
                model = parts[1].strip() if len(parts) > 1 else 'Unknown'
                identity.update({
                    'device_path': normalized,
                    'disk_key': canonical_disk_key(normalized),
                    'model': model,
                    'size_bytes': size_bytes,
                    'size_human': format_size(size_bytes),
                })
                return identity

        if system == 'Darwin':
            disk_id = os.path.basename(_normalize_unix_disk_device(str(disk_path)))
            info = subprocess.check_output(['diskutil', 'info', disk_id], stderr=subprocess.STDOUT).decode('utf-8', errors='ignore')
            size_match = re.search(r'Disk Size:\s+([0-9,]+)\s+Bytes', info)
            name_match = re.search(r'Device / Media Name:\s+(.+)', info)
            size_bytes = int(size_match.group(1).replace(',', '')) if size_match else 0
            model = name_match.group(1).strip() if name_match else 'Unknown'
            identity.update({
                'device_path': f"/dev/{disk_id}",
                'disk_key': canonical_disk_key(disk_id),
                'model': model,
                'size_bytes': size_bytes,
                'size_human': format_size(size_bytes),
            })
            return identity
    except Exception:
        pass

    return identity

def verify_disk_identity(expected, actual):
    """Compare expected vs actual disk identity and return (ok, mismatches).
    
    Args:
        expected: Dict with expected identity fields (e.g. from UI selection).
        actual: Dict from get_disk_identity().
    
    Returns:
        Tuple of (bool, list[str]) — True if identities match, list of mismatch descriptions.
    """
    mismatches = []
    expected = expected or {}
    actual = actual or {}

    # Compare disk_key if available
    expected_key = (expected.get('disk_key') or '').strip().lower()
    actual_key = (actual.get('disk_key') or '').strip().lower()
    if expected_key and actual_key and expected_key != actual_key:
        mismatches.append(f"disk_key mismatch: expected={expected_key}, actual={actual_key}")

    # Compare model if specified
    expected_model = (expected.get('model') or '').strip().lower()
    actual_model = (actual.get('model') or '').strip().lower()
    if expected_model and expected_model != 'unknown' and actual_model and actual_model != 'unknown':
        if expected_model != actual_model:
            mismatches.append(f"model mismatch: expected={expected_model}, actual={actual_model}")

    # Compare serial if specified
    expected_serial = (expected.get('serial') or '').strip().lower()
    actual_serial = (actual.get('serial') or '').strip().lower()
    if expected_serial and actual_serial and expected_serial != actual_serial:
        mismatches.append(f"serial mismatch: expected={expected_serial}, actual={actual_serial}")

    # Compare size if both are known and differ significantly (>1%)
    expected_size = int(expected.get('size_bytes', 0) or 0)
    actual_size = int(actual.get('size_bytes', 0) or 0)
    if expected_size > 0 and actual_size > 0:
        diff_pct = abs(expected_size - actual_size) / max(expected_size, actual_size)
        if diff_pct > 0.01:
            mismatches.append(
                f"size mismatch: expected={expected_size} bytes, actual={actual_size} bytes"
            )

    return len(mismatches) == 0, mismatches


def detect_device_profile(disk_path):
    """Detect device class and transport for strategy selection."""
    identity = get_disk_identity(disk_path)
    profile = {
        'device_path': str(identity.get('device_path') or disk_path),
        'disk_key': canonical_disk_key(identity.get('device_path') or disk_path),
        'model': identity.get('model') or 'Unknown',
        'size_bytes': int(identity.get('size_bytes', 0) or 0),
        'size_human': identity.get('size_human') or format_size(int(identity.get('size_bytes', 0) or 0)),
        'transport': 'unknown',
        'is_rotational': None,
        'device_name': os.path.basename(_normalize_unix_disk_device(str(disk_path))),
        'device_type': DEVICE_TYPE_SATA_SSD,
        'source': 'inference',
    }

    system = platform.system()
    try:
        if system == 'Linux':
            normalized = _normalize_unix_disk_device(str(disk_path))
            output = check_output_silent(
                ['lsblk', '-J', '-d', '-o', 'NAME,ROTA,TRAN,TYPE,MODEL,SIZE', normalized],
                stderr=subprocess.STDOUT,
            ).decode('utf-8', errors='ignore')
            payload = json.loads(output) if output else {}
            rows = payload.get('blockdevices') or []
            if rows:
                row = rows[0]
                rota_raw = str(row.get('rota')).strip().lower()
                is_rotational = rota_raw in ('1', 'true', 'yes')
                transport = str(row.get('tran') or '').strip().lower()
                model = str(row.get('model') or profile['model']).strip() or profile['model']
                device_name = str(row.get('name') or profile['device_name']).strip()
                profile.update({
                    'transport': transport or 'unknown',
                    'is_rotational': is_rotational,
                    'model': model,
                    'device_name': device_name,
                    'source': 'lsblk',
                })

        elif system == 'Windows':
            disk_num = resolve_windows_disk_number(disk_path)
            if disk_num is not None:
                disk_out = _run_powershell(
                    f"Get-Disk -Number {disk_num} | "
                    "Select-Object Number,BusType,FriendlyName,Size | ConvertTo-Json -Compress"
                )
                disk_data = json.loads(disk_out) if disk_out else {}
                if isinstance(disk_data, list):
                    disk_data = disk_data[0] if disk_data else {}
                transport = str(disk_data.get('BusType') or '').strip().lower()
                model = str(disk_data.get('FriendlyName') or profile['model']).strip() or profile['model']

                media_out = _run_powershell(
                    f"Get-PhysicalDisk | Where-Object {{$_.DeviceId -eq {disk_num}}} | "
                    "Select-Object DeviceId,MediaType,BusType,FriendlyName | ConvertTo-Json -Compress"
                )
                media_data = json.loads(media_out) if media_out else {}
                if isinstance(media_data, list):
                    media_data = media_data[0] if media_data else {}
                media_type = str(media_data.get('MediaType') or '').strip().lower()
                if media_type in ('hdd', 'hard disk drive', 'unspecified hdd'):
                    is_rotational = True
                elif media_type in ('ssd', 'solid state drive', 'scm'):
                    is_rotational = False
                else:
                    is_rotational = None

                profile.update({
                    'transport': transport or str(media_data.get('BusType') or '').strip().lower() or 'unknown',
                    'is_rotational': is_rotational,
                    'model': model,
                    'source': 'Get-Disk/Get-PhysicalDisk',
                })

        elif system == 'Darwin':
            disk_id = os.path.basename(_normalize_unix_disk_device(str(disk_path)))
            info = check_output_silent(['diskutil', 'info', disk_id], stderr=subprocess.STDOUT).decode('utf-8', errors='ignore')
            protocol_match = re.search(r'Protocol:\s+(.+)', info)
            solid_state_match = re.search(r'Solid\s+State:\s+(Yes|No)', info, re.IGNORECASE)
            protocol = protocol_match.group(1).strip().lower() if protocol_match else 'unknown'
            is_rotational = None
            if solid_state_match:
                is_rotational = solid_state_match.group(1).strip().lower() != 'yes'

            profile.update({
                'transport': protocol,
                'is_rotational': is_rotational,
                'source': 'diskutil info',
            })
    except Exception:
        pass

    device_name = profile['device_name'].lower()
    transport = profile['transport'].lower()
    model = profile['model'].lower()

    if 'nvme' in transport or device_name.startswith('nvme') or 'nvme' in model:
        profile['device_type'] = DEVICE_TYPE_NVME_SSD
    elif profile['is_rotational'] is True:
        profile['device_type'] = DEVICE_TYPE_HDD
    else:
        profile['device_type'] = DEVICE_TYPE_SATA_SSD

    return profile

def get_sector_geometry(disk_path):
    """Get strict sector geometry baseline for HPA/DCO analysis."""
    geometry = {
        'current_sectors': None,
        'native_sectors': None,
        'hpa_present': False,
        'dco_restricted': False,
        'source': 'unknown',
        'errors': [],
    }
    system = platform.system()

    try:
        if system == 'Linux':
            output = check_output_silent(['hdparm', '-N', str(disk_path)], stderr=subprocess.STDOUT).decode('utf-8', errors='ignore')
            match = re.search(r'\b(\d+)\s*/\s*(\d+)\b', output)
            if match:
                current = int(match.group(1))
                native = int(match.group(2))
                geometry.update({
                    'current_sectors': current,
                    'native_sectors': native,
                    'hpa_present': current != native,
                    'source': 'hdparm -N',
                })

            try:
                dco_out = check_output_silent(['hdparm', '--dco-identify', str(disk_path)], stderr=subprocess.STDOUT).decode('utf-8', errors='ignore')
                real_match = re.search(r'Real\s+max\s+sectors\s*[:=]\s*(\d+)', dco_out, re.IGNORECASE)
                cur_match = re.search(r'Current\s+max\s+sectors\s*[:=]\s*(\d+)', dco_out, re.IGNORECASE)
                if real_match and cur_match:
                    real_val = int(real_match.group(1))
                    cur_val = int(cur_match.group(1))
                    geometry['dco_restricted'] = cur_val < real_val
            except Exception:
                pass

            return geometry

        identity = get_disk_identity(disk_path)
        size_bytes = int(identity.get('size_bytes', 0) or 0)
        if size_bytes > 0:
            sectors = size_bytes // 512
            geometry.update({
                'current_sectors': sectors,
                'native_sectors': sectors,
                'hpa_present': False,
                'source': 'size-inference',
            })
    except Exception as exc:
        geometry['errors'].append(str(exc))

    return geometry

def collect_hidden_region_status(disk_path):
    """Public helper for UI/preview to display hidden-region detection state."""
    geometry = get_sector_geometry(disk_path)
    return {
        'hpa_present': bool(geometry.get('hpa_present')),
        'dco_restricted': bool(geometry.get('dco_restricted')),
        'current_sectors': geometry.get('current_sectors'),
        'native_sectors': geometry.get('native_sectors'),
        'source': geometry.get('source'),
    }

def get_macos_disk_info():
    """Get detailed disk information for macOS systems."""
    try:
        disks_output = subprocess.check_output(['diskutil', 'list'], stderr=subprocess.STDOUT).decode('utf-8')
        physical_disks = []
        
        for line in disks_output.split('\n'):
            if line.startswith('/dev/disk'):
                disk_id = line.split()[0].replace('/dev/', '')
                if disk_id not in physical_disks and not any(c.isdigit() and c != disk_id[-1] for c in disk_id):
                    physical_disks.append(disk_id)
        
        disk_info = {}
        
        for disk_id in physical_disks:
            try:
                disk_info[disk_id] = {}
                info = subprocess.check_output(['diskutil', 'info', disk_id], stderr=subprocess.STDOUT).decode('utf-8')
                
                name_match = re.search(r'Device / Media Name:\s+(.+)', info)
                if name_match:
                    disk_info[disk_id]['name'] = name_match.group(1).strip()
                else:
                    disk_info[disk_id]['name'] = f"Disk {disk_id}"
                
                size_bytes = 0
                size_human = "Unknown"
                
                for part in psutil.disk_partitions(all=True):
                    if disk_id in part.device:
                        try:
                            usage = psutil.disk_usage(part.mountpoint)
                            if usage.total > size_bytes:
                                size_bytes = usage.total
                                size_human = format_size(usage.total)
                        except:
                            pass
                
                if size_bytes == 0:
                    size_match = re.search(r'Disk Size:\s+([0-9,]+)\s+Bytes\s+\(([^)]+)\)', info)
                    if size_match:
                        size_bytes = int(size_match.group(1).replace(',', ''))
                        size_human = size_match.group(2).strip()
                
                disk_info[disk_id]['size'] = size_bytes
                disk_info[disk_id]['size_human'] = size_human
                
                volumes = []
                for part in psutil.disk_partitions(all=True):
                    if disk_id in part.device:
                        vol_info = {
                            'device': part.device,
                            'mountpoint': part.mountpoint,
                            'fstype': part.fstype
                        }
                        try:
                            usage = psutil.disk_usage(part.mountpoint)
                            vol_info['total'] = usage.total
                            vol_info['free'] = usage.free
                        except:
                            vol_info['total'] = 0
                            vol_info['free'] = 0
                        volumes.append(vol_info)
                
                best_vol = None
                for vol in volumes:
                    if not best_vol:
                        best_vol = vol
                    elif vol['mountpoint'] == '/':
                        best_vol = vol
                    elif '/System/Volumes/Data' in vol['mountpoint'] and best_vol['mountpoint'] != '/':
                        best_vol = vol
                
                if best_vol:
                    disk_info[disk_id]['mountpoint'] = best_vol['mountpoint']
                    disk_info[disk_id]['fstype'] = get_friendly_fs_type(best_vol['fstype'])
                    disk_info[disk_id]['free'] = best_vol['free']
                else:
                    disk_info[disk_id]['mountpoint'] = None
                    disk_info[disk_id]['fstype'] = "Unknown"
                    disk_info[disk_id]['free'] = 0
                    
            except Exception as e:
                continue
        
        return disk_info
    except Exception as e:
        return {}

def is_virtual_filesystem(fstype, device, mountpoint):
    """Check if a filesystem is virtual/system and should be excluded."""
    fstype_lower = fstype.lower() if fstype else ""
    device_lower = device.lower() if device else ""
    mountpoint_lower = mountpoint.lower() if mountpoint else ""
    
    virtual_fs_types = {
        'sysfs', 'proc', 'devtmpfs', 'devpts', 'tmpfs', 'securityfs',
        'cgroup', 'cgroup2', 'pstore', 'bpf', 'configfs', 'debugfs',
        'tracefs', 'fusectl', 'binfmt_misc', 'mqueue', 'hugetlbfs',
        'autofs', 'rpc_pipefs', 'nfsd', 'sunrpc', 'overlay'
    }
    
    fuse_virtual = {
        'fuse.gvfsd-fuse', 'fuse.portal', 'fuse.gvfs-fuse-daemon',
        'fuse.snapfuse', 'fuse.lxcfs', 'fuse.dbus'
    }
    
    if fstype_lower in virtual_fs_types or any(fuse in fstype_lower for fuse in fuse_virtual):
        return True
    
    virtual_devices = {
        'none', 'udev', 'tmpfs', 'sysfs', 'proc', 'devpts',
        'securityfs', 'debugfs', 'configfs', 'fusectl', 'binfmt_misc',
        'gvfsd-fuse', 'portal', 'overlay'
    }
    
    if device_lower in virtual_devices:
        return True
    
    system_mounts = {
        '/sys', '/proc', '/dev', '/run', '/tmp', '/var/run',
        '/sys/kernel', '/proc/sys', '/dev/pts', '/dev/shm',
        '/run/user', '/snap'
    }
    
    for sys_mount in system_mounts:
        if mountpoint_lower.startswith(sys_mount):
            return True
            
    return False

def _get_windows_physical_drives():
    """Enumerate ALL physical disks on Windows via Get-Disk (same source as Disk Management).
    
    This catches disks that psutil misses:
    - Disks with no drive letter assigned
    - Raw/uninitialized disks
    - Offline disks
    - Disks with no partitions
    """
    physical_drives = []
    seen_disk_nums = set()

    try:
        # Step 1: Get ALL physical disks via Get-Disk (mirrors Disk Management)
        cmd = (
            "Get-Disk | Select-Object Number,FriendlyName,Size,OperationalStatus,"
            "PartitionStyle,BusType | ConvertTo-Json -Compress"
        )
        output = _run_powershell(cmd)
        if not output:
            return physical_drives

        disks = json.loads(output)
        if isinstance(disks, dict):
            disks = [disks]

        # Step 2: For each disk, get partition/volume info for mount and free space
        for disk in disks:
            disk_num = disk.get('Number')
            if disk_num is None:
                continue
            if disk_num in seen_disk_nums:
                continue
            seen_disk_nums.add(disk_num)

            name = str(disk.get('FriendlyName') or f'Disk {disk_num}').strip()
            size_bytes = int(disk.get('Size', 0) or 0)
            status = str(disk.get('OperationalStatus') or 'Unknown').strip()
            part_style = str(disk.get('PartitionStyle') or 'Unknown').strip()
            bus_type = str(disk.get('BusType') or 'Unknown').strip()

            # Build the device path
            device_path = f"\\\\.\\PhysicalDrive{disk_num}"

            # Get partition info (drive letters, mount points, free space)
            mount_point = 'Not mounted'
            fstype = 'Unknown'
            free_bytes = 0

            try:
                part_cmd = (
                    f"Get-Partition -DiskNumber {disk_num} -ErrorAction SilentlyContinue | "
                    "Select-Object DriveLetter,Size,Type | ConvertTo-Json -Compress"
                )
                part_output = _run_powershell(part_cmd)
                if part_output:
                    parts = json.loads(part_output)
                    if isinstance(parts, dict):
                        parts = [parts]

                    for p in parts:
                        dl = p.get('DriveLetter')
                        if dl and str(dl).strip() and str(dl).strip() != '\x00':
                            drive_letter = str(dl).strip()
                            mount_point = f"{drive_letter}:\\"
                            # Get volume info for this drive letter
                            try:
                                usage = psutil.disk_usage(mount_point)
                                free_bytes = usage.free
                            except Exception:
                                pass
                            # Get filesystem type
                            try:
                                vol_cmd = (
                                    f"Get-Volume -DriveLetter '{drive_letter}' -ErrorAction SilentlyContinue | "
                                    "Select-Object FileSystemType | ConvertTo-Json -Compress"
                                )
                                vol_output = _run_powershell(vol_cmd)
                                if vol_output:
                                    vol_data = json.loads(vol_output)
                                    if isinstance(vol_data, list):
                                        vol_data = vol_data[0] if vol_data else {}
                                    fs = str(vol_data.get('FileSystemType') or '').strip()
                                    if fs:
                                        fstype = get_friendly_fs_type(fs)
                            except Exception:
                                pass
                            break  # Use first drive letter found
            except Exception:
                pass

            # Determine display status
            if status.lower() == 'offline':
                display_status = 'Offline'
            elif part_style.lower() == 'raw':
                display_status = 'Raw (No Partitions)'
            elif mount_point == 'Not mounted':
                display_status = 'No Drive Letter'
            else:
                display_status = 'Online'

            physical_drives.append({
                'id': len(physical_drives),
                'device': device_path,
                'name': name,
                'mountpoint': mount_point,
                'fstype': fstype,
                'size': size_bytes,
                'size_human': format_size(size_bytes),
                'free': free_bytes,
                'status': display_status,
                'bus_type': bus_type,
                'disk_number': disk_num,
            })

    except Exception:
        pass

    return physical_drives


def _get_linux_physical_drives():
    """Enumerate physical drives on Linux via lsblk, falling back to psutil."""
    physical_drives = []
    seen_devices = set()

    try:
        # Use lsblk to get all block devices (catches disks without mounts)
        output = check_output_silent(
            ['lsblk', '-J', '-d', '-b', '-o', 'NAME,SIZE,TYPE,MODEL,MOUNTPOINT,FSTYPE,TRAN'],
            stderr=subprocess.STDOUT,
        ).decode('utf-8', errors='ignore')

        payload = json.loads(output) if output else {}
        for dev in payload.get('blockdevices', []):
            dev_type = str(dev.get('type') or '').strip().lower()
            if dev_type not in ('disk',):
                continue

            dev_name = str(dev.get('name') or '').strip()
            if not dev_name:
                continue

            device_path = f"/dev/{dev_name}"
            if device_path in seen_devices:
                continue
            seen_devices.add(device_path)

            size_bytes = int(dev.get('size', 0) or 0)
            if size_bytes < 1024 * 1024:
                continue

            model = str(dev.get('model') or f'Disk {dev_name}').strip()
            mountpoint = str(dev.get('mountpoint') or '').strip() or 'Not mounted'
            fstype = get_friendly_fs_type(str(dev.get('fstype') or '').strip()) or 'Unknown'

            # Get free space if mounted
            free_bytes = 0
            if mountpoint != 'Not mounted':
                try:
                    usage = psutil.disk_usage(mountpoint)
                    free_bytes = usage.free
                except Exception:
                    pass

            physical_drives.append({
                'id': len(physical_drives),
                'device': device_path,
                'name': model,
                'mountpoint': mountpoint,
                'fstype': fstype,
                'size': size_bytes,
                'size_human': format_size(size_bytes),
                'free': free_bytes,
            })
    except Exception:
        # Fallback: use psutil
        for part in psutil.disk_partitions(all=True):
            try:
                if is_virtual_filesystem(part.fstype, part.device, part.mountpoint):
                    continue
                base_device = _normalize_unix_disk_device(part.device)
                if base_device in seen_devices:
                    continue
                seen_devices.add(base_device)
                usage = psutil.disk_usage(part.mountpoint)
                if usage.total < 1024 * 1024:
                    continue
                physical_drives.append({
                    'id': len(physical_drives),
                    'device': base_device,
                    'name': f"Disk {len(physical_drives)}",
                    'mountpoint': part.mountpoint,
                    'fstype': get_friendly_fs_type(part.fstype),
                    'size': usage.total,
                    'size_human': format_size(usage.total),
                    'free': usage.free,
                })
            except Exception:
                continue

    return physical_drives


def get_physical_drives():
    """Get list of unique physical drives.
    
    On Windows, uses Get-Disk (same source as Disk Management) to enumerate 
    ALL physical disks including those without drive letters, raw/uninitialized
    disks, and offline disks. On Linux, uses lsblk. On macOS, uses diskutil.
    Falls back to psutil.disk_partitions() when platform-specific tools fail.
    """
    system = platform.system()

    if system == 'Windows':
        drives = _get_windows_physical_drives()
        if drives:
            return drives

    elif system == 'Linux':
        drives = _get_linux_physical_drives()
        if drives:
            return drives

    elif system == 'Darwin':
        disk_info = get_macos_disk_info()
        physical_drives = []
        for disk_id, info in disk_info.items():
            physical_drives.append({
                'id': len(physical_drives),
                'device': f"/dev/{disk_id}",
                'name': info.get('name', f"Disk {disk_id}"),
                'mountpoint': info.get('mountpoint') or 'Not mounted',
                'fstype': info.get('fstype', 'Unknown'),
                'size': info.get('size', 0),
                'size_human': info.get('size_human', 'Unknown'),
                'free': info.get('free', 0)
            })
        if physical_drives:
            return physical_drives

    # Ultimate fallback: psutil only
    physical_drives = []
    try:
        for part in psutil.disk_partitions(all=True):
            try:
                if is_virtual_filesystem(part.fstype, part.device, part.mountpoint):
                    continue
                usage = psutil.disk_usage(part.mountpoint)
                if usage.total < 1024 * 1024:
                    continue
                physical_drives.append({
                    'id': len(physical_drives),
                    'device': part.device,
                    'name': f"Drive {len(physical_drives)}",
                    'mountpoint': part.mountpoint,
                    'fstype': get_friendly_fs_type(part.fstype),
                    'size': usage.total,
                    'size_human': format_size(usage.total),
                    'free': usage.free,
                })
            except Exception:
                continue
    except Exception:
        pass

    return physical_drives
