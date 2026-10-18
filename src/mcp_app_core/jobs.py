# In the name of God, the Most Gracious, the Most Merciful
"""Windows kill-on-close job object. No-op off Windows."""

from __future__ import annotations

import sys
import threading

import structlog

_logger = structlog.get_logger(__name__)
_LOCK = threading.Lock()
_JOB_HANDLE: object | None = None
_JOB_UNAVAILABLE = False
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
_PROCESS_TERMINATE = 0x0001
_PROCESS_SET_QUOTA = 0x0100


def _create_job_handle() -> object | None:
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class BasicLimit(ctypes.Structure):
        _fields_ = (
            ("per_process_user_time_limit", wintypes.LARGE_INTEGER),
            ("per_job_user_time_limit", wintypes.LARGE_INTEGER),
            ("limit_flags", wintypes.DWORD),
            ("minimum_working_set_size", ctypes.c_size_t),
            ("maximum_working_set_size", ctypes.c_size_t),
            ("active_process_limit", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority_class", wintypes.DWORD),
            ("scheduling_class", wintypes.DWORD),
        )

    class IoCounters(ctypes.Structure):
        _fields_ = tuple(
            (name, ctypes.c_ulonglong)
            for name in (
                "read_operation_count",
                "write_operation_count",
                "other_operation_count",
                "read_transfer_count",
                "write_transfer_count",
                "other_transfer_count",
            )
        )

    class ExtendedLimit(ctypes.Structure):
        _fields_ = (
            ("basic", BasicLimit),
            ("io_info", IoCounters),
            ("process_memory_limit", ctypes.c_size_t),
            ("job_memory_limit", ctypes.c_size_t),
            ("peak_process_memory_used", ctypes.c_size_t),
            ("peak_job_memory_used", ctypes.c_size_t),
        )

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        return None
    info = ExtendedLimit()
    info.basic.limit_flags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    ok = kernel32.SetInformationJobObject(
        handle,
        _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
        ctypes.byref(info),
        ctypes.sizeof(info),
    )
    if not ok:
        kernel32.CloseHandle(handle)
        return None
    _logger.debug("job_object_created")
    return int(handle)


def _ensure_job_handle() -> object | None:
    global _JOB_HANDLE, _JOB_UNAVAILABLE
    if _JOB_HANDLE is not None or _JOB_UNAVAILABLE:
        return _JOB_HANDLE
    with _LOCK:
        if _JOB_HANDLE is None and not _JOB_UNAVAILABLE:
            handle = _create_job_handle()
            if handle is None:
                _JOB_UNAVAILABLE = True
            else:
                _JOB_HANDLE = handle
    return _JOB_HANDLE


def assign_process_to_kill_on_close_job(pid: int) -> bool:
    """Assign a child PID to the kill-on-close job. Returns False when unavailable."""

    if sys.platform != "win32":
        return False
    handle = _ensure_job_handle()
    if handle is None:
        return False
    import ctypes

    kernel32 = ctypes.windll.kernel32
    process_handle = kernel32.OpenProcess(_PROCESS_SET_QUOTA | _PROCESS_TERMINATE, False, pid)
    if not process_handle:
        return False
    try:
        assigned = kernel32.AssignProcessToJobObject(handle, process_handle)
    finally:
        kernel32.CloseHandle(process_handle)
    return bool(assigned)


def reset_job_object_state_for_tests() -> None:
    """Clear the memoized job handle. Tests only."""

    global _JOB_HANDLE, _JOB_UNAVAILABLE
    with _LOCK:
        _JOB_HANDLE = None
        _JOB_UNAVAILABLE = False
