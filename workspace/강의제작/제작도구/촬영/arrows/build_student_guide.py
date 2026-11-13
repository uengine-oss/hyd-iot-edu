"""낸 영상에서 조작 화면 사진을 뽑고 단계 결과 그림에 네모를 그려, 두 과정 학생 가이드와 한 파일 가이드(<랩>.html, lab_package.pack_page)를 갱신한다.
Usage: python build_student_guide.py [--video <낸 mp4>]
  --video를 주면 images/를 그 영상에서 UI_SHOTS(조작 화면) · STAGE_SHOTS(단계 결과 그림)대로 새로 만들고 사진 근거(학생가이드_사진근거.json)를 고쳐 쓴다.
  없으면 지금 사진과 사진 근거를 그대로 두고 가이드 · 한 파일 가이드만 다시 만든다.
네모: 대상 바깥 margin px(기본 6)에 굵기 6 빨간 선(가이드 P-8). 옆 글자에 걸리는 곳은 margin을 줄였다.
가이드 글의 까닭(원마다 왜 놓는지, 화살표마다 왜 그 이름 · 그 방향인지)은 대본원고.md의 그 자리 말을 줄인 것이다. 대본에 없는 까닭을 여기서 새로 짓지 않는다.
영상·대본·완성 참조 원본은 수정하지 않는다.
"""
from pathlib import Path
import argparse
import hashlib
import html
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[5]
LAB = '01일차_실습4_관계그림'
LINE = 6          # 네모 굵기(px)
RED = (230, 0, 0)
# 낸 실습 영상(통합반_01회차_08_실습_관계그림.mp4, 2294.27초 — 2026-11-14 이 PC Playwright 헤드리스 판, 검색 결과 광고 칸을 가린 판)에서 뽑는 ARROWS 화면.
# 시각은 그 영상 자막의 그 조작 큐 안(또는 그 조작이 끝나 다음 조작으로 넘어가기 직전)이고, 프레임마다 커서가 대상을 가리지 않고 값이 다 들어간 순간을 눈으로 골랐다.
# boxes: (x0, y0, x1, y1, margin) — 대상 경계(프레임 px)와 대상 바깥 간격. crop: 오른쪽 칸 · 창처럼 볼 곳만 자를 때(글자가 가이드 폭에서 읽히게).
VIDEO_DURATION = '00:38:14.27'
STAGE_CROP = (0, 38, 1537, 1053)   # 그림판(위 막대 아래 ~ 오른쪽 칸 앞 ~ 아래 막대 위)
PANEL = (1000, 0, 1920, 640)       # 오른쪽 칸과 그 옆 그림판
UI_SHOTS = [
    ('ui-01-search', 47.5, (60, 470, 1060, 700), [(142, 492, 640, 580, 4)]),                                              # e003 끝: 검색 결과에서 주소가 arrows.app인 줄(광고 칸은 이 자름 밖)
    ('ui-02-radius', 100.0, PANEL, [(1718, 213, 1816, 244, (2, 4, 4, 4)), (1670, 546, 1760, 568, (4, 4, 4, 2))]),         # e010: Customize · radius 60
    ('ui-03-orientation', 120.0, (1000, 0, 1920, 760), [(1616, 636, 1804, 658, 3)]),                                      # e010b: detail-orientation horizontal
    ('ui-04-caption', 188.0, PANEL, [(1550, 236, 1906, 268, (2, 0, 2, 2)), (1834, 348, 1907, 375, 4)]),                  # e016: Caption 칸 · + Label
    ('ui-05-ring', 222.0, (0, 430, 1000, 660), [(48, 476, 187, 614, 12)]),                                                # e019: 원 둘레의 하늘색 띠
    ('ui-06-type', 287.0, PANEL, [(1550, 266, 1906, 298, (2, 0, 2, 2))]),                                                # e023 끝: 화살표의 Type
    ('ui-07-reverse', 538.3, PANEL, [(1619, 112, 1712, 141, (3, 3, 1, 3))]),                                  # e040 끝: Reverse(뒤집고 OBSERVED_BY를 적은 뒤)
    ('ui-08-property', 890.0, PANEL, [(1550, 399, 1906, 459, (2, 2, 2, 0)), (1817, 475, 1907, 502, (4, 2, 4, 4))]),       # e062: Properties 두 줄 · + Property
    ('ui-09-procedure', 1874.0, (860, 0, 1920, 640), [(1550, 333, 1906, 366, 2), (895, 228, 1029, 272, 3)]),              # e115 끝: 화살표의 절차 속성 · 그림판에 붙은 번호
    ('ui-10-color', 1916.6, (860, 0, 1920, 800), [(1550, 72, 1653, 98, (4, 0, 4, 4)), (1652, 662, 1800, 686, (3, 3, 3, 1))]),                       # e118 끝: nodes: 3 · node-color(칠해진 원은 핀 오염만 이 자름에 든다)
    ('ui-11-judge', 2099.0, STAGE_CROP, [(1195, 260, 1497, 398, 6), (188, 280, 474, 400, 6), (731, 882, 1021, 1010, 6)]),  # e130: 색칠을 마친 그림 — 원인 셋과 조건
    ('ui-12-export-png', 2118.5, (430, 55, 1490, 850), [(465, 146, 515, 178, 3), (488, 377, 647, 397, 4)]),               # e132(JSON 탭으로 가는 중, PNG 탭이 아직 열려 있다): PNG 탭 · 맨 위 줄 Download
    ('ui-13-export-json', 2123.0, (430, 55, 1490, 810), [(654, 146, 709, 178, 3), (479, 207, 592, 238, 4)]),              # e133: JSON 탭 · Download
    ('ui-14-menu', 2141.0, (0, 0, 1000, 420), [(10, 6, 38, 34, 2), (86, 110, 238, 134, 3), (12, 154, 58, 174, 3)]),       # e136: 로고 · New 밑의 Web Browser storage · Import — New 네모는 로고 네모와 붙어 겹쳐서 뺐다
    ('ui-15-import', 2165.1, (430, 55, 1490, 682), [(465, 273, 600, 305, 4), (1382, 622, 1458, 654, 4)]),                 # e140: Choose File · Import
    ('ui-16-imported', 2169.0, None, [(1550, 72, 1815, 98, (4, 0, 4, 4)), (44, 117, 136, 208, (4, 1, 1, 4))]),                       # e141: nodes: 17 · relationships: 21 · 지울 빈 원
    ('ui-17-cypher', 2246.0, (430, 55, 1490, 838), [(580, 146, 645, 178, 3), (498, 301, 567, 319, 3)]),                   # e147: Cypher 탭 · CREATE
]
# 단계 결과 그림 — 같은 영상에서 그 단계의 마지막 입력이 끝난 순간(커서가 오른쪽 칸에 있을 때)의 그림판을 자르고, 「이번에 추가」한 곳에 네모를 둔다.
STAGE_SHOTS = {
    '01': (439.8, [(58, 486, 474, 802, 6)]),                                  # 설비 · 쿨러 · 센서
    '02': (674.4, [(484, 486, 745, 802, 6)]),                                 # 유온 상승 · 쿨러 냉각 성능 상실
    '03': (884.4, [(1195, 260, 1520, 398, 6)]),                               # 쿨러 핀 오염과 두 조건
    '04': (1207.6, [(903, 78, 1021, 398, 6), (1195, 486, 1313, 802, 6)]),     # 팬 최대 운전 → HM-8.5 · 핀 세척 → HM-8.7
    '05': (1390.5, [(58, 78, 474, 402, 6)]),                                  # 팬 구동 불량과 조건 · 팬 점검 → HM-8.1
    '06': (1579.2, [(731, 882, 1313, 1012, 6)]),                              # 주변 온도 상승과 조건 · 캐비닛 환기 보강
    '07': (1874.0, [(627, 78, 745, 444, 6), (215, 120, 340, 158, 4), (895, 228, 1029, 272, 3), (1187, 611, 1324, 656, 3), (1187, 832, 1324, 877, 3)]),   # 진동 증가 → 팬 베어링 열화 · 절차 번호 넷
}
STAGE_ADDED = {'01': '설비 · 오일 쿨러 · 유온 센서', '02': '유온 상승 · 쿨러 냉각 성능 상실', '03': '쿨러 핀 오염 · 조건 두 줄', '04': '팬 최대 운전 · 쿨러 핀 세척 · 매뉴얼 절 둘',
               '05': '팬 구동 불량 · 팬 점검 · HM-8.1', '06': '주변 온도 상승 · 캐비닛 환기 보강', '07': '팬 베어링 열화 · 진동 증가 · 절차 번호 넷'}
STAGE_CAPTION = '이 단계를 마친 그림. 빨간 네모가 이번에 더한 곳입니다'
H, K, S, U, F = 'HYD-01 유압 파워팩', '오일 쿨러', '유온 센서 TS1', '유온 상승', '쿨러 냉각 성능 상실'
PO, MX, PC, M85, M87 = '쿨러 핀 오염', '팬 최대 운전', '쿨러 핀 세척', 'HM-8.5 즉시 완화 조치', 'HM-8.7 근본 조치'
FD, FI, M81, AT, CV, BR, VB = '팬 구동 불량', '팬 점검', 'HM-8.1 팬 벨트 점검', '주변 온도 상승', '캐비닛 환기 보강', '팬 베어링 열화', '진동 증가'
KEEP = '맞음'

def flip(src):
    """주어가 아닌 원에서 끌어내 화살표가 거꾸로 나온 자리."""
    return f'{src}에서 끌어내 거꾸로 나옴 → Reverse'

def onto(a, b):
    """주어의 띠를 이미 있는 원 위에 놓아 화살표만 만드는 자리."""
    return f'{a}의 띠를 {b} 원 위에 놓기'

def table(headers, rows):
    return '<div class="table-wrap"><table><thead><tr>' + ''.join('<th>'+html.escape(x)+'</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join('<td>'+html.escape(x)+'</td>' for x in row)+'</tr>' for row in rows) + '</tbody></table></div>'

def nodes(rows):
    """놓을 원: 이름 · 종류 · 띠를 끌어낼 원 · 왜 놓는지."""
    return table(['Caption · 이름', 'Label · 종류', '끌어낼 원', '왜 놓나'], rows)

def rels(rows):
    """그을 화살표: 문장의 주어(화살표가 나가는 원) · 상대(닿는 원) · 둘을 잇는 말 · 이름 · 끌어낸 방향이 맞는지 뒤집는지."""
    return table(['주어 · 화살표가 나가는 원', '상대 · 닿는 원', '읽으면', 'Type · 화살표 이름', '방향'], rows)

def figure(file, caption):
    return f'<figure><a href="{file}" target="_blank"><img src="{file}" alt="{caption}" loading="lazy"></a><figcaption>{caption}</figcaption></figure>'

def photo(stage, caption=STAGE_CAPTION):
    """단계 결과 그림. 빨간 네모는 이번 단계에서 더한 곳이다."""
    return f'<p class="added"><b>이번에 추가</b> {STAGE_ADDED[stage]}</p>'+figure(f'images/stage-{stage}.png', caption)

def shot(name, caption):
    """ARROWS 화면 사진. 빨간 네모는 누르거나 입력할 곳, 볼 곳이다."""
    return figure(f'images/{name}.png', caption)

def draw_boxes(im, boxes):
    """대상 바깥 margin에 굵기 LINE 네모를 그린다. 화면 밖으로 나가는 변은 화면 끝에 붙인다. 네모끼리 겹치면 멈춘다."""
    """margin은 네 변 같은 값 하나 또는 (왼, 위, 오른, 아래). 돌려주는 값: 네모마다 (바깥 경계, 선 아래에 깔린 어두운 화소 수 — 글자 · 선을 덮었는지 재는 값)."""
    from PIL import ImageDraw
    gray=im.convert('L'); d=ImageDraw.Draw(im); outer=[]; dark=[]
    for x0,y0,x1,y1,m in boxes:
        ml,mt,mr,mb=(m,)*4 if isinstance(m,int) else m
        r=[max(0,x0-ml-LINE),max(0,y0-mt-LINE),min(im.width-1,x1+mr+LINE),min(im.height-1,y1+mb+LINE)]
        for o in outer:
            if r[0]<=o[2] and o[0]<=r[2] and r[1]<=o[3] and o[1]<=r[3]:
                raise SystemExit(f'네모가 겹친다: {r} · {o}')
        band=[(x,y) for x in range(r[0],r[2]+1) for y in list(range(r[1],r[1]+LINE))+list(range(r[3]-LINE+1,r[3]+1))]
        band+=[(x,y) for y in range(r[1]+LINE,r[3]-LINE+1) for x in list(range(r[0],r[0]+LINE))+list(range(r[2]-LINE+1,r[2]+1))]
        dark.append(sum(1 for p in band if gray.getpixel(p)<150))
        outer.append(r)
    for r in outer:d.rectangle(r,outline=RED,width=LINE)
    return [(list(map(int,r)),n) for r,n in zip(outer,dark)]

def section(n, title, body):
    return f'<section id="step{n}"><div class="step-head"><span class="number">{n:02}</span><h2>{title}</h2></div>{body}</section>'

def check(text):
    return '<p class="check"><strong>확인</strong> '+text+'</p>'

def render():
    parts=[]
    parts.append(section(1,'ARROWS를 열고 그릴 준비하기','''<p>그림은 <b>Arrows</b>라는 무료 웹 도구로 그립니다. 원과 화살표로 무엇과 무엇이 어떻게 이어지는지 그려 보는 도구입니다. 위의 <b>ARROWS 열기</b>를 누르거나, 검색창에 <code>arrows.app</code>을 치고 주소가 <b>https://arrows.app</b>인 결과를 누르세요.</p>'''+shot('ui-01-search','검색 결과에서 주소가 arrows.app인 줄')+'''
<p>쿠키 안내는 아무 쪽이나 누르고 도움말 창은 아래 <b>Done</b>으로 닫습니다. 왼쪽 넓은 곳에 그리고, 오른쪽 칸에는 고른 것의 이름 같은 것을 적습니다. 가운데에 처음부터 있는 원을 첫 원으로 씁니다.</p>
<p>원이 이름을 적기에 작아서 먼저 키웁니다. <b>STYLE</b> 아래 <b>Customize</b>를 누르고 <b>radius</b>(원 크기)를 <code>50</code>에서 <code>60</code>으로 바꾼 뒤 <b>Tab</b>을 누르세요. 여기서 Enter를 치면 원이 하나 더 생깁니다. 앞으로 만드는 원도 이 크기로 나옵니다.</p>'''+shot('ui-02-radius','STYLE의 Customize와 radius 칸')+'''
<p>화살표에 적는 이름은 원래 화살표를 따라 기울어서 나오는데, 가로로 나와야 읽기 편합니다. 오른쪽 칸을 아래로 내려 <b>Arrows</b> 묶음의 <b>detail-orientation</b>을 <b>horizontal</b>로 바꾸고 칸을 다시 맨 위로 올리세요.</p>'''+shot('ui-03-orientation','Arrows 묶음의 detail-orientation')+'''
<p>그릴 자리를 넉넉히 쓰려고 첫 원을 왼쪽으로 옮겨 놓습니다. 원 안쪽을 잡고 끌되, 화면 끝에 바짝 대면 그림이 줄어드니 끝까지는 가져가지 마세요.</p>'''+check('radius가 60, detail-orientation이 horizontal이고, 빈 원이 그림판 왼쪽에 있습니다.')))
    parts.append(section(2,'설비 · 쿨러 · 센서 잇기','''<p>쿨러도 센서도 설비에 달려 있어서 설비부터 놓습니다. 옮겨 둔 원을 누르고 <b>Caption</b>에 이름을 적으세요. 이름만 봐서는 설비인지 부품인지 알 수 없으니 <b>+ Label</b>을 눌러 종류도 적고 <b>Tab</b>으로 마칩니다. 종류는 보통 영어로 적습니다. 적을 글은 모두 표에 있으니 복사해 오면 편합니다.</p>'''+shot('ui-04-caption','Caption 칸과 + Label')+nodes([
        (H,'Asset','(처음부터 있는 원)','설비입니다. HYD-01은 설비 번호입니다.'),
        (K,'Component',H,'부품입니다. 기름을 식히고, 이번에 고장 나는 곳입니다.'),
        (S,'Sensor',K,'쿨러가 잘 식히는지는 기름 온도(유온)를 재 봐야 압니다.')])+'''
<p>새 원은 이미 있는 원에서 끌어냅니다. 원을 누르면 둘레에 하늘색 띠가 생기는데, 안쪽을 잡으면 원이 옮겨지고 띠를 잡아 빈 곳에 놓아야 새 원이 나옵니다. 함께 생기는 화살표는 늘 끌기 시작한 원에서 새 원 쪽으로 나갑니다.</p>'''+shot('ui-05-ring','원을 눌렀을 때 둘레에 생기는 하늘색 띠')+'''
<p>선만으로는 둘이 무슨 사이인지 알 수 없어서 화살표에 이름을 붙입니다. 화살표는 모두 이 차례로 긋습니다.</p>
<ol><li>둘 사이를 한 문장으로 말합니다. <b>유압 파워팩은 오일 쿨러를 부품으로 가진다.</b></li><li>화살표가 그 문장의 주어(유압 파워팩)에서 나가 있는지 봅니다. 반대면 뒤집습니다(다음 단계에 나옵니다).</li><li>화살표를 누르고 <b>Type</b>에 「부품으로 가진다」에 해당하는 이름 <code>HAS_COMPONENT</code>를 적습니다. 영어 대문자로 쓰고 낱말 사이는 밑줄로 잇습니다.</li><li>화살표를 따라 읽어 봅니다. 나가는 쪽이 주어, 닿는 쪽이 상대입니다. 처음 말한 문장으로 읽히면 맞습니다.</li></ol>'''+shot('ui-06-type','화살표를 누르면 나오는 Type 칸')+rels([
        (H,K,'…를 부품으로 가진다','HAS_COMPONENT',KEEP),
        (K,S,'…로 감시된다','MONITORED_BY',KEEP)])+'''
<p>이름에 정답은 없고, 둘 사이가 누가 봐도 분명하게 읽히면 됩니다. 둘째 화살표도 「센서가 쿨러를 감시한다」고 할 수 있지만, 이름을 감시된다(MONITORED_BY)로 정했으면 주어는 쿨러이고 화살표도 쿨러에서 나가야 합니다.</p>'''+photo('01')+check('원 3개 · 화살표 2개. 설비에서 화살표 두 개를 따라가면 쿨러를 어느 센서로 보는지 나옵니다. 이론에서 원은 노드, 이름과 방향이 있는 화살표는 관계라고 했습니다.')))
    parts.append(section(3,'증상과 고장 유형 구분하기','''<p>어느 날부터 유온이 자꾸 오른다고 해 봅니다. 온도가 올랐다는 것은 센서에 잡힌 일이라 원으로 놓습니다. 다만 그것은 눈에 보인 신호이고, 진짜 문제는 쿨러가 기름을 못 식힌다는 것입니다. 온도는 다른 고장 때문에도 오를 수 있어서 둘을 한 원에 섞지 않습니다.</p>'''+nodes([
        (U,'Symptom',S,'증상입니다. 눈에 보인 이상을 말합니다.'),
        (F,'FailureMode',U,'고장 유형입니다. 어떤 기능을 잃었는지를 말합니다(식히는 힘).')])+'''
<p>첫 화살표의 문장은 <b>유온 상승은 유온 센서로 관측된다</b>이고 주어는 유온 상승인데, 센서에서 끌어냈기 때문에 화살표는 센서에서 나가 있습니다. 이대로 읽으면 「유온 센서가 유온 상승으로 관측된다」가 되니, 화살표를 누르고 <b>Reverse</b>로 뒤집은 뒤 Type을 적습니다. 끌어내다 보면 이렇게 거꾸로 나올 때가 있어서 문장을 먼저 말해 봅니다.</p>'''+shot('ui-07-reverse','화살표를 누르면 위쪽에 나오는 Reverse')+'''
<p>고장이 난 곳은 이미 있는 오일 쿨러입니다. 쿨러 원을 하나 더 만들면 그림에서 쿨러가 두 대가 되니, 고장을 누르고 띠를 <b>오일 쿨러</b> 원 위에 놓으세요. 원은 안 생기고 화살표만 생깁니다.</p>'''+rels([
        (U,S,'…로 관측된다','OBSERVED_BY',flip('센서')),
        (U,F,'…을 가리킨다','INDICATES',KEEP),
        (F,K,'…에서 일어난다','OCCURS_IN',onto('고장','오일 쿨러'))])+'''
<p>쿨러 같은 물건은 센서가 지켜본다고 감시(MONITORED_BY), 온도가 오른 것 같은 일은 센서에 잡혔다고 관측(OBSERVED_BY)으로 이름을 나눴습니다.</p>'''+photo('02')+check('원 5개 · 화살표 5개. 유온 상승은 유온 센서로 관측됐고 쿨러 냉각 성능 상실을 가리키며, 그 고장은 오일 쿨러에서 일어났습니다.')))
    parts.append(section(4,'원인과 증거 달기','''<p>왜 못 식히는지는 아직 모릅니다. 쿨러 안에는 핀이라는 얇은 날개가 촘촘히 서 있고, 팬 바람이 그 사이를 지나가며 열을 가져갑니다. 여기에 먼지가 끼면 바람길이 막힙니다. 고장이 왜 났는지를 말해 주는 것이 원인이고, 원인은 여러 가지일 수 있어서 원인마다 원을 하나씩 놓습니다.</p>'''+nodes([(PO,'Cause',F,'원인입니다. 핀에 먼지가 껴 바람길이 막힌 것입니다.')])+rels([
        (PO,F,'…을 일으킨다','CAUSES',flip('고장'))])+'''
<p><code>CAUSES</code>는 원인에서 고장 쪽으로만 긋기로 약속합니다. 그래야 나중에 고장에서 이 화살표를 거꾸로 따라가기만 해도 원인이 다 나옵니다.</p>
<p>핀 오염이 맞는지는 값을 재서 기준에 대어 봐야 압니다. 무슨 값을 어떤 기준에 대어 볼지 정해 둔 것이 이론에서 말한 증거입니다. 증거는 대어 보는 기준이라서 원을 새로 놓지 않고 핀 오염 원에 꼬리표처럼 답니다. 핀 오염을 누르고 <b>+ Property</b>를 눌러 왼쪽 칸에 무엇을 볼지, 오른쪽 칸에 기준을 적고 <b>Tab</b>을 누르세요. 오른쪽 칸에서 Enter를 치면 빈 줄이 하나 더 생깁니다. 둘째 줄은 <b>+ Property</b>를 한 번 더 누릅니다.</p>'''+table(['왼쪽 칸(무엇을 볼지)','오른쪽 칸(기준)','뜻'], [
        ('냉각 효율','30초 평균 < 70 %','쿨러가 열을 얼마나 빼내는지 본 값입니다. 70 %가 안 되면 제대로 못 빼는 것입니다.'),
        ('팬 진동','2분 평균 < 0.9 mm/s','팬이 떨리는 정도입니다. 탈 난 팬은 심하게 떨리니, 작으면 팬은 멀쩡한 것입니다.')])+shot('ui-08-property','Properties의 두 줄과 + Property. 원 옆에도 같은 두 줄이 붙습니다')+'''
<p>열을 못 빼는데 팬은 멀쩡하다면 핀이 막혔다고 볼 수 있어서, 두 줄이 다 맞아야 핀 오염입니다. 이렇게 원에 달아 둔 것을 이론에서 속성이라고 했습니다.</p>'''+photo('03')+check('원 6개 · 화살표 6개. CAUSES 화살표가 핀 오염에서 고장 쪽으로 나가고, 핀 오염 옆에 조건 두 줄이 있습니다.')))
    parts.append(section(5,'조치와 근거 매뉴얼 잇기','''<p>원인을 찾았으면 손을 봐야 합니다. 손보는 것은 사람이 하는 일이라 고장 · 원인과 다른 원으로 놓고, 종류는 Skill로 적습니다. 할 줄 아는 일 하나하나를 스킬이라고 부르는데 조치 하나가 그런 일 하나입니다. 조치에는 근거가 있어야 하니 그 조치가 적힌 매뉴얼의 절도 원으로 놓습니다. 절은 매뉴얼을 번호로 나눈 토막이고, HM-8.5는 쿨러 팬 매뉴얼 HM-8의 다섯 번째 절입니다. 절의 내용은 맨 위 <b>매뉴얼 근거</b> 단추로 볼 수 있습니다.</p>'''+nodes([
        (MX,'Skill',F,'완화 조치입니다. 팬을 가장 세게 돌려 우선 온도만 낮춥니다.'),
        (PC,'Skill',F,'근본 조치입니다. 핀을 닦아 원인인 먼지까지 없앱니다.'),
        (M85,'ManualSection',MX,'매뉴얼 절입니다. 팬을 세게 돌려 온도를 낮추는 방법이 적혀 있습니다.'),
        (M87,'ManualSection',PC,'핀을 닦는 법이 적힌 절입니다.')])+rels([
        (F,MX,'…으로 완화된다','MITIGATED_BY',KEEP),
        (F,PC,'…으로 근본 해결된다','REMEDIED_BY',KEEP),
        (PC,PO,'…을 없앤다','ADDRESSES',onto('핀 세척','쿨러 핀 오염')),
        (MX,M85,'…를 참조한다','REFERS_TO',KEEP),
        (PC,M87,'…를 참조한다','REFERS_TO',KEEP)])+'''
<p>완화와 근본 해결은 이름을 다르게 적어 둬야 온도만 낮춘 조치인지 원인까지 없앤 조치인지 헷갈리지 않습니다. 또 핀 세척은 핀 오염일 때만 통하니, 어느 원인에 맞는 조치인지도 <code>ADDRESSES</code>로 이어 둡니다.</p>'''+photo('04')+check('원 10개 · 화살표 11개. 핀 오염이라고 나오면 화살표만 따라가도 조치는 쿨러 핀 세척, 근거는 HM-8.7까지 나옵니다.')))
    parts.append(section(6,'다른 원인으로 넓히기','''<p>온도가 오르는 까닭이 핀 오염 하나만은 아닙니다. 고장은 같고 원인만 다르니, 원인을 하나씩 더 놓고 증거와 그 원인에 맞는 조치를 붙입니다.</p>'''+nodes([
        (FD,'Cause',F,'팬을 돌리는 벨트가 미끄러지면 팬이 제대로 못 돌아 바람이 줄고, 똑같이 열이 안 빠집니다.'),
        (FI,'Skill',F,'벨트를 살펴 손보는 근본 조치입니다. 팬이 문제인데 핀을 닦으면 안 됩니다.'),
        (M81,'ManualSection',FI,'벨트 살피는 법이 적힌 절입니다.')])+table(['증거를 달 원','왼쪽 칸','오른쪽 칸'], [(FD,'팬 진동','2분 평균 ≥ 0.9 mm/s')])+'''
<p>핀 오염의 팬 진동은 0.9 미만이고 여기는 0.9 이상입니다. 같은 값을 놓고 떨림이 작으면 핀 쪽, 크면 팬 쪽으로 원인이 갈립니다.</p>'''+rels([
        (FD,F,'…을 일으킨다','CAUSES',flip('고장')),
        (F,FI,'…으로 근본 해결된다','REMEDIED_BY',KEEP),
        (FI,FD,'…을 없앤다','ADDRESSES',onto('팬 점검','팬 구동 불량')),
        (FI,M81,'…를 참조한다','REFERS_TO',KEEP)])+photo('05')+'''
<p>원인이 하나 더 있습니다.</p>'''+nodes([
        (AT,'Cause',F,'설비를 넣어 둔 함(캐비닛) 안이 더우면 쿨러도 팬도 멀쩡한데 열이 안 빠집니다. 온도가 오른 일이지만 쿨러가 왜 못 식히는지를 말해 주는 까닭이라 원인으로 놓습니다.'),
        (CV,'Skill',AT,'필터를 청소하고 공기를 빼 주는 팬을 살펴 캐비닛에 바람이 통하게 하는 근본 조치입니다.')])+table(['증거를 달 원','왼쪽 칸','오른쪽 칸'], [(AT,'캐비닛 온도','2분 평균 ≥ 35 ℃')])+rels([
        (AT,F,'…을 일으킨다','CAUSES',flip('고장')),
        (CV,AT,'…을 없앤다','ADDRESSES',flip('원인')),
        (F,CV,'…으로 근본 해결된다','REMEDIED_BY',onto('고장','캐비닛 환기 보강')),
        (CV,M87,'…를 참조한다','REFERS_TO',onto('환기 보강','HM-8.7'))])+'''
<p>새 원은 이어질 원이면 어디서 끌어내도 되어서 환기 보강은 원인에서 끌어냈습니다. 그래서 화살표가 거꾸로 나와 「주변 온도 상승이 환기 보강을 없앤다」가 되니 뒤집습니다. 환기 보강 하는 법은 핀 세척과 같은 8.7절에 있어 이미 있는 HM-8.7 원에 잇기만 합니다. 절을 원으로 놓아 둔 덕분에 조치 둘이 같은 절을 근거로 삼습니다.</p>'''+photo('06')+check('원 15개 · 화살표 19개. 핀 오염에는 쿨러 핀 세척, 팬 구동 불량에는 팬 점검, 주변 온도 상승에는 캐비닛 환기 보강이 붙었습니다.')))
    parts.append(section(7,'고장이 고장으로 번지는 길과 절차 번호','''<p>고장이 다른 고장으로 번지는 경우도 있습니다. 팬의 축을 받쳐 주는 베어링이 닳으면(베어링 열화) 팬이 흔들리고, 그러다 쿨러까지 못 식히게 됩니다.</p>'''+nodes([
        (BR,'FailureMode',F,'알려 주는 증상이 따로 있어서 그 증상에서 출발해 찾아올 수 있어야 합니다. 그래서 원인 말고 고장 유형으로 놓습니다.'),
        (VB,'Symptom',BR,'베어링이 닳으면 팬 진동이 커집니다. 원인에 단 팬 진동은 재서 견주는 기준이고, 이것은 실제로 일어난 일이라 원으로 놓습니다.')])+rels([
        (BR,F,'…로 이어진다','LEADS_TO',flip('쿨러 냉각 성능 상실')),
        (VB,BR,'…를 가리킨다','INDICATES',flip('베어링 열화'))])+'''
<p>여기는 양쪽이 다 고장이라 <code>CAUSES</code>를 쓰지 않습니다. 쓰면 나중에 거꾸로 따라갔을 때 원인과 고장이 섞여서 나옵니다. 고장이 고장으로 이어질 때는 <code>LEADS_TO</code>를 씁니다.</p>
<p>남은 것은 절차 번호입니다. 매뉴얼 한 절 안에는 작업 순서가 여러 개 적혀 있습니다. 이 작업 순서를 절차라고 하고, 현장에서는 표준 작업 절차를 줄여 SOP라고 부르며 SOP로 시작하는 번호를 붙입니다. 같은 8.7절이어도 핀 세척과 환기 보강이 따르는 절차는 다릅니다. 번호를 8.7절 원에 적으면 두 조치가 같은 번호를 보게 되니, 조치에서 절로 가는 화살표에 적습니다. 화살표를 누르고 <b>+ Property</b>의 왼쪽 칸에 <code>절차</code>, 오른쪽 칸에 번호를 적은 뒤 <b>Tab</b>을 누르세요.</p>'''+table(['누를 화살표','왼쪽 칸','오른쪽 칸'], [
        (FI+' → '+M81,'절차','SOP-FAN-11'),(CV+' → '+M87,'절차','SOP-COOL-15'),(PC+' → '+M87,'절차','SOP-COOL-14'),(MX+' → '+M85,'절차','SOP-COOL-11')])+shot('ui-09-procedure','화살표의 Properties에 적은 절차 번호와 그림에 붙은 모습')+photo('07')+check('원 17개 · 화살표 21개. HM-8.7로 들어가는 화살표 둘의 번호가 SOP-COOL-14와 SOP-COOL-15로 다릅니다.')))
    parts.append(section(8,'색칠하고 그림으로 판단하기','''<p>판단에 쓰기 전에 원인과 조치가 눈에 잘 띄게 색을 넣습니다. <b>쿨러 핀 오염</b>을 누르고 <b>Ctrl</b>을 누른 채 <b>팬 구동 불량</b>, <b>주변 온도 상승</b>을 누르세요. 오른쪽에 <b>nodes: 3</b>이 나오면 셋이 같이 골라진 것입니다. <b>node-color</b> 칸에 연한 빨강 <code>#fca5a5</code>를 넣고 <b>Tab</b>을 누르면 한꺼번에 칠해집니다. 조치 넷(<b>팬 최대 운전</b> · <b>쿨러 핀 세척</b> · <b>캐비닛 환기 보강</b> · <b>팬 점검</b>)에는 연한 초록 <code>#86efac</code>를 넣고, 빈 곳을 눌러 고른 것을 푸세요.</p>'''+shot('ui-10-color','함께 고른 원의 수와 node-color 칸. 왼쪽에 칠해진 쿨러 핀 오염이 보입니다')+'''
<p>이제 그림을 써 봅니다. 유온이 올라서 경보가 왔다면, 유온 상승이 가리키는 고장은 쿨러 냉각 성능 상실이고, 여기로 들어오는 <code>CAUSES</code>를 거꾸로 따라가면 원인 셋이 나옵니다. 어느 것인지는 증거로 가립니다. 이론에서 본 쿨러 사건의 값은 냉각 효율 30초 평균 <b>46.2 %</b>, 팬 진동 2분 평균 <b>0.575 mm/s</b>, 캐비닛 온도 2분 평균 <b>28 ℃</b>입니다.</p>'''+shot('ui-11-judge','색칠을 마친 그림. 빨간 네모가 값과 견줄 원인과 조건입니다')+check('핀 오염의 두 줄만 맞습니다(46.2는 70 미만, 0.575는 0.9 미만). 화살표를 따라가면 조치는 쿨러 핀 세척, 근거는 HM-8.7, 절차는 SOP-COOL-14입니다. 세척은 설비를 세워야 하니 그 전에 팬 최대 운전으로 온도부터 낮춰 둡니다.')+'''
<p>값이 다르면 가는 길도 달라집니다.</p>
<ul><li>팬 진동이 <b>1.4 mm/s</b>였다면 0.9 이상이라 팬 구동 불량이 남고, 길은 팬 점검, HM-8.1, SOP-FAN-11입니다. 진동 증가가 가리키는 팬 베어링 열화도 같이 의심하고, 상한 팬을 세게 돌리면 진동이 더 커지니 팬 최대 운전은 쓰지 않습니다.</li><li>처음 값에서 캐비닛 온도만 <b>38 ℃</b>였다면 주변 온도 상승과 핀 오염이 둘 다 맞습니다. 하나 맞았다고 멈추지 말고 캐비닛 환기 보강과 쿨러 핀 세척을 둘 다 봅니다.</li><li>팬 진동 값을 아직 못 받았다면 두 줄이 다 맞는지 알 수 없으니 핀 오염이라고 정하지 않고, 보류해 두고 진동 값부터 받습니다.</li></ul>'''))
    parts.append(section(9,'파일로 남기고 다시 열기','''<p>그린 것은 파일로 받아 둬야 나중에 이어서 고칠 수 있습니다. 위쪽 <b>Download / Export</b>를 누르세요. 처음 열려 있는 <b>PNG</b>는 보고서 같은 데 붙이는 그림 파일입니다. 맨 위 줄의 <b>Download</b> 하나만 받으면 됩니다.</p>'''+shot('ui-12-export-png','PNG 탭과 맨 위 줄의 Download')+'''
<p>나중에 다시 열어서 고치려면 원과 화살표를 글자로 적어 둔 JSON 파일이 있어야 합니다. <b>JSON</b> 탭에서도 <b>Download</b>를 누르고 <b>Done</b>으로 닫으세요.</p>'''+shot('ui-13-export-json','JSON 탭의 Download')+'''
<p>받은 파일이 잘 열리는지 새 그림에서 확인합니다. 원이나 화살표를 여러 개 골라 둔 채로는 새 그림으로 넘어가지 않으니, 먼저 빈 곳을 눌러 고른 것을 푸세요. 왼쪽 위 로고를 누르면 <b>Web Browser storage</b>가 두 군데 있는데, <b>New</b>에 커서를 올리면 나오는 쪽을 눌러야 합니다. 새 그림이 열려도 메뉴는 떠 있으니 그림 쪽을 한 번 눌러 닫고, 다시 로고에서 <b>Import</b>를 누르세요.</p>'''+shot('ui-14-menu','로고, New에 올리면 나오는 Web Browser storage, Import')+'''
<p><b>Choose File</b>로 방금 받은 <code>Untitled graph.json</code>을 고르고 아래 <b>Import</b>를 누르세요.</p>'''+shot('ui-15-import','Choose File과 아래 Import')+'''
<p>들어온 것이 전부 골라져 있어서 오른쪽 위에 개수가 나옵니다. 원 크기와 화살표 이름의 방향이 처음대로 돌아와 있는데 잘못 들어온 것이 아닙니다. 처음에 Customize에서 바꾼 두 가지는 같이 따라오지 않습니다. 새 그림에 처음부터 있던 빈 원은, 빈 곳을 눌러 고른 것을 푼 뒤 그 원만 누르고 오른쪽 <b>Delete</b>로 지우세요.</p>'''+shot('ui-16-imported','다시 연 그림의 원 · 화살표 수와 지울 빈 원')+check('nodes: 17 · relationships: 21로 그린 것과 같고, 원인 옆의 조건과 화살표의 절차 번호, 색이 함께 들어와 있습니다.')+'''<p>받은 두 파일은 이름이 <code>Untitled graph</code>라서 <code>쿨러_지식그래프.json</code>, <code>쿨러_지식그래프.png</code>로 바꿔 두세요.</p><p class="save">학교 PC는 껐다 켜면 받은 파일이 지워지니, 두 파일을 USB나 본인 클라우드에 옮겨 두세요.</p>
<p>마지막으로, 컴퓨터가 이 그림을 쓰려면 그림이 데이터를 쌓아 두는 데이터베이스에 들어가 있어야 합니다. 이론에서 이름을 본 Neo4j가 이런 그림을 담는 데이터베이스입니다. <b>Download / Export</b>를 다시 누르고 <b>Cypher</b> 탭을 누르면 이 그림을 Neo4j에 넣는 명령이 나옵니다. 맨 앞 <code>CREATE</code>가 만들라는 뜻입니다. <b>Done</b>으로 닫으세요.</p>'''+shot('ui-17-cypher','Cypher 탭과 CREATE로 시작하는 명령')+check('글이 CREATE로 시작하고, 그 뒤로 원과 화살표, 속성까지 다 들어 있습니다.')))
    nav=''.join(f'<a href="#step{i}">{i:02} {t}</a>' for i,t in enumerate(['열기·준비','설비·쿨러·센서','증상·고장 유형','원인·증거','조치·매뉴얼','원인 넓히기','번지는 고장·절차','색칠·판단','저장·다시 열기'],1))
    return '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>쿨러 지식 그래프 만들기 · 실습 가이드</title><style>
:root{--ink:#213330;--muted:#5a6c67;--line:#dce5df;--green:#216953;--paper:#fff;--bg:#f4f6f2}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:30px}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.85 "Malgun Gothic","Segoe UI",sans-serif}a{color:var(--green);text-underline-offset:4px}a:focus-visible,button:focus-visible{outline:3px solid #d18424;outline-offset:4px}.shell{max-width:1380px;margin:auto;padding:56px 36px}header{padding:40px 48px;background:#e6eee6;border-radius:22px;margin-bottom:36px}.eyebrow{font-size:13px;font-weight:700;letter-spacing:2px;color:var(--green)}h1{font-size:40px;letter-spacing:-1.8px;line-height:1.3;margin:16px 0}header p{max-width:860px;margin:0 0 10px;color:#40584f}.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:26px}.button{display:inline-block;padding:11px 22px;background:var(--green);color:white;text-decoration:none;border-radius:9px;font-weight:700}.button.secondary{background:white;color:var(--green)}.layout{display:grid;grid-template-columns:170px minmax(0,1fr);gap:32px}nav{position:sticky;top:30px;align-self:start}nav span{display:block;color:var(--muted);font-size:12px;letter-spacing:2px;margin:8px 0 16px}nav a{display:block;padding:10px 12px;margin-bottom:5px;text-decoration:none;font-size:14px;border-radius:7px}nav a:hover{background:#e6eee6}section{background:var(--paper);border:1px solid var(--line);border-radius:16px;padding:36px;margin-bottom:32px}.step-head{display:flex;gap:16px;align-items:center;border-bottom:1px solid var(--line);padding-bottom:24px;margin-bottom:24px}.number{font:600 27px/1 Georgia,serif;color:var(--green)}h2{font-size:25px;line-height:1.4;margin:0;letter-spacing:-.7px}p{margin:18px 0}ol,ul{margin:18px 0;padding-left:26px}li{margin:6px 0}b,strong{font-weight:700}code{font-family:Consolas,monospace;background:#edf3ee;padding:3px 6px;border-radius:4px;user-select:all;font-size:.95em}.table-wrap{overflow:auto;margin:24px 0}table{width:100%;border-collapse:collapse;font-size:14px;line-height:1.7}th{text-align:left;background:#f0f4ef;color:#445e52;font-weight:600;white-space:nowrap}td,th{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top}td{user-select:text}figure{margin:28px 0}img{display:block;max-width:100%;height:auto;margin:0 auto;border:1px solid var(--line);border-radius:9px}figcaption{font-size:13px;color:var(--muted);margin-top:10px}.check{padding:18px 20px;background:#edf5ee;border-left:3px solid #45846a;border-radius:0 8px 8px 0;font-size:15px}.check strong{display:block;color:var(--green);margin-bottom:4px}.save{padding:18px 20px;background:#faf4e6;border-radius:8px;font-size:15px}footer{color:var(--muted);font-size:13px;text-align:center;padding:16px}.top{display:inline-block;margin-top:12px}@media(max-width:850px){.shell{padding:20px 14px}header{padding:28px 22px}h1{font-size:30px}.layout{display:block}nav{position:static;display:flex;flex-wrap:wrap;margin-bottom:20px;gap:4px}nav span{display:none}nav a{padding:6px 9px;font-size:12px;background:white}section{padding:24px 18px}h2{font-size:22px}.step-head{gap:12px}}@media print{body{background:white}.shell{padding:0}nav,.actions,.top{display:none}.layout{display:block}section{break-before:page;border:0;padding:0}figure,table,.check{break-inside:avoid}a{color:inherit}}
</style></head><body><div class="shell"><header><div class="eyebrow">1회차 · 통합반 / 실전반 공통</div><h1>쿨러 지식 그래프 만들기</h1><p>설비 온도가 오르면 현장에서는 왜 오르는지, 그래서 무엇을 해야 하는지부터 찾습니다. 이론에서 본 쿨러 이야기로 그 찾아가는 길을 그림 한 장에 그립니다.</p><p>그리는 것은 원을 놓고 화살표로 잇는 일이 전부입니다. 다만 원은 놓을 때마다 이것이 무엇인지 정하고, 화살표는 그을 때마다 둘이 무슨 사이인지 한 문장으로 말해 본 뒤 긋습니다. 단계마다 놓을 원과 그을 화살표가 표에 있고, 사진의 빨간 네모가 누르거나 볼 곳입니다. 사진을 누르면 크게 볼 수 있습니다.</p><div class="actions"><a class="button" href="https://arrows.app" target="_blank" rel="noopener">ARROWS 열기 ↗</a><a class="button secondary" href="매뉴얼_발췌.md">매뉴얼 근거</a></div></header><div class="layout"><nav aria-label="실습 단계"><span>진행 순서</span>'''+nav+'</nav><main>'+''.join(parts)+'''<a class="top" href="#">맨 위로 ↑</a></main></div><footer>쿨러 지식 그래프 · 통합반 / 실전반 공통 실습</footer></div></body></html>'''

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--video',type=Path)   # 없으면 지금 사진 · 사진 근거를 그대로 두고 가이드 · 한 파일 가이드만 다시 만든다
    args=parser.parse_args()
    sys.path.insert(0,str(ROOT/'workspace/강의제작/제작도구/실습시작'))
    from lab_package import pack_page
    guide=render()
    guide=guide.replace('<style>','<style>.added{border-top:1px solid #dce5df;padding-top:18px;color:#216953;font-size:15px}.added b{display:inline-block;background:#e6eee6;padding:3px 10px;border-radius:5px;margin-right:8px}')
    source=ROOT/'workspace/강의제작/산출물/통합반/실습/01회차/랩'/LAB
    images=source/'images'
    if args.video:
        build_images(args.video, images)
    for course in ['통합반','실전반']:
        lab=ROOT/'workspace/강의제작/산출물'/course/'실습/01회차/랩'/LAB
        if lab!=source:
            if (lab/'images').exists():shutil.rmtree(lab/'images')   # 가이드가 열지 않는 옛 사진을 남기지 않는다(P-13)
            shutil.copytree(images,lab/'images')
        (lab/'가이드.html').write_text(guide,encoding='utf-8')
        pack_page(lab)
    print('두 과정 가이드 · 한 파일 가이드(<랩>.html) 갱신.')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def frame(video, sec, out):
    import imageio_ffmpeg
    from PIL import Image
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-ss',f'{sec:.2f}','-i',str(video),'-frames:v','1','-y',str(out)],check=True)
    im=Image.open(out).convert('RGB')
    if im.size!=(1920,1080):raise SystemExit(f'{out.name}: 프레임 크기 {im.size}')
    return im

def build_images(video, images):
    """images/를 낸 영상의 UI_SHOTS · STAGE_SHOTS 프레임으로 새로 채우고 사진 근거를 고쳐 쓴다."""
    import imageio_ffmpeg, tempfile
    probe=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-i',str(video)],capture_output=True).stderr.decode('utf-8','replace')
    dur=[l.split('Duration:')[1].split(',')[0].strip() for l in probe.splitlines() if 'Duration:' in l]
    if dur!=[VIDEO_DURATION]:
        raise SystemExit(f'{video}: 낸 영상({VIDEO_DURATION})이 아니다 — Duration {dur}')
    if images.exists():shutil.rmtree(images)
    images.mkdir()
    manifest={'video':{'file':'Release 영상 통합반_01회차_08_실습_관계그림.mp4','duration':VIDEO_DURATION,'sha256':sha(video)},
              'box':{'color':'#e60000','width':LINE,'note':'대상 경계 바깥 margin px에서 굵기 6 선이 바깥으로 그려진다. outer는 네모 바깥 경계다'},
              'ui_frames':[],'stage_frames':[]}
    shots=[(name,sec,crop,boxes,'ui_frames') for name,sec,crop,boxes in UI_SHOTS]+[(f'stage-{n}',sec,STAGE_CROP,boxes,'stage_frames') for n,(sec,boxes) in STAGE_SHOTS.items()]
    with tempfile.TemporaryDirectory() as tmp:
        for name,sec,crop,boxes,kind in shots:
            raw=Path(tmp)/f'{name}.png'
            im=frame(video,sec,raw)
            outer=draw_boxes(im,boxes)
            if crop:
                for o,_ in outer:
                    if o[0]<crop[0] or o[1]<crop[1] or o[2]>=crop[2] or o[3]>=crop[3]:raise SystemExit(f'{name}: 네모 {o}가 자름 {crop} 밖으로 나간다')
                im=im.crop(crop)
            im.save(images/f'{name}.png')
            manifest[kind].append({'file':f'images/{name}.png','seconds':sec,'frame_sha256':sha(raw),'crop':list(crop) if crop else None,
                                   'boxes':[{'target':list(b[:4]),'margin':b[4],'outer':o,'dark_px_under_line':n} for b,(o,n) in zip(boxes,outer)],'sha256':sha(images/f'{name}.png')})
    (Path(__file__).parent/'학생가이드_사진근거.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':main()
