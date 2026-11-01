"""DAQ reporting contract in wall seconds — the tag list and how often each tag is reported. One place for the edge filter
(plant-sim daq), the detector's trust check (observations · patterns), connect-ingest's tag check and the agent's gap check
(agentsvc mcp_tsdb).

TAGS      every measurement plant-sim publishes on plant/{a}/tag/{name}; nothing else is a tag.
ALWAYS    reported every second in both profiles: temporal predicates must see every sampled value, including changes smaller
          than a reporting deadband (otherwise a suppressed crossing can fake a hold).
AUX       lite: auxiliary channels on a 30 s heartbeat.
DEADBAND  lite: the other core tags — sent when the value moved by at least this much, else on a 10 s heartbeat.
PLC_STATE the PLC status (plant/{a}/status) is published every wall second, in both profiles.
OBSERVATION_GRACE_S  wall seconds a sample may be late beyond its interval before it counts as missing (detector and agent).
"""
import os

PROFILES = ('lite', 'full')
TAGS = ('TS1', 'TS2', 'TS3', 'TS4', 'PS1', 'PS2', 'PS3', 'PS4', 'PS5', 'PS6', 'EPS1', 'FS1', 'FS2', 'VS1', 'CE', 'CP', 'SE',
        'FanSpeedSP', 'LoadSP')
ALWAYS = frozenset({'TS1', 'CE', 'PS1', 'FS1', 'VS1', 'LoadSP'})
AUX = frozenset({'TS2', 'PS2', 'PS3', 'PS4', 'PS5', 'PS6', 'FS2'})
DEADBAND = {'TS3': .2, 'TS4': .2, 'EPS1': .05, 'CP': .1, 'SE': .5, 'FanSpeedSP': .5}
CORE_HEARTBEAT_S = 10.
AUX_HEARTBEAT_S = 30.
STATUS_INTERVAL_S = 1.
OBSERVATION_GRACE_S = 2.

if (len(TAGS) != len(set(TAGS)) or ALWAYS & AUX or (ALWAYS | AUX) & set(DEADBAND)
        or ALWAYS | AUX | set(DEADBAND) != set(TAGS)):
    raise ValueError('daq_contract: every tag must be in exactly one of ALWAYS · AUX · DEADBAND')


def profile_from_env(env=None):
    """DAQ_PROFILE as compose gives it to plant-sim · detector · agent · dmn-mcp (no code default: one contract for all)."""
    value = (os.environ if env is None else env).get('DAQ_PROFILE')
    if value not in PROFILES:
        raise ValueError(f'DAQ_PROFILE must be lite or full (compose.yaml gives it to this service), got {value!r}')
    return value


def reporting_interval(tag, profile='lite'):
    if profile not in PROFILES:
        raise ValueError('DAQ profile must be lite or full')
    if tag == 'PLC_STATE':
        return STATUS_INTERVAL_S
    if tag not in TAGS:
        raise ValueError(f'{tag}: not a DAQ tag')
    if profile == 'full' or tag in ALWAYS:
        return 1.
    return AUX_HEARTBEAT_S if tag in AUX else CORE_HEARTBEAT_S
