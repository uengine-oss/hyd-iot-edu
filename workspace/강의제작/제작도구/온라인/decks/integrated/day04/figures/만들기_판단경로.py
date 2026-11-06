"""두 과정의 문서 검토·점검 요청 도식. 설명 글상자는 각 장 원고에 둔다."""
from pathlib import Path
from 만들기_삽화 import (BLUE, LIGHT, NAVY, NORM, ON, PALE, WHITE, agent_icon,
                      approve_icon, arrow, book_icon, check_badge, cylinder_db,
                      doc, g, graph_icon, grid_icon, id_link, line, magnifier,
                      outline_doc, query_graph, quote_doc, rect, steps_icon, svg)

HERE = Path(__file__).resolve().parent


def icon(draw, x, y, scale=0.9):
    return g(x, y, scale, draw(0, 0, ON))


def branch(first, upper, lower):
    paths = [arrow([(255, 205), (375, 205), (375, y), (755, y)], BLUE)
             for y in (85, 315)]
    return paths + icon(first, 180, 205) + icon(upper, 825, 85) + icon(lower, 825, 315)


def double_route():
    o = [arrow([(445, 90), (595, 90), (595, 320), (755, 320)], BLUE),
         arrow([(445, 90), (755, 90)], BLUE),
         arrow([(190, 90), (335, 90)], NAVY),
         arrow([(190, 320), (278, 320), (278, 124), (342, 110)], NAVY)]
    for draw,x,y in [(doc,130,90),(doc,130,320),(steps_icon,395,90),
                     (check_badge,830,90),(magnifier,830,320)]:
        o.extend(icon(draw,x,y))
    return o


def loop():
    o = [arrow([(200, 126), (395, 126)], NAVY),
         arrow([(505, 126), (700, 126)], NAVY),
         arrow([(760, 69), (760, 30), (450, 30), (450, 70)], BLUE),
         arrow([(813, 126), (1005, 126)], BLUE)]
    for draw,x in [(agent_icon,145),(query_graph,450),(magnifier,760),(doc,1060)]:
        o.extend(icon(draw,x,126))
    o += [rect(50,365,1100,138,14,fill=PALE,stroke=LIGHT,sw=2)]
    return o


def hosting():
    o=[rect(40,35,475,450,16,fill=PALE,stroke=NAVY,sw=3),
       rect(680,35,470,450,16,fill=WHITE,stroke=NAVY,sw=3),
       rect(86,180,379,255,10,fill=WHITE,stroke=BLUE,sw=2.5),
       rect(730,180,365,255,10,fill=PALE,stroke=BLUE,sw=2.5),
       arrow([(470,240),(723,240)],BLUE), arrow([(722,290),(470,290)],NAVY)]
    return o+icon(agent_icon,270,236,0.65)+icon(query_graph,910,236,0.65)


def main():
    drawings={'지침_두입력':double_route(), '에이전트_재조회':loop(),
              '호스트_클라이언트':hosting(),
              '개정_소유범위':branch(quote_doc,outline_doc,graph_icon),
              '점검_진동경계':branch(query_graph,magnifier,steps_icon)}
    for name, body in drawings.items():
        (HERE/f'{name}.svg').write_text(svg(body),encoding='utf8')


if __name__=='__main__':
    main()

