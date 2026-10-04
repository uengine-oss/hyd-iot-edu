"""Definition-driven held patterns; source adapter and delivery are separate concerns."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import math

from . import cep
from .features import SlopeWindow
from .observations import Observations
from .patterns import Pattern, compile_catalog, compile_pattern


@dataclass
class Run:
    definition: Pattern
    state: cep.CepState = field(default_factory=cep.CepState)
    quality: dict = field(default_factory=dict)


@dataclass
class Asset:
    observations: Observations
    runs: dict = field(default_factory=dict)
    windows: dict = field(default_factory=dict)


class PatternRuntime:
    """Explicit catalog replacement, TS1 evaluation clock, no last-value interpolation.

    Candidate holds restart on revision change. Raised alerts keep their original
    definition until CLEAR, including when that definition is removed from the catalog.
    Invalid catalog replacements fail atomically, leaving the applied catalog unchanged.
    """
    def __init__(self, rows, profile='lite', time_scale=20., grace_s=2.):
        Observations(profile, grace_s)  # validate before accepting any catalog
        self.profile, self.time_scale, self.grace_s = profile, time_scale, grace_s
        self.catalog = compile_catalog(rows, profile, time_scale)
        self.assets = {}
        self.source_ready = True

    def replace(self, rows):
        validated = compile_catalog(rows, self.profile, self.time_scale)
        self.catalog = validated
        self.source_ready = True

    def source_failed(self):
        self.source_ready = False
        for asset in self.assets.values():
            for run in asset.runs.values():
                if run.state.phase not in ('RAISED', 'CLEARING'):
                    cep.interrupt(run.state)

    def invalidate(self, asset_id, name, reason):
        asset = self.assets.setdefault(asset_id, Asset(Observations(self.profile, self.grace_s)))
        self._sync(asset)
        asset.observations.invalidate(name, reason)
        for run in asset.runs.values():
            if name in run.definition.inputs | {'TS1'}:
                cep.interrupt(run.state)
                run.quality = {'status': 'UNKNOWN', 'problems': {name: reason}}
        for (tag, _), window in asset.windows.items():
            if name == tag or name == 'TS1':window.pts.clear()

    def snapshot(self):
        return dict(profile=self.profile, time_scale=self.time_scale, grace_s=self.grace_s,
                    catalog=[p.source() for p in self.catalog.values()],
                    assets={asset_id: {code: dict(definition=run.definition.source(), state=asdict(run.state))
                                      for code, run in asset.runs.items()} for asset_id, asset in self.assets.items()})

    @classmethod
    def restore(cls, data):
        runtime = cls(data['catalog'], data['profile'], data['time_scale'], data['grace_s'])
        runtime.source_ready = False  # recheck source; retain raised alerts while disconnected
        for asset_id, runs in data['assets'].items():
            asset = Asset(Observations(runtime.profile, runtime.grace_s))
            for code, item in runs.items():
                definition = compile_pattern(item['definition'])
                definition.validate_reporting(runtime.profile, runtime.time_scale)
                if code != definition.code:raise ValueError('persisted code mismatch')
                state = cep.CepState(**item['state'])
                cep.interrupt(state)  # no unobserved downtime may count toward either hold
                state.last_t = None
                asset.runs[code] = Run(definition, state)
            runtime.assets[asset_id] = asset
            runtime._sync(asset)
        return runtime

    def _sync(self, asset):
        for code, run in list(asset.runs.items()):
            new = self.catalog.get(code)
            if run.state.phase in ('RAISED', 'CLEARING'):
                continue
            if new is None:
                del asset.runs[code]
            elif new.revision != run.definition.revision:
                # Keep the sequence counter, never transfer the old candidate's elapsed hold.
                asset.runs[code] = Run(new, cep.CepState(seq=run.state.seq))
        for code, definition in self.catalog.items():
            asset.runs.setdefault(code, Run(definition))
        required = {(tag, run.definition.slope_window) for run in asset.runs.values() for tag in run.definition.slopes}
        asset.windows = {key: asset.windows.get(key, SlopeWindow(key[1])) for key in required}

    def observe(self, asset_id, name, value, at, quality='good', now=None):
        """Accept event seconds (UTC epoch); returns zero or more real state transitions."""
        if type(at) not in (int, float) or not math.isfinite(at):
            raise ValueError('event timestamp must be finite seconds')
        now = at if now is None else now
        if type(now) not in (int, float) or not math.isfinite(now):
            raise ValueError('wall timestamp must be finite seconds')
        asset = self.assets.setdefault(asset_id, Asset(Observations(self.profile, self.grace_s)))
        self._sync(asset)
        old = asset.observations.samples.get(name)
        if old and old['time'] is not None and at < old['time']:
            return []
        if at > now + self.grace_s:
            asset.observations.invalidate(name, 'FUTURE_TIMESTAMP')
            status, gap = 'invalid', False
        else:
            status, gap = asset.observations.record(name, at, value, quality)
        if status == 'ignored':
            return []
        if gap or status == 'invalid':
            for run in asset.runs.values():
                if name in run.definition.inputs | {'TS1'}:
                    cep.interrupt(run.state)
                    run.quality = {'status': 'UNKNOWN', 'problems': {name: 'OBSERVATION_GAP' if gap else 'INVALID_INPUT'}}
            for (tag, _), window in asset.windows.items():
                if name == tag or name == 'TS1':
                    window.pts.clear()
        if status == 'invalid':
            return []
        for (tag, _), window in asset.windows.items():
            if tag == name:
                window.push(at*self.time_scale, value)
        if name != 'TS1':
            return []
        for window in asset.windows.values():
            window.trim(at*self.time_scale)
        events = []
        for code, run in asset.runs.items():
            definition = run.definition
            if not self.source_ready and run.state.phase not in ('RAISED', 'CLEARING'):
                run.quality = {'status': 'UNKNOWN', 'problems': {'definition': 'SOURCE_UNAVAILABLE'}, 'evaluated_at': at}
                continue
            inputs = definition.inputs | {'TS1'}
            problems = asset.observations.problems(inputs, at, now)
            for tag in definition.slopes:
                if len(asset.windows[(tag, definition.slope_window)].pts) < 2:
                    problems[f'slope({tag})'] = 'INSUFFICIENT_WINDOW'
            run.quality = {'status': 'UNKNOWN' if problems else 'VALID', 'problems': problems, 'evaluated_at': at}
            if problems:
                cep.interrupt(run.state)
                continue
            values = {tag: asset.observations.samples[tag]['value'] for tag in inputs}
            slopes = {tag: asset.windows[(tag, definition.slope_window)].slope() for tag in definition.slopes}
            cond, clear = definition.rule.evaluate(values, slopes), definition.clear.evaluate(values, slopes)
            if cond and clear:
                cep.interrupt(run.state)
                run.quality = {'status': 'UNKNOWN', 'problems': {'definition': 'CONFLICTING_RAISE_CLEAR'}, 'evaluated_at': at}
                continue
            evidence = dict(definition=definition.describe(), values=values, slopes=slopes,
                            condition=cond, clear_condition=clear,
                            observation=dict(hold_clock='simulated_seconds', time_scale=self.time_scale,
                                             profile=self.profile, grace_wall_s=self.grace_s,
                                             ages_wall_s={tag: at-asset.observations.samples[tag]['time'] for tag in inputs}))
            hold = definition.clear_hold if run.state.phase in ('RAISED', 'CLEARING') else definition.hold
            event = cep._step(run.state, asset_id, at*self.time_scale, code, definition.severity,
                              cond, clear, hold, datetime.fromtimestamp(at, timezone.utc).isoformat(), evidence,
                              max_gap_s=asset.observations.limit('TS1')*self.time_scale)
            if event:
                events.append(event)
        return events

    def describe(self):
        return {'source_ready': self.source_ready, 'catalog': {code: p.describe() for code, p in self.catalog.items()},
                'assets': {asset: {code: dict(phase=r.state.phase, alert_id=r.state.alert_id,
                                             revision=r.definition.revision, quality=r.quality)
                                   for code, r in state.runs.items()} for asset, state in self.assets.items()}}
