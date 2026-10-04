"""Version-owned form contracts shared by the engine, API, and CLI worker."""
from copy import deepcopy
import math

FIELD_TYPES = {'text', 'textarea', 'number', 'integer', 'boolean', 'select', 'object', 'array'}


def choices(field):
    values = []
    for item in field.get('items') or []:
        if isinstance(item, dict):
            values.extend(item.keys())
        else:
            values.append(item)
    return values


def validate_fields(fields):
    if not isinstance(fields, list):
        raise ValueError('fields_json은 목록이어야 합니다')
    keys = []
    for f in fields:
        if not isinstance(f, dict) or not isinstance(f.get('key'), str) or not f['key'].strip():
            raise ValueError('폼 필드 key가 필요합니다')
        if f.get('type') not in FIELD_TYPES:
            raise ValueError(f"지원하지 않는 폼 타입: {f.get('type')}")
        if f['key'] in {'__proto__','prototype','constructor'}:
            raise ValueError('예약된 폼 필드 key입니다')
        if 'required' in f and not isinstance(f['required'], bool):
            raise ValueError('required는 boolean이어야 합니다')
        if f['type'] == 'select':
            items=f.get('items')
            if not isinstance(items,list) or not items or any(not isinstance(i,(str,dict)) for i in items):
                raise ValueError('select items는 문자열 또는 값:표시명 객체 목록이어야 합니다')
            if any(not isinstance(v,str) or not v for v in choices(f)) or not choices(f):
                raise ValueError('select 선택값은 비어 있지 않은 문자열이어야 합니다')
        keys.append(f['key'])
    if len(keys) != len(set(keys)):
        raise ValueError('폼 필드 key가 중복됩니다')


def pinned_form(definition, tool):
    """None means a pre-contract definition. A declared but missing form is an error."""
    if not str(tool).startswith('formHandler:') or 'forms' not in definition:
        return None
    fid = tool.split(':', 1)[1]
    form = definition['forms'].get(fid)
    if not isinstance(form, dict):
        raise ValueError(f'정의 버전 안에 폼이 없습니다: {fid}')
    return dict(deepcopy(form), id=fid)


def validate_output(form, output):
    if not isinstance(output, dict):
        raise ValueError('폼 결과는 JSON 객체여야 합니다')
    for f in form.get('fields_json') or []:
        key, kind = f['key'], f['type']
        value = output.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            if f.get('required', True):
                raise ValueError(f'필수 폼 필드가 비어 있습니다: {key}')
            continue
        valid = {'text': lambda: isinstance(value, str), 'textarea': lambda: isinstance(value, str),
                 'number': lambda: type(value) in (float, int) and math.isfinite(value),
                 'integer': lambda: type(value) is int, 'boolean': lambda: type(value) is bool,
                 'select': lambda: value in choices(f), 'object': lambda: isinstance(value, dict),
                 'array': lambda: isinstance(value, list)}[kind]()
        if not valid:
            raise ValueError(f'폼 필드 타입/선택값이 맞지 않습니다: {key} ({kind})')
