"""업무 시뮬레이터(it/enterprise-sim/entsim/main.py) — 업무 데이터는 Supabase ent 스키마 한 벌, 쓰기는 process 만(하-05)."""
import os

import httpx
import pytest

CALLER = {'X-HYD-Process-Caller': os.environ['PROCESS_CALLER_TOKEN']}
WRITES = [('/api/exec', {'decision': 'D-x', 'option': 'o', 'skill': 'skill:없는-스킬', 'asset': 'HYD-01', 'params': {}}),
          ('/api/reset', {}), ('/api/reanchor', {}), ('/erp/spare/reset', {'part_no': 'P-PMP-SEAL'}), ('/cmms/pm/reset', {})]


@pytest.mark.parametrize('path, body', WRITES)
def test_쓰기_끝점은_process만_아는_값이_없으면_실행하지_않는다(engine_services, path, body):
    for headers in ({}, {'X-HYD-Process-Caller': 'guess'}):
        r = httpx.post(engine_services.ent + path, json=body, headers=headers, timeout=20)
        assert r.status_code == 403 and '사람 승인을 거친 process' in r.json()['detail']


def test_process의_실행_요청은_업무_DB_가_판정한다(engine_services):
    r = httpx.post(engine_services.ent + '/api/exec', json=WRITES[0][1], headers=CALLER, timeout=20)
    assert r.status_code == 400, r.text           # 문지기를 지나 업무 DB(ent.exec_skill)가 없는 스킬을 거절한다


def test_읽기_끝점은_누구나_읽는다(engine_services):
    r = httpx.get(engine_services.ent + '/erp/spare_stock', params={'part': 'P-PMP-SEAL'}, timeout=20)
    assert r.status_code == 200 and r.json()['facts']['part_no'] == 'P-PMP-SEAL'
