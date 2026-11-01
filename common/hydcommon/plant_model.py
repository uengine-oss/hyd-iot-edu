"""The lumped hydraulic-unit model — one set of constants and equations for the simulator (plant-sim thermal.step integrates it
every simulated second) and the approval forecast (hydcommon.forecast solves the same ODE in closed form for constant inputs).

    heat          = (K_HEAT + K_LEAK * leak) * (load/100)^2           pump losses + leakage flow turned into heat
    cooling_coef  = K_BASE + K_COOL * fan/100 * cooler_health          running
                  = K_BASE                                             stopped or tripped: the pump is off, no oil flows
                                                                       through the cooler, so its fan removes no heat
    dTS1/dt       = (heat - cooling_coef * (TS1 - T_AMB)) / C          [C per simulated second]
    PS1           = PS_BASE + PS_LOAD * load - LEAK_PS1_DROP * leak    (sv:leak -> sv:ps1, high)
    FS1           = 10 * load/100 * (1 - leak)                         (sv:leak -> sv:fs1, high); 0 when stopped
    VS1           = 0.55 + 0.004 * (TS1 - 48)+ + K_VIB * bearing_wear * (fan/60)^2   fan 0 when stopped
leak is the running pump's leakage: only pump A leaks (standby pump B is sound). load is 0 when the unit is not running.

Constants were solved so that
    normal   (load 90, fan 60,  health 1.00) settles near 48 C, PS1 182 bar, FS1 9.0 l/min, VS1 0.6 mm/s
    degraded (load 90, fan 60,  health 0.43) heads for ~70 C  -> passes the 65 C trip   (severity "high", API default)
    moderate (load 90, fan 60,  health 0.55) settles at 62.5 C -> alarm (TS1 > 55, CE 46 < 70) but never the 65 C trip
    mitigated(load 80, fan 100, health 0.43) settles near 49 C -> clears the 52 C CLEAR line (health 0.55: ~44.6 C)
    leaking  (load 90, leak 0.15, pump A)    PS1 ~162 bar < 165, FS1 ~7.65 < 8.0 -> PUMP_LEAKAGE; pump B restores 182
    worn fan (fan 60, wear 0.8)              VS1 ~1.35 > 1.2 -> FAN_VIBRATION; fan 40 -> ~0.9; fan 100 -> ~2.8 >= 2.0 interlock
"""
K_HEAT = 1.0
K_LEAK = 0.08            # leakage flow -> heat (sv:leak -> sv:ts1, low)
K_COOL = 0.05036
K_BASE = 0.005
C = 20.0
T_AMB = 25.0
PS_BASE, PS_LOAD = 155.0, 0.3
LEAK_PS1_DROP = 130.0    # bar of discharge pressure lost per unit leakage (0.15 -> ~19.5 bar)
K_VIB = 1.0              # mm/s of fan vibration per unit bearing wear at fan 60 %
TRIP_TS1 = 65.0          # interlocks (ontology AFFECTS notes / sv limits)
TRIP_PS1 = 130.0
TRIP_VS1 = 2.0
RESET_TS1 = 55.0         # the PLC refuses a reset at or above this oil temperature
LOAD_MIN_PCT = 60.0      # the PLC write range of LoadSP is LOAD_MIN_PCT..100, FanSpeedSP 0..100


def effective_leak(leak: float, pump: str) -> float:
    return leak if pump == "A" else 0.0


def heat(load_pct: float, leak: float) -> float:
    return (K_HEAT + K_LEAK * leak) * (load_pct / 100.0) ** 2


def cooling_coef(fan_pct: float, cooler_health: float, running: bool) -> float:
    return K_BASE + (K_COOL * (fan_pct / 100.0) * cooler_health if running else 0.0)


def pressure(load_pct: float, leak: float) -> float:
    return PS_BASE + PS_LOAD * load_pct - LEAK_PS1_DROP * leak


def flow(load_pct: float, leak: float, running: bool) -> float:
    return 10.0 * load_pct / 100.0 * (1.0 - leak) if running else 0.0


def vibration(ts1: float, bearing_wear: float, fan_pct: float) -> float:
    """Fan vibration without noise: thermal part + bearing wear amplified by fan speed (ontology AFFECTS sv:fan-speed -> sv:vs1)."""
    return 0.55 + 0.004 * max(0.0, ts1 - 48.0) + K_VIB * bearing_wear * (fan_pct / 60.0) ** 2


def steady_ts1(load_pct: float, leak: float, fan_pct: float, cooler_health: float, running: bool, t_amb: float = T_AMB) -> float:
    return t_amb + heat(load_pct if running else 0.0, leak) / cooling_coef(fan_pct, cooler_health, running)
