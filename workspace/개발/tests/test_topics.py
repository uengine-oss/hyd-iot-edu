"""Kafka 토픽 준비(it/redpanda/topics.sh) — 「이미 있음」만 통과이고 다른 실패는 종료 코드 1(하-17).

규칙: compose 의 topic-init 은 service_completed_successfully 로 하류 서비스를 막는다. 그래서 토픽을 만들지 못했거나 보존 기간을
맞추지 못하면 0 이 아닌 코드로 끝나야 한다. 이미 있는 토픽(rpk 가 TOPIC_ALREADY_EXISTS 로 답하고 1 로 끝남)은 정상이다.
rpk(Redpanda 도구)는 바깥이라 같은 꼴로 답하는 bash 함수로 대신한다. 답 모양은 이 PC 스택의 topic-init 기록에서 옮겼다.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / 'it' / 'redpanda' / 'topics.sh'
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


def bash() -> str:
    for candidate in (r'C:\Program Files\Git\bin\bash.exe', shutil.which('bash')):
        if candidate and Path(candidate).exists():
            return candidate
    pytest.fail('bash 가 없어 topics.sh 를 돌리지 못했다 — Git for Windows(또는 bash)를 설치한다', pytrace=False)


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
