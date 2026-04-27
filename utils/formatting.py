import re
import time
import os
import platform
from colorama import Fore, Style
from utils.system import is_path_writable

GREEN  = Fore.GREEN
YELLOW = Fore.YELLOW
RESET  = Style.RESET_ALL

def format_size(num):
    if num is None or num == 0:
        return "Unknown"
        
    for unit in ['B','KB','MB','GB','TB']:
        if num < 1024.0:
            return f"{num:.2f}{unit}"
        num /= 1024.0
    return f"{num:.2f}PB"

def parse_size(size_str):
    """Parse a size string like '500.1 GB' into bytes."""
    if not size_str or size_str == "Unknown":
        return 0
    
    match = re.match(r'([0-9,.]+)\s*([A-Za-z]+)', size_str)
    if not match:
        try:
            return int(size_str)
        except:
            return 0
            
    value = match.group(1).replace(',', '')
    value = float(value)
    unit = match.group(2).upper()
    
    if unit == 'B':
        return int(value)
    elif unit in ('KB', 'K'):
        return int(value * 1024)
    elif unit in ('MB', 'M'):
        return int(value * 1024**2)
    elif unit in ('GB', 'G'):
        return int(value * 1024**3)
    elif unit in ('TB', 'T'):
        return int(value * 1024**4)
    elif unit in ('PB', 'P'):
        return int(value * 1024**5)
    else:
        return 0

def get_friendly_fs_type(fs_type):
    """Get a user-friendly filesystem type name."""
    fs_type = fs_type.lower() if fs_type else ""
    
    if fs_type in ["apfs", "apple", "apfs_case_sensitive"]:
        return "APFS"
    elif fs_type in ["hfs", "hfs+"]:
        return "HFS+"
    elif fs_type in ["fat32", "vfat", "fat"]:
        return "FAT32"
    elif fs_type in ["exfat"]:
        return "exFAT"
    elif fs_type in ["ntfs"]:
        return "NTFS"
    elif fs_type in ["ext2", "ext3", "ext4"]:
        return fs_type.upper()
    elif fs_type in ["xfs"]:
        return "XFS"
    elif fs_type in ["btrfs"]:
        return "Btrfs"
    elif fs_type in ["zfs"]:
        return "ZFS"
    elif fs_type in ["ufs"]:
        return "UFS"
    elif fs_type in ["tmpfs"]:
        return "tmpfs"
    elif fs_type in ["devfs"]:
        return "devfs"
    else:
        return fs_type.upper() if fs_type else "Unknown"

def format_time_human_readable(seconds, abbreviated=False):
    """
    Format time in seconds to a human-readable string.
    Examples: 
      Normal: "2 hours 15 minutes", "45 minutes 30 seconds"
      Abbreviated: "2h 15m", "45m 30s"
    """
    if seconds < 0:
        return "0s" if abbreviated else "0 seconds"
    
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    
    if abbreviated:
        if hours > 0: parts.append(f"{hours}h")
        if minutes > 0 or (hours > 0 and seconds > 0): parts.append(f"{minutes}m")
        if seconds > 0 or (not parts): parts.append(f"{seconds}s")
    else:
        if hours > 0: parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0 or (hours > 0 and seconds > 0): parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds > 0 or (not parts): parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    
    if len(parts) > 2:
        parts = parts[:2]
    
    return " ".join(parts)

def estimate_write_speed():
    """
    Estimate the write speed for the current system.
    Returns estimated bytes per second based on storage type heuristics.
    """
    system = platform.system()
    if system == 'Darwin':
        return 200 * 1024 * 1024
    elif system == 'Linux':
        return 100 * 1024 * 1024
    elif system == 'Windows':
        return 80 * 1024 * 1024
    else:
        return 50 * 1024 * 1024

def benchmark_write_speed(path, test_size=50 * 1024 * 1024):
    """Run a small write benchmark and return bytes/second, or None on failure."""
    try:
        test_file = os.path.join(path, '.Securewipe_speed_test.tmp')
        block = os.urandom(min(test_size, 4 * 1024 * 1024))
        bytes_written = 0
        start_time = time.time()

        with open(test_file, 'wb') as f:
            while bytes_written < test_size:
                remaining = test_size - bytes_written
                chunk = block if remaining >= len(block) else block[:remaining]
                f.write(chunk)
                bytes_written += len(chunk)
            f.flush()
            os.fsync(f.fileno())

        elapsed = time.time() - start_time
        if elapsed <= 0:
            return None
        return bytes_written / elapsed
    except Exception:
        return None
    finally:
        try:
            if os.path.exists(test_file):
                os.remove(test_file)
        except Exception:
            pass

def estimate_operation_time(data_size, passes=1, include_benchmark=True, path=None):
    """
    Estimate the total time for a wiping operation.
    """
    estimated_speed = estimate_write_speed()
    
    if include_benchmark and path and is_path_writable(path):
        print(f"{YELLOW}Running quick write speed test...{RESET}")
        try:
            benchmark_speed = benchmark_write_speed(path)
            if benchmark_speed:
                estimated_speed = benchmark_speed * 0.8  # 20% safety margin
                print(f"{GREEN}Benchmark complete: {format_size(int(benchmark_speed))}/s{RESET}")
            else:
                print(f"{YELLOW}Benchmark failed, using system estimates{RESET}")
        except Exception as e:
            print(f"{YELLOW}Benchmark error: {e}, using system estimates{RESET}")
    
    base_time = data_size / estimated_speed
    pass_overhead = 2
    total_time = (base_time * passes) + (pass_overhead * passes)
    
    fs_overhead = min(30, total_time * 0.1)
    total_time += fs_overhead
    
    completion_time = time.time() + total_time
    completion_str = time.strftime("%I:%M %p on %B %d", time.localtime(completion_time))
    
    return {
        'estimated_seconds': total_time,
        'estimated_human': format_time_human_readable(total_time, abbreviated=False),
        'estimated_speed': estimated_speed,
        'completion_time': completion_str,
        'data_size': data_size,
        'passes': passes
    }
