"""Tiny Prometheus text-format registry (enough for a student prototype; no external dependency)."""
from collections import defaultdict
from threading import Lock


class Registry:
    def __init__(self):
        self._lock = Lock()
        self._counters: dict[str, dict[tuple, float]] = defaultdict(dict)
        self._gauges: dict[str, dict[tuple, float]] = defaultdict(dict)
        self._help: dict[str, str] = {}

    def counter(self, name: str, help: str = ""):
        self._help.setdefault(name, help)
        reg = self

        class _C:
            def inc(self, n: float = 1, **labels):
                with reg._lock:
                    k = tuple(sorted(labels.items()))
                    reg._counters[name][k] = reg._counters[name].get(k, 0) + n
        return _C()

    def gauge(self, name: str, help: str = ""):
        self._help.setdefault(name, help)
        reg = self

        class _G:
            def set(self, v: float, **labels):
                with reg._lock:
                    reg._gauges[name][tuple(sorted(labels.items()))] = v
        return _G()

    @staticmethod
    def _fmt(name, series, typ, help_):
        out = [f"# HELP {name} {help_}", f"# TYPE {name} {typ}"]
        for k, v in series.items():
            lbl = ",".join(f'{a}="{b}"' for a, b in k)
            out.append(f"{name}{{{lbl}}} {v}" if lbl else f"{name} {v}")
        return out

    def render(self) -> str:
        with self._lock:
            lines = []
            for n, s in self._counters.items():
                lines += self._fmt(n, s, "counter", self._help.get(n, ""))
            for n, s in self._gauges.items():
                lines += self._fmt(n, s, "gauge", self._help.get(n, ""))
        return "\n".join(lines) + "\n"
