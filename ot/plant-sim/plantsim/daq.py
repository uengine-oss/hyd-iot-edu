"""DAQ publishing profile (env DAQ_PROFILE, default "lite").

full : every tag every second + 1 s waveform batches (PS1/EPS1 100 Hz, FS1 10 Hz) — the v3 "고속 DAQ" as drawn.
lite : report-by-exception, the way real historians/edge gateways save bandwidth:
       - TS1 and CE (the CEP inputs) every second,
       - other core tags only when they move past a deadband, plus a 10 s heartbeat,
       - auxiliary channels (unused by detector, agent evidence or dashboards) on a 30 s heartbeat,
       - no waveforms.
       About 10 messages/s for 3 units instead of ~70, and ~6x fewer rows in tag_1s.
"""
from __future__ import annotations

ALWAYS = {"TS1", "CE"}
AUX = {"TS2", "PS2", "PS3", "PS4", "PS5", "PS6", "FS1", "FS2"}
DEADBAND = {"TS3": 0.2, "TS4": 0.2, "PS1": 1.0, "EPS1": 0.05, "VS1": 0.02, "CP": 0.1, "SE": 0.5, "FanSpeedSP": 0.5, "LoadSP": 0.5}
CORE_HEARTBEAT_S = 10.0
AUX_HEARTBEAT_S = 30.0


class DaqFilter:
    def __init__(self, profile: str = "lite"):
        self.profile = "full" if str(profile).lower() == "full" else "lite"
        self.waves = self.profile == "full"
        self._last: dict[tuple[str, str], tuple[float, float]] = {}   # (asset, tag) -> (value, t_sent)

    def select(self, asset: str, tags: dict[str, float], t: float) -> dict[str, float]:
        """Subset of `tags` to publish now (t = monotonic seconds)."""
        if self.profile == "full":
            return dict(tags)
        out = {}
        for name, v in tags.items():
            key = (asset, name)
            prev = self._last.get(key)
            if prev is None or name in ALWAYS:
                send = True
            elif name in AUX:
                send = t - prev[1] >= AUX_HEARTBEAT_S
            else:
                send = abs(v - prev[0]) >= DEADBAND.get(name, 0.5) or t - prev[1] >= CORE_HEARTBEAT_S
            if send:
                out[name] = v
                self._last[key] = (v, t)
        return out
