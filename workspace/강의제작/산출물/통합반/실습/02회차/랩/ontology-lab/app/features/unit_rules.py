# 제공 빈 틀 — 기준 단위와 빈 단위 칸을 정하는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def base_unit(quantity, units):
    """물리량 하나(quantity = 6단계에서 정한 이름)의 기준 단위. units = 그 물리량 센서 행들의 단위 칸 글자(빈칸 뺌, 센서 목록 차례).
    돌려줄 것: 단위(str). 다른 단위의 값은 제공 코드가 이 단위로 환산한다."""
    raise NotImplementedError


def blank_unit(row, candidates):
    """단위 칸이 빈 센서 행(row)의 단위. row · candidates = {'설비코드', '모델', '태그', '단위', '정상값', '한계', '한계구분', '물리량', '줄'},
    candidates = 같은 물리량에서 단위 칸이 찬 센서 행들. 돌려줄 것: 단위(str) 또는 '미확인'."""
    raise NotImplementedError
