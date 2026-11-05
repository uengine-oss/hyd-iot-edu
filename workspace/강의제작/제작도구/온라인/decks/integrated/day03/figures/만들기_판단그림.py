"""3회차 판단 그림. 글과 값은 각 덱의 고칠 수 있는 라벨이고, 여기에는 형상만 둔다."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "tools" / "deck"))
from 삽화_기본 import BLUE, GREY, LIGHT, NAVY, PALE, SKY, WHITE, ON, NORM, arrow, circle, line, path, rect, svg

HERE=Path(__file__).resolve().parent

def interval():
    y=240
    return [line(100,y,1090,y,GREY,5),line(310,y,875,y,BLUE,13),
            circle(310,y,16,WHITE,BLUE,5),circle(875,y,16,WHITE,BLUE,5),
            circle(592,y,16,BLUE,NAVY,4),line(592,y+23,592,y+55,NAVY,3)]

def routes():
    return [rect(74,72,300,132,16,PALE,NAVY),rect(74,307,300,132,16,LIGHT,NAVY),
            arrow([(374,139),(540,139),(645,255)],BLUE,5),
            arrow([(374,374),(540,374),(645,255)],NAVY,5),
            arrow([(652,257),(864,257)],BLUE,5),rect(872,185,260,147,16,PALE,NAVY)]

def window_gap():
    # 선 아래 눈금은 0~12 ℃ 여유다. 두 점과 목표까지의 거리도 같은 축척을 쓴다.
    x=lambda value:124+value*78
    y=243
    return [line(x(0),y,x(12),y,GREY,5),
            line(x(0),y,x(2.53),y,BLUE,15),circle(x(2.53),y,13,BLUE,NAVY),
            line(x(10),y-75,x(10),y+75,NAVY,4,stroke_dasharray='7 10'),
            arrow([(x(2.53),y+84),(x(10),y+84)],BLUE,4),
            line(x(0),y-13,x(0),y+14,NAVY,3)]

def deadlines():
    start, due = 171, 793
    pixels_per_hour = (due - start) / 5.98
    fast = round(start + 5.63 * pixels_per_hour, 2)
    slow = round(start + 6.43 * pixels_per_hour, 2)
    return [line(start,185,1080,185,GREY,4),line(start,360,1080,360,GREY,4),
            rect(start,167,round(fast-start, 2),36,10,SKY,BLUE),rect(start,342,due-start,36,10,SKY,BLUE),
            rect(due,342,round(slow-due, 2),36,8,NAVY,NAVY),line(due,98,due,425,NAVY,4,stroke_dasharray='6 10'),
            circle(fast,185,10,WHITE,BLUE),circle(slow,360,10,WHITE,NAVY)]

def isolation():
    # 압력계의 두 바늘은 잔압이 남았을 때와 확인 뒤의 낮은 압력을 대비한다.
    out=[]
    for cx,dy in [(285,-41),(904,29)]:
        out.extend([circle(cx,200,75,WHITE,NAVY,5),circle(cx,200,7,BLUE,NAVY,3),
                    line(cx,200,cx+36 if dy<0 else cx-40,200+dy,BLUE,7),
                    line(cx,277,cx,304,NAVY,6),line(cx-88,304,cx+88,304,NAVY,9)])
    out.extend([arrow([(425,200),(752,200)],BLUE,4),
                rect(570,162,40,25,4,PALE,NAVY,3),path('M 578 162 v -11 a 12 12 0 0 1 24 0 v 11',NAVY,3)])
    return out

def document_review():
    out=[rect(66,112,260,220,10,WHITE,NAVY),rect(84,130,260,220,10,PALE,NAVY),
         line(113,177,307,177,BLUE,8),line(113,213,279,213,NAVY,5),line(113,249,289,249,GREY,5),
         arrow([(369,224),(475,224)],BLUE,5),rect(489,135,262,178,14,WHITE,NAVY),
         line(516,178,717,178,GREY,5),line(516,215,699,215,BLUE,9),line(516,252,687,252,GREY,5),
         arrow([(770,224),(875,224)],BLUE,5),circle(995,224,82,PALE,NAVY,5),
         path('M 952 225 l 29 28 57 -67',BLUE,10)]
    return out

def rollback():
    out=[rect(63,93,325,280,18,LIGHT,NAVY),rect(100,178,249,103,12,WHITE,BLUE),
         arrow([(401,230),(570,230)],NAVY,5),circle(590,230,13,BLUE,NAVY),
         arrow([(605,229),(690,150),(795,150)],BLUE,5),
         arrow([(605,231),(690,352),(795,352)],NAVY,5),
         rect(812,84,310,139,15,PALE,BLUE),rect(812,288,310,139,15,WHITE,NAVY)]
    return out

def fan_history():
    # 두 구간을 더한 시간과 현재까지 끊기지 않은 시간을 같은 기준선에 맞춘다.
    return [line(103,218,1096,218,GREY,4),rect(120,189,480,57,8,SKY,BLUE),
            rect(600,212,162,12,3,GREY,GREY),rect(762,189,300,57,8,SKY,BLUE),
            line(1062,122,1062,334,NAVY,3,stroke_dasharray='6 10')]

def checkpoints():
    return [line(115,230,1085,230,GREY,5),circle(200,230,28,PALE,NAVY),
            circle(594,230,28,PALE,NAVY),circle(1000,230,28,WHITE,BLUE),
            arrow([(247,230),(536,230)],BLUE,5),arrow([(644,230),(946,230)],BLUE,5)]

def lookup_routes():
    return [circle(146,254,75,PALE,NAVY),circle(624,143,75,LIGHT,NAVY),
            circle(1011,343,75,PALE,NAVY),circle(626,345,95,WHITE,NAVY),
            arrow([(224,231),(537,151)],BLUE,5),arrow([(222,278),(524,339)],NAVY,5),
            arrow([(728,345),(926,345)],NAVY,5)]

def evidence_request():
    return [rect(74,71,398,129,14,PALE,BLUE),rect(74,277,398,139,14,WHITE,NAVY,3,stroke_dasharray='9 7'),
            arrow([(481,136),(595,136),(657,238)],BLUE,5),arrow([(481,345),(595,345),(657,253)],NAVY,5),
            arrow([(671,246),(792,246)],NAVY,5),rect(812,130,317,225,16,PALE,NAVY),line(844,311,1098,311,BLUE,3)]

if __name__=='__main__':
    for name,draw in [('온도구간의_두끝',interval),('독립조건의_공통출력',routes),('목표까지_남은여유',window_gap),('납기선과_완료시점',deadlines),('정지와_잔압확인',isolation),('원문인용과_검토',document_review),('한묶음의_반영과취소',rollback),('연속운전의_다시시작',fan_history),('서로다른_판단시점',checkpoints),('원인질문의_두경로',lookup_routes),('관측누락의_점검요청',evidence_request)]:
        (HERE/(name+'.svg')).write_text(svg(draw()),'utf8')
    (HERE/'중단된_두운전기록.svg').write_text(svg(fan_history()).replace('width="480"','width="450"').replace('x="600"','x="570"').replace('width="162"','width="192"'),'utf8')
