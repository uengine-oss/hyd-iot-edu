"""4회차 덱의 갈래 그림(코어 식별 근거 · 작업 조건 일괄 반영). 글자는 덱 MD에서 붙인다."""
from pathlib import Path
from 만들기_삽화 import NAVY, WHITE, svg


def branch_art():
    from 만들기_판단경로 import branch
    from 만들기_삽화 import (radiator, circle, line, id_link, magnifier,
                         check_badge, steps_icon)

    def cooler(x,y,st):
        return radiator(x-33,y-26,66,52,st)

    def cancel(x,y,st):
        return [circle(x,y,23,fill=WHITE,stroke=NAVY),
                line(x-10,y-10,x+10,y+10,NAVY),line(x-10,y+10,x+10,y-10,NAVY)]

    return {'코어_식별근거':branch(cooler,id_link,magnifier),
            '작업조건_일괄반영':branch(steps_icon,check_badge,cancel)}


if __name__ == '__main__':
    folder=Path(__file__).resolve().parent
    for name,drawing in branch_art().items():
        (folder/(name+'.svg')).write_text(svg(drawing),encoding='utf8')
