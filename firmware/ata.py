import subprocess
import platform
import signal
import threading
from colorama import Fore, Style

from utils.system import command_exists, run_silent_command, check_output_silent

YELLOW = Fore.YELLOW
GREEN = Fore.GREEN
RESET = Style.RESET_ALL
BRIGHT = Style.BRIGHT

def check_hpa_dco(disk_path):
    """Check for HPA/DCO on a disk and attempt to remove them."""
    system = platform.system()
    has_hidden_areas = False
    messages = []

    try:
        if system == 'Linux':
            if command_exists('hdparm'):
                result = run_silent_command(['hdparm', '-N', str(disk_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if result.returncode == 0:
                    if "HPA" in result.stdout:
                        has_hidden_areas = True
                        messages.append(f"{YELLOW}HPA detected on {disk_path}{RESET}")
                        
                result = run_silent_command(['hdparm', '-I', str(disk_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if result.returncode == 0:
                    if "DCO is" in result.stdout and "not" not in result.stdout:
                        has_hidden_areas = True
                        messages.append(f"{YELLOW}DCO detected on {disk_path}{RESET}")

        elif system == 'Darwin':
            result = run_silent_command(['diskutil', 'info', str(disk_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                if "Hidden" in result.stdout:
                    has_hidden_areas = True
                    messages.append(f"{YELLOW}Hidden areas detected on {disk_path}{RESET}")

    except Exception as e:
        messages.append(f"{YELLOW}Warning: Could not check for HPA/DCO: {e}{RESET}")
        return False, messages

    return has_hidden_areas, messages

def remove_hpa_dco(disk_path):
    """Remove HPA/DCO from a disk. Returns success status and messages."""
    system = platform.system()
    success = False
    messages = []

    try:
        if system == 'Linux':
            if command_exists('hdparm'):
                result = run_silent_command(['hdparm', '--yes-i-know-what-i-am-doing', '--native-max', str(disk_path)],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if result.returncode == 0:
                    messages.append(f"{GREEN}Successfully removed HPA from {disk_path}{RESET}")
                    success = True
                else:
                    messages.append(f"{YELLOW}Failed to remove HPA: {result.stderr}{RESET}")

                result = run_silent_command(['hdparm', '--yes-i-know-what-i-am-doing', '--dco-restore', str(disk_path)],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if result.returncode == 0:
                    messages.append(f"{GREEN}Successfully removed DCO from {disk_path}{RESET}")
                    success = True
                else:
                    messages.append(f"{YELLOW}Failed to remove DCO: {result.stderr}{RESET}")

        elif system == 'Darwin':
            messages.append(f"{YELLOW}HPA/DCO removal not directly supported on macOS{RESET}")
            messages.append(f"{YELLOW}Consider using Linux-based tools for complete disk sanitization{RESET}")

    except Exception as e:
        messages.append(f"{YELLOW}Error removing HPA/DCO: {e}{RESET}")

    return success, messages

def expand_hpa_only(disk_path):
    """Expand HPA only (no DCO changes)."""
    system = platform.system()
    messages = []
    if system != 'Linux':
        messages.append(f"{YELLOW}HPA expansion is only supported on Linux/hdparm path.{RESET}")
        return False, messages

    try:
        if not command_exists('hdparm'):
            messages.append(f"{YELLOW}hdparm not found; cannot expand HPA.{RESET}")
            return False, messages

        result = run_silent_command(
            ['hdparm', '--yes-i-know-what-i-am-doing', '--native-max', str(disk_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 0:
            messages.append(f"{GREEN}HPA expansion succeeded on {disk_path}{RESET}")
            return True, messages
        messages.append(f"{YELLOW}HPA expansion failed: {result.stderr.strip()}{RESET}")
        return False, messages
    except Exception as exc:
        messages.append(f"{YELLOW}HPA expansion error: {exc}{RESET}")
        return False, messages

def restore_dco_only(disk_path):
    """Perform DCO restore (expert-only operation)."""
    system = platform.system()
    messages = []
    if system != 'Linux':
        messages.append(f"{YELLOW}DCO restore is only supported on Linux/hdparm path.{RESET}")
        return False, messages

    try:
        if not command_exists('hdparm'):
            messages.append(f"{YELLOW}hdparm not found; cannot restore DCO.{RESET}")
            return False, messages

        result = run_silent_command(
            ['hdparm', '--yes-i-know-what-i-am-doing', '--dco-restore', str(disk_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 0:
            messages.append(f"{GREEN}DCO restore succeeded on {disk_path}{RESET}")
            return True, messages
        messages.append(f"{YELLOW}DCO restore failed: {result.stderr.strip()}{RESET}")
        return False, messages
    except Exception as exc:
        messages.append(f"{YELLOW}DCO restore error: {exc}{RESET}")
        return False, messages

def secure_erase_enhanced(disk_path):
    """Attempt ATA secure erase, preferring enhanced mode when supported."""
    system = platform.system()
    messages = []
    success = False

    try:
        if system == 'Linux':
            if command_exists('hdparm'):
                identify = run_silent_command(['hdparm', '-I', str(disk_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                identify_out = (identify.stdout or '').lower()
                if 'frozen' in identify_out and 'not frozen' not in identify_out and 'not\tfrozen' not in identify_out:
                    messages.append(f"{YELLOW}Drive is in frozen state; ATA secure erase cannot proceed until power-cycle/unfreeze.{RESET}")
                    return False, messages

                secure_supported = ('security erase unit' in identify_out) or ('supported: enhanced erase' in identify_out)
                enhanced_supported = 'enhanced security erase' in identify_out
                if not secure_supported:
                    messages.append(f"{YELLOW}ATA secure erase is not reported as supported by this device.{RESET}")
                    return False, messages

                set_pass = run_silent_command(
                    ['hdparm', '--security-set-pass', 'NULL', str(disk_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if set_pass.returncode != 0:
                    messages.append(f"{YELLOW}Failed to set temporary ATA security password: {(set_pass.stderr or '').strip()}{RESET}")
                    return False, messages

                erase_cmd = ['hdparm', '--security-erase-enhanced', 'NULL', str(disk_path)] if enhanced_supported else ['hdparm', '--security-erase', 'NULL', str(disk_path)]
                erase_result = run_silent_command(erase_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if erase_result.returncode == 0:
                    if enhanced_supported:
                        messages.append(f"{GREEN}Successfully performed enhanced ATA secure erase{RESET}")
                    else:
                        messages.append(f"{GREEN}Successfully performed ATA secure erase{RESET}")
                    success = True
                else:
                    messages.append(f"{YELLOW}ATA secure erase command failed: {(erase_result.stderr or erase_result.stdout).strip()}{RESET}")
            else:
                messages.append(f"{YELLOW}hdparm not found; enhanced secure erase unavailable on this Linux host.{RESET}")
        else:
            messages.append(f"{YELLOW}Enhanced secure erase path is only supported on Linux/hdparm.{RESET}")
    except Exception as e:
        messages.append(f"{YELLOW}Error during enhanced secure erase: {e}{RESET}")

    return success, messages

def run_secure_erase_with_interrupt_lock(disk_path):
    """Run secure erase with interruption lock in main-thread contexts."""
    in_main_thread = threading.current_thread() is threading.main_thread()
    original_handler = None

    def locked_handler(_sig, _frame):
        print(f"{YELLOW}{BRIGHT}Secure erase is running; interruption is blocked until a safe checkpoint.{RESET}")

    try:
        if in_main_thread:
            original_handler = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, locked_handler)
        else:
            print(f"{YELLOW}Warning: secure-erase interruption lock unavailable outside main thread.{RESET}")
        return secure_erase_enhanced(disk_path)
    finally:
        if in_main_thread and original_handler is not None:
            signal.signal(signal.SIGINT, original_handler)

def handle_remapped_sectors(disk_path):
    """Handle remapped/reallocated sectors and defect lists."""
    system = platform.system()
    messages = []
    success = False

    try:
        if system == 'Linux':
            if command_exists('smartctl'):
                result = run_silent_command(['smartctl', '-A', str(disk_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if "Reallocated_Sector_Ct" in result.stdout:
                    messages.append(f"{YELLOW}Drive has reallocated sectors - these will be included in secure wipe{RESET}")
                
                run_silent_command(['smartctl', '-t', 'select,0-max', str(disk_path)], 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                success = True
    except Exception as e:
        messages.append(f"{YELLOW}Error handling remapped sectors: {e}{RESET}")

    return success, messages
