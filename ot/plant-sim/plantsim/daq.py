"""DAQ publishing profile (compose DAQ_PROFILE; the tag sets and intervals are hydcommon.daq_contract).

full : every tag every second + 1 s waveform batches (PS1/EPS1 100 Hz, FS1 10 Hz) — the v3 "고속 DAQ" as drawn.
lite : report-by-exception, the way real historians/edge gateways save bandwidth:
       - all numeric CEP inputs (ALWAYS: TS1, CE, PS1, FS1, VS1, LoadSP) every second,
       - other core tags only past their deadband, plus a 10 s heartbeat,
       - auxiliary channels (unused by detector, agent evidence or dashboards) on a 30 s heartbeat,
       - no waveforms.
       Temporal predicates must not infer uninterrupted conditions from suppressed samples.
due() says what to publish now; sent() records what actually left (a value the broker client refused is not "reported",
so the next tick offers it again instead of waiting for the heartbeat).
"""
from __future__ import annotations

from hydcommon.daq_contract import ALWAYS, AUX, AUX_HEARTBEAT_S, CORE_HEARTBEAT_S, DEADBAND, PROFILES


class DaqFilter:
    def __init__(self, profile: str):
        if profile not in PROFILES:
            raise ValueError(f"DAQ profile must be one of {PROFILES}, got {profile!r}")
        self.profile = profile
        self.waves = profile == "full"
        self._last: dict[tuple[str, str], tuple[float, float]] = {}   # (asset, tag) -> (value, t_sent)

    def due(self, asset: str, tags: dict[str, float], t: float) -> dict[str, float]:
        """Subset of `tags` to publish now (t = monotonic seconds)."""
        if self.profile == "full":
            return dict(tags)
        out = {}
        for name, v in tags.items():
            prev = self._last.get((asset, name))
            if prev is None or name in ALWAYS:
                send = True
            elif name in AUX:
                send = t - prev[1] >= AUX_HEARTBEAT_S
            else:
                send = abs(v - prev[0]) >= DEADBAND[name] or t - prev[1] >= CORE_HEARTBEAT_S
            if send:
                out[name] = v
        return out

    def sent(self, asset: str, name: str, v: float, t: float) -> None:
        self._last[(asset, name)] = (v, t)
