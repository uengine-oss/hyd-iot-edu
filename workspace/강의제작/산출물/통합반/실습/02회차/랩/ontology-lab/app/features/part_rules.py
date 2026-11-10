# 제공 빈 틀 — 교체 부품을 잇는 내 판단. 함수 머리와 설명은 그대로 두고 본문만 채웁니다.


def find_part(cell, asset, component, spares, cross, same_component):
    """components.csv의 교체부품 칸을 제공 코드가 바로 풀지 못한 행(빈칸 · 품명 · 짧은 표기)에서 부른다.
    cell = 교체부품 칸 글자(빈칸이면 ''), asset = {'설비코드', '모델'}, component = 내가 정한 구성 요소 이름,
    spares = spare_parts.csv 행들(dict), cross = part_aliases.csv 행들(dict),
    same_component(원자료 이름) = 그 이름이 이 구성 요소와 같은 것인지(정한 이름 기준 — 그 모델의 구성 요소에 없는 이름은 원자료 이름 그대로 견줌) True · False.
    돌려줄 것: 이을 사내 품번(str) 또는 None(잇지 않음)."""
    raise NotImplementedError


def same_item(maker_code, internal_codes):
    """같은 제조사 품번(maker_code)으로 등록된 사내 품번이 둘 이상일 때 부른다(internal_codes = 그 사내 품번들).
    돌려줄 것: True(한 물품으로 잇는다) 또는 False(따로 둔다)."""
    raise NotImplementedError
