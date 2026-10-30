"""수업 흐름 A(냉각) · B(정기 정비) · C(예비품 구매)가 배포돼 있는지 확인하고 없으면 배포한다 — 시작 6단계가 부른다.

    python scripts/c3_flows.py ensure      # PROCESS_URL(기본 http://127.0.0.1:8080)의 POST /api/course-bootstrap

흐름 그림 · 매핑의 정본은 it/process/procsvc/course_flows.json 하나이고, 가져오기 → 사전 검사 → 등록 → 배포는 process 의
/api/course-bootstrap(it/process/procsvc/course_bootstrap.py)이 한다. 이미 수업 흐름으로 배포된 것은 건너뛴다(두 번째 실행은 아무것도 바꾸지 않는다).
모르는 명령은 사용법과 함께 거절한다(종료 코드 2).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("PROCESS_URL", "http://127.0.0.1:8080")


def ensure() -> int:
    request = urllib.request.Request(API + '/api/course-bootstrap', data=b'{}', method='POST', headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', 'replace')
        try:
            detail = json.loads(detail).get('detail', detail)
        except (ValueError, AttributeError):
            pass
        print(f'수업 흐름 준비가 거절됐습니다({exc.code}): {str(detail)[:400]}', file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError) as exc:
        print(f'처리 엔진({API})에 닿지 않습니다: {exc}', file=sys.stderr)
        return 1
    for row in result['flows']:
        print(row['definition'], '이미 수업 흐름으로 배포됨 — 건너뜀' if row['reused'] else '수업 기본 흐름 배포 완료')
    return 0


def main(argv: list[str]) -> int:
    if argv[1:] != ['ensure']:
        print('사용: c3_flows.py ensure   (수업 흐름 A · B · C 가 없으면 배포)', file=sys.stderr)
        return 2
    return ensure()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
