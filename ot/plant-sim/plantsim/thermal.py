"""L1 hydraulic unit physics (student edition): the state of one unit and its one-second step.

One unit = pump A (+ standby pump B) + motor + cooler + fan + reservoir. The only slow state is the oil temperature TS1;
every other channel is derived from TS1, load, fan and the three slow disturbances the ontology names
(sv:fouling -> cooler_health, sv:leak -> leak, sv:bearing-wear -> bearing_wear), so the whole plant stays explainable in a
lecture. The constants and equations are hydcommon.plant_model — the same ones the approval forecast solves.
"""
from dataclasses import dataclass, field
import math
import random

from hydcommon import plant_model as m

DEGRADED_HEALTH = 0.43   # default fault-injection target (cooler fin fouling, sv:fouling): severity "high", trips at 65 C
MODERATE_HEALTH = 0.55   # severity "moderate": equilibrium 62.5 C — alarm without the trip (window for slow agents, A146)
DEGRADED_LEAK = 0.15     # default fault-injection target: 15 % internal leakage (pump A shaft seal wear, sv:leak)
DEGRADED_BEARING = 0.8   # default fault-injection target: fan bearing wear 0..1 (sv:bearing-wear)
NORMAL_FAN_PCT, NORMAL_LOAD_PCT = 60.0, 90.0   # the normal operating point: set-points before any mitigation command
NORMAL_TS1 = 48.0


@dataclass
class UnitState:
    ts1: float = NORMAL_TS1   # oil temperature at cooler inlet (C)
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
    fan_pct: float = NORMAL_FAN_PCT
    load_pct: float = NORMAL_LOAD_PCT
    cooler_health: float = 1.0
    leak: float = 0.0          # pump A internal leakage fraction (sv:leak); pump B is sound
    bearing_wear: float = 0.0  # fan bearing wear 0..1 (sv:bearing-wear)
    pump: str = "A"            # running pump (sv:pump-select, actr:pump-selector)
    ce: float = 100.0   # cooler efficiency (virtual)
    cp: float = 1.5     # cooling power (virtual)
    se: float = 60.0    # system efficiency (virtual)
    t_amb: float = m.T_AMB
    rng: random.Random = field(default_factory=lambda: random.Random(1), repr=False)


def step(s: UnitState, dt: float, running: bool) -> UnitState:
    """Advance the unit by dt simulated seconds. running=False is a tripped or stopped unit: pump and fan off, no load,
    natural cooling only (plant_model.cooling_coef)."""
    load = s.load_pct if running else 0.0
    leak = m.effective_leak(s.leak, s.pump)
    coef = m.cooling_coef(s.fan_pct, s.cooler_health, running)
    s.ts1 += (m.heat(load, leak) - coef * (s.ts1 - s.t_amb)) / m.C * dt

    n = s.rng.gauss(0, 1)
    d = s.ts1 - s.t_amb
    s.ts2 = s.t_amb + d * 0.85
    s.ts3 = s.t_amb + d * 0.60
    s.ts4 = s.t_amb + 3.0 + 0.1 * n   # cabinet/ambient reference (independent of TS1)
    s.ps1 = m.pressure(load, leak) + 0.4 * n
    s.ps2 = s.ps1 - 10.0 + 0.2 * n
    s.ps3 = 2.0 + 0.02 * n
    s.ps4 = 1.5 + 0.02 * n
    s.ps5 = 8.5 + 0.03 * n
    s.ps6 = 8.2 + 0.03 * n
    s.eps1 = 0.0 if not running else 0.032 * load + 0.0004 * (s.ts1 - 48.0) + 0.01 * n
    s.fs1 = 0.0 if not running else m.flow(load, leak, running) + 0.05 * n
    s.fs2 = s.fs1 * 1.02
    s.vs1 = m.vibration(s.ts1, s.bearing_wear, s.fan_pct if running else 0.0) + 0.02 * abs(n)

    s.ce = 100.0 * s.cooler_health * (0.6 + 0.4 * s.fan_pct / 100.0)
    s.cp = coef * d * 10.0
    s.se = 100.0 * (1 - 0.35 * (load / 100.0) ** 2) * (1 - max(0.0, s.ts1 - 50.0) / 100.0)
    return s


def wave_ps1(s: UnitState, hz: int = 100) -> list[float]:
    """One second of pump pressure ripple (rotational frequency 25 Hz)."""
    base = m.pressure(s.load_pct, m.effective_leak(s.leak, s.pump))
    return [round(base + 3.0 * math.sin(2 * math.pi * 25 * i / hz) + s.rng.gauss(0, 0.3), 3) for i in range(hz)]


def wave_eps1(s: UnitState, hz: int = 100) -> list[float]:
    return [round(s.eps1 + 0.05 * math.sin(2 * math.pi * 50 * i / hz) + s.rng.gauss(0, 0.01), 4) for i in range(hz)]


def wave_fs1(s: UnitState, hz: int = 10) -> list[float]:
    return [round(s.fs1 + s.rng.gauss(0, 0.05), 3) for _ in range(hz)]
