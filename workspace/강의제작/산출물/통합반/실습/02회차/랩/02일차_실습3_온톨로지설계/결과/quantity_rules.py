# 제공 빈 틀 — 같은 물리량과 센서 종류를 가르는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def same_quantity(a, b):
    """센서 행 두 개(a, b)를 같은 물리량을 재는 것으로 볼지. 제공 코드가 모든 짝에 부르고, True인 짝끼리 이어 한 묶음으로 만든다.
    a, b = {'설비코드', '모델', '제조사', '태그', '계장태그', '재는것', '단위', '수집방식', '비고', '줄'(센서_목록.csv:<행>)}.
    돌려줄 것: True 또는 False."""
    raise NotImplementedError


def quantity_name(members):
    """한 묶음의 센서 행들(위와 같은 dict, 센서 목록 차례)에 쓸 물리량 이름 하나. 돌려줄 것: 이름(str)."""
    raise NotImplementedError


def kind_of(row):
    """센서 행 하나(위와 같은 dict)의 종류. 돌려줄 것: '실측' · '계산값' · '설정값' 가운데 하나."""
    raise NotImplementedError
