"""강의 중계 확인(scripts/relay_probe.py) — process 관문이 실제로 가는 주소(LLM_RELAY_URL)와 머리글로 묻고, 결과를 학생 말로 낸다.

규칙(정답의 출처):
  · 주소는 관문의 규칙 그대로(it/process/procsvc/course_model.py relay_url — https, 또는 이 PC 안 loopback 의 http,
    사용자 정보 · 쿼리 · 조각 없음). 아니면 묻지 않고 실패.
  · 묻는 길: 기본 GET <주소>/v1/models(키가 받아들여지고 수업 모델이 목록에 있는가), --call 이면 POST <주소>/v1/messages(관문이 부르는 길).
    머리글 x-api-key 는 관문과 같다.
  · 401 · 403 · 404 · 429 는 바로 판정(학생이 할 일이 다르다), 네트워크 · 5xx 는 세 번까지 다시 묻고 「닿지 않음」.
  · 키 없음은 묻지 않는다. 키는 출력에 나오지 않는다.
강의 중계(LiteLLM)는 바깥이라 conftest 의 FakeRelay(로컬 포트)로 대신한다(유료 중계를 부르지 않는다).
"""
import json

import pytest

import relay_probe
from conftest import FakeRelay

KEY = 'sk-test-key'


@pytest.fixture
def relay():
    fake = FakeRelay()

    def run(plan, *, call=False, model='coding'):
        fake.plan(plan)
        return relay_probe.ask(fake.url, KEY, model, call=call, sleep=lambda s: None, timeout=5)
    run.seen = lambda: [(r['method'], r['path'], r['headers'].get('x-api-key')) for r in fake.requests]
    yield run
    fake.server.shutdown()


MODELS = {'data': [{'id': 'coding'}, {'id': 'other'}]}


@pytest.mark.parametrize('plan, ok, code, words', [
    ([(200, MODELS)], True, 'listed', '연결됨'),
    ([(200, {'data': [{'id': 'other'}]})], False, 'model', '수업 모델(coding)을 쓸 수 없습니다'),
    ([(401, {'error': 'bad key'})], False, '401', 'LLM_API_KEY'),
    ([(403, {'error': 'blocked'})], False, '403', '강사에게'),
    ([(404, {'error': 'no route'})], False, '404', '주소'),
    ([(429, {'error': 'budget'})], False, '429', '한도'),
    ([(502, {}), (502, {}), (200, MODELS)], True, 'listed', '연결됨'),       # 중계가 쉬다 깨어날 때 — 세 번째에 닿는다
    ([(500, {}), (500, {}), (500, {})], False, 'unreachable', '닿지 않습니다'),
])
def test_중계_답에_따라_학생이_할_일을_말한다(relay, plan, ok, code, words):
    out = relay(plan)
    assert (out['ok'], out['code']) == (ok, code) and words in out['message']
    assert KEY not in json.dumps(out, ensure_ascii=False)


def test_관문과_같은_길_같은_머리글로_묻는다(relay):
    relay([(200, MODELS)])
    assert relay.seen() == [('GET', '/v1/models', KEY)]


@pytest.mark.parametrize('body, ok', [
    ({'content': [{'type': 'text', 'text': 'OK'}]}, True),
    ({'content': []}, False),
])
def test_실제로_한_번_묻기는_관문이_부르는_메시지_길로_간다(relay, body, ok):
    out = relay([(200, body)], call=True)
    assert out['ok'] is ok and relay.seen()[-1][:2] == ('POST', '/v1/messages')


def test_관문이_받지_않는_주소는_묻지_않고_실패한다():
    """주소 규칙의 정본 · 표는 관문(course_model.relay_url — test_course_model)에 있다. 점검은 그 규칙을 그대로 쓰는지만 본다."""
    assert relay_probe.url_problem('http://relay.example.com') is not None and relay_probe.url_problem('https://relay.example.com') is None


@pytest.mark.parametrize('environ, code', [
    ({}, 'no-key'),
    ({'LLM_API_KEY': '  '}, 'no-key'),
    ({'LLM_API_KEY': KEY, 'LLM_RELAY_URL': 'http://insecure'}, 'url'),
])
def test_키나_주소가_틀리면_중계를_부르지_않고_1로_끝난다(capsys, environ, code):
    assert relay_probe.main(['relay_probe.py'], environ=environ) == 1
    out = json.loads(capsys.readouterr().out)
    assert out['code'] == code and not out['ok']
