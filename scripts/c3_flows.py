"""수업 흐름 A(냉각) · B(정기 정비) · C(예비품 구매)가 지금 판으로 배포돼 있는지 확인하고 없거나 옛 판이면 배포한다 — 시작 6단계가 부른다.

    python scripts/c3_flows.py ensure      # 이 PC의 process(포트 표 .hyd-runtime/ports.json 의 8080 자리)에 POST /api/course-bootstrap

흐름 그림 · 매핑의 정본은 it/process/procsvc/course_flows.json 하나이고, 비교 · 가져오기 → 사전 검사 → 등록 → 배포는 process 의
/api/course-bootstrap(it/process/procsvc/course_bootstrap.py)이 한다. 배포된 판이 같은 내용이면 아무것도 바꾸지 않는다.
모르는 명령은 사용법과 함께 거절한다(종료 코드 2).
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import prepare_ports   # 같은 scripts 폴더(시작 파일이 이 폴더의 스크립트로 부른다)

ROOT = Path(__file__).resolve().parents[1]


def process_url(root: Path = ROOT) -> str:
    """이 PC의 process 주소 — 점검(check_stack)과 같은 포트 표 한 곳에서."""
    return f'http://127.0.0.1:{prepare_ports.saved_port(root, 8080)}'


def report(result: dict) -> list[str]:
    """설치 결과 한 줄씩(학생 화면)."""
    lines = []
    for row in result['flows']:
        if row['reused']:
            lines.append(f"{row['definition']}: 지금 판(판본 {row['version']})이 배포돼 있음 — 그대로 둠")
        elif row.get('replaced'):
            lines.append(f"{row['definition']}: 흐름이 바뀌어 새 판본 {row['version']}을 배포함(이전 판본 {row['replaced']}은 기록으로 남음)")
        else:
            lines.append(f"{row['definition']}: 기본 제공 흐름 판본 {row['version']} 배포 완료")
    return lines


def ensure(api: str) -> int:
    request = urllib.request.Request(api + '/api/course-bootstrap', data=b'{}', method='POST', headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', 'replace')
        try:
            detail = json.loads(detail).get('detail', detail)
        except (ValueError, AttributeError):
            pass
        print(f'기본 제공 흐름 준비를 서버가 받지 않았습니다({exc.code}): {str(detail)[:600]}', file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError) as exc:
        print(f'처리 엔진({api})에 닿지 않습니다: {exc}', file=sys.stderr)
        return 1
    for line in report(result):
        print(line)
    return 0


def main(argv: list[str]) -> int:
    if argv[1:] != ['ensure']:
        print('사용: c3_flows.py ensure   (수업 흐름 A · B · C 가 없거나 옛 판이면 배포)', file=sys.stderr)
        return 2
    try:
        api = process_url()
    except prepare_ports.PrepareError as exc:          # 포트 표가 없음 — 학생이 읽을 문장 그대로
        print(str(exc), file=sys.stderr)
        return 1
    return ensure(api)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
