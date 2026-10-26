import json
from pathlib import Path

from procsvc import bpmn_import as B
from procsvc.definition_registry import validate_definition

ROOT = Path(__file__).parents[1]/'it/process/definitions'


def test_student_bpmn_maps_to_handover_contracts_and_distinct_people():
    base = json.loads((ROOT/'anomaly_response_v22.json').read_text(encoding='utf8'))
    users = [dict(id='agent:handover', username='인계 에이전트', is_agent=True, agent_type='agent', tools='neo4j,enterprise,hyd-dmn')]
    cat = B.catalog(base, users)
    xml = (ROOT/'shift_handover.bpmn').read_text(encoding='utf8')
    parsed = B.parse_bpmn(xml)
    mapping = json.loads((ROOT/'shift_handover.mapping.json').read_text(encoding='utf8'))
    report = B.check(parsed, mapping, dict(catalog=cat, definition_id='student_shift_handover', version='1', file_name='shift_handover.bpmn', xml_sha256=B.xml_sha256(xml)))
    assert report['ok'], report['problems']
    definition = validate_definition(report['definition']).raw
    assert {f['contract'] for f in definition['forms'].values()} == {
        'shift-handover-draft-v1', 'shift-handover-sender-v1', 'shift-handover-receiver-v1'}
    assert definition['startForm']['fields_json'] == mapping['start']['fields']
    assert len(definition['activities']) == 9 and not definition.get('alertPolicy')
    assert all(a['type'] == 'userTask' for a in definition['activities'])
    roles = {r['name']: r['endpoint'] for r in definition['roles']}
    assert roles['인계자'] == 'user:kim-op' and roles['인수자'] == 'user:choi-op'
