import os
import uuid
import tempfile
import subprocess
import platform

from utils.system import is_admin, run_silent_command

def _run_windows_diskpart(script_file):
    """Run diskpart script, auto-requesting elevation when needed."""
    if platform.system() != 'Windows':
        return run_silent_command(['diskpart', '/s', script_file], capture_output=True, text=True)

    if is_admin():
        return run_silent_command(['diskpart', '/s', script_file], capture_output=True, text=True)

    output_file = os.path.join(tempfile.gettempdir(), f"diskpart_output_{uuid.uuid4().hex}.log")
    launcher_script = os.path.join(tempfile.gettempdir(), f"diskpart_elevated_{uuid.uuid4().hex}.ps1")

    script_file_single_escaped = script_file.replace("'", "''")
    output_file_single_escaped = output_file.replace("'", "''")

    try:
        with open(launcher_script, 'w', encoding='utf-8') as f:
            f.write("$ErrorActionPreference = 'Stop'\n")
            f.write(
                f"$cmd = 'diskpart.exe /s \"{script_file_single_escaped}\" > \"{output_file_single_escaped}\" 2>&1'\n"
            )
            f.write("cmd.exe /c $cmd\n")
            f.write("exit $LASTEXITCODE\n")

        launcher_script_ps = launcher_script.replace("'", "''")
        launch_cmd = (
            "$ErrorActionPreference='Stop'; "
            "$p = Start-Process -FilePath 'powershell.exe' -Verb RunAs "
            f"-ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','{launcher_script_ps}') "
            "-WindowStyle Hidden "
            "-PassThru -Wait; "
            "exit $p.ExitCode"
        )

        elevation = run_silent_command(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', launch_cmd],
            capture_output=True,
            text=True,
        )

        diskpart_output = ''
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8', errors='ignore') as f:
                diskpart_output = f.read()

        if elevation.returncode != 0:
            stderr_text = (elevation.stderr or elevation.stdout or '').strip()
            if 'canceled' in stderr_text.lower() or 'cancelled' in stderr_text.lower():
                raise RuntimeError('diskpart elevation was canceled by the user.')
            detail = diskpart_output.strip() or stderr_text or f'exit code {elevation.returncode}'
            raise RuntimeError(f'diskpart failed (elevated): {detail}')

        return subprocess.CompletedProcess(
            args=['diskpart', '/s', script_file],
            returncode=0,
            stdout=diskpart_output,
            stderr='',
        )
    finally:
        for temp_path in (launcher_script, output_file):
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass


def build_windows_diskpart_commands(disk_num, fs_format, label=None):
    """Build resilient diskpart command sequence for removable media formatting."""
    commands = [
        f"select disk {disk_num}",
        "online disk noerr",
        "attributes disk clear readonly",
        "clean",
        "create partition primary",
    ]

    format_cmd = f"format fs={fs_format} quick"
    if label:
        format_cmd += f" label=\"{label}\""
    commands.append(format_cmd)
    commands.extend([
        "assign",
        "exit",
    ])
    return commands


def is_windows_diskpart_lock_error(error_text):
    """Return True when error text matches known transient Windows diskpart lock/state failures."""
    error_low = str(error_text or '').lower()
    lock_signatures = (
        'access is denied',
        'device is not ready',
        'there is no volume selected',
        'virtual disk service error',
        'diskpart has encountered an error',
    )
    return any(signature in error_low for signature in lock_signatures)
