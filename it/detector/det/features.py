"""L4 feature extraction (the Flink 1 s window job) and the anomaly-score stand-in for the ONNX autoencoder."""
import math
from collections import deque

# The "trained" baseline of the healthy operating point: (mean, std) per signal, fixed so the score is restart-safe.
NORMAL = {"TS1": (48.0, 1.0), "CE": (84.0, 3.0), "VS1": (0.6, 0.05)}


def wave_features(v: list[float]) -> dict:
    """mean, rms and per-sample linear-regression slope of a 1 s waveform batch (checked by hydcommon.schemas.wave_record)."""
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
    """Moving linear-regression slope over the last `window_s` simulated seconds (units: value per simulated second)."""

    def __init__(self, window_s: float):
        self.window_s = window_s
        self.pts: deque = deque()

    def push(self, t: float, v: float) -> None:
        self.pts.append((t, v))
        self.trim(t)

    def trim(self, t: float) -> None:
        """Expire samples even when this signal itself has stopped publishing."""
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


def anomaly_score(values: dict) -> float:
    """Reconstruction-error proxy: RMS of the z-scores of TS1 · CE · VS1 against NORMAL, squashed to 0..1 (z≈4 → 1.0)."""
    z = [(values[sig] - mean) / std for sig, (mean, std) in NORMAL.items()]
    return round(min(1.0, math.sqrt(sum(x * x for x in z) / len(z)) / 4.0), 3)
