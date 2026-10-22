"""Task13-only, explicitly owned main-thread deadline including finalization."""
from __future__ import annotations

import math
import signal
import threading
import time


class WorkDeadlineExpired(TimeoutError):
    pass


class HardDeadlineExpired(BaseException):
    """Bypass broad Exception handlers after the cleanup reserve is exhausted."""


class DeadlineOwnershipError(ValueError):
    pass


class OverallDeadline:
    def __init__(self, timeout):
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 3600:
            raise ValueError('Task13 remaining budget must satisfy 0 < timeout <= 3600')
        self.started = time.monotonic()
        self.timeout = timeout
        self.deadline = self.started + timeout
        self.reserve = min(30.0, timeout * 0.1)
        self.work_deadline = self.deadline - self.reserve
        self.expired = False
        self.hard_expired = False
        self.ownership_lost = False
        self.entered = False
        self._handler = self._expire

    def _expire(self, signum, frame):
        if self.expired:
            self.hard_expired = True
            raise HardDeadlineExpired('Task13 overall deadline exhausted during cleanup')
        self.expired = True
        signal.setitimer(signal.ITIMER_REAL, max(0.000001, self.deadline - time.monotonic()))
        raise WorkDeadlineExpired('Task13 shared work deadline exhausted; cleanup reserve remains inside overall budget')

    def check_work(self):
        if signal.getsignal(signal.SIGALRM) != self._handler:
            self.ownership_lost = True
            raise DeadlineOwnershipError('Task13 timer ownership changed')
        if self.expired:
            raise WorkDeadlineExpired('Task13 shared work deadline already expired')
        if time.monotonic() >= self.work_deadline:
            self._expire(signal.SIGALRM, None)

    def __enter__(self):
        if threading.current_thread() is not threading.main_thread():
            raise DeadlineOwnershipError('Task13 deadline requires the main thread; no work started')
        if not all(hasattr(signal, name) for name in ['SIGALRM', 'ITIMER_REAL', 'setitimer', 'getitimer',
                                                     'pthread_sigmask', 'sigpending', 'sigwait']):
            raise DeadlineOwnershipError('Task13 requires an owned POSIX real timer; no work started')
        self.previous_handler = signal.getsignal(signal.SIGALRM)
        timer = signal.getitimer(signal.ITIMER_REAL)
        if self.previous_handler != signal.SIG_DFL or any(timer):
            raise DeadlineOwnershipError('Task13 refuses a foreign SIGALRM handler/timer; no work started')
        if hasattr(signal, 'pthread_sigmask') and signal.SIGALRM in signal.pthread_sigmask(signal.SIG_BLOCK, []):
            raise DeadlineOwnershipError('Task13 refuses blocked SIGALRM; no work started')
        if hasattr(signal, 'sigpending') and signal.SIGALRM in signal.sigpending():
            raise DeadlineOwnershipError('Task13 refuses pending SIGALRM; no work started')
        signal.signal(signal.SIGALRM, self._handler)
        try:
            signal.setitimer(signal.ITIMER_REAL, max(0.000001, self.work_deadline - time.monotonic()))
            self.entered = True
        except BaseException:
            if signal.getsignal(signal.SIGALRM) == self._handler:
                try:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                finally:
                    signal.signal(signal.SIGALRM, self.previous_handler)
            raise
        return self

    def __exit__(self, kind, value, trace):
        if signal.getsignal(signal.SIGALRM) != self._handler:
            # Never cancel or restore a handler installed by another owner.
            self.ownership_lost = True
            raise DeadlineOwnershipError('Task13 timer ownership changed; foreign handler left untouched')
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGALRM])
        pending = False
        try:
            signal.setitimer(signal.ITIMER_REAL, 0)
            pending = signal.SIGALRM in signal.sigpending()
            if pending:
                signal.sigwait([signal.SIGALRM])
            signal.signal(signal.SIGALRM, self.previous_handler)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        if time.monotonic() >= self.deadline:
            self.expired = self.hard_expired = True
            raise HardDeadlineExpired('Task13 overall deadline exhausted at context exit')
        if not self.expired and (pending or time.monotonic() >= self.work_deadline):
            self.expired = True
            raise WorkDeadlineExpired('Task13 work deadline exhausted at context exit')

    def diagnostic(self):
        return {'overallTimeoutSeconds': self.timeout, 'startedMonotonic': self.started,
                'overallDeadlineMonotonic': self.deadline, 'workDeadlineMonotonic': self.work_deadline,
                'cleanupReserveSeconds': self.reserve, 'overallElapsedSeconds': time.monotonic() - self.started,
                'publicFinalizationInsideDeadline': True, 'cleanupInsideDeadline': not self.hard_expired,
                'cleanupBoundByOverallHardDeadline': True,
                'softExpired': self.expired, 'hardExpired': self.hard_expired,
                'ownershipLost': self.ownership_lost,
                'ownership': 'exclusive main-thread SIGALRM; foreign alarms rejected without modification'}
