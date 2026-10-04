"""DAQ reporting cadence in wall seconds, shared by edge filtering and detector trust."""
# Temporal predicates must see every sampled value, including changes smaller
# than a reporting deadband. Otherwise a suppressed crossing can fake a hold.
ALWAYS = {'TS1', 'CE', 'PS1', 'FS1', 'VS1', 'LoadSP'}
AUX = {'TS2', 'PS2', 'PS3', 'PS4', 'PS5', 'PS6', 'FS2'}
DEADBAND = {'TS3': .2, 'TS4': .2, 'PS1': 1., 'FS1': .1, 'EPS1': .05, 'VS1': .02,
            'CP': .1, 'SE': .5, 'FanSpeedSP': .5, 'LoadSP': .5}
CORE_HEARTBEAT_S = 10.
AUX_HEARTBEAT_S = 30.


def reporting_interval(tag, profile='lite'):
    if profile not in ('lite', 'full'):
        raise ValueError('DAQ profile must be lite or full')
    if tag == 'PLC_STATE':
        return 10.  # edge status heartbeat, separate from tag reporting profile
    if profile == 'full' or tag in ALWAYS:
        return 1.
    return AUX_HEARTBEAT_S if tag in AUX else CORE_HEARTBEAT_S
