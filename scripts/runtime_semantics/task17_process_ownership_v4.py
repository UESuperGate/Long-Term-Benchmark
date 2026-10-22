"""Verbatim reviewed controller process primitives, isolated from ArkTS imports.

Reference: tasks16_17_native_controller_v3.py
SHA256: ad7139d5eb4f23e9014da48b4b4e44388978f13ab00dfbe653ee3a2d1080cad9
Tests compare the five definitions' ASTs to that retained source. This is not a
new ownership algorithm or permission to signal a reaped leader's numeric PGID.
"""
import os
import signal
import subprocess
import time

REFERENCE_SHA256 = 'ad7139d5eb4f23e9014da48b4b4e44388978f13ab00dfbe653ee3a2d1080cad9'


class UnsafeReapedGroupError(RuntimeError):
    """A numeric PGID after leader reap no longer establishes ownership."""


def reap_nonblocking(process):
    # SIGALRM must not interrupt waitpid -> Popen.returncode assignment. Otherwise
    # a hard handler could mistake an already-reaped PID for an owned zombie.
    old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGALRM])
    try:
        try:
            process.wait(timeout=0)
        except subprocess.TimeoutExpired:
            pass
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)


def wait_leader(process, deadline):
    while process.returncode is None:
        reap_nonblocking(process)
        if process.returncode is not None:
            return
        left = deadline - time.monotonic()
        if left <= 0:
            raise subprocess.TimeoutExpired(process.args, 0)
        time.sleep(min(0.01, left))


def signal_unreaped(process):
    if process is None or process.returncode is not None:
        return False
    # No poll/wait/reap between these signals: the unreaped leader pins its PID
    # throughout both sends, including when TERM causes an immediate exit.
    errors = []
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        except OSError as error:
            # macOS may return EPERM for a disappearing/zombie-only group.
            # Still attempt both sends before any reap; never infer success.
            errors.append(dict(signal=int(sig), errno=error.errno, error=str(error)))
    return dict(attempted=True, errors=errors)


def stop_group(process, hard_deadline):
    if process is None:
        return dict(started=False, leaderReaped=True, groupGone=True)
    signaled = signal_unreaped(process)
    if signaled:
        try:
            wait_leader(process, hard_deadline)
        except subprocess.TimeoutExpired:
            pass
    query_error = None
    try:
        os.killpg(process.pid, 0)
        gone = False
    except ProcessLookupError:
        gone = True
    except OSError as error:
        gone = False
        query_error = dict(errno=error.errno, error=str(error))
    signal_errors = signaled['errors'] if signaled else []
    return dict(started=True, pid=process.pid, pgid=process.pid, leaderReaped=process.returncode is not None,
                groupGone=gone, groupSignalsSentWhileLeaderUnreaped=bool(signaled),
                groupSignalErrors=signal_errors, readonlyGroupQueryError=query_error,
                unsafeReapedGroup=bool(signal_errors or query_error or (process.returncode is not None and not gone)),
                foreignProcessesSignaled=False)
