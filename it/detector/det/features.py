"""L4 feature extraction (the Flink 1 s window job) and the anomaly-score stand-in for the ONNX autoencoder."""
import math
from collections import deque


def wave_features(v: list[float]) -> dict:
    """mean, rms and per-sample linear-regression slope of a 1 s waveform batch."""
    n = len(v)
    if n == 0:
        return {"mean": None, "rms": None, "slope": None}
    mean = sum(v) / n
    rms = math.sqrt(sum(x * x for x in v) / n)
    if n < 2:
        return {"mean": mean, "rms": rms, "slope": 0.0}
    xm = (n - 1) / 2
    sxx = sum((i - xm) ** 2 for i in range(n))
    sxy = sum((i - xm) * (x - mean) for i, x in enumerate(v))
    return {"mean": mean, "rms": rms, "slope": sxy / sxx}


class SlopeWindow:
    """Moving linear-regression slope over the last `window_s` simulated seconds (units: value per sim-second)."""

    def __init__(self, window_s: float = 60.0):
        self.window_s = window_s
        self.pts: deque = deque()

    def push(self, t: float, v: float) -> None:
        self.pts.append((t, v))
        while self.pts and t - self.pts[0][0] > self.window_s:
            self.pts.popleft()

    def slope(self) -> float:
        n = len(self.pts)
        if n < 2:
            return 0.0
        tm = sum(t for t, _ in self.pts) / n
        vm = sum(v for _, v in self.pts) / n
        sxx = sum((t - tm) ** 2 for t, _ in self.pts)
        if sxx == 0:
            return 0.0
        return sum((t - tm) * (v - vm) for t, v in self.pts) / sxx


class Baseline:
    """Per-signal normal statistics learned from the first n samples (the model's 'training set')."""

    def __init__(self, n: int = 30, min_std: float = 0.5):
        self.n, self.min_std = n, min_std
        self.samples: dict[str, list[float]] = {}
        self.stats: dict[str, tuple[float, float]] = {}

    def push(self, sig: str, v: float) -> None:
        if sig in self.stats:
            return
        s = self.samples.setdefault(sig, [])
        s.append(v)
        if len(s) >= self.n:
            mean = sum(s) / len(s)
            std = math.sqrt(sum((x - mean) ** 2 for x in s) / len(s))
            self.stats[sig] = (mean, max(std, self.min_std))

    def ready(self, sig: str) -> bool:
        return sig in self.stats

    def z(self, sig: str, v: float) -> float:
        if sig not in self.stats:
            return 0.0
        mean, std = self.stats[sig]
        return (v - mean) / std


def anomaly_score(z_ts1: float, z_ce: float, z_vs1: float) -> float:
    """Reconstruction-error proxy: RMS of z-scores, squashed to 0..1 (z≈4 → 1.0)."""
    rms = math.sqrt((z_ts1 ** 2 + z_ce ** 2 + z_vs1 ** 2) / 3)
    return round(min(1.0, rms / 4.0), 3)
