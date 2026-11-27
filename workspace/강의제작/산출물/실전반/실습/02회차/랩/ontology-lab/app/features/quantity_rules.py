# 제공 빈 틀 — 같은 물리량을 가르는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def same_quantity(a, b):
    """센서 행 두 개(a, b)를 같은 물리량을 재는 것으로 볼지. 제공 코드가 모든 짝에 부르고, True인 짝끼리 이어 한 묶음으로 만든다.
    a, b = {'설비코드', '태그', '센서명', '재는것', '단위', '붙은곳'(센서가 붙은 구성 요소의 이름 — 같은 모델의 설비끼리는 하나로 맞춘 이름), '계통'(그 구성 요소의 계통), '줄'(sensors.csv:<행>)}.
    돌려줄 것: True 또는 False."""
    raise NotImplementedError


def quantity_name(members):
    """한 묶음의 센서 행들(위와 같은 dict, 센서 목록 차례)에 쓸 물리량 이름 하나. 서로 다른 묶음에는 다른 이름을 줍니다. 돌려줄 것: 이름(str)."""
    raise NotImplementedError
