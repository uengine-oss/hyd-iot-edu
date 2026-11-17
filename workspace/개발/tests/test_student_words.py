"""학생 화면으로 가는 서버의 글에 작업자끼리 쓰는 말 · 내부어가 없는가 — 금지어 표(student_words.py) 한 곳을 **실제 응답 · 실제 처리 기록**에 댄다.

소스 글자를 찾지 않는다. 실제 process(world) · 실제 판단 서비스 · 실제 재생 워커가 한 바퀴 돌며 남긴 것과, 화면이 읽는 실제 응답을 훑는다.
작업자 말은 「강사」 · 「녹화」 · 「수업」 · 「실습」 · 「(시나리오 A)」 · 「C3」 · 「지식 관리」(없어진 화면 이름) 같은 것이다(CLAUDE.md 5절, 요청문 18 · 23).
재생 모드의 안내 「AI 키가 없을 때 쓰는 재생 모드에서는 …」의 「재생 모드」는 계약이 정한 말이라 표에 없다.
"""
import json
import urllib.request

import pytest

from conftest import COOLING, OPERATOR
from student_words import WORKER_TALK


def talk(value, where=''):
    """값(사전 · 목록 · 글) 안의 글 가운데 작업자 말이 든 것 → [(자리, 그 글 앞부분)]."""
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            found += talk(item, f'{where}.{key}')
    elif isinstance(value, list):
        for n, item in enumerate(value):
            found += talk(item, f'{where}[{n}]')
    elif isinstance(value, str) and WORKER_TALK.search(value):
        found.append((where, value[:160]))
    return found


#: 처리 기록 줄에서 학생이 읽는 칸(원문 칸 raw_error · 도구 입출력 원문 · AI가 읽는 지시는 접기 안의 원문이라 보지 않는다)
SHOWN = ('name', 'goal', 'friendly', 'content', 'reason', 'summary', 'note', 'effect', 'title')


def shown_of(events):
    return [{k: (e.get('data') or {}).get(k) for k in SHOWN if isinstance((e.get('data') or {}).get(k), str)} | {'_job': e.get('job_id')} for e in events]


def test_냉각_경보_한_건이_승인과_효과_확인을_거쳐_끝나는_동안_처리_기록과_알림에_작업자_말이_없다(world):
    """결함 시뮬레이션의 조작 기록(「수업 버튼 [쿨러 열화 주입]」) · 단계 메모(「re-observing command for 45 s …」) · 처리 완료 알림(「끝난 곳: 끝」) ·
    판단 설명문이 한 바퀴에 다 나온다. 실제 재생 워커 · 실제 판단 등록 · 실제 엔진으로 끝까지 간다."""
    import re
    from procsvc import scenario_buttons
    alert, pid, decision = world.start_cooling()
    world.rt.repo.record_events([scenario_buttons.press_event(
        pid, '쿨러 열화 주입', COOLING[1], {'by': OPERATOR['by'], 'user_id': OPERATOR['by'], 'roles': [OPERATOR['role']]}, world.now_iso())])
    made = world.main.book[decision]
    assert talk(made.get('explanation'), 'decision.explanation') == []
    assert '장 중' not in made['explanation'] and '권한다' not in made['explanation'], made['explanation']      # 화면 용어: 조치 후보 N개 · 권장
    world.approve(pid, decision, 'skill:sop-cool-11', OPERATOR)
    world.ack(COOLING[1], world.commanded(pid)['cmdId'])
    world.tag(COOLING[1], 'TS1', 50.0)
    world.clear_alert(alert)
    world.clock.advance(15 * 60 / 20 + 1)
    world.poll()
    status, view = world.api('GET', f'/api/instances/{pid}')
    assert status == 200 and view['instance']['status'] == 'COMPLETED', [(w['activity_id'], w['status']) for w in world.rows(pid)]
    assert talk(shown_of(world.events(pid)), 'events') == []
    logs = [w.get('log') or '' for w in world.rows(pid)]
    assert talk(logs, 'workitem.log') == [] and not [text for text in logs if re.search(r're-observing|\bfor \d+ s\b', text)], logs
    assert talk(view.get('attention'), 'attention') == [] and talk(view['instance'].get('end_label'), 'end_label') == []
    status, incidents = world.api('GET', '/api/incidents')
    mine = next(i for i in incidents if i['id'] == world.values(pid)['incident'])
    assert status == 200 and mine['pattern'] == COOLING[0] and mine['card'] is None      # 목록은 card 를 싣지 않고 경보 종류 칸을 싣는다
    assert talk([h.get('note') for h in mine['history']], 'incident.history') == []
    import psycopg
    with psycopg.connect(world.dsn) as db:
        notes = db.execute("SELECT title, description FROM notifications WHERE url = %s", (f'/instances/{pid}',)).fetchall()
    assert notes and talk([list(n) for n in notes], 'notifications') == [] and not [n for n in notes if '끝난 곳' in (n[1] or '')], notes


def _agent(world, path, body=None):
    request = urllib.request.Request(world.stack.services['agent'].url + path, data=None if body is None else json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'}, method='GET' if body is None else 'POST')
    try:
        with urllib.request.urlopen(request, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def test_이상_패턴_목록은_판단할_수_있는지와_까닭을_미리_알려_주고_그_까닭은_판단을_돌렸을_때의_답과_같다(world):
    """규칙 판단에서 패턴을 고르고 [모의 판단]을 눌러야 「원인 지식이 아직 없습니다 — [지식 관리]에서 …」(없어진 화면 이름)를 봤다."""
    status, patterns = _agent(world, '/api/ontology/patterns')
    assert status == 200 and {p['judgeable'] for p in patterns} == {True, False}, patterns      # 이 그래프에는 되는 패턴과 안 되는 패턴이 다 있다
    for p in patterns:
        assert (p['reason'] is None) is p['judgeable'] and talk(p['reason'], p['code']) == [], p
        status, out = _agent(world, '/api/agent/decide', {'asset': 'HYD-01', 'pattern': p['code']})
        if not p['judgeable']:
            assert status == 404 and out['detail'] == p['reason'], (p['code'], status, out)
        else:
            assert status != 404, (p['code'], out)


def test_데이터_원천의_미연결_까닭은_지금_있는_화면_이름을_가리킨다(world):
    status, links = world.api('GET', '/api/fabric/links')
    assert status == 200, links
    reasons = [i.get('reason') for i in links['inputs'] if i.get('state') == 'UNBOUND']
    assert reasons and talk(reasons, 'fabric.links') == [] and all('문서 등록' in r for r in reasons), reasons[:2]


def test_조건별_손익의_1순위가_바뀌는_값에는_뜻이_없는_음수_가중치가_없고_문장은_화면_말이다(world):
    """「1순위가 바뀌는 값」 표에 「−1.068배 이하」가 나왔다 — 순위 항목의 가중치를 음수로 뒤집어야 1순위가 바뀐다는 줄은 학생에게 뜻이 없다.
    결론 문장의 「정책 점수와 돈 기준이 다른 카드를 고릅니다 — 가치의 상충」도 화면 말(조치)로."""
    world.plant.inject('HYD-01', 'cooler_degradation', severity='moderate')      # 쿨러 오염이 끝까지 진행돼 유온이 경보선 위에 머문 설비
    world.settle(1800)
    world.reported_for('HYD-01')                             # 30분째 보고하는 상태 — 규칙 판단의 근거 구간이 비지 않는다
    status, started = _agent(world, '/api/agent/whatif', {'asset': 'HYD-01', 'pattern': 'COOLER_DEGRADATION'})
    assert status == 200, started
    assert talk(started['summary'], 'summary') == [] and '카드' not in started['summary'], started['summary']
    money_words = [src.get('where') for c in started['cards'] for item in (c.get('money') or {}).get('items') or [] for src in item.get('sources') or []]
    assert not [w for w in money_words if w and '카드' in w], [w for w in money_words if w and '카드' in w][:3]
    status, out = _agent(world, f"/api/agent/whatif/{started['id']}/boundaries", {})
    assert status == 200 and out['boundaries'], out
    weights = [b for b in out['boundaries'] if b['variable'].startswith('w:')]
    assert all(b['value'] >= 0 for b in weights), [(b['label'], b['value'], b['direction']) for b in weights if b['value'] < 0]
