# 제공 빈 틀 — 승인과 구매 담당이 함께 볼 것을 담는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def approval(entry, as_of):
    """SCM 승인 목록(승인공급사_목록.csv)의 그 공급사 · 부품 등록(dict — 원자료 칸 그대로와 '줄') 또는 None(등록 없음)을 받는다.
    돌려줄 것: {'approved': True 또는 False, ...} — approved 말고 남길 속성(이름은 영어 snake_case)도 이 dict에 함께."""
    raise NotImplementedError


def buyer_info(pair):
    """쌍 하나(공급사 · 부품 · 단가 · 불량률 · 납기 · 승인 결과 등 지금까지 붙은 값의 dict)를 받는다.
    돌려줄 것: 구매 담당이 공급사를 비교할 때 함께 봐야 해서 이 쌍에 더 남길 속성 dict(남길 것이 없으면 {}). 이미 있는 속성은 덮어쓰지 않는다."""
    raise NotImplementedError
