"""Per-source validity. Time is wall/event seconds, not accelerated process time.

Evaluation reads each input as of the evaluation time (`at_time`): the last sample, or — when that one is later than the
evaluation time — the valid sample it replaced. Tags and PLC status arrive on two topics with no order between them, so a
detector that fell a second behind can process the status of tick t+1 before the TS1 of tick t; that newer status is not a
"future" value to refuse, the state at t is simply the one before it (전수검사 06-4: every such tick interrupted the hold).
"""
import math

from hydcommon.daq_contract import reporting_interval


class Observations:
    def __init__(self, profile, grace_s):
        reporting_interval('TS1', profile)
        if not math.isfinite(grace_s) or grace_s < 0:
            raise ValueError('Observation grace must be finite and nonnegative')
        self.profile, self.grace_s = profile, grace_s
        self.samples = {}
        self.replaced = {}      # name -> the valid sample that samples[name] replaced (one step back, for at_time)

    def limit(self, name):
        return reporting_interval(name, self.profile) + self.grace_s

    def invalidate(self, name, reason):
        old = self.samples.get(name, {'time': None, 'value': None})
        self.samples[name] = dict(old, valid=False, reason=reason)
        self.replaced.pop(name, None)

    def record(self, name, at, value, quality='good'):
        old = self.samples.get(name)
        if old and old['time'] is not None:
            if at < old['time']:
                return 'ignored', False
            if at == old['time']:
                if value == old['value'] and quality == old.get('quality'):
                    return 'ignored', False
                self.invalidate(name, 'CONFLICTING_TIMESTAMP')
                return 'invalid', False
        valid = (quality == 'good' and (value in ('RUN', 'STOP', 'TRIP') if name == 'PLC_STATE'
                 else type(value) in (float, int) and math.isfinite(value)))
        gap = bool(old and old['time'] is not None and at - old['time'] > self.limit(name))
        if valid and old and old.get('valid') and not gap:
            self.replaced[name] = old
        else:
            self.replaced.pop(name, None)
        self.samples[name] = dict(time=at, value=value if valid else None, valid=valid, quality=str(quality),
                                  reason=None if valid else 'INVALID_VALUE_OR_QUALITY')
        return 'valid' if valid else 'invalid', gap

    def at_time(self, name, at):
        """The sample that was current at event time `at` (module docstring): the last one, or the valid one it replaced when
        the last one is later than `at`. None when the tag was never seen."""
        sample = self.samples.get(name)
        if sample and sample['time'] is not None and at < sample['time']:
            before = self.replaced.get(name)
            if before and before['time'] <= at:
                return before
        return sample

    def problems(self, names, at, now):
        out = {}
        for name in names:
            sample = self.at_time(name, at)
            if not sample or sample['time'] is None:
                out[name] = 'MISSING'
            elif not sample['valid']:
                out[name] = sample['reason']
            elif at < sample['time'] or now < sample['time'] - self.grace_s:
                out[name] = 'FUTURE_TIMESTAMP'
            elif max(at - sample['time'], now - sample['time']) > self.limit(name):
                out[name] = 'STALE'
        return out

    def view(self, now):
        return {name: dict(sample, age_wall_s=None if sample['time'] is None else round(now - sample['time'], 3),
                           max_age_wall_s=self.limit(name)) for name, sample in self.samples.items()}
