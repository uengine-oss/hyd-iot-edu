"""FUXA 화면 생성기(workspace/개발/scripts/build_fuxa_project.py) — 같은 재료면 같은 파일, 경보선은 정본 값, 학생이 읽는 알람 문구에 내부어가 없다."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_fuxa_project as fuxa  # noqa: E402
from build_grafana_dashboard import ts1_limits  # noqa: E402


def test_두_번_만들어도_글자까지_같다():
    assert json.dumps(fuxa.build_project(), ensure_ascii=False) == json.dumps(fuxa.build_project(), ensure_ascii=False)


def test_유온_경고와_정지선은_감지_규칙과_PLC_인터록_값이다():
    from hydcommon.plant_model import TRIP_TS1
    warn, trip = ts1_limits()
    assert (warn, trip) == (55.0, TRIP_TS1)
    ts1 = [a for a in fuxa.build_project()['alarms'] if a['name'].endswith(' TS1')]
    assert ts1 and all(a['high']['min'] == warn and a['high']['max'] == trip and a['highhigh']['min'] == trip for a in ts1)


def test_IT_경보_알람_문구는_특정_패턴이나_개발자_말을_박지_않는다():
    texts = [a['highhigh']['text'] for a in fuxa.build_project()['alarms'] if a['name'].endswith('IT ALERT')]
    assert len(texts) == 3
    assert not [t for t in texts if any(w in t for w in ('Flink', 'CEP', 'RAISE', '쿨러 성능 저하'))]


def test_MQTT_장치는_브로커가_허락한_fuxa_계정으로_붙는다():
    assert fuxa.build_project()['devices']['emqx']['property']['username'] == 'fuxa'


def test_저장소의_FUXA_프로젝트는_생성기_결과와_같다():
    assert json.loads(fuxa.OUT.read_text(encoding='utf-8')) == json.loads(json.dumps(fuxa.build_project(), ensure_ascii=False)), \
        'ot/fuxa/project.json 이 생성기 결과와 다르다 — build_fuxa_project.py 로 다시 만든다'
