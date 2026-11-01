"""토픽 이름(common/hydcommon/topics.py)과 Kafka 토픽 준비(it/redpanda/topics.sh) — 「이미 있음」만 통과이고 다른 실패는 종료 코드 1(하-17).

규칙: compose 의 topic-init 은 service_completed_successfully 로 하류 서비스를 막는다. 그래서 토픽을 만들지 못했거나 보존 기간을
맞추지 못하면 0 이 아닌 코드로 끝나야 한다. 이미 있는 토픽(rpk 가 TOPIC_ALREADY_EXISTS 로 답하고 1 로 끝남)은 정상이다.
rpk(Redpanda 도구)는 바깥이라 같은 꼴로 답하는 bash 함수로 대신한다. 답 모양은 이 PC 스택의 topic-init 기록에서 옮겼다.
"""
import subprocess

import pytest

from conftest import bash, ROOT
from hydcommon import topics
SCRIPT = ROOT / 'it' / 'redpanda' / 'topics.sh'
FAKE_RPK = r'''
rpk() {
  case "$1 $2" in
    "topic create")
      case "$FAKE_CREATE" in
        new) printf 'TOPIC  STATUS\n%s  OK\n' "$3"; return 0;;
        exists) printf 'TOPIC  STATUS\n%s  TOPIC_ALREADY_EXISTS: The topic has already been created\n' "$3"; return 1;;
        broken) printf 'TOPIC  STATUS\n%s  NOT_CONTROLLER: This is not the correct controller for this cluster\n' "$3"; return 1;;
      esac;;
    "topic alter-config") [ "$FAKE_ALTER" = ok ];;
    "topic list") echo 'NAME  PARTITIONS  REPLICAS';;
  esac
}
export -f rpk
'''




@pytest.mark.parametrize('create, alter, code', [
    ('new', 'ok', 0),          # 처음 — 만든다
    ('exists', 'ok', 0),       # 두 번째 시작 — 이미 있음은 정상
    ('broken', 'ok', 1),       # 브로커 오류 — 하류 서비스가 뜨지 않게 실패
    ('exists', 'fail', 1),     # 보존 기간을 못 맞춤 — 실패
])
def test_이미_있음만_통과하고_다른_실패는_1로_끝난다(create, alter, code):
    out = subprocess.run([bash(), '-c', FAKE_RPK + 'bash "$1"', '_', SCRIPT.as_posix()], capture_output=True, text=True,
                         encoding='utf-8', env={'PATH': subprocess.os.environ['PATH'], 'FAKE_CREATE': create, 'FAKE_ALTER': alter})
    assert out.returncode == code, out.stdout + out.stderr
    if code:
        assert '못' in out.stderr


def test_topics_sh가_만드는_토픽은_서비스가_쓰는_토픽_이름과_같다():
    """두 자리(it/redpanda/topics.sh · common/hydcommon/topics.py)가 같은 토픽 일곱을 말해야 한다 — 한쪽에만 생기면 하류가 없는 토픽을 기다린다."""
    out = subprocess.run([bash(), '-c', FAKE_RPK + 'bash "$1"', '_', SCRIPT.as_posix()], capture_output=True, text=True,
                         encoding='utf-8', env={'PATH': subprocess.os.environ['PATH'], 'FAKE_CREATE': 'new', 'FAKE_ALTER': 'ok'})
    created = {line.split()[0] for line in out.stdout.splitlines() if line.split()[1:] == ['OK']}
    assert out.returncode == 0 and created == set(topics.ALL_KAFKA_TOPICS), out.stdout + out.stderr


@pytest.mark.parametrize('topic, parsed', [
    ('plant/hyd02/tag/CE', ('HYD-02', 'tag', 'CE')),
    ('plant/hyd01/status', ('HYD-01', 'status', None)),
    ('plant/hyd03/cmd/auto', ('HYD-03', 'cmd/auto', None)),
    ('plant/hyd01/wave/PS1', ('HYD-01', 'wave', 'PS1')),
    ('plant/hyd09/tag/TS1', None),            # G3b-28: 없는 설비 키는 설비가 아니다(상태 · 행 · 지표를 만들지 않는다)
    ('plant/HYD01/tag/TS1', None),
    ('plant/hyd01', None),
    ('plant/hyd01/tag/TS1/extra', None),
    ('plant/hyd01/cmd', None),
    ('factory/hyd01/tag/TS1', None),
])
def test_MQTT_토픽은_알려진_설비만_설비_종류_이름으로_푼다(topic, parsed):
    assert topics.parse_mqtt(topic) == parsed


def test_설비_키와_토픽_이름은_서로_돌아온다():
    for asset in topics.ASSETS:
        key = topics.asset_key(asset)
        assert topics.parse_mqtt(topics.mqtt_tag(key, 'TS1')) == (asset, 'tag', 'TS1')
        assert topics.parse_mqtt(topics.mqtt_cmd_manual(key)) == (asset, 'cmd/manual', None)
