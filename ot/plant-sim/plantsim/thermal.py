"""L1 hydraulic unit physics (student edition).

One unit = pump A (+ standby pump B) + motor + cooler + fan + reservoir. The only slow state is the oil
temperature TS1; every other channel is derived from TS1, load, fan and the three slow disturbances the
ontology names (sv:fouling -> cooler_health, sv:leak -> leak, sv:bearing-wear -> bearing_wear), so the
whole plant stays explainable in a lecture.

    heat  = K_HEAT * (load/100)^2 + K_LEAK * leak * (load/100)^2     (pump losses + leakage flow turned into heat)
    cool  = (K_BASE + K_COOL * fan/100 * cooler_health) * (TS1 - T_AMB)
    dTS1/dt = (heat - cool) / C                                        [C per simulated second]
    PS1   = 155 + 0.3*load - LEAK_PS1_DROP * leak      (sv:leak -> sv:ps1, high)      pump B has no leak
    FS1   = 10 * load/100 * (1 - leak)                 (sv:leak -> sv:fs1, high)
    VS1   = 0.55 + 0.004*(TS1-48)+ + K_VIB * bearing_wear * (fan/60)^2   (sv:bearing-wear -> sv:vs1; "팬이 빠를수록 진동이 크다")

Constants were solved so that
    normal   (load 90, fan 60,  health 1.00) settles near 48 C, PS1 182 bar, FS1 9.0 l/min, VS1 0.6 mm/s
    degraded (load 90, fan 60,  health 0.43) heads for ~70 C  -> passes the 65 C trip
    mitigated(load 80, fan 100, health 0.43) settles near 49 C -> clears the 52 C CLEAR line
    leaking  (load 90, leak 0.15, pump A)    PS1 ~162 bar < 165, FS1 ~7.65 < 8.0 -> PUMP_LEAKAGE; pump B restores 182 (fc:pump-switch)
    worn fan (fan 60, wear 0.8)              VS1 ~1.35 > 1.2 -> FAN_VIBRATION; fan 40 -> ~0.9 (fc:fan-slow-vs1); fan 100 -> ~2.8 >= 2.0 interlock
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
TRIP_PS1 = 130.0         # low-pressure interlock (ontology sv:ps1 limit)
TRIP_VS1 = 2.0           # vibration interlock (ontology sv:vs1 limit)
DEGRADED_HEALTH = 0.43   # default fault-injection target (cooler fin fouling, sv:fouling)
DEGRADED_LEAK = 0.15     # default fault-injection target: 15 % internal leakage (pump A shaft seal wear, sv:leak)
DEGRADED_BEARING = 0.8   # default fault-injection target: fan bearing wear 0..1 (sv:bearing-wear)
K_LEAK = 0.08            # leakage flow -> heat (sv:leak -> sv:ts1, low)
LEAK_PS1_DROP = 130.0    # bar of discharge pressure lost per unit leakage (0.15 -> ~19.5 bar)
K_VIB = 1.0              # mm/s of fan vibration per unit bearing wear at fan 60 %


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
    leak: float = 0.0          # pump A internal leakage fraction (sv:leak); pump B is sound
    bearing_wear: float = 0.0  # fan bearing wear 0..1 (sv:bearing-wear)
    pump: str = "A"            # running pump (sv:pump-select, actr:pump-selector)
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


def effective_leak(s: UnitState) -> float:
    """Only pump A leaks; switching to the standby pump B takes the leak out of the circuit."""
    return s.leak if s.pump == "A" else 0.0


def vibration(s: UnitState, fan_pct: float) -> float:
    """Fan vibration without noise: thermal part + bearing wear amplified by fan speed (ontology AFFECTS sv:fan-speed -> sv:vs1)."""
    return 0.55 + 0.004 * max(0.0, s.ts1 - 48.0) + K_VIB * s.bearing_wear * (fan_pct / 60.0) ** 2


def step(s: UnitState, dt: float, running: bool) -> UnitState:
    """Advance the unit by dt simulated seconds. running=False models a tripped or stopped unit (pump and fan off)."""
    load = s.load_pct if running else 0.0
    leak = effective_leak(s)
    heat = (K_HEAT + K_LEAK * leak) * (load / 100.0) ** 2
    cool_coef = K_BASE + K_COOL * (s.fan_pct / 100.0) * s.cooler_health
    cool = cool_coef * (s.ts1 - s.t_amb)
    s.ts1 += (heat - cool) / C * dt
    s.sim_t += dt

    n = s.rng.gauss(0, 1)
    d = s.ts1 - s.t_amb
    s.ts2 = s.t_amb + d * 0.85
    s.ts3 = s.t_amb + d * 0.60
    s.ts4 = s.t_amb + 3.0 + 0.1 * n   # cabinet/ambient reference (independent of TS1)
    s.ps1 = 155.0 + 0.3 * load - LEAK_PS1_DROP * leak + 0.4 * n
    s.ps2 = s.ps1 - 10.0 + 0.2 * n
    s.ps3 = 2.0 + 0.02 * n
    s.ps4 = 1.5 + 0.02 * n
    s.ps5 = 8.5 + 0.03 * n
    s.ps6 = 8.2 + 0.03 * n
    s.eps1 = 0.0 if not running else 0.032 * load + 0.0004 * (s.ts1 - 48.0) + 0.01 * n
    s.fs1 = 0.0 if not running else 10.0 * load / 100.0 * (1.0 - leak) + 0.05 * n
    s.fs2 = s.fs1 * 1.02
    s.vs1 = vibration(s, s.fan_pct if running else 0.0) + 0.02 * abs(n)

    s.ce = 100.0 * s.cooler_health * (0.6 + 0.4 * s.fan_pct / 100.0)
    s.cp = cool_coef * d * 10.0
    s.se = 100.0 * (1 - 0.35 * (load / 100.0) ** 2) * (1 - max(0.0, s.ts1 - 50.0) / 100.0)
    return s


def wave_ps1(s: UnitState, hz: int = 100) -> list[float]:
    """One second of pump pressure ripple (rotational frequency 25 Hz)."""
    base = 155.0 + 0.3 * s.load_pct - LEAK_PS1_DROP * effective_leak(s)
    return [round(base + 3.0 * math.sin(2 * math.pi * 25 * i / hz) + s.rng.gauss(0, 0.3), 3) for i in range(hz)]


def wave_eps1(s: UnitState, hz: int = 100) -> list[float]:
    return [round(s.eps1 + 0.05 * math.sin(2 * math.pi * 50 * i / hz) + s.rng.gauss(0, 0.01), 4) for i in range(hz)]


def wave_fs1(s: UnitState, hz: int = 10) -> list[float]:
    return [round(s.fs1 + s.rng.gauss(0, 0.05), 3) for _ in range(hz)]
