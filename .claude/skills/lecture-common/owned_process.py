"""Bounded Windows cleanup for a Popen handle owned by the current task."""
import os
import subprocess

def terminate_owned_process(process: subprocess.Popen, *, timeout=10):
    """Never kill by image name, port, a stale PID file, or an unrelated process.

    The caller must retain the original Popen handle. On Windows taskkill /T
    terminates that still-live process and its descendants, including cmd wrappers.
    This does not claim to capture processes detached before the parent exited.
    """
    if process.poll() is not None:
        return {'action': 'already_exited', 'exit_code': process.returncode}
    if os.name != 'nt':
        raise RuntimeError('Process-tree cleanup is implemented for Windows only')
    result = subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                            capture_output=True, timeout=timeout)
    if result.returncode != 0 and process.poll() is None:
        raise RuntimeError(f'Owned process cleanup failed: taskkill exit {result.returncode}')
    process.wait(timeout=timeout)
    return {'action': 'terminated_owned_tree', 'pid': process.pid,
            'taskkill_exit_code': result.returncode, 'exit_code': process.returncode}
