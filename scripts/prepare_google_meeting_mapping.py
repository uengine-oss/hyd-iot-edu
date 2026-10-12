"""Prepare an explicit Google-server copy; never call Google or the portal.

The copy can pass structural import. Registration, agent tools, Google access,
and approval of real inputs remain separate checks, described in preconditions.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'students/_template/example_meeting'
CONTRACT = ROOT / 'students/_template/google_meeting_mcp/meeting-contract.json'

CONTEXT_FIELDS = (
    ('meeting_calendar_id', 'text', '명시 선택한 실제 일정 캘린더 ID'),
    ('meeting_title', 'text', '동일 요청의 실제 회의 제목'),
    ('meeting_duration_min', 'number', '동일 요청의 실제 회의 시간(분)'),
    ('meeting_time_zone', 'text', '실제 IANA 시간대'),
    ('meeting_attendees', 'array', '동일 요청의 실제 참석자 [{email,required}]'),
    ('meeting_required_emails', 'array', '동일 요청에서 required=true인 실제 이메일 목록'),
    ('meeting_room_resources', 'object', '실제 room_id → 자원 캘린더 이메일 사전'),
    ('meeting_attachments', 'array', '접근 확인한 실제 Google 문서 [{title,file_url}]'),
)


def explicit(value, label):
    if not isinstance(value, str) or not value.strip() or '<' in value or '>' in value:
        raise ValueError(f'{label}: 명시적인 등록 값을 입력하세요')
    return value.strip()


def prepare(*, agent_id, organizer_role, calendar_server, drive_server):
    """Return independent JSON values, without asserting registration or access."""
    values = {k: explicit(v, k) for k, v in locals().items()}
    if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9:_-]*', values[k])
           for k in ('calendar_server', 'drive_server')):
        raise ValueError('서버는 실제 등록 이름이어야 합니다')
    original = json.loads((EXAMPLE / 'mapping.json').read_text(encoding='utf-8'))
    mapping = deepcopy(original)
    contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
    mapping['_comment'] = 'Google 서버 계약에 맞춘 사본. 구조 검사와 실제 계정/자료/승인 실행은 별도이다.'
    mapping['lanes']['Lane_organizer'] = values['organizer_role']
    mapping['start']['fields'] += [dict(key=k, type=t, text=label, required=True)
                                   for k, t, label in CONTEXT_FIELDS]
    tasks = mapping['tasks']
    proposal = tasks['Activity_propose']
    proposal['agent'] = values['agent_id']
    proposal['inputs'] += [k for k, _, _ in CONTEXT_FIELDS]
    proposal['instruction'] += (
        f" 실제 읽기 도구는 {values['drive_server']}.search_files/read_file와 "
        f"{values['calendar_server']}.free_busy/get_event이다. 등록 agent에 해당 읽기 도구가 필요하다. "
        '추가 시작값은 같은 request_id의 검증된 업무 원천이다. 실제 room_id는 '
        'meeting_room_resources에 등록된 주소만 쓰고 후보에 room/room_email을 함께 보존한다. '
        '각 후보의 slot은 오프셋 있는 RFC3339이며 end는 실제 meeting_duration_min 뒤 시각이다. '
        'slot/reason/score와 기존 승인 카드 필드를 보존한다. proposal.docs는 실제 '
        'meeting_attachments의 title/file_url을 title/link로 표시하며 첨부와 다른 문서를 '
        '승인 카드에 표시하지 않는다. 읽지 못한 자료·빈 시간은 '
        '추정하지 말고 보류한다. 참석자와 문서 접근은 실제 조회로 확인한다. 일정 생성은 하지 않는다.'
    )
    tasks['Activity_approve']['inputs'] += [k for k, _, _ in CONTEXT_FIELDS]
    for activity in ('Activity_invite', 'Activity_check'):
        binding = contract[activity]
        cfg = tasks[activity]['config']
        cfg['server'] = values['calendar_server']
        cfg['tool'] = binding['tool']
        cfg['arguments'] = deepcopy(binding['arguments'])
        cfg['extract'] = deepcopy(binding['extract'])
        tasks[activity]['inputs'] += [k for k, _, _ in CONTEXT_FIELDS
                                     if k not in tasks[activity]['inputs']]
    # Actual instance:workitem key is injected by call_effect after tools/list.
    # A caller-supplied request-only key must never shadow that runtime key.
    tasks['Activity_invite']['config']['arguments'].pop('idempotency_key', None)
    tasks['Activity_check']['config']['effect'] = False
    requirements = dict(
        purpose='structural mapping preparation; not Google execution evidence',
        google_read_verified=False, execution_ready=False, registration_verified=False,
        names=values, required_start_fields=[k for k, _, _ in CONTEXT_FIELDS],
        approved_option_fields=['slot', 'end', 'room', 'room_email', 'reason', 'score'],
        idempotency='process instance:workitem injected by mcp_check.call_effect',
        additional_checks=[
            '실제 등록 agent/사람 역할/두 MCP 서버와 agent 읽기 도구를 확인한다.',
            'Google OAuth와 실제 자료/필수 참석자/회의실 읽기 접근을 확인한다.',
            '같은 요청의 명단·필수 여부·실제 회의실·기간·첨부 출처를 확인한다.',
            'validate_runtime는 독립 사전검사이며 흐름에 자동 설치되는 task가 아니다.',
            '주관자 승인 뒤에만 허용 캘린더에서 일정 생성/초대를 실행한다.',
            '승인 반려/지연은 생성 호출 없이 끝나며 실제 응답을 재조회한다.',
        ],
        original_sha256={name: hashlib.sha256((EXAMPLE / name).read_bytes()).hexdigest()
                         for name in ('mapping.json', 'flow.bpmn')},
    )
    return mapping, requirements


def validate_runtime(context, approved_option, *, execution_key, proposal):
    """Validate supplied inputs locally; never certify their real-world provenance.

    Uses the actual Google server's field validators. No OAuth or API object is
    created. Returned arguments are a read-only preview, not an executed result.
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from students._template.google_meeting_mcp.server import Attendee, Attachment, email, interval
    if not isinstance(context, dict) or not isinstance(approved_option, dict):
        raise ValueError('실제 회의 context와 승인한 후보 객체가 필요합니다')
    for key in ('request_id',) + tuple(k for k, _, _ in CONTEXT_FIELDS):
        if key not in context or context[key] is None:
            raise ValueError('실제 회의 필수 입력이 없습니다: ' + key)
    for key in ('request_id', 'meeting_calendar_id', 'meeting_title', 'meeting_time_zone'):
        explicit(context[key], key)
    for key in ('slot', 'end', 'room', 'room_email'):
        explicit(approved_option.get(key), key)
    duration = context['meeting_duration_min']
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
        raise ValueError('동일 요청의 실제 회의 기간이 필요합니다')
    interval(approved_option['slot'], approved_option['end'], context['meeting_time_zone'])
    stamps = [datetime.fromisoformat(approved_option[k].replace('Z', '+00:00')) for k in ('slot', 'end')]
    if (stamps[1] - stamps[0]).total_seconds() != duration * 60:
        raise ValueError('승인 후보의 종료 시각과 실제 회의 기간이 다릅니다')
    rooms = context['meeting_room_resources']
    if not isinstance(rooms, dict) or rooms.get(approved_option['room']) != approved_option['room_email']:
        raise ValueError('승인 후보의 회의실이 실제 등록 자원 주소와 다릅니다')
    room = email(approved_option['room_email'])
    roster = context['meeting_attendees']
    if not isinstance(roster, list) or not roster or len(roster) > 49:
        raise ValueError('동일 요청의 실제 참석자 명단이 필요합니다')
    if any(not isinstance(a, dict) or type(a.get('required')) is not bool for a in roster):
        raise ValueError('참석자 필수 여부는 원천의 명시 Boolean이어야 합니다')
    attendees = [Attendee.model_validate(a) for a in roster]
    addresses = [a.email for a in attendees]
    required = [a.email for a in attendees if a.required]
    supplied = context['meeting_required_emails']
    if (not isinstance(supplied, list) or not required or len(set(addresses)) != len(addresses)
            or room in addresses or len(supplied) != len(required)
            or {email(e) for e in supplied} != set(required)):
        raise ValueError('필수 명단과 동일 요청 참석자 원천이 일치하지 않습니다')
    raw_attachments = context['meeting_attachments']
    if not isinstance(raw_attachments, list) or len(raw_attachments) > 25:
        raise ValueError('실제 Google 첨부 목록이 필요합니다')
    attachments = [Attachment.model_validate(a) for a in raw_attachments]
    for attachment in attachments:
        url = urlparse(attachment.file_url)
        if not (re.search(r'/d/[^/\s]+', url.path) or parse_qs(url.query).get('id')):
            raise ValueError('Google 홈페이지 대신 실제 파일을 식별하는 첨부 링크가 필요합니다')
    if len({a.file_url for a in attachments}) != len(attachments):
        raise ValueError('실제 Google 첨부가 중복되었습니다')
    if not isinstance(proposal, dict) or not isinstance(proposal.get('options'), list):
        raise ValueError('실제 검토한 제안과 후보 목록이 필요합니다')
    options = proposal['options']
    slots = [a.get('slot') for a in options if isinstance(a, dict)]
    if (len(slots) != len(options) or any(not isinstance(s, str) or not s.strip() for s in slots)
            or len(set(slots)) != len(slots) or approved_option not in options):
        raise ValueError('승인 후보는 실제 제안의 고유한 원안이어야 합니다')
    expected_docs = [dict(title=a.title, link=a.file_url) for a in attachments]
    if proposal.get('docs') != expected_docs:
        raise ValueError('승인 카드의 문서와 실제 전송할 첨부가 다릅니다')
    return dict(calendar_id=context['meeting_calendar_id'], idempotency_key=explicit(execution_key, '실행 키'),
                summary=context['meeting_title'], start=approved_option['slot'], end=approved_option['end'],
                time_zone=context['meeting_time_zone'], room_email=room,
                attendees=[a.model_dump() for a in attendees], attachments=[a.model_dump() for a in attachments])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('agent-id', 'organizer-role', 'calendar-server', 'drive-server'):
        parser.add_argument('--' + field, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        mapping, requirements = prepare(agent_id=args.agent_id, organizer_role=args.organizer_role,
                                        calendar_server=args.calendar_server, drive_server=args.drive_server)
        target = args.output_dir.resolve()
        if target == EXAMPLE.resolve() or EXAMPLE.resolve() in target.parents:
            raise ValueError('원본 예제 폴더에는 사본을 쓸 수 없습니다')
        target.mkdir(parents=True, exist_ok=True)
        names = ('mapping.json', 'flow.bpmn', 'preconditions.json')
        if any((target / name).exists() for name in names):
            raise ValueError('기존 사본을 덮지 않습니다. 새 출력 폴더를 선택하세요')
        (target / 'mapping.json').write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (target / 'flow.bpmn').write_bytes((EXAMPLE / 'flow.bpmn').read_bytes())
        (target / 'preconditions.json').write_text(json.dumps(requirements, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except ValueError as exc:
        parser.error(str(exc))
    print('사본 준비 완료. 등록/Google 연결/실제 실행 준비는 확인하지 않았습니다.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
