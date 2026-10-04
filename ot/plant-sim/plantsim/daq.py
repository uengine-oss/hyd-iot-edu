"""DAQ publishing profile (env DAQ_PROFILE, default "lite").

full : every tag every second + 1 s waveform batches (PS1/EPS1 100 Hz, FS1 10 Hz) — the v3 "고속 DAQ" as drawn.
lite : report-by-exception, the way real historians/edge gateways save bandwidth:
       - all numeric CEP inputs (TS1, CE, PS1, FS1, VS1, LoadSP) every second,
       - other core tags only past a deadband, plus a 10 s heartbeat,
       - auxiliary channels (unused by detector, agent evidence or dashboards) on a 30 s heartbeat,
       - no waveforms.
       Temporal predicates must not infer uninterrupted conditions from suppressed samples.
"""
from __future__ import annotations

from hydcommon.daq_contract import ALWAYS, AUX, DEADBAND, CORE_HEARTBEAT_S, AUX_HEARTBEAT_S


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
