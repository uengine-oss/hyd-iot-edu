"""A100 — parallel gateway: a split starts every branch at once, a join waits for every branch (process-gpt-completion
check_task_status). Driven exactly like the runtime drives the engine (test_engine.World), plus the registry contract."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from procsvc import engine, definition_registry

NOW = datetime(2026, 10, 7, 15, 0, tzinfo=timezone.utc)


def definition():
    form = lambda key: {'fields_json': [{'key': key, 'type': 'text', 'text': key}]}
    return {'processDefinitionId': 'par', 'processDefinitionName': '병렬', 'version': '1',
            'roles': [{'name': '운전원', 'endpoint': 'role:operator'}],
            'data': [{'name': 'a_out', 'type': 'Text'}, {'name': 'b_out', 'type': 'Text'}, {'name': 'c_out', 'type': 'Text'}],
            'forms': {'fa': form('a_out'), 'fb': form('b_out'), 'fc': form('c_out')},
            'activities': [{'id': 'a', 'name': '작업지시 발행', 'type': 'userTask', 'role': '운전원', 'tool': 'formHandler:fa', 'outputData': ['a_out']},
                           {'id': 'b', 'name': '제어 명령', 'type': 'userTask', 'role': '운전원', 'tool': 'formHandler:fb', 'outputData': ['b_out']},
                           {'id': 'c', 'name': '결과 확인', 'type': 'userTask', 'role': '운전원', 'tool': 'formHandler:fc', 'outputData': ['c_out']}],
            'events': [{'id': 'start', 'type': 'startEvent'}, {'id': 'end', 'type': 'endEvent'}],
            'gateways': [{'id': 'split', 'type': 'parallelGateway'}, {'id': 'join', 'type': 'parallelGateway'}],
            'sequences': [{'id': 's0', 'source': 'start', 'target': 'split'},
                          {'id': 's1', 'source': 'split', 'target': 'a'}, {'id': 's2', 'source': 'split', 'target': 'b'},
                          {'id': 's3', 'source': 'a', 'target': 'join'}, {'id': 's4', 'source': 'b', 'target': 'join'},
                          {'id': 's5', 'source': 'join', 'target': 'c'}, {'id': 's6', 'source': 'c', 'target': 'end'}]}


class World:
    def __init__(self, defn):
        self.defn = defn
        self.inst = engine.new_instance(defn, {}, now=NOW)
        self.rows = []
        self.apply(engine.start(defn, self.inst, now=NOW))

    def apply(self, adv):
        for r in adv.created:
            if r not in self.rows:
                self.rows.append(r)
        return adv

    def row(self, aid):
        rows = [r for r in self.rows if r['activity_id'] == aid]
        return rows[-1] if rows else None

    def turn_in(self, aid, output):
        row = self.row(aid)
        engine.submit(self.defn, self.inst, row, output, now=NOW)
        return self.apply(engine.process_submitted(self.defn, self.inst, row, self.rows, now=NOW))

    def status(self):
        return {r['activity_id']: r['status'] for r in self.rows}


def test_split_starts_both_branches_and_join_waits_for_the_last_one():
    defn = definition_registry.validate_definition(definition())
    w = World(defn)
    assert w.status()['a'] == 'IN_PROGRESS' and w.status()['b'] == 'IN_PROGRESS' and w.status()['c'] == 'TODO'
    adv = w.turn_in('a', {'a_out': 'wo-1'})
    assert w.row('a')['status'] == 'DONE' and w.row('c')['status'] == 'TODO' and adv.waiting_joins == ['join']    # first arrival waits
    assert w.inst['status'] == 'RUNNING'
    adv = w.turn_in('b', {'b_out': 'ok'})
    assert 'join' in adv.visited and adv.waiting_joins == [] and w.row('c')['status'] == 'IN_PROGRESS'            # last arrival fires
    w.turn_in('c', {'c_out': 'done'})
    assert w.inst['status'] == 'COMPLETED' and w.inst['end_event'] == 'end'
    assert engine.variables(w.inst)['a_out'] == 'wo-1' and engine.variables(w.inst)['b_out'] == 'ok'


def test_join_fires_again_only_after_a_reworked_branch_finishes_again():
    """Readiness is read from the rows: a fresh (re-entered) row of one branch must be DONE again, the other branch's DONE row still counts."""
    defn = engine.Definition.from_dict(definition())
    w = World(defn)
    w.turn_in('a', {'a_out': '1'}); w.turn_in('b', {'b_out': '1'})
    assert w.row('c')['status'] == 'IN_PROGRESS'
    fresh = engine.new_workitem(defn, w.inst, defn.activities['a'], NOW)        # the rework runtime re-enters the branch with a new row
    w.rows.append(fresh); engine.reach(defn, w.inst, fresh, w.rows, NOW, 1.0)
    assert not engine._join_ready(defn, 'join', w.rows)                            # latest a row is live → the join is not ready
    engine.submit(defn, w.inst, fresh, {'a_out': '2'}, now=NOW)
    adv = w.apply(engine.process_submitted(defn, w.inst, fresh, w.rows, now=NOW))
    assert 'join' in adv.visited and engine.variables(w.inst)['a_out'] == '2'


@pytest.mark.parametrize('change', [
    lambda d: d['sequences'][1].update(condition='a_out == "x"'),                                              # conditioned parallel split
    lambda d: (d['gateways'].append({'id': 'x', 'type': 'exclusiveGateway'}), d['sequences'][3].update(target='x'),
               d['sequences'].append({'id': 's7', 'source': 'x', 'target': 'join'})),                            # gateway feeding the join
    lambda d: d['gateways'][0].update(type='inclusiveGateway'),                                                  # not supported at registration
])
def test_registry_refuses_parallel_shapes_the_engine_does_not_guarantee(change):
    d = definition(); change(d)
    with pytest.raises(ValueError):
        definition_registry.validate_definition(d)
