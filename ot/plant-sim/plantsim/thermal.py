"""L1 hydraulic unit physics (student edition).

One unit = pump + motor + cooler + reservoir. The only slow state is the oil
temperature TS1; every other channel is derived from TS1, load and fan so the
whole plant stays explainable in a lecture.

    heat  = K_HEAT * (load/100)^2                       (pump losses)
    cool  = (K_BASE + K_COOL * fan/100 * cooler_health) * (TS1 - T_AMB)
    dTS1/dt = (heat - cool) / C                          [C per simulated second]

Constants were solved so that
    normal   (load 90, fan 60,  health 1.00) settles near 48 C
    degraded (load 90, fan 60,  health 0.43) heads for ~70 C  -> passes the 65 C trip
    mitigated(load 80, fan 100, health 0.43) settles near 49 C -> clears the 52 C CLEAR line
"""
from dataclasses import dataclass, field
import math
import random

K_HEAT = 1.0
K_COOL = 0.05036
K_BASE = 0.005
C = 20.0
T_AMB = 25.0
TRIP_TS1 = 65.0
DEGRADED_HEALTH = 0.43   # default fault-injection target (cooler fin fouling)


@dataclass
class UnitState:
    ts1: float = 48.0   # oil temperature at cooler inlet (C)
    ts2: float = 44.0   # cooler outlet
    ts3: float = 40.0   # reservoir
    ts4: float = 42.0   # ambient/cabinet reference
    ps1: float = 160.0  # pump outlet pressure (bar)
    ps2: float = 150.0
    ps3: float = 2.0
    ps4: float = 1.5
    ps5: float = 8.5
    ps6: float = 8.2
    eps1: float = 2.8   # motor power (kW)
    fs1: float = 9.0    # flow (l/min)
    fs2: float = 10.0
    vs1: float = 0.6    # vibration (mm/s)
    fan_pct: float = 60.0
    load_pct: float = 90.0
    cooler_health: float = 1.0
    ce: float = 100.0   # cooler efficiency (virtual)
    cp: float = 1.5     # cooling power (virtual)
    se: float = 60.0    # system efficiency (virtual)
    t_amb: float = T_AMB
    sim_t: float = 0.0  # simulated seconds since start
    rng: random.Random = field(default_factory=lambda: random.Random(1), repr=False)


def equilibrium_ts1(load: float, fan: float, health: float, t_amb: float = T_AMB) -> float:
    heat = K_HEAT * (load / 100.0) ** 2
    cool_coef = K_BASE + K_COOL * (fan / 100.0) * health
    return t_amb + heat / cool_coef


def step(s: UnitState, dt: float, running: bool) -> UnitState:
    """Advance the unit by dt simulated seconds. running=False models a tripped (stopped) pump."""
    load = s.load_pct if running else 0.0
    heat = K_HEAT * (load / 100.0) ** 2
    cool_coef = K_BASE + K_COOL * (s.fan_pct / 100.0) * s.cooler_health
    cool = cool_coef * (s.ts1 - s.t_amb)
    s.ts1 += (heat - cool) / C * dt
    s.sim_t += dt

    n = s.rng.gauss(0, 1)
    d = s.ts1 - s.t_amb
    s.ts2 = s.t_amb + d * 0.85
    s.ts3 = s.t_amb + d * 0.60
    s.ts4 = s.t_amb + 3.0 + 0.1 * n   # cabinet/ambient reference (independent of TS1)
    s.ps1 = 155.0 + 0.3 * load + 0.4 * n
    s.ps2 = s.ps1 - 10.0 + 0.2 * n
    s.ps3 = 2.0 + 0.02 * n
    s.ps4 = 1.5 + 0.02 * n
    s.ps5 = 8.5 + 0.03 * n
    s.ps6 = 8.2 + 0.03 * n
    s.eps1 = 0.0 if not running else 0.032 * load + 0.0004 * (s.ts1 - 48.0) + 0.01 * n
    s.fs1 = 0.0 if not running else 10.0 * load / 100.0 + 0.05 * n
    s.fs2 = s.fs1 * 1.02
    s.vs1 = 0.55 + 0.004 * max(0.0, s.ts1 - 48.0) + 0.02 * abs(n)

    s.ce = 100.0 * s.cooler_health * (0.6 + 0.4 * s.fan_pct / 100.0)
    s.cp = cool_coef * d * 10.0
    s.se = 100.0 * (1 - 0.35 * (load / 100.0) ** 2) * (1 - max(0.0, s.ts1 - 50.0) / 100.0)
    return s


def wave_ps1(s: UnitState, hz: int = 100) -> list[float]:
    """One second of pump pressure ripple (rotational frequency 25 Hz)."""
    base = 155.0 + 0.3 * s.load_pct
    return [round(base + 3.0 * math.sin(2 * math.pi * 25 * i / hz) + s.rng.gauss(0, 0.3), 3) for i in range(hz)]


def wave_eps1(s: UnitState, hz: int = 100) -> list[float]:
    return [round(s.eps1 + 0.05 * math.sin(2 * math.pi * 50 * i / hz) + s.rng.gauss(0, 0.01), 4) for i in range(hz)]


def wave_fs1(s: UnitState, hz: int = 10) -> list[float]:
    return [round(s.fs1 + s.rng.gauss(0, 0.05), 3) for _ in range(hz)]
