"""낸 영상에서 조작 화면 사진을 뽑고 단계 결과 그림에 네모를 그려, 두 과정 학생 가이드와 한 파일 가이드(<랩>.html, lab_package.pack_page)를 갱신한다.
Usage: python build_student_guide.py [--video <낸 mp4> --captures <따로 찍은 사진 폴더>]
  --video와 --captures를 함께 주면 images/를 새로 만들고 사진 근거(학생가이드_사진근거.json)를 고쳐 쓴다.
    --video: 영상 프레임에서 UI_SHOTS(조작 화면) · STAGE_SHOTS(단계 결과 그림)를 뽑는다.
    --captures: 영상에 없는 11단계(파일로 남기기 · 다시 열기 — 영상은 말로만 짚는다) 화면을 같은 화면 값으로 따로 찍은 1920×1080 사진 폴더. CAPTURE_SHOTS가 그 파일을 자르고 네모를 그린다.
  둘 다 없으면 지금 사진과 사진 근거를 그대로 두고 가이드 · 한 파일 가이드만 다시 만든다.
네모: 대상 바깥 margin px(기본 6)에 굵기 6 빨간 선(가이드 P-8). 옆 글자에 걸리는 곳은 margin을 줄였다.
가이드 글의 까닭(원마다 왜 놓는지, 화살표마다 쉬운 뜻 · 말로 하면 · 왜 그 방향인지)은 대본원고.md의 그 자리 말을 줄인 것이다. 대본에 없는 까닭을 여기서 새로 짓지 않는다.
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
# 낸 실습 영상(통합반_01회차_08_실습_관계그림.mp4, 34:02.90 — 2026-11-20 클라우드 Playwright 헤드리스 새 대본 판, sha256 65f1cf2a)에서 뽑는 ARROWS 화면.
# 시각은 합성기록(합성기록/통합1-08-관계그림.json)의 큐 시각 안에서, 영상이 그리는 강조(동그라미 · 밑줄 · 띠 · 테두리)가 없고 커서가 대상을 가리지 않으며 값이 다 들어간 순간을 프레임을 보며 골랐다.
# boxes: (x0, y0, x1, y1, margin) — 대상 경계(프레임 px)와 대상 바깥 간격. crop: 오른쪽 칸 · 창처럼 볼 곳만 자를 때(글자가 가이드 폭에서 읽히게).
VIDEO_DURATION = '00:34:02.90'
STAGE_CROP = (0, 38, 1537, 1053)   # 그림판(위 막대 아래 ~ 오른쪽 칸 앞 ~ 아래 막대 위)
PANEL = (1000, 0, 1920, 640)       # 오른쪽 칸과 그 옆 그림판
PANEL_ONLY = (1480, 0, 1920, 640)  # 오른쪽 칸만(그 옆 그림판이 비어 있는 1 · 2 · 3단계)
UI_SHOTS = [
    ('ui-01-search', 49.6, (60, 120, 760, 340), [(142, 158, 280, 218, 4)]),                                                      # g005: 검색 결과에서 주소가 arrows.app인 줄(커서가 누르러 온 자리)
    ('ui-02-cookie', 54.5, (200, 600, 1720, 1080), [(1268, 1039, 1446, 1057, 4)]),                                              # g006 앞: 쿠키 안내의 Use necessary cookies only
    ('ui-03-done', 57.95, (580, 620, 1360, 1060), [(1218, 919, 1287, 953, 3)]),                                                 # g006: 쿠키 안내가 닫혀 보이는 도움말 창의 Done(커서는 아래쪽)
    ('ui-04-radius', 110.8, PANEL_ONLY, [(1718, 213, 1816, 244, (2, 4, 4, 4)), (1670, 546, 1760, 568, (4, 4, 4, 2))]),               # g011 앞: Customize · radius 60(오른쪽 칸을 맨 위로 올린 뒤)
    ('ui-05-orientation', 108.5, (1480, 0, 1920, 760), [(1616, 636, 1804, 658, 3)]),                                            # g010 끝: detail-orientation horizontal(강조가 꺼진 뒤)
    ('ui-06-caption', 202.5, PANEL_ONLY, [(1550, 236, 1906, 268, (2, 0, 2, 2)), (1550, 304, 1906, 335, (2, 2, 2, 0)), (1834, 348, 1907, 375, (4, 0, 4, 4))]),   # g017: Caption · Labels의 Asset · + Label
    ('ui-07-ring', 391.7, (0, 430, 760, 680), [(349, 478, 482, 612, 3)]),                                                       # g028: 쿨러를 누른 둘레의 하늘색 띠 — 커서가 띠를 잡는 자리
    ('ui-08-type', 312.0, PANEL_ONLY, [(1550, 266, 1906, 298, (2, 0, 2, 2))]),                                                       # g024: 화살표의 Type(HAS_COMPONENT)
    ('ui-09-reverse', 533.0, PANEL_ONLY, [(1619, 112, 1712, 141, (3, 3, 1, 3))]),                                                    # g040: Reverse(뒤집고 OBSERVED_BY를 적은 뒤)
    ('ui-10-property', 878.0, PANEL, [(1550, 399, 1906, 459, (2, 2, 2, 0)), (1817, 475, 1907, 502, (4, 2, 4, 4))]),             # g061 앞: Properties 두 줄 · + Property
    ('ui-11-procedure', 1764.5, (860, 0, 1920, 672), [(1550, 333, 1906, 366, 2), (891, 224, 1035, 270, 2)]),                    # g116 앞: 화살표의 절차 속성 · 그림판에 붙은 번호(SOP-COOL-11)
    ('ui-12-color', 1807.0, (860, 0, 1920, 800), [(1550, 72, 1653, 98, (4, 0, 4, 4)), (1652, 662, 1800, 686, (3, 3, 3, 1))]),   # g119 앞: nodes: 3 · node-color(색 고르는 판이 함께 떠 있다)
    ('ui-13-judge', 1853.0, STAGE_CROP, [(1195, 260, 1504, 398, (4, 4, 4, 2)), (182, 280, 474, 400, 4), (722, 891, 1020, 1010, 4)]),   # g122 앞: 원인 셋과 증거 · 오른쪽 위 잰 값 글상자
]
# 단계 결과 그림 — 같은 영상에서 그 단계의 마지막 입력이 끝나고 강조가 없는 순간(커서는 오른쪽 칸)의 그림판을 자르고, 「이번에 추가」한 곳에 네모를 둔다. 열쇠는 가이드 단계 번호다.
STAGE_SHOTS = {
    '02': (426.5, [(58, 486, 474, 802, 6)]),                                                                       # 설비 · 쿨러 · 센서
    '03': (661.0, [(498, 486, 745, 802, 4)]),                                                                      # 유온 상승 · 쿨러 냉각 성능 상실과 화살표 셋
    '04': (878.0, [(1195, 260, 1520, 398, 6), (948, 427, 1015, 449, 3)]),                                          # 쿨러 핀 오염과 증거 두 줄 · CAUSES
    '05': (1173.3, [(903, 78, 1021, 398, 6), (1195, 438, 1313, 802, 6), (763, 436, 866, 458, 3), (907, 534, 1013, 553, 3)]),   # 팬 최대 운전 → 8.5절 · 핀 세척 → 8.7절 · MITIGATED_BY · REMEDIED_BY
    '06': (1333.5, [(58, 78, 474, 402, 6)]),                                                                       # 팬 구동 불량과 증거 · 팬 점검 → 8.1절
    '07': (1496.2, [(731, 884, 1313, 1012, (6, 2, 6, 6)), (1203, 840, 1305, 862, 2)]),                              # 주변 온도 상승과 증거 · 캐비닛 환기 보강 · 8.7절로 가는 REFERS_TO
    '08': (1776.0, [(627, 78, 745, 444, 6), (215, 120, 340, 158, 4), (891, 224, 1035, 270, 2), (1187, 611, 1324, 656, 3), (1187, 832, 1324, 877, 3)]),   # 진동 증가 → 팬 베어링 열화 · 절차 번호 넷
}
# 영상 밖에서 따로 찍은 11단계 화면(영상은 「내보내고 불러오기는 설명만」 — 사용자 2026-11-20). (사진 이름, --captures 폴더의 원본 파일, 자름, 네모)
CAPTURE_SHOTS = [
    ('ex-01-button', 'ex-00-main.png', (960, 0, 1920, 280), [(1496, 3, 1656, 35, (4, 0, 4, 4))]),                              # 위쪽 Download / Export
    ('ex-02-png', 'ex-01-png.png', (430, 55, 1490, 850), [(465, 146, 515, 178, 3), (488, 377, 647, 397, 4)]),                 # PNG 탭 · 맨 위 줄 Download
    ('ex-03-json', 'ex-02-json.png', (430, 55, 1490, 810), [(654, 146, 709, 178, 3), (479, 207, 592, 238, 4)]),               # JSON 탭 · Download
    ('ex-04-cypher', 'ex-03-cypher.png', (430, 55, 1490, 838), [(580, 146, 645, 178, 3), (498, 301, 567, 319, (3, 3, 3, 0))]),           # Cypher 탭 · CREATE
    ('ex-05-menu', 'ex-04-menu.png', (0, 0, 1000, 420), [(10, 6, 38, 34, 2), (86, 110, 238, 134, 3), (12, 154, 58, 174, 3)]), # 로고 · New에 올리면 나오는 Web Browser storage · Import — New 네모는 로고 네모와 붙어 겹쳐서 뺐다
    ('ex-06-import', 'ex-05b-chosen.png', (430, 55, 1490, 682), [(465, 273, 600, 305, 4), (1382, 622, 1458, 654, 4)]),        # Choose File로 고른 JSON이 들어온 Import 창 · 아래 Import
    ('ex-07-imported', 'ex-06-imported.png', None, [(1550, 73, 1817, 99, (4, 0, 4, 3)), (44, 119, 138, 214, 3)]),             # 다시 연 그림의 nodes: 17 · relationships: 21 · 지울 빈 원
]
CAPTURE_NOTE = {'source': '따로 찍음(영상 밖)', 'date': '2026-11-20',
                'screen': '클라우드 Playwright 헤드리스 Chromium(촬영도구 run.sh up · open, config.json cloud) — CSS 2128×1197 × 배율 0.9022556 = 1920×1080, 맑은 고딕',
                'state': '끝 그림 take r2-11 end-state를 새 그림에 가져와 radius 60 · detail-orientation horizontal로 맞춘 뒤(run.sh restore가 이 화면 값에서 오른쪽 칸을 접어 같은 일을 스크립트가 했다) Download / Export → PNG · JSON 받기 → Cypher 탭 → Done → New › Web Browser storage → Import(받은 JSON) 차례로 실제로 눌렀다',
                'result': '다시 연 그림: 원 18(빈 원 1 + 17) · 화살표 21 · 색 7 · 증거 4줄 · 절차 번호 4(SOP-COOL-11 · 14 · 15 · SOP-FAN-11), radius 50 · detail-orientation parallel(Customize 값은 따라오지 않음), 빈 원을 지운 뒤 원 17 · 화살표 21',
                'script': '촬영/arrows/따로찍은사진/capture.mjs · dismiss.mjs(끝 그림은 같은 폴더 끝그림.json), 빈 원을 지운 뒤 개수를 센 cleanup_check.mjs는 작업 폴더(git 밖)'}
STAGE_ADDED = {'02': '설비 · 오일 쿨러 · 유온 센서', '03': '유온 상승 · 쿨러 냉각 성능 상실과 화살표 셋', '04': '쿨러 핀 오염 · 증거 두 줄 · CAUSES',
               '05': '팬 최대 운전 · 쿨러 핀 세척 · 매뉴얼 절 둘', '06': '팬 구동 불량 · 팬 점검 · HM-8.1', '07': '주변 온도 상승 · 캐비닛 환기 보강 · 8.7절로 가는 화살표',
               '08': '팬 베어링 열화 · 진동 증가 · 절차 번호 넷'}
STAGE_CAPTION = '이 단계를 마친 그림. 빨간 네모가 이번에 더한 곳입니다'
H, K, S, U, F = 'HYD-01 유압 파워팩', '오일 쿨러', '유온 센서 TS1', '유온 상승', '쿨러 냉각 성능 상실'
PO, MX, PC, M85, M87 = '쿨러 핀 오염', '팬 최대 운전', '쿨러 핀 세척', 'HM-8.5 즉시 완화 조치', 'HM-8.7 근본 조치'
FD, FI, M81, AT, CV, BR, VB = '팬 구동 불량', '팬 점검', 'HM-8.1 팬 벨트 점검', '주변 온도 상승', '캐비닛 환기 보강', '팬 베어링 열화', '진동 증가'
RED_HEX, GREEN_HEX = '#fca5a5', '#86efac'


class Raw(str):
    """이미 HTML인 칸(복사 단추 등) — table()이 이스케이프하지 않는다."""


_copy_ids = []


def cp(text):
    """적을 글 하나와 그 복사 단추(가이드 P-7). 복사되는 것은 code 안의 글뿐이다."""
    n = f'c{len(_copy_ids) + 1:02}'
    _copy_ids.append(n)
    return Raw(f'<span class="cp"><code id="{n}">{html.escape(text)}</code><button type="button" data-copy="{n}">복사</button></span>')


def cell(x):
    return x if isinstance(x, Raw) else html.escape(x)


def table(headers, rows):
    return '<div class="table-wrap"><table><thead><tr>' + ''.join('<th>'+html.escape(x)+'</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join('<td>'+cell(x)+'</td>' for x in row)+'</tr>' for row in rows) + '</tbody></table></div>'


def nodes(rows):
    """놓을 원: 이름 · 종류(둘 다 복사 단추) · 띠를 끌어낼 원 · 왜 놓는지."""
    return table(['Caption · 이름', 'Label · 종류', '끌어낼 원', '왜 놓나'], [(cp(a), cp(b), c, d) for a, b, c, d in rows])


def rels(rows):
    """그을 화살표: 쉬운 뜻 · 말로 하면(앞이 주어 = 화살표가 나가는 원, 영상 g022 「말로 하면」) · 이름(복사 단추) · 방향(맞는지, 뒤집는지, 있는 원 위에 놓는지)."""
    return table(['쉬운 뜻', '말로 하면', 'Type · 화살표 이름', '방향'], [(a, b, cp(c), d) for a, b, c, d in rows])


def evidence(rows):
    """증거 한 줄 = 앞 칸(무엇을 볼지) + 뒤 칸(기준). 영상 말과 같은 이름이다."""
    return table(['증거를 붙일 원', '앞 칸 · 무엇을 볼지', '뒤 칸 · 기준'], [(a, cp(b), cp(c)) for a, b, c in rows])


def keep(src):
    return f'맞음({src}에서 끌어냄)'


def flip(src):
    """주어가 아닌 원에서 끌어내 화살표가 거꾸로 나온 자리."""
    return f'Reverse로 뒤집기({src}에서 끌어내 거꾸로 나옴)'


def onto(a, b):
    """주어의 띠를 이미 있는 원 위에 놓아 화살표만 만드는 자리."""
    return f'{a}의 띠를 {b} 원 위에 놓기'


def figure(file, caption):
    return f'<figure><a href="{file}" target="_blank"><img src="{file}" alt="{caption}" loading="lazy"></a><figcaption>{caption}</figcaption></figure>'


def photo(stage, caption=STAGE_CAPTION):
    """단계 결과 그림. 빨간 네모는 이번 단계에서 더한 곳이다."""
    return f'<p class="added"><b>이번에 추가</b> {STAGE_ADDED[stage]}</p>'+figure(f'images/stage-{stage}.png', caption)


def shot(name, caption):
    """ARROWS 화면 사진. 빨간 네모는 누르거나 입력할 곳, 볼 곳이다."""
    return figure(f'images/{name}.png', caption)


def draw_boxes(im, boxes):
    """대상 바깥 margin에 굵기 LINE 네모를 그린다. 화면 밖으로 나가는 변은 화면 끝에 붙인다. 네모끼리 겹치면 멈춘다.
    margin은 네 변 같은 값 하나 또는 (왼, 위, 오른, 아래). 돌려주는 값: 네모마다 (바깥 경계, 선 아래에 깔린 어두운 화소 수 — 글자 · 선을 덮었는지 재는 값)."""
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


def why(text):
    """무엇을 왜 놓는지 — 두어 문장."""
    return f'<p class="why">{text}</p>'


def check(text):
    return '<p class="check"><strong>확인</strong> '+text+'</p>'


def note(text):
    """정상 진행 밖의 한 줄(엔터 같은 예외, 이론 이름 되짚기) — 그 단계 끝에 둔다(가이드 P-5)."""
    return f'<p class="note">{text}</p>'


STEPS = ['열기 · 원 크기', '설비 · 쿨러 · 센서', '증상 · 고장 유형', '원인 · 증거', '조치 · 매뉴얼', '팬 구동 불량', '주변 온도 상승', '번지는 고장 · 절차', '색칠', '판단하기', '저장 · 다시 열기']


def render():
    _copy_ids.clear()
    parts=[]
    parts.append(section(1,'Arrows를 열고 원 크기 맞추기',
        why('Arrows는 원과 화살표로 무엇과 무엇이 어떻게 이어지는지 그리는 무료 웹 도구입니다. 지식 그래프를 그래프 데이터베이스에 넣기 전에, 무엇을 어떤 종류로 두고 어떤 관계로 이을지 손으로 먼저 설계해 볼 때 씁니다.')+
        '<p>위의 <b>ARROWS 열기</b>를 누르거나, 검색창에 <code>arrows.app</code>을 치고 주소가 <b>https://arrows.app</b>인 결과를 누르세요.</p>'+shot('ui-01-search','검색 결과에서 주소가 arrows.app인 줄')+
        '<p>처음 뜨는 안내 창은 다 닫습니다. 아래 쿠키 안내에서 <b>Use necessary cookies only</b>(꼭 필요한 쿠키만)를 누르세요.</p>'+shot('ui-02-cookie','쿠키 안내의 Use necessary cookies only')+
        '<p>쿠키 안내가 닫히면 그 밑에 가려 있던 도움말 창의 <b>Done</b>(닫기)이 보입니다. Done을 누르세요. 왼쪽 넓은 곳이 그림을 그리는 그림판이고, 가운데에 처음부터 있는 원을 첫 원으로 씁니다.</p>'+shot('ui-03-done','도움말 창 아래의 Done')+
        '<p>이름을 적기에는 원이 작아서 먼저 키웁니다. 오른쪽 칸의 <b>Customize</b>(모양 설정)를 누르고 <b>radius</b>(원 크기)를 <code>50</code>에서 <code>60</code>으로 바꾼 뒤 <b>Tab</b>을 누르세요. 앞으로 만드는 원도 이 크기로 나옵니다.</p>'+shot('ui-04-radius','Customize와 radius 60')+
        '<p>화살표에 적는 이름은 원래 비스듬히 기울어 나옵니다. 오른쪽 칸을 아래로 내려 <b>detail-orientation</b>을 <b>horizontal</b>(가로)로 바꾸고, 칸을 다시 맨 위로 올리세요.</p>'+shot('ui-05-orientation','detail-orientation을 horizontal로 바꾼 칸')+
        '<p>그릴 자리를 넉넉하게 쓰려고 첫 원의 안쪽을 잡아 왼쪽으로 끌어 놓으세요. 화면 끝에 바짝 대면 그림 전체가 작아지니 끝에서 조금 띄웁니다.</p>'+
        check('radius가 60, detail-orientation이 horizontal이고, 빈 원이 그림판 왼쪽에 있습니다.')+
        note('radius 같은 모양 칸(9단계의 node-color도)은 Enter 말고 Tab으로 마칩니다. Enter를 치면 원이 하나 더 생깁니다.')))
    parts.append(section(2,'설비 · 쿨러 · 센서 놓고 잇기',
        why('유온이 오른다는 말을 들으면 현장에서는 어느 설비 얘기인지부터 묻습니다. 경보도 정비 기록도 설비 번호로 남아서, 설비부터 놓고 나머지를 여기에 잇습니다.')+
        '<p>옮겨 둔 원을 누르고 오른쪽 맨 위 <b>Caption</b>(원 안에 보일 이름)에 이름을 적은 뒤, <b>+ Label</b>을 눌러 나온 칸에 종류를 적고 <b>Tab</b>으로 마치세요. 이름만으로는 컴퓨터가 설비인지 부품인지 모르니 원마다 종류를 붙입니다. 표의 적을 글은 옆의 <b>복사</b>를 눌러 붙여 넣으세요. 손으로 치면 한 글자만 달라도 컴퓨터는 다른 이름으로 봅니다.</p>'+shot('ui-06-caption','Caption의 이름, Labels의 종류(Asset), + Label')+
        '<p>새 원은 이미 있는 원에서 끌어냅니다. 원을 누르면 둘레에 하늘색 띠가 생기는데, 원 안쪽을 잡으면 원이 옮겨지고 이 띠를 잡아 빈 곳에 놓아야 새 원과 화살표가 함께 나옵니다. 화살표는 늘 끌기 시작한 원에서 새 원 쪽으로 나갑니다. 아래 표의 「끌어낼 원」이 띠를 잡을 원입니다.</p>'+shot('ui-07-ring','쿨러를 누르면 둘레에 생기는 하늘색 띠. 이 띠를 잡고 끕니다')+nodes([
        (H,'Asset','(처음부터 있는 원)','설비입니다. HYD-01은 설비 번호이고, 유압 파워팩은 기름의 압력으로 기계를 움직이는 설비입니다. Asset(자산)은 공장에서 설비를 부르는 말입니다.'),
        (K,'Component',H,'기름을 식히는 부품입니다. 고장은 대개 부품 하나에서 시작되고, 기름 온도가 오르면 먼저 볼 부품이 쿨러라서 따로 놓습니다.'),
        (S,'Sensor',K,'쿨러가 잘 식히는지는 쿨러로 들어가는 유온을 재 봐야 압니다. 센서는 번호가 따로 있고 따로 고장 나거나 바뀌는 다른 물건이라 따로 놓습니다. TS1은 센서 번호입니다.')])+
        '<p>화살표는 이름이 있어야 둘이 무슨 사이인지 압니다. 화살표마다 이 차례로 긋습니다.</p><ol><li>둘 사이를 말로 해 봅니다(표의 「말로 하면」). 거꾸로 그으면 「쿨러가 파워팩을 부품으로 가진다」 같은 틀린 말이 됩니다.</li><li>화살표가 그 말의 주어 원에서 나가 있는지 봅니다. 나가는 쪽이 주어, 닿는 쪽이 상대입니다.</li><li>화살표를 누르고 <b>Type</b>(화살표 이름)에 이름을 적습니다. 영어 대문자로 쓰고 낱말 사이는 밑줄로 잇습니다.</li></ol>'+shot('ui-08-type','화살표를 누르면 나오는 Type 칸')+rels([
        ('파워팩 안에 쿨러가 부품으로 들어 있다','유압 파워팩은 오일 쿨러를 부품으로 가진다','HAS_COMPONENT',keep('파워팩')),
        ('센서가 쿨러를 지켜본다','오일 쿨러는 유온 센서로 감시된다','MONITORED_BY',keep('쿨러'))])+
        photo('02')+check('원 3개 · 화살표 2개. 설비에서 화살표 두 개를 따라가면 쿨러를 어느 센서로 보는지까지 나옵니다.')+
        note('원 하나가 이론에서 말한 노드이고, 이름과 방향이 있는 화살표가 관계입니다.')))
    parts.append(section(3,'증상과 고장 유형 · 방향 뒤집기',
        why('어느 날부터 유온이 자꾸 오른다고 해 봅니다. 이 일을 그림에 담으려고, 눈에 보인 신호인 온도 상승과 그 뒤의 진짜 문제인 쿨러가 식히는 힘을 잃은 일을 원으로 놓습니다.')+
        '<p>끌어낸 화살표가 주어가 아닌 원에서 나가 있으면(표의 방향 칸이 Reverse인 화살표), 화살표를 누르고 오른쪽 칸 위쪽의 <b>Reverse</b>(뒤집기)를 누른 뒤 Type을 적습니다. 이미 있는 원과 이을 때는 띠를 그 원 위에 놓습니다. 원은 생기지 않고 화살표만 생깁니다.</p>'+shot('ui-09-reverse','화살표를 누르면 오른쪽 칸 위쪽에 나오는 Reverse')+nodes([
        (U,'Symptom',S,'눈에 보인 이상, 증상입니다. 센서는 늘 있는 물건이고 온도가 오른 것은 어느 날 생긴 일이라 한 원에 적지 않습니다.'),
        (F,'FailureMode',U,'무엇이 어떤 기능을 잃었는지, 고장 유형입니다(식히는 힘을 잃음). 유온은 다른 고장으로도 오르고 고장 하나가 여러 증상으로 드러나기도 해서 증상과 따로 놓습니다.')])+rels([
        ('유온이 오른 것은 센서 값에 잡혀서 안다','유온 상승은 유온 센서로 관측된다','OBSERVED_BY',flip('센서')),
        ('유온이 오르면 쿨러가 식히는 힘을 잃은 건 아닌지 의심한다','유온 상승은 쿨러 냉각 성능 상실을 가리킨다','INDICATES',keep('유온 상승')),
        ('식히는 힘을 잃은 것이 이 쿨러다','쿨러 냉각 성능 상실은 오일 쿨러에서 일어난다','OCCURS_IN',onto('고장','오일 쿨러')+'. 쿨러 원을 하나 더 만들면 쿨러 이야기가 두 군데로 갈라집니다')])+
        photo('03')+check('원 5개 · 화살표 5개. 유온 센서로 관측된 유온 상승은 쿨러 냉각 성능 상실을 가리키고, 그 고장은 오일 쿨러에서 일어났습니다.')))
    parts.append(section(4,'원인과 증거 달기',
        why('왜 못 식히는지는 아직 모릅니다. 쿨러 안의 핀(얇은 날개) 사이로 팬 바람이 지나가며 기름의 열을 가져가는데, 핀에 먼지가 끼면 바람길이 막혀 열이 빠지지 않습니다. 같은 고장이라도 원인마다 확인할 값도 고치는 방법도 달라서, 원인은 고장과 따로 놓습니다.')+nodes([
        (PO,'Cause',F,'고장이 왜 났는지를 말해 주는 원인입니다.')])+rels([
        ('핀에 먼지가 껴서 쿨러가 못 식히게 됐다','쿨러 핀 오염은 쿨러 냉각 성능 상실을 일으킨다','CAUSES',flip('고장'))])+
        '<p><code>CAUSES</code>는 늘 원인에서 고장 쪽으로만 긋습니다. 방향을 하나로 맞춰 두면 고장에서 CAUSES를 거꾸로 따라가기만 해도 원인이 다 나옵니다.</p>'+
        why('핀 오염이 맞는지는 값을 재서 기준에 견줘 봐야 압니다. 무슨 값을 어떤 기준에 견줄지 정해 둔 것이 이론에서 말한 증거이고, 따로 있는 물건이나 일이 아니라서 핀 오염 원에 꼬리표처럼 붙입니다.')+
        '<p>핀 오염을 누르고 오른쪽 칸 <b>Properties</b>의 <b>+ Property</b>를 누르면 칸 두 개가 나란히 생깁니다. 앞 칸에 무엇을 볼지, 뒤 칸에 기준을 적고 <b>Tab</b>으로 마칩니다. 둘째 줄은 + Property를 한 번 더 누릅니다.</p>'+
        table(['앞 칸 · 무엇을 볼지','뒤 칸 · 기준','뜻'], [
        (cp('냉각 효율'),cp('30초 평균 < 70 %'),'쿨러가 들어온 열을 얼마나 빼내는지 본 값입니다. 70 %가 안 되면 열을 제대로 못 빼고 있습니다.'),
        (cp('팬 진동'),cp('2분 평균 < 0.9 mm/s'),'팬이 얼마나 떨리는지 잰 값입니다. 탈 난 팬은 심하게 떨리니, 떨림이 작으면 팬은 멀쩡합니다.')])+
        '<p>열은 못 빼는데 팬은 멀쩡하면 핀이 막혔다고 볼 수 있어서, 증거 두 줄이 다 맞아야 핀 오염으로 봅니다.</p>'+shot('ui-10-property','Properties의 증거 두 줄과 + Property. 원 옆에도 같은 두 줄이 붙습니다')+
        photo('04')+check('원 6개 · 화살표 6개. CAUSES 화살표가 핀 오염에서 고장 쪽으로 나가고, 핀 오염 옆에 증거 두 줄이 붙어 있습니다.')+
        note('원에 붙여 둔 이 줄이 이론에서 말한 속성입니다.')+note('뒤 칸은 Enter 말고 Tab으로 마칩니다. Enter를 치면 빈 줄이 하나 더 생깁니다.')))
    parts.append(section(5,'완화 조치 · 근본 조치와 근거 매뉴얼',
        why('원인을 찾았으면 손을 봐야 합니다. 손보는 것은 사람이 하는 일이라 고장 · 원인과 다른 종류로 따로 놓고, 우선 온도만 낮추는 완화 조치와 원인까지 없애는 근본 조치를 나눠 놓습니다. 조치는 설비에 손을 대는 일이라 근거가 있어야 하니, 이 설비에 쿨러와 팬을 다루는 매뉴얼 HM-8이 있다고 해 보고 그 절(번호가 붙은 토막)도 원으로 놓습니다.')+
        '<p>그 매뉴얼의 발췌는 맨 위 <b>매뉴얼 근거</b>에서 볼 수 있습니다. 4단계에서 적은 기준(HM-8.4)도, 아래 절 번호와 8단계에서 적을 절차 번호도 그 발췌에 적힌 대로 적습니다. 이론에서 조치라고 한 종류는 <b>Skill</b>, 근거 문서는 <b>ManualSection</b>이라는 이름으로 적기로 정해 둡니다.</p>'+nodes([
        (MX,'Skill',F,'완화 조치입니다. 팬을 가장 세게 돌려 바람을 키워 우선 온도만 낮춥니다.'),
        (PC,'Skill',F,'근본 조치입니다. 팬을 아무리 세게 돌려도 핀에 낀 먼지는 남으니, 핀을 닦아 원인까지 없앱니다.'),
        (M85,'ManualSection',MX,'팬을 세게 돌리는 방법이 적힌 HM-8 매뉴얼의 8.5절입니다. 절 하나를 여러 조치가 함께 근거로 쓸 수 있어서 절도 원으로 놓습니다.'),
        (M87,'ManualSection',PC,'핀을 닦는 법이 적힌 8.7절입니다.')])+rels([
        ('팬을 세게 돌리면 못 식히는 것을 우선 덜어 준다(누그러진다)','쿨러 냉각 성능 상실은 팬 최대 운전으로 완화된다','MITIGATED_BY',keep('고장')),
        ('핀을 닦으면 못 식히던 문제가 아예 풀린다(아예 고쳐진다)','쿨러 냉각 성능 상실은 쿨러 핀 세척으로 근본 해결된다','REMEDIED_BY',keep('고장')),
        ('핀 세척은 핀 오염일 때만 소용이 있다. 고장하고만 이으면 어느 원인에 맞는 조치인지 모른다','쿨러 핀 세척은 쿨러 핀 오염을 없앤다','ADDRESSES',onto('핀 세척','핀 오염')),
        ('팬 최대 운전은 이 절을 보고 따라 한다','팬 최대 운전은 8.5절을 참조한다','REFERS_TO',keep('팬 최대 운전')),
        ('핀 세척도 이 절을 보고 한다','쿨러 핀 세척은 8.7절을 참조한다','REFERS_TO',keep('핀 세척'))])+
        '<p>MITIGATED_BY와 REMEDIED_BY를 다르게 적어 둬야 온도만 낮춘 조치인지 원인까지 없앤 조치인지 갈라 볼 수 있습니다. 같으면 온도가 내려간 것만 보고 다 끝났다고 닫아 버리기 쉽습니다.</p>'+
        photo('05')+check('원 10개 · 화살표 11개. 핀 오염이라고 나오면 화살표만 따라가도 조치는 핀 세척, 근거는 8.7절까지 나옵니다.')))
    parts.append(section(6,'두 번째 원인 · 팬 구동 불량',
        why('온도가 오르는 원인이 핀 오염 하나만은 아닙니다. 고장은 같고 원인만 다르니, 원인 하나와 그 원인에 맞는 조치 · 근거를 더 놓습니다.')+
        '<p>놓고 잇는 법은 앞 단계와 같습니다. 증거는 팬 구동 불량을 누르고 + Property로 붙입니다.</p>'+nodes([
        (FD,'Cause',F,'팬을 돌리는 벨트가 미끄러져 팬이 제대로 못 도는 원인입니다. 바람이 줄어 똑같이 열이 빠지지 않습니다.'),
        (FI,'Skill',F,'벨트가 늘어지지 않았는지 살펴 손보는 근본 조치입니다. 팬이 문제인데 핀을 닦아 봐야 소용없어서 따로 놓습니다.'),
        (M81,'ManualSection',FI,'벨트 살피는 법이 적힌 8.1절입니다.')])+rels([
        ('이것도 고장을 일으키는 쪽이다','팬 구동 불량은 쿨러 냉각 성능 상실을 일으킨다','CAUSES',flip('고장')),
        ('원인을 없애는 근본 조치다','쿨러 냉각 성능 상실은 팬 점검으로 근본 해결된다','REMEDIED_BY',keep('고장')),
        ('팬 구동 불량에 맞는 조치다','팬 점검은 팬 구동 불량을 없앤다','ADDRESSES',onto('팬 점검','팬 구동 불량')),
        ('벨트 살피는 법이 이 절에 있다','팬 점검은 8.1절을 참조한다','REFERS_TO',keep('팬 점검'))])+
        evidence([(FD,'팬 진동','2분 평균 ≥ 0.9 mm/s')])+
        '<p>핀 오염의 팬 진동은 0.9 미만이고 여기는 0.9 이상입니다. 같은 값 하나를 놓고 떨림이 작으면 핀 쪽, 크면 팬 쪽으로 원인이 갈립니다.</p>'+
        photo('06')+check('원 13개 · 화살표 15개. 팬 구동 불량에서 팬 점검, 8.1절까지 화살표로 이어집니다.')))
    parts.append(section(7,'세 번째 원인 · 주변 온도 상승',
        why('원인이 하나 더 있습니다. 쿨러는 열을 둘레의 공기로 내보내는데, 설비를 넣어 둔 함, 캐비닛 안 공기가 이미 뜨거우면 쿨러도 팬도 멀쩡한데 열이 빠지지 않습니다.')+
        '<p>새 원은 이어질 원이면 어디서 끌어내도 되어서, 이번 조치는 원인에서 끌어냅니다. 8.7절 원은 이미 있으니 환기 보강의 띠를 그 위에 놓기만 합니다.</p>'+nodes([
        (AT,'Cause',F,'캐비닛 안이 더워 열이 빠지지 않는 원인입니다. 이것도 온도가 오른 일이지만, 유온 상승처럼 눈에 보인 이상이 아니라 쿨러가 왜 못 식히는지를 말해 주는 까닭이라 원인으로 놓습니다.'),
        (CV,'Skill',AT,'필터를 청소하고 캐비닛의 환풍기를 살펴 캐비닛에 바람이 잘 통하게 하는 근본 조치입니다.')])+rels([
        ('이것도 고장을 일으키는 쪽이다','주변 온도 상승은 쿨러 냉각 성능 상실을 일으킨다','CAUSES',flip('고장')),
        ('환기를 보강하면 캐비닛 안이 더운 게 없어진다','캐비닛 환기 보강은 주변 온도 상승을 없앤다','ADDRESSES',flip('주변 온도 상승')),
        ('환기 보강도 원인을 없애는 근본 조치다','쿨러 냉각 성능 상실은 캐비닛 환기 보강으로 근본 해결된다','REMEDIED_BY',onto('고장','환기 보강')),
        ('환기 보강하는 법도 핀 세척과 같은 8.7절에 있다','캐비닛 환기 보강은 8.7절을 참조한다','REFERS_TO',onto('환기 보강','8.7절'))])+
        evidence([(AT,'캐비닛 온도','2분 평균 ≥ 35 ℃')])+
        '<p>캐비닛 안이 정말 더운지는 온도를 재 보면 됩니다.</p>'+
        photo('07')+check('원 15개 · 화살표 19개. 원인마다 맞는 조치가 하나씩 붙었습니다. 팬 구동 불량에는 팬 점검, 핀 오염에는 핀 세척, 주변 온도 상승에는 환기 보강입니다.')))
    parts.append(section(8,'고장이 고장으로 번지는 길과 절차 번호',
        why('고장이 다른 고장으로 번지기도 합니다. 팬의 축을 받쳐 주는 베어링이 닳으면(베어링 열화) 팬이 흔들리고, 그러다 쿨러까지 못 식히게 됩니다.')+nodes([
        (BR,'FailureMode',F,'베어링이 축을 받쳐 주는 기능을 잃어 가는 고장 유형입니다. 진동이 커지는 자기 증상이 있어, 그 증상에서 출발해 찾아올 수도 있어야 합니다.'),
        (VB,'Symptom',BR,'진동이 실제로 커졌다는 일, 유온 상승처럼 눈에 보인 증상이라 원으로 놓습니다. 원인에 붙인 팬 진동은 0.9를 넘는지 견주는 증거라서 원이 아닙니다.')])+rels([
        ('베어링이 닳으면 결국 쿨러까지 못 식히게 된다','팬 베어링 열화는 쿨러 냉각 성능 상실로 이어진다','LEADS_TO',flip('냉각 성능 상실')),
        ('진동이 커지면 베어링이 닳은 건 아닌지 의심해 볼 수 있다','진동 증가는 팬 베어링 열화를 가리킨다','INDICATES',flip('베어링 열화'))])+
        '<p>양쪽이 다 고장이라 <code>CAUSES</code>를 쓰지 않습니다. CAUSES는 원인에서 고장으로만 긋기로 해서, 여기에 쓰면 원인을 찾을 때 고장이 섞여 나옵니다.</p>'+
        why('매뉴얼 한 절에는 작업 순서가 여러 개 있습니다. 이 작업 순서를 절차라고 하고, 현장에서는 표준 작업 절차를 줄여 SOP라고 부릅니다. 절차마다 SOP-로 시작하는 번호가 있습니다. 같은 8.7절을 보는 두 조치도 따르는 절차가 달라서, 번호를 절 원에 적으면 어느 조치의 번호인지 알 수 없습니다. 조치 원에 적어도 되지만, 여기서는 조치가 그 절에서 따르는 절차가 한 줄로 읽히게 조치에서 절로 가는 화살표에 적습니다.')+
        '<p>화살표에도 속성을 달 수 있습니다. 화살표를 누르고 <b>+ Property</b>의 앞 칸에 절차, 뒤 칸에 번호를 적은 뒤 <b>Tab</b>으로 마치세요.</p>'+
        table(['누를 화살표','앞 칸','뒤 칸'], [
        (CV+' → 8.7절',cp('절차'),cp('SOP-COOL-15')),(PC+' → 8.7절',cp('절차'),cp('SOP-COOL-14')),(MX+' → 8.5절',cp('절차'),cp('SOP-COOL-11')),(FI+' → 8.1절',cp('절차'),cp('SOP-FAN-11'))])+
        shot('ui-11-procedure','화살표의 Properties에 적은 절차 번호와 그림에 붙은 모습')+
        photo('08')+check('원 17개 · 화살표 21개. 8.7절로 들어가는 화살표 둘의 번호가 SOP-COOL-14와 SOP-COOL-15로 다릅니다.')))
    parts.append(section(9,'원인과 조치 색칠하기',
        why('그림은 다 그렸습니다. 이 그림으로 판단하기 전에, 원인과 조치가 한눈에 띄게 색을 넣습니다.')+
        '<p><b>쿨러 핀 오염</b>을 누르고 <b>Ctrl</b>을 누른 채 <b>팬 구동 불량</b>, <b>주변 온도 상승</b>을 누르세요. 오른쪽 칸 위에 <b>nodes: 3</b>이 나오면 셋이 같이 골라진 것입니다. <b>node-color</b>(원 색깔) 칸에 연한 빨강 값을 넣고 <b>Tab</b>을 누르면 셋이 한꺼번에 칠해집니다. 조치 넷도 같은 식으로 골라 연한 초록 값을 넣으세요.</p>'+
        table(['함께 고를 원','node-color 값'], [('원인 셋: 쿨러 핀 오염 · 팬 구동 불량 · 주변 온도 상승',cp(RED_HEX)),('조치 넷: 팬 최대 운전 · 쿨러 핀 세척 · 캐비닛 환기 보강 · 팬 점검',cp(GREEN_HEX))])+
        shot('ui-12-color','함께 고른 원의 수와 node-color 칸(색 고르는 판이 함께 뜹니다). 왼쪽에 칠해진 쿨러 핀 오염이 보입니다')+
        check('원인 셋이 연한 빨강, 조치 넷이 연한 초록입니다(다음 단계 사진).')))
    parts.append(section(10,'그림으로 판단하기',
        '<p>빈 곳을 한 번 눌러 고른 것을 푸세요.</p>'+
        why('유온이 올라서 경보가 왔다고 해 봅니다. 유온 상승이 가리키는 고장은 쿨러 냉각 성능 상실이고, 여기로 들어오는 CAUSES를 거꾸로 따라가면 원인 셋이 나옵니다. 셋 가운데 어느 것인지는 증거로 가립니다.')+
        '<p>경보가 왔을 때 잰 값이 냉각 효율 30초 평균 <b>46.2 %</b>, 팬 진동 2분 평균 <b>0.575 mm/s</b>, 캐비닛 온도 2분 평균 <b>28 ℃</b>였다고 해 봅니다. 이 값은 그림에 적지 않고, 원인마다 붙은 증거와 견줍니다.</p>'+
        shot('ui-13-judge','색칠을 마친 그림. 빨간 네모가 견줄 원인 셋과 그 증거입니다. 오른쪽 위 어두운 상자는 잰 값을 보기 쉽게 띄운 것이라 그리지 않습니다')+
        check('핀 오염의 증거 두 줄만 맞습니다(46.2는 70 미만, 0.575는 0.9 미만). 팬 구동 불량은 0.9 이상, 주변 온도 상승은 35 ℃ 이상이어야 해서 빠집니다. 화살표를 따라가면 조치는 쿨러 핀 세척, 절차는 SOP-COOL-14, 근거는 8.7절입니다. 세척은 설비를 세워야 하니, 그 전에 팬 최대 운전으로 온도부터 낮춰 둡니다.')+
        '<p>값이 다르면 가는 길도 달라집니다.</p><ul>'
        '<li>팬 진동이 <b>1.4 mm/s</b>였다면 핀 오염의 0.9 미만에는 안 맞아 빠지고 팬 구동 불량의 0.9 이상에 맞습니다. 길은 팬 점검, SOP-FAN-11, 8.1절로 달라지고, 진동 증가가 가리키는 팬 베어링 열화도 함께 의심합니다.</li>'
        '<li>처음 값에서 캐비닛 온도만 <b>38 ℃</b>였다면 핀 오염의 두 줄은 그대로 맞고 주변 온도 상승에도 맞아 원인이 둘 남습니다. 하나 맞았다고 멈추지 말고 환기 보강과 핀 세척을 둘 다 봅니다.</li>'
        '<li>팬 진동 값을 아직 못 받았다면 두 줄이 다 맞는지 알 수 없으니 핀 오염이라고 정하지 않고, 진동 값부터 받습니다.</li></ul>'
        '<p>처음의 정비 메모 한 줄(유온이 올라 살펴보니 쿨러 핀이 더러워서 닦았다)만으로는 진동이 1.4일 때 어디를 봐야 할지 알 수 없습니다. 원인 · 증거 · 조치를 관계로 이어 둔 그림은 잰 값에 따라 다른 원인과 조치, 근거로 가는 길을 찾아 줍니다.</p>'))
    parts.append(section(11,'파일로 남기고 다시 열기',
        why('그린 그림은 지금 이 브라우저에만 저장돼 있습니다. 다른 컴퓨터에서 열거나 다른 사람에게 주려면 파일로 받아 둡니다.')+
        '<p>위쪽 <b>Download / Export</b>(내려받기)를 누르세요.</p>'+shot('ex-01-button','위쪽 Download / Export')+
        '<p>처음 열리는 <b>PNG</b>는 보고서 같은 데 붙이는 그림 파일입니다. 맨 위 줄의 <b>Download</b>를 누르세요.</p>'+shot('ex-02-png','PNG 탭과 맨 위 줄의 Download')+
        '<p><b>JSON</b>은 원과 화살표를 글자로 적어 둔 파일이라, 나중에 다시 열어 이어 고칠 수 있습니다. JSON 탭에서도 <b>Download</b>를 누르세요.</p>'+shot('ex-03-json','JSON 탭의 Download')+
        '<p>같은 창의 <b>Cypher</b> 탭에는 이 그림의 종류 · 화살표 · 꼬리표를 그래프 데이터베이스 Neo4j에 넣는 명령이 나옵니다. 보기만 하고 아래 <b>Done</b>으로 창을 닫으세요.</p>'+shot('ex-04-cypher','Cypher 탭과 CREATE로 시작하는 명령')+
        '<p>받은 JSON이 잘 열리는지 새 그림에서 봅니다. 빈 곳을 눌러 고른 것을 풀고(골라 둔 채 New를 누르면 그림판이 옛 그림에 멈춥니다), 왼쪽 위 로고를 눌러 <b>New</b>(새 그림)에 커서를 올린 뒤 오른쪽으로 곧장 옮겨 <b>Web Browser storage</b>를 누르세요. 새 그림이 열려도 메뉴는 떠 있으니 그림 쪽을 한 번 눌러 닫습니다.</p>'+shot('ex-05-menu','로고, New에 올리면 나오는 Web Browser storage, Import')+
        '<p>다시 로고에서 <b>Import</b>(가져오기)를 누르고, <b>Choose File</b>(파일 고르기)로 받은 <code>Untitled graph.json</code>을 고른 뒤 아래 <b>Import</b>를 누르세요.</p>'+shot('ex-06-import','Choose File로 고른 JSON이 들어온 창과 아래 Import')+
        '<p>들어온 것이 모두 골라져 오른쪽 위에 개수가 나옵니다. 원 크기와 화살표 이름의 방향은 처음 값으로 돌아와 있습니다. 1단계에서 Customize로 바꾼 두 값은 파일을 열 때 따라오지 않기 때문입니다. 새 그림에 처음부터 있던 빈 원은, 빈 곳을 눌러 고른 것을 푼 뒤 그 원만 누르고 오른쪽 <b>Delete</b>(지우기)로 지우세요.</p>'+shot('ex-07-imported','다시 연 그림의 원 · 화살표 수와 지울 빈 원')+
        check('nodes: 17 · relationships: 21로 그린 것과 같고, 원인의 증거 줄과 화살표의 절차 번호, 색이 함께 들어와 있습니다.')+
        '<p class="save">학교 PC는 껐다 켜면 받은 파일이 지워지니, 두 파일을 USB나 본인 클라우드에 옮겨 두세요.</p>'))
    nav=''.join(f'<a href="#step{i}">{i:02} {t}</a>' for i,t in enumerate(STEPS,1))
    copy_js=('<div id="copy-status" role="status" aria-live="polite"></div><script>document.querySelectorAll("[data-copy]").forEach(b=>b.addEventListener("click",async()=>{const e=document.getElementById(b.dataset.copy),s=document.getElementById("copy-status");'
             'try{await navigator.clipboard.writeText(e.textContent);s.textContent="복사했습니다. ARROWS 오른쪽 칸의 그 입력칸에 붙여 넣으세요."}catch(x){const r=document.createRange();r.selectNodeContents(e);const g=window.getSelection();g.removeAllRanges();g.addRange(r);s.textContent="선택된 글을 Ctrl+C로 복사해 ARROWS에 붙여 넣으세요."}'
             'clearTimeout(window.copyTimer);window.copyTimer=setTimeout(()=>{s.textContent=""},4000)}));</script>')
    return '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>설비 이상과 원인·조치의 관계를 시각화하기 · 실습 가이드</title><style>
:root{--ink:#213330;--muted:#5a6c67;--line:#dce5df;--green:#216953;--paper:#fff;--bg:#f4f6f2}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:30px}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.85 "Malgun Gothic","Segoe UI",sans-serif}a{color:var(--green);text-underline-offset:4px}a:focus-visible,button:focus-visible{outline:3px solid #d18424;outline-offset:4px}.shell{max-width:1380px;margin:auto;padding:56px 36px}header{padding:40px 48px;background:#e6eee6;border-radius:22px;margin-bottom:36px}.eyebrow{font-size:13px;font-weight:700;letter-spacing:2px;color:var(--green)}h1{font-size:40px;letter-spacing:-1.8px;line-height:1.3;margin:16px 0}header p{max-width:860px;margin:0 0 10px;color:#40584f}.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:26px}.button{display:inline-block;padding:11px 22px;background:var(--green);color:white;text-decoration:none;border-radius:9px;font-weight:700}.button.secondary{background:white;color:var(--green)}.layout{display:grid;grid-template-columns:170px minmax(0,1fr);gap:32px}nav{position:sticky;top:30px;align-self:start}nav span{display:block;color:var(--muted);font-size:12px;letter-spacing:2px;margin:8px 0 16px}nav a{display:block;padding:10px 12px;margin-bottom:5px;text-decoration:none;font-size:14px;border-radius:7px}nav a:hover{background:#e6eee6}section{background:var(--paper);border:1px solid var(--line);border-radius:16px;padding:36px;margin-bottom:32px}.step-head{display:flex;gap:16px;align-items:center;border-bottom:1px solid var(--line);padding-bottom:24px;margin-bottom:24px}.number{font:600 27px/1 Georgia,serif;color:var(--green)}h2{font-size:25px;line-height:1.4;margin:0;letter-spacing:-.7px}p{margin:18px 0}ol,ul{margin:18px 0;padding-left:26px}li{margin:6px 0}b,strong{font-weight:700}code{font-family:Consolas,monospace;background:#edf3ee;padding:3px 6px;border-radius:4px;font-size:.95em}.why{color:var(--muted)}.table-wrap{overflow:auto;margin:24px 0}table{width:100%;min-width:680px;border-collapse:collapse;font-size:14px;line-height:1.7}th{text-align:left;background:#f0f4ef;color:#445e52;font-weight:600;white-space:nowrap}td,th{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top}td{user-select:text}.cp{display:inline-flex;align-items:center;gap:6px;flex-wrap:wrap}.cp code{user-select:all;white-space:nowrap}.cp button{font:inherit;font-size:12px;line-height:1.4;border:1px solid #8ba9bd;border-radius:6px;background:white;color:#245e8c;padding:1px 8px;cursor:pointer}figure{margin:28px 0}img{display:block;max-width:100%;height:auto;margin:0 auto;border:1px solid var(--line);border-radius:9px}figcaption{font-size:13px;color:var(--muted);margin-top:10px}.check{padding:18px 20px;background:#edf5ee;border-left:3px solid #45846a;border-radius:0 8px 8px 0;font-size:15px}.check strong{display:block;color:var(--green);margin-bottom:4px}.note{font-size:14px;color:var(--muted);margin:10px 0}.save{padding:18px 20px;background:#faf4e6;border-radius:8px;font-size:15px}.added{border-top:1px solid #dce5df;padding-top:18px;color:#216953;font-size:15px}.added b{display:inline-block;background:#e6eee6;padding:3px 10px;border-radius:5px;margin-right:8px}#copy-status{position:fixed;bottom:12px;right:12px;background:#213330;color:white;padding:8px 14px;border-radius:8px;font-size:14px}#copy-status:empty{display:none}footer{color:var(--muted);font-size:13px;text-align:center;padding:16px}.top{display:inline-block;margin-top:12px}@media(max-width:850px){.shell{padding:20px 14px}header{padding:28px 22px}h1{font-size:30px}.layout{display:block}nav{position:static;display:flex;flex-wrap:wrap;margin-bottom:20px;gap:4px}nav span{display:none}nav a{padding:6px 9px;font-size:12px;background:white}section{padding:24px 18px}h2{font-size:22px}.step-head{gap:12px}}@media print{body{background:white}.shell{padding:0}nav,.actions,.top,.cp button{display:none}.layout{display:block}section{break-before:page;border:0;padding:0}figure,table,.check{break-inside:avoid}a{color:inherit}}
</style></head><body><div class="shell"><header><div class="eyebrow">1회차 · 통합반 / 실전반 공통</div><h1>설비 이상과 원인·조치의 관계를 시각화하기</h1><p>이론에서 본 정비 메모, 「유온이 올라서 살펴보니 쿨러 핀이 더러워서 닦았다」는 이야기를 컴퓨터가 따라갈 수 있는 지식 그래프로 옮깁니다. 온톨로지 → 에이전트 → 프로세스로 쌓아 갈 이 과정의 첫 단계로, 온톨로지에 맞춰 지식 그래프를 손으로 그려 보는 실습입니다. 원마다 무엇인지(종류)를 붙이고 화살표마다 이름과 방향을 붙여, 온도가 오른 데서 출발해 원인 · 조치 · 근거까지 화살표로 찾아가는 그림(원 17개 · 화살표 21개)을 만듭니다.</p><p>설비와 부품 → 증상과 고장 유형 → 원인과 증거 → 조치와 근거 매뉴얼 → 다른 원인 둘 → 번지는 고장과 절차 번호 → 색칠 → 판단 → 파일로 남기기 차례입니다. 단계마다 놓을 원과 그을 화살표가 표에 있고, 사진의 빨간 네모가 누를 곳이나 볼 곳입니다. 사진을 누르면 크게 보입니다.</p><div class="actions"><a class="button" href="https://arrows.app" target="_blank" rel="noopener">ARROWS 열기</a><a class="button secondary" href="매뉴얼_발췌.md">매뉴얼 근거</a></div></header><div class="layout"><nav aria-label="실습 단계"><span>진행 순서</span>'''+nav+'</nav><main>'+''.join(parts)+'''<a class="top" href="#">맨 위로</a></main></div><footer>설비 이상과 원인·조치의 관계를 시각화하기 · 통합반 / 실전반 공통 실습</footer></div>'''+copy_js+'</body></html>'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--video',type=Path)      # 낸 영상 — UI_SHOTS · STAGE_SHOTS를 뽑는다
    parser.add_argument('--captures',type=Path)   # 영상 밖에서 따로 찍은 11단계 사진 폴더 — CAPTURE_SHOTS
    args=parser.parse_args()
    if bool(args.video)!=bool(args.captures):
        raise SystemExit('--video와 --captures는 함께 준다(images/를 통째로 다시 만든다). 둘 다 없으면 지금 사진을 그대로 쓴다.')
    sys.path.insert(0,str(ROOT/'workspace/강의제작/제작도구/실습시작'))
    from lab_package import pack_page
    guide=render()
    source=ROOT/'workspace/강의제작/산출물/통합반/실습/01회차/랩'/LAB
    images=source/'images'
    if args.video:
        build_images(args.video, args.captures, images)
    for course in ['통합반','실전반']:
        lab=ROOT/'workspace/강의제작/산출물'/course/'실습/01회차/랩'/LAB
        if lab!=source:
            if (lab/'images').exists():shutil.rmtree(lab/'images')   # 가이드가 열지 않는 옛 사진을 남기지 않는다(P-13)
            shutil.copytree(images,lab/'images')
        (lab/'가이드.html').write_text(guide,encoding='utf-8',newline='\n')
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


def cut_and_box(im, name, crop, boxes, images):
    """네모를 그리고 자른 사진을 images/<name>.png로 쓴다. 네모가 자름 밖으로 나가면 멈춘다."""
    outer=draw_boxes(im,boxes)
    if crop:
        for o,_ in outer:
            if o[0]<crop[0] or o[1]<crop[1] or o[2]>=crop[2] or o[3]>=crop[3]:raise SystemExit(f'{name}: 네모 {o}가 자름 {crop} 밖으로 나간다')
        im=im.crop(crop)
    im.save(images/f'{name}.png')
    return [{'target':list(b[:4]),'margin':b[4],'outer':o,'dark_px_under_line':n} for b,(o,n) in zip(boxes,outer)]


def build_images(video, captures, images):
    """images/를 낸 영상의 UI_SHOTS · STAGE_SHOTS 프레임과 따로 찍은 CAPTURE_SHOTS로 새로 채우고 사진 근거를 고쳐 쓴다."""
    import imageio_ffmpeg, tempfile
    from PIL import Image
    probe=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-i',str(video)],capture_output=True).stderr.decode('utf-8','replace')
    dur=[l.split('Duration:')[1].split(',')[0].strip() for l in probe.splitlines() if 'Duration:' in l]
    if dur!=[VIDEO_DURATION]:
        raise SystemExit(f'{video}: 낸 영상({VIDEO_DURATION})이 아니다 — Duration {dur}')
    missing=[src for _,src,_,_ in CAPTURE_SHOTS if not (captures/src).is_file()]
    if missing:raise SystemExit(f'{captures}: 따로 찍은 사진이 없다 — {missing}')
    if images.exists():shutil.rmtree(images)
    images.mkdir()
    manifest={'video':{'file':'Release 영상 통합반_01회차_08_실습_관계그림.mp4','duration':VIDEO_DURATION,'sha256':sha(video)},
              'box':{'color':'#e60000','width':LINE,'note':'대상 경계 바깥 margin px에서 굵기 6 선이 바깥으로 그려진다. outer는 네모 바깥 경계다'},
              'ui_frames':[],'stage_frames':[],'captured_frames':{'note':CAPTURE_NOTE,'files':[]}}
    shots=[(name,sec,crop,boxes,'ui_frames') for name,sec,crop,boxes in UI_SHOTS]+[(f'stage-{n}',sec,STAGE_CROP,boxes,'stage_frames') for n,(sec,boxes) in STAGE_SHOTS.items()]
    with tempfile.TemporaryDirectory() as tmp:
        for name,sec,crop,boxes,kind in shots:
            raw=Path(tmp)/f'{name}.png'
            im=frame(video,sec,raw)
            drawn=cut_and_box(im,name,crop,boxes,images)
            manifest[kind].append({'file':f'images/{name}.png','seconds':sec,'frame_sha256':sha(raw),'crop':list(crop) if crop else None,'boxes':drawn,'sha256':sha(images/f'{name}.png')})
    for name,src,crop,boxes in CAPTURE_SHOTS:
        im=Image.open(captures/src).convert('RGB')
        if im.size!=(1920,1080):raise SystemExit(f'{src}: 사진 크기 {im.size} — 녹화와 같은 1920×1080이어야 한다')
        drawn=cut_and_box(im,name,crop,boxes,images)
        manifest['captured_frames']['files'].append({'file':f'images/{name}.png','source':src,'source_sha256':sha(captures/src),'crop':list(crop) if crop else None,'boxes':drawn,'sha256':sha(images/f'{name}.png')})
    (Path(__file__).parent/'학생가이드_사진근거.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


if __name__=='__main__':main()
