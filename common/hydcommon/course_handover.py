"""The shipped handover is the only editable classroom flow contract."""
from copy import deepcopy
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

CONTENT = json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf8'))
DEFINITION = 'ShiftHandover'
DRAFTS = {'task_draft', 'task_draft_r2', 'task_draft_r3'}
BPMN = '{http://www.omg.org/spec/BPMN/20100524/MODEL}'


def skeleton(xml):
    if not isinstance(xml, str) or len(xml) > 200000 or '<!' in xml:
        raise ValueError('unsupported XML')
    root = ET.fromstring(xml)
    processes = root.findall(BPMN+'process')
    if len(processes) != 1 or any(e.tag.startswith(BPMN) and e is not processes[0] for e in root):
        raise ValueError('one approved process required')
    def node(e):
        return (e.tag, tuple(sorted((k,v) for k,v in e.attrib.items() if k != 'name')),
                (e.text or '').strip(), tuple(node(child) for child in e))
    return node(processes[0])


def approved_xml(xml):
    try:
        return skeleton(xml) == skeleton(CONTENT['xml'])
    except (ValueError, TypeError, ET.ParseError):
        return False


def approved_mapping(mapping):
    if not isinstance(mapping, dict):return False
    value = deepcopy(mapping)
    if not isinstance(value.get('name'),str) or not 1 <= len(value['name']) <= 160:return False
    if not isinstance(value.get('tasks'),dict):return False
    value['name'] = CONTENT['mapping']['name']
    for task in DRAFTS:
        item = (value.get('tasks') or {}).get(task)
        if not isinstance(item,dict) or not re.fullmatch(r'agent:[A-Za-z0-9_.-]{1,80}',str(item.get('agent',''))):return False
        item['agent'] = CONTENT['mapping']['tasks'][task]['agent']
    return value == CONTENT['mapping']


def allowed_request(method, path, body):
    if path == '/api/flows/import':
        return (method == 'POST' and set(body) <= {'xml','file_name','definition_id','start_patterns','class_flow'}
            and body.get('definition_id',DEFINITION) == DEFINITION and not body.get('class_flow')
            and body.get('start_patterns') in (None,[]) and approved_xml(body.get('xml')))
    match = re.fullmatch(r'/api/flows/ShiftHandover/(mapping|check|register)',path)
    return bool(match and method == ('PUT' if match[1]=='mapping' else 'POST')
        and set(body) <= {'mapping','class_flow'} and not body.get('class_flow')
        and approved_mapping(body.get('mapping')))
