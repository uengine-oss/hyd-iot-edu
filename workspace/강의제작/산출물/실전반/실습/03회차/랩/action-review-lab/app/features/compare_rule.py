"""제공 빈 틀입니다. 이 파일을 바로 고쳐 채웁니다 — 정할 지점: 쓰는 사람에 따라 갈리는 답.

경보마다 판정이 유지인 후보 목록으로 제공 코드 judge_tools.py가 이 함수를 부릅니다. 돌려준 후보는 비교 산식으로 견주지 않고 그 까닭을 결과에 남깁니다.
kept(읽기만): [{'sop': 후보 ID, 'inputs': 판단 입력 일곱 개, 'warnings': 맞은 경고 규칙 목록, 'penalties': 맞은 감점 규칙 목록}, ...]
돌려줄 값: {견주지 않을 후보 ID: 까닭 글} — 모두 견주면 빈 dict
"""


def choose_compared(kept):
    raise NotImplementedError('빈 틀: app/features/compare_rule.py choose_compared')
