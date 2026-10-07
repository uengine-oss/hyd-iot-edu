"""A131 — development-only memory diagnostics: GET /debug/memory (enabled by PROCESS_MEMDEBUG=1).

The process container died twice on 2026-10-07 from the kernel OOM killer (uvicorn anon-rss ~773 MB against a 768 MB limit)
while Docker still reported OOMKilled=false, so the restart looked silent. This endpoint makes a growth measurable instead of
guessed: tracemalloc top allocation sites, RSS from /proc, the size of every long-lived container the service owns, live
counts of DB/driver/consumer objects (via gc) and the executor/thread state. Off by default; nothing here runs unless the
flag is set, so the product path is untouched.
"""
from __future__ import annotations

import gc
import os
import sys
import threading
import tracemalloc
from collections import Counter

TOP = 20
FRAMES = int(os.getenv("PROCESS_MEMDEBUG_FRAMES", "3"))   # 6 frames cost ~150 MB on 2.4 M blocks


def enabled() -> bool:
    return os.getenv("PROCESS_MEMDEBUG", "0") == "1"


def _proc_status() -> dict:
    out = {}
    try:
        with open("/proc/self/status", encoding="ascii", errors="replace") as fh:
            for line in fh:
                key, _, value = line.partition(":")
                if key in ("VmRSS", "VmHWM", "VmData", "VmSize", "Threads", "RssAnon", "RssFile"):
                    out[key] = value.strip()
    except OSError:
        pass
    return out


def _mallinfo() -> dict | None:
    """glibc arena statistics: tells a fragmentation problem (RSS high, in-use low) from a leak (in-use high)."""
    try:
        import ctypes
        libc = ctypes.CDLL("libc.so.6")

        class MallInfo2(ctypes.Structure):
            _fields_ = [(n, ctypes.c_size_t) for n in ("arena", "ordblks", "smblks", "hblks", "hblkhd", "usmblks",
                                                     "fsmblks", "uordblks", "fordblks", "keepcost")]
        libc.mallinfo2.restype = MallInfo2
        m = libc.mallinfo2()
        return {"arena_bytes": m.arena, "mmap_bytes": m.hblkhd, "in_use_bytes": m.uordblks, "free_bytes": m.fordblks,
                "trim_able_bytes": m.keepcost}
    except Exception as exc:  # noqa: BLE001 — not glibc / no ctypes
        return {"error": repr(exc)}


def malloc_trim() -> bool:
    try:
        import ctypes
        return bool(ctypes.CDLL("libc.so.6").malloc_trim(0))
    except Exception:  # noqa: BLE001
        return False


def _live_objects() -> dict:
    """Counts of the object kinds a leak in this service would show up as (connections, drivers, locks, queues, tasks)."""
    wanted = {
        "psycopg.Connection": 0, "neo4j.Driver": 0, "neo4j.Session": 0, "sqlite3.Connection": 0,
        "asyncio.Task": 0, "asyncio.Queue": 0, "threading.Lock": 0, "threading.RLock": 0,
        "aiokafka.Consumer": 0, "aiokafka.Producer": 0, "StreamingResponse": 0, "pypdf.PdfReader": 0,
    }
    by_type: Counter = Counter()
    for obj in gc.get_objects():
        t = type(obj)
        mod, name = getattr(t, "__module__", ""), getattr(t, "__name__", "?")
        if not isinstance(mod, str):          # a class object's own __module__ slot is a getset_descriptor
            mod = ""
        by_type[f"{mod}.{name}"] += 1
        if mod.startswith("psycopg") and name == "Connection":
            wanted["psycopg.Connection"] += 1
        elif mod.startswith("neo4j") and name in ("Driver", "BoltDriver", "Neo4jDriver"):
            wanted["neo4j.Driver"] += 1
        elif mod.startswith("neo4j") and name == "Session":
            wanted["neo4j.Session"] += 1
        elif mod == "sqlite3" and name == "Connection":
            wanted["sqlite3.Connection"] += 1
        elif mod.startswith("asyncio") and name == "Task":
            wanted["asyncio.Task"] += 1
        elif mod.startswith("asyncio") and name == "Queue":
            wanted["asyncio.Queue"] += 1
        elif mod.startswith("aiokafka") and name == "AIOKafkaConsumer":
            wanted["aiokafka.Consumer"] += 1
        elif mod.startswith("aiokafka") and name == "AIOKafkaProducer":
            wanted["aiokafka.Producer"] += 1
        elif name == "StreamingResponse":
            wanted["StreamingResponse"] += 1
        elif mod.startswith("pypdf") and name == "PdfReader":
            wanted["pypdf.PdfReader"] += 1
    wanted["threading.Lock"] = by_type.get("_thread.lock", 0)
    wanted["threading.RLock"] = by_type.get("_thread.RLock", 0)
    return {"tracked": wanted, "top_types": by_type.most_common(25), "gc_objects": sum(by_type.values())}


def _tracemalloc_top() -> dict:
    if not tracemalloc.is_tracing():
        return {"tracing": False}
    snap = tracemalloc.take_snapshot().filter_traces((
        tracemalloc.Filter(False, tracemalloc.__file__),
        tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
    ))
    current, peak = tracemalloc.get_traced_memory()
    rows = []
    for st in snap.statistics("traceback")[:TOP]:
        rows.append({"size_kb": round(st.size / 1024, 1), "count": st.count,
                     "where": [f"{f.filename}:{f.lineno}" for f in st.traceback[-FRAMES:]][::-1]})
    by_line = [{"size_kb": round(st.size / 1024, 1), "count": st.count, "where": str(st.traceback)}
               for st in snap.statistics("lineno")[:TOP]]
    return {"tracing": True, "traced_current_kb": round(current / 1024, 1), "traced_peak_kb": round(peak / 1024, 1),
            "top_by_traceback": rows, "top_by_line": by_line}


def _executor(loop) -> dict:
    ex = getattr(loop, "_default_executor", None) if loop else None
    if ex is None:
        return {"present": False}
    q = getattr(ex, "_work_queue", None)
    return {"present": True, "threads": len(getattr(ex, "_threads", ()) or ()), "max_workers": getattr(ex, "_max_workers", None),
            "queued": q.qsize() if q is not None else None}


def snapshot(collect: dict | None = None, *, loop=None, trim: bool = False, trace: bool = True) -> dict:
    """trace=False skips the tracemalloc snapshot: on this service's heap (~2.4 M blocks) take_snapshot() needs tens of
    seconds and ~80 MB of transient memory, which would distort a per-phase RSS reading. proc/mallinfo/gc stay cheap."""
    out = {"pid": os.getpid(), "proc": _proc_status(), "mallinfo": _mallinfo(),
           "python_allocated_blocks": sys.getallocatedblocks(), "threads": threading.active_count(),
           "thread_names": sorted(Counter(t.name.split("_")[0] for t in threading.enumerate()).items()),
           "executor": _executor(loop), "gc_counts": gc.get_count(),
           "traced_kb": [round(v / 1024, 1) for v in tracemalloc.get_traced_memory()] if tracemalloc.is_tracing() else None}
    if trim:
        out["malloc_trim"] = malloc_trim()
        out["proc_after_trim"] = _proc_status()
        out["mallinfo_after_trim"] = _mallinfo()
    out["containers"] = {}
    for name, fn in (collect or {}).items():
        try:
            out["containers"][name] = fn()
        except Exception as exc:  # noqa: BLE001 — a broken collector must not hide the rest
            out["containers"][name] = f"error: {exc!r}"
    out["objects"] = _live_objects()
    out["tracemalloc"] = _tracemalloc_top() if trace else {"tracing": tracemalloc.is_tracing(), "skipped": True}
    return out


def register(app, collectors: dict, get_loop=lambda: None) -> None:
    """Mount GET /debug/memory[?trim=1][&trace=0]. Starts tracemalloc at mount time so growth since start is attributable."""
    if not tracemalloc.is_tracing():
        tracemalloc.start(FRAMES)

    @app.get("/debug/memory")
    def debug_memory(trim: int = 0, trace: int = 1):
        return snapshot(collectors, loop=get_loop(), trim=bool(trim), trace=bool(trace))
