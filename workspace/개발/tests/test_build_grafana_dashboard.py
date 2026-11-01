"""Grafana 대시보드 생성기(workspace/개발/scripts/build_grafana_dashboard.py) — 경보선은 정본 값, 표 · 주석은 학생이 읽는 한국어, 생성물 = 생성기 결과."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_grafana_dashboard as graf  # noqa: E402


def panel(title):
    return next(p for p in graf.dashboard['panels'] if p['title'] == title)


def test_유온_패널의_경고와_정지선은_감지_규칙과_PLC_인터록_값이다():
    warn, trip = graf.ts1_limits()
    steps = [s['value'] for s in panel('유온 TS1 · 경보와 조치 전후 추이')['fieldConfig']['defaults']['thresholds']['steps'] if s['value'] is not None]
    assert steps == [warn, trip] and f'{warn:g} ℃ 경고' in panel('유온 TS1 · 경보와 조치 전후 추이')['description']


def test_표의_열_이름과_주석은_한국어이고_경보_이름은_그래프가_붙인_이름을_쓴다():
    sql = ' '.join(t['rawSql'] for p in graf.dashboard['panels'] for t in p.get('targets') or [])
    notes = ' '.join(a['target']['rawSql'] for a in graf.dashboard['annotations']['list'] if 'target' in a)
    for table in ('설비 명령 — 관문을 통과한 명령과 PLC 응답', '처리 기록(감사)'):
        select = re.match(r'SELECT (.*?) FROM ', panel(table)['targets'][0]['rawSql']).group(1)
        columns = [c.strip() for c in select.split(', ')]
        assert columns and all(re.search(r'AS "[^"]*[가-힣][^"]*"$', c) for c in columns), [c for c in columns if '가' > c[-2:]]
    assert 'SELECT name,' in sql and "'RAISE '" not in notes and "'CLEAR '" not in notes and ' by ' not in notes
    assert '승인된 action.cmd' not in json.dumps(graf.dashboard, ensure_ascii=False)


def test_심각도_표시는_감지기가_내는_네_값만_옮긴다():
    severities = graf.alert_values['severity']
    assert set(severities) == {'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'}
    assert 'pattern' not in graf.alert_values                     # 경보 이름 사전 사본 없음 — alerts.name


def test_저장소의_대시보드는_생성기_결과와_같다():
    assert json.loads(graf.OUT.read_text(encoding='utf-8')) == json.loads(json.dumps(graf.dashboard, ensure_ascii=False)), \
        'hyd-trend.json 이 생성기 결과와 다르다 — build_grafana_dashboard.py 로 다시 만든다'
