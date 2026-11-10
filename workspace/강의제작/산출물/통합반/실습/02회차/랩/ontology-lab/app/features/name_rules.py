# 제공 빈 틀 — 같은 장치를 가르는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def same_device(a, b):
    """원자료 구성 요소 행 두 개(a, b)를 같은 장치로 볼지. 제공 코드가 모든 짝에 부르고, True인 짝끼리 이어 한 묶음으로 만든다.
    a, b = {'설비코드', '모델', '계통', '이름'(원자료 이름), '태그'(그 자리에 붙은 센서 태그 목록),
            '부품'(제공 코드가 괄호 속 품번 · 사내 품번 · 품번 교차표로 푼 사내 품번, 못 풀면 ''), '줄'(components.csv:<행>)}.
    돌려줄 것: True 또는 False."""
    raise NotImplementedError


def group_name(members):
    """같은 장치로 묶인 행들(위와 같은 dict, 구성 요소 목록 차례)에 쓸 이름 하나. 돌려줄 것: 이름(str)."""
    raise NotImplementedError
