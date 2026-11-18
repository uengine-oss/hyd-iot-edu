"""제공 빈 틀 — 정할 지점 「쓰는 사람에 따라 갈리는 답」을 구현하는 함수입니다.

허용된 후보는 경고나 감점이 붙어도 모두 비교값을 냅니다. 제공 코드(app/utils/actions.py)가 경보마다 비교값이 나온 후보 목록으로 이 함수를 부르고,
돌려준 후보는 1순위로 내주지 않고 다른 후보 뒤에 까닭과 함께 보입니다. 비교값과 비교값 순위는 그대로 남습니다.
kept(읽기만): [{'sop': 후보 ID, 'warnings': 그 후보에 붙은 경고 규칙 이름들(값이 비어 경고로 남은 규칙 포함), 'penalties': 맞은 감점 규칙 이름들}, ...]
돌려줄 값: {뒤에 보일 후보 ID: 까닭 글} — 뒤로 미룰 후보가 없으면 빈 dict
"""


def hold_back(kept):
    raise NotImplementedError('빈 틀: app/features/compare_rule.py hold_back')
