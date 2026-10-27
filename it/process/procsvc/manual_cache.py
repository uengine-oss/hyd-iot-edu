"""Exact extraction reuse; the process DB remains the single source of truth.

PostgreSQL 15 explicit-locking.html: the existing event_transaction uses a
transaction-level advisory lock only while creating the instance/work items.
No lock or database transaction spans AI work. Duplicate callers join the same
durable event. Cache-Aside does not ensure freshness: all source/configuration
revisions are explicit keys; mutable plant judgments never use this module.

Authorization must precede this layer. `scope` and `profile` are supplied by the
instructor authority, never copied from an extraction request body.
"""
import hashlib
import json
from copy import deepcopy

from . import engine, manual_extraction


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def source_fingerprint(source):
    return _digest({key: source.get(key) for key in ('sha256', 'extractor', 'media_type', 'pages')})


def identity(tenant, source, catalog, *, scope, profile, feedback=None):
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError('강사 서버의 승인 범위 판본이 필요합니다')
    if not isinstance(profile, dict) or not profile.get('model') or not profile.get('revision'):
        raise ValueError('강사 서버의 추출 모델·설정 판본이 필요합니다')
    return _digest(dict(contract='hyd-extraction-cache-v1', tenant=tenant, scope=scope,
                        source=source['sha256'], extractor=source.get('extractor'),
                        media_type=source.get('media_type'), pages=source['pages'],
                        definition=manual_extraction.definition(), catalog=catalog,
                        segments=manual_extraction.manual_segments.segments(source),
                        profile=profile, feedback=manual_extraction.validate_review_feedback(feedback)))


def start(rt, source, request_id, catalog, *, scope, profile, feedback=None, execution_run_id=None):
    key = identity(rt.tenant_id, source, catalog, scope=scope, profile=profile, feedback=feedback)
    inst = manual_extraction.start(rt, source, request_id, review_feedback=feedback,
                                   catalog=catalog, cache_identity=key, execution_run_id=execution_run_id)
    # A failed or in-flight work item is not a successful cache result. We do
    # not mint another request ID and spend again when it failed. Instructor
    # authorization of a new profile revision is required for a fresh attempt.
    _, state = manual_extraction._task_state(rt, inst)
    return dict(instance=inst['proc_inst_id'], status=state['status'],
                source_id=source['source_id'], cache=dict(key=key, reused=inst['cache_reused'],
                                                        validated=False),
                segments=(engine.variables(inst).get('segment') or {}).get('total', 1))


def result(rt, archive, source, pid, previous_batch):
    inst = rt.repo.get_instance(pid)
    if not inst or inst.get('tenant_id') != rt.tenant_id:
        raise KeyError('해당 문서 추출 작업이 없습니다')
    variables = engine.variables(inst)
    cache = variables.get('extraction_cache')
    if not cache:
        return manual_extraction.result(rt, source, pid, previous_batch)
    original = archive.get(rt.tenant_id, cache['source_id'])
    # A content hash alone is not enough if the parser or extracted text changed.
    for field in ('sha256', 'extractor', 'media_type', 'pages'):
        if original.get(field) != source.get(field):
            raise ValueError('캐시 원문·파서 판본이 요청 문서와 다릅니다')
    value = manual_extraction.result(rt, original, pid, previous_batch)
    value['cache'] = dict(key=cache['key'], stored=True, validated=False)
    preview = value.get('preview')
    if value['status'] != 'DONE' or not preview:
        return value
    issues = manual_extraction.content_issues(preview, original, variables.get('ontology_catalog'),
                                             criteria_scope=manual_extraction._criteria_contract(inst))
    if issues:
        raise ValueError('저장된 추출 결과가 검증되지 않았습니다 — ' + ' / '.join(issues))
    # Only source citations change when identical approved bytes were uploaded
    # under another filename/document. No graph head or human approval is reused.
    def rebind(item):
        if isinstance(item, dict):
            return {k: source['source_id'] if k == 'source_id' and v == original['source_id'] else rebind(v)
                    for k, v in item.items()}
        if isinstance(item, list):
            return [rebind(v) for v in item]
        return deepcopy(item)
    preview = rebind(preview)
    preview.update(document_id=source['document_id'], filename=source['filename'], previous_batch=previous_batch)
    value['preview'] = preview
    value['cache']['validated'] = True
    origin = cache.get('approved_origin')
    if origin:
        value['cache']['origin'] = deepcopy(origin)
    preview['extraction']['cache'] = deepcopy(value['cache'])
    return value
