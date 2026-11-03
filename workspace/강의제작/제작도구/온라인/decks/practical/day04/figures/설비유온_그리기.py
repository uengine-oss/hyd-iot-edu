"""별도 관측 자료의 첫 5분을 그린다. 빈 표본을 잇지 않으며 글자는 덱 MD에 둔다."""
import csv
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
COURSE = HERE.parents[5]
sys.path.insert(0, str(HERE.parents[2] / 'integrated/day04/figures'))
from 조각_1일차 import BLUE, GREY, NAVY, WHITE, circle, line, svg

source = COURSE / '산출물/통합반/실습/05회차/랩/05일차_실습4_센서이상시각화/코드/source/sensor_training.csv'
with source.open(encoding='utf-8-sig') as fp:
    series = [r for r in csv.DictReader(fp) if r['equipment']=='HYD-TRAIN' and r['tag']=='TS1'][:5]
assert [r['timestamp'][11:16] for r in series] == ['09:00','09:01','09:02','09:03','09:04']
assert [(r['value'],r['unit']) for r in series] == [(v,'degC') for v in ['40','42','45','','49']]
shapes = [line(55,355,1145,355,stroke=GREY,sw=2)]
previous = None
for i,row in enumerate(series):
    x=120+240*i
    shapes.append(line(x,350,x,361,stroke=GREY,sw=2))
    if row['value']:
        y=305-(float(row['value'])-40)*20
        if previous: shapes.append(line(*previous,x,y,stroke=BLUE,sw=5))
        shapes.append(circle(x,y,8,fill=WHITE,stroke=NAVY,sw=3))
        previous=x,y
    else:
        previous=None
        shapes.append(line(x,315,x,346,stroke=GREY,sw=2,stroke_dasharray='4 5'))
(HERE/'설비유온_빈구간.svg').write_text(svg(shapes),encoding='utf8')
