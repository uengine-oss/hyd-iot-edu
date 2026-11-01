"""메일 도구 본체(it/effects-mcp/effects_mcp/tools.py) — 바깥(SMTP 메일함)만 FakeSmtp(conftest)로, 멱등 기록은 실제 SQLite 파일."""
import smtplib
import threading
import uuid

import pytest

from effects_mcp.tools import MAX_BODY_CHARS, MAX_SUBJECT_CHARS, EffectTools, Ledger

GOOD = {'to': 'production@hyd.local', 'subject': '[정비 공지] 시험', 'body': '본문'}


@pytest.fixture
def mail(smtp, tmp_path):
    tools = EffectTools(Ledger(str(tmp_path / 'effects.sqlite3')), smtp_factory=lambda: smtplib.SMTP('127.0.0.1', smtp.port, timeout=5))
    return tools, smtp


def sent(smtp, before):
    return len(smtp.messages) - before


@pytest.mark.parametrize('to, ok', [
    ('production@hyd.local', True),
    ('production@hyd.local, purchasing@hyd.local', True),
    ('a@b.example', False),               # 수업 도메인 밖 — SMTP 설정이 바뀌어도 바깥으로 나가지 않게
    ('@hyd.local', False), ('x@', False), ('@y', False), ('x@hyd.local.evil.example', False),
    ('', False), (','.join(f'u{i}@hyd.local' for i in range(21)), False),   # 받는 사람 없음 · 21명
], ids=['한_명', '두_명', '바깥_도메인', '이름_없음', '도메인_없음', '골뱅이_뒤만', '도메인_꼬리', '빈_주소', '21명'])
def test_받는_주소는_수업_도메인의_이름_골뱅이_꼴만_받는다(mail, to, ok):
    tools, smtp = mail
    before = len(smtp.messages)
    out = tools.send_mail(to, GOOD['subject'], GOOD['body'])
    assert (out['result'] == 'ok') is ok and sent(smtp, before) == (1 if ok else 0)
    if not ok:
        assert out['error_kind'] == 'INVALID'


@pytest.mark.parametrize('subject, body, ok', [
    ('가' * MAX_SUBJECT_CHARS, '본문', True), ('가' * (MAX_SUBJECT_CHARS + 1), '본문', False),
    ('제목', '가' * MAX_BODY_CHARS, True), ('제목', '가' * (MAX_BODY_CHARS + 1), False),
    ('   ', '본문', False),
], ids=['제목_한도', '제목_한도_넘음', '본문_한도', '본문_한도_넘음', '빈_제목'])
def test_제목과_본문은_한도_안에서만_보낸다(mail, subject, body, ok):
    tools, smtp = mail
    before = len(smtp.messages)
    out = tools.send_mail(GOOD['to'], subject, body)
    assert (out['result'] == 'ok') is ok and sent(smtp, before) == (1 if ok else 0)


def test_같은_멱등_키_같은_내용이면_한_통이고_두_번째는_첫_결과를_돌려준다(mail):
    tools, smtp = mail
    key, before = 'case:' + uuid.uuid4().hex, len(smtp.messages)
    first, again = tools.send_mail(**GOOD, idempotency_key=key), tools.send_mail(**GOOD, idempotency_key=key)
    assert sent(smtp, before) == 1 and again['document']['replayed'] is True
    assert again['document']['message_id'] == first['document']['message_id']


def test_같은_멱등_키에_다른_내용이면_보내지_않고_거절한다(mail):
    """G2-17: 옛 판은 다른 제목도 첫 결과를 「성공(replayed)」으로 돌려줬다."""
    tools, smtp = mail
    key = 'case:' + uuid.uuid4().hex
    tools.send_mail(**GOOD, idempotency_key=key)
    before = len(smtp.messages)
    out = tools.send_mail(GOOD['to'], '다른 제목', GOOD['body'], idempotency_key=key)
    assert out['result'] == 'error' and out['error_kind'] == 'INVALID' and sent(smtp, before) == 0


def test_같은_멱등_키가_동시에_와도_메일은_한_통이다(mail):
    """G2-17: 확인 → 발송 → 기록 사이에 잠금이 없어 동시 재시도 두 번이 두 통을 보냈다."""
    tools, smtp = mail
    key, before, results = 'case:' + uuid.uuid4().hex, len(smtp.messages), []
    threads = [threading.Thread(target=lambda: results.append(tools.send_mail(**GOOD, idempotency_key=key))) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sent(smtp, before) == 1 and sorted(r['document']['replayed'] for r in results) == [False, True, True, True]


def test_멱등_기록은_도구를_다시_만들어도_남는다(smtp, tmp_path):
    path, key = str(tmp_path / 'effects.sqlite3'), 'case:' + uuid.uuid4().hex
    factory = lambda: smtplib.SMTP('127.0.0.1', smtp.port, timeout=5)
    EffectTools(Ledger(path), factory).send_mail(**GOOD, idempotency_key=key)
    before = len(smtp.messages)
    again = EffectTools(Ledger(path), factory).send_mail(**GOOD, idempotency_key=key)
    assert again['document']['replayed'] is True and sent(smtp, before) == 0


def test_이전_판의_멱등_기록에는_같은_메일인지_가릴_수_없다고_말하고_다시_보내지_않는다(mail):
    """G2-17 뒤: 지문을 남기기 전 판의 기록(요청 내용 없음)에 「다른 내용」이라는 틀린 까닭을 내지 않는다."""
    tools, smtp = mail
    key = 'case:' + uuid.uuid4().hex
    tools.ledger.put(key, 'send_mail', {'tool': 'send_mail', 'document': {'message_id': '<old@hyd.local>'}})   # 이전 판이 쓴 꼴
    before = len(smtp.messages)
    out = tools.send_mail(**GOOD, idempotency_key=key)
    assert out['error_kind'] == 'INVALID' and '이전 판' in out['message'] and '다른 내용' not in out['message'] and sent(smtp, before) == 0


@pytest.mark.parametrize('up', [True, False], ids=['메일함_켜짐', '메일함_꺼짐'])
def test_메일함이_꺼져_있으면_보내기는_UNKNOWN이고_건강_검사는_실패를_알린다(smtp, tmp_path, up):
    port = smtp.port if up else 9
    tools = EffectTools(Ledger(str(tmp_path / 'e.sqlite3')), smtp_factory=lambda: smtplib.SMTP('127.0.0.1', port, timeout=3))
    out, health = tools.send_mail(**GOOD), tools.smtp_ready()
    assert (out['result'] == 'ok') is up and health['ok'] is up
    if not up:
        assert out['error_kind'] == 'UNKNOWN' and '메일 서버에 보내지 못했습니다' in out['message'] and health['error']
