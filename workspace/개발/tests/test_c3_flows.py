"""시작 6단계 스크립트(scripts/c3_flows.py) — 이 PC의 process(포트 표)에 수업 흐름 설치를 부르고 흐름마다 한 줄로 알린다.
설치 판정 자체는 test_course_bootstrap 이 본다. 여기서는 실제 process(world)의 HTTP 주소로 부른 결과와 문장, 포트 표 · 명령 오류를 본다."""
import pytest

import c3_flows
import prepare_ports


def test_실제_process에_설치를_부르면_흐름마다_지금_판이_있다고_알린다(world, capsys):
    assert c3_flows.ensure(world.url) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 3 and all('지금 판' in line and '그대로 둠' in line for line in lines)


@pytest.mark.parametrize('row, line', [
    ({'definition': 'c3_pm', 'reused': True, 'version': '1'}, 'c3_pm: 지금 판(판본 1)이 배포돼 있음 — 그대로 둠'),
    ({'definition': 'c3_pm', 'reused': False, 'version': '2', 'replaced': '1'}, 'c3_pm: 흐름이 바뀌어 새 판본 2을 배포함(이전 판본 1은 기록으로 남음)'),
    ({'definition': 'c3_pm', 'reused': False, 'version': '1', 'replaced': None}, 'c3_pm: 기본 제공 흐름 판본 1 배포 완료'),
], ids=['그대로', '새 판으로 바꿈', '처음 설치'])
def test_설치_결과는_흐름마다_학생이_읽을_한_줄이다(row, line):
    assert c3_flows.report({'flows': [row]}) == [line]


def test_process에_닿지_않으면_주소를_대며_1로_끝난다(capsys):
    assert c3_flows.ensure('http://127.0.0.1:9') == 1
    assert '127.0.0.1:9' in capsys.readouterr().err


def test_포트_표가_없으면_시작_파일을_먼저_실행하라고_한다(tmp_path):
    with pytest.raises(prepare_ports.PrepareError, match='ports.json'):
        c3_flows.process_url(tmp_path)


@pytest.mark.parametrize('argv', [['c3_flows.py'], ['c3_flows.py', 'status'], ['c3_flows.py', 'ensure', 'x']])
def test_모르는_명령은_사용법과_함께_2로_끝난다(argv, capsys):
    assert c3_flows.main(argv) == 2 and '사용:' in capsys.readouterr().err
