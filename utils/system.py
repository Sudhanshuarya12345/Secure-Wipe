import os
import sys
import platform
import subprocess

def configure_console_streams():
    """Avoid hard failures when terminal encoding cannot represent UI glyphs."""
    for stream in (sys.stdout, sys.stderr):
        try:
            if hasattr(stream, 'reconfigure'):
                stream.reconfigure(errors='replace')
        except Exception:
            continue

def is_admin():
    """Return True when current process has admin/root privileges."""
    if platform.system() == 'Windows':
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    else:
        return os.geteuid() == 0 if hasattr(os, 'geteuid') else False

def run_silent_command(args, **kwargs):
    """Run a subprocess command without showing a console window on Windows
    and ensuring no terminal interaction on Unix.
    """
    if 'stdin' not in kwargs:
        kwargs['stdin'] = subprocess.DEVNULL

    if platform.system() == 'Windows':
        # 0x08000000 is CREATE_NO_WINDOW
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | 0x08000000
    return subprocess.run(args, **kwargs)

def check_output_silent(args, **kwargs):
    """Run a subprocess check_output without showing a console window on Windows
    and ensuring no terminal interaction on Unix.
    """
    if 'stdin' not in kwargs:
        kwargs['stdin'] = subprocess.DEVNULL

    if platform.system() == 'Windows':
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | 0x08000000
    return subprocess.check_output(args, **kwargs)

def command_exists(command_name):
    """Return True when an external command exists on PATH."""
    return run_silent_command(
        ['where' if platform.system() == 'Windows' else 'which', command_name], 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE
    ).returncode == 0

def is_path_writable(path):
    """Check if the path is writable."""
    if not os.path.exists(path):
        try:
            os.makedirs(path, exist_ok=True)
        except (OSError, PermissionError):
            return False
    
    test_file = os.path.join(path, ".write_test")
    try:
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return True
    except (OSError, PermissionError):
        return False
