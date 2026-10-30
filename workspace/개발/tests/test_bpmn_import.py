"""흐름 그림 가져오기(procsvc/bpmn_import.py) — 학생이 bpmn.io 로 그린 그림을 매핑 · 사전 검사 · 등록 검사까지.

제공 교대 그림(it/process/procsvc/course_handover.json)을 원본으로 쓴다. 카탈로그(부품 · 역할 · 에이전트)는 실제 DB(시드 테넌트 hyd)에서 읽는다.
"""
import json
import re

import pytest

from procsvc import bpmn_import, flows_api
from procsvc.course_policy import HANDOVER



def _check(world, xml, mapping=None):
    parsed = bpmn_import.parse_bpmn(xml)
    catalog = bpmn_import.catalog(flows_api.default_base_loader(world.rt), world.rt.repo.list_users(None, 'hyd'))
    ctx = {'catalog': catalog, 'definition_id': 'ShiftHandover', 'version': '1', 'file_name': 'shift-handover.bpmn',
           'xml_sha256': bpmn_import.xml_sha256(xml), 'name': None}
    return bpmn_import.check(parsed, HANDOVER['mapping'] if mapping is None else mapping, ctx)


def test_제공_그림_그대로는_검사를_통과하고_정의가_된다(world):
    result = _check(world, HANDOVER['xml'])
    assert result['ok'], result['problems']
    assert {a['id'] for a in result['definition']['activities']} >= {'task_draft', 'task_sender', 'task_receiver'}


def test_이름과_배치만_바꾼_그림도_같은_흐름으로_통과한다(world):
    xml = HANDOVER['xml'].replace('name="인계자 검토"', 'name="보내는 사람 검토"').replace('name="인수자 확인"', 'name="받는 사람 확인"')
    xml = re.sub(r'<dc:Bounds x="(\d+)" y="(\d+)"', lambda m: f'<dc:Bounds x="{int(m[1]) + 37}" y="{int(m[2]) + 11}"', xml)
    result = _check(world, xml)
    assert result['ok'], result['problems']
    names = {a['id']: a['name'] for a in result['definition']['activities']}
    assert names['task_sender'] == '보내는 사람 검토' and names['task_receiver'] == '받는 사람 확인'


def _chained_gateway(xml):
    """인계자 승인 뒤에 분기를 하나 더 — 조건 선만 있고 「그 밖의 경우」가 없다(#16)."""
    xml = xml.replace('<bpmn:exclusiveGateway id="gw_sender" name="검토 결정" />',
                      '<bpmn:exclusiveGateway id="gw_sender" name="검토 결정" /><bpmn:exclusiveGateway id="gw_extra" name="긴급 분기" />')
    xml = xml.replace("<bpmn:sequenceFlow id=\"seq_3\" sourceRef=\"gw_sender\" targetRef=\"task_receiver\" name=\"sender_decision == 'approve'\" />",
                      "<bpmn:sequenceFlow id=\"seq_3\" sourceRef=\"gw_sender\" targetRef=\"gw_extra\" name=\"sender_decision == 'approve'\" />"
                      "<bpmn:sequenceFlow id=\"seq_extra\" sourceRef=\"gw_extra\" targetRef=\"task_receiver\" name=\"sender_notes == '긴급'\" />"
                      "<bpmn:sequenceFlow id=\"seq_extra2\" sourceRef=\"gw_extra\" targetRef=\"ev_followup\" name=\"sender_notes == '보통'\" />")
    mapping = json.loads(json.dumps(HANDOVER['mapping']))
    mapping['flows']['seq_extra'] = {'var': 'sender_notes', 'op': '==', 'value': '긴급'}
    mapping['flows']['seq_extra2'] = {'var': 'sender_notes', 'op': '==', 'value': '보통'}
    return xml, mapping


def _cut_receiver(xml):
    return xml.replace("<bpmn:sequenceFlow id=\"seq_3\" sourceRef=\"gw_sender\" targetRef=\"task_receiver\" name=\"sender_decision == 'approve'\" />", ''), None


@pytest.mark.parametrize('change, words', [
    (_cut_receiver, '시작에서 닿지 않습니다'),             # 인수자 확인으로 가는 선을 끊음
    (_chained_gateway, '그 밖의 경우'),                    # #16: 분기 뒤 분기에 기본 선 없음
])
def test_구조를_바꾼_그림은_학생이_읽을_사유와_함께_검사에서_멈춘다(world, change, words):
    xml, mapping = change(HANDOVER['xml'])
    result = _check(world, xml, mapping)
    assert not result['ok']
    reasons = ' '.join(p['reason'] for p in result['problems'])
    assert words in reasons and re.search('[가-힣]', reasons), reasons


@pytest.mark.parametrize('xml, words', [
    (HANDOVER['xml'][:5000], '행'),                                       # 잘린 파일
    ('<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"><bpmn:process id="p">', '행'),
    ('', '빈 파일'),
    ('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x/>', 'DOCTYPE'),
])
def test_깨진_XML은_위치와_할_일을_말하고_파서_영문을_보이지_않는다(xml, words):
    with pytest.raises(bpmn_import.BpmnError) as caught:
        bpmn_import.parse_bpmn(xml)
    message = str(caught.value)
    assert words in message and 'unclosed' not in message and 'not well-formed' not in message
