"""같은 판의 반복과 독립 출처의 합류. 글자는 덱 MD에서 붙인다."""
from pathlib import Path
from 만들기_삽화 import BLUE, NAVY, LIGHT, PALE, WHITE, ON, arrow, doc, g, graph_icon, rect, svg


def illustration():
    parts = [rect(15, 25, 565, 470, 18, fill=WHITE, stroke=LIGHT),
             rect(620, 25, 565, 470, 18, fill=PALE, stroke=LIGHT)]
    for x in (0, 605):
        for y in (180, 345):
            parts.extend(g(x+115,y,.83,doc(0,0,ON)))
            parts.append(arrow([(x+160,y),(x+260,y),(x+345,260)],BLUE))
        parts.extend(g(x+410,260,.85,graph_icon(0,0,ON)))
    return svg(parts)


def branch_art():
    from 만들기_판단경로 import branch
    from 만들기_삽화 import (fan, radiator, circle, line, id_link, magnifier,
                         approve_icon, check_badge, steps_icon, grid_icon)

    def fan_at(x,y,st):
        return fan(x,y,32,st)

    def cooler(x,y,st):
        return radiator(x-33,y-26,66,52,st)

    def cancel(x,y,st):
        return [circle(x,y,23,fill=WHITE,stroke=NAVY),
                line(x-10,y-10,x+10,y+10,NAVY),line(x-10,y+10,x+10,y-10,NAVY)]

    return {'모드에_따른_팬조작':branch(fan_at,approve_icon,cancel),
            '코어_식별근거':branch(cooler,id_link,magnifier),
            '작업조건_일괄반영':branch(steps_icon,check_badge,cancel),
            '후보제외와_감점':branch(fan_at,cancel,grid_icon)}


if __name__ == '__main__':
    folder=Path(__file__).resolve().parent
    (folder/'반복과_독립출처.svg').write_text(illustration(),encoding='utf8')
    for name,drawing in branch_art().items():
        (folder/(name+'.svg')).write_text(svg(drawing),encoding='utf8')
