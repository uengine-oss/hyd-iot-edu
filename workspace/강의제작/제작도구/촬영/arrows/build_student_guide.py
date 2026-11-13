"""확정 영상에서 조작 화면 사진을 뽑고 단계 결과 그림에 네모를 그려, 두 과정 학생 가이드와 한 파일 가이드(<랩>.html, lab_package.pack_page)를 갱신한다.
Usage: python build_student_guide.py [--video <확정 mp4>]
  --video를 주면 images/를 그 영상에서 UI_SHOTS(조작 화면) · STAGE_SHOTS(단계 결과 그림)대로 새로 만들고 사진 근거(학생가이드_사진근거.json)를 고쳐 쓴다.
  둘 다 없으면 지금 사진과 사진 근거를 그대로 두고 가이드 · 한 파일 가이드만 다시 만든다.
네모: 대상 바깥 margin px(기본 6)에 굵기 6 빨간 선(가이드 P-8). 옆 글자에 걸리는 곳은 margin을 줄였다.
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
# 확정 실습 영상(통합반_01회차_08_실습_관계그림.mp4, 2044.17초 — 2026-11-12 클라우드 Playwright 판)에서 뽑는 ARROWS 화면.
# 시각은 그 영상 자막의 그 조작 큐 안이고, 프레임마다 커서가 대상을 가리지 않고 값이 다 들어간 순간을 눈으로 골랐다.
# boxes: (x0, y0, x1, y1, margin) — 대상 경계(프레임 px)와 대상 바깥 간격. crop: 그림 영역만 자를 때.
VIDEO_DURATION = '00:34:04.20'
UI_SHOTS = [
    ('ui-01-radius', 135.7, None, [(1674, 262, 1792, 299, 4), (1626, 674, 1712, 700, 4)]),                                  # Customize · radius 50
    ('ui-02-caption', 205.8, None, [(1468, 287, 1904, 328, 2), (1815, 388, 1904, 421, 4)]),                                 # Caption 칸 · + Label
    ('ui-03-type', 319.8, None, [(1468, 323, 1903, 365, 2)]),                                                               # 화살표의 Type
    ('ui-04-reverse', 466.8, None, [(1552, 138, 1666, 174, 3)]),                                                            # Reverse
    ('ui-05-property', 774.9, None, [(1468, 487, 1908, 566, (2, 2, 2, 0)), (1795, 582, 1904, 615, (4, 2, 4, 4))]),                                # Properties 두 줄 · + Property
    ('ui-06-color', 1643.0, None, [(1468, 88, 1596, 122, 3), (1598, 810, 1758, 842, 4)]),                                   # nodes: 3 · node-color
    ('ui-07-export-png', 1822.1, None, [(390, 167, 450, 205, 4), (407, 448, 600, 470, 4)]),                                 # PNG 탭 · @1x 줄의 Download
    ('ui-08-export-json', 1830.4, None, [(620, 167, 687, 205, 4), (406, 240, 544, 278, 4)]),                                # JSON 탭 · Download
    ('ui-09-menu', 1850.8, None, [(12, 6, 48, 40, 2), (94, 130, 300, 168, (3, 3, 3, 0)), (4, 185, 95, 215, (3, 1, 3, 3))]),   # 로고 · Web Browser storage(New에 올리면 열림) · Import — New 네모는 로고 네모와 붙어 겹쳐서 뺐다
    ('ui-10-import', 1884.4, None, [(390, 343, 555, 381, 4), (1442, 768, 1536, 806, 4)]),                                   # Choose File · Import
    ('ui-11-imported', 1902.5, None, [(1468, 88, 1793, 122, 4)]),                                                           # 다시 연 그림의 nodes: 17 · relationships: 21
    ('ui-12-cypher', 1973.0, None, [(530, 166, 610, 204, 4), (430, 350, 515, 378, 4)]),                                     # Cypher 탭 · CREATE
]
# 단계 결과 그림 — 같은 영상에서 그 단계가 끝난 순간의 그림판(오른쪽 칸 앞까지)을 자르고, 「이번에 추가」한 곳에 네모를 둔다.
STAGE_CROP = (0, 45, 1455, 1045)
STAGE_SHOTS = {
    '01': (419.0, [(50, 523, 518, 958, 6)]),                                  # 설비 · 쿨러 · 센서
    '02': (599.4, [(657, 523, 805, 958, 6)]),                                 # 유온 상승 · 냉각 성능 상실
    '03': (800.5, [(1092, 715, 1430, 895, 6)]),                               # 쿨러 핀 오염과 두 조건
    '04': (1025.0, [(964, 523, 1422, 671, 6), (860, 876, 1416, 1024, 6)]),    # 핀 세척 → HM-8.7 · 팬 최대 운전 → HM-8.5
    '05': (1187.0, [(420, 98, 772, 263, 6), (928, 56, 1422, 198, (6, 3, 6, 6))]),        # 팬 구동 불량과 조건 · 팬 점검 → HM-8.1
    '06': (1335.6, [(772, 214, 1108, 399, 6), (1282, 205, 1414, 337, 6)]),    # 주변 온도 상승과 조건 · 캐비닛 환기 보강
    '07': (1591.3, [(50, 279, 518, 427, 6)]),                                 # 진동 증가 → 팬 베어링 열화
}

def table(headers, rows):
    return '<div class="table-wrap"><table><thead><tr>' + ''.join('<th>'+html.escape(x)+'</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join('<td>'+html.escape(x)+'</td>' for x in row)+'</tr>' for row in rows) + '</tbody></table></div>'

def figure(file, caption):
    return f'<figure><a href="{file}" target="_blank"><img src="{file}" alt="{caption}" loading="lazy"></a><figcaption>{caption}</figcaption></figure>'

def photo(stage, caption):
    """단계 결과 그림. 빨간 네모는 이번 단계에서 더한 곳이다."""
    additions={'01':'설비 · 오일 쿨러 · 유온 센서','02':'유온 상승 · 냉각 성능 상실','03':'핀 오염 · 판별 조건','04':'팬 최대 운전 · 핀 세척 · 매뉴얼','05':'팬 구동 불량 · 팬 점검 · HM-8.1','06':'주변 온도 상승 · 캐비닛 환기 보강','07':'진동 증가 · 팬 베어링 열화 · 절차 번호'}
    return f'<p class="added"><b>이번에 추가</b> {additions[stage]}</p>'+figure(f'images/stage-{stage}.png', caption)

def shot(name, caption):
    """ARROWS 화면 사진. 빨간 네모는 누르거나 입력할 곳이다."""
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
    parts.append(section(1,'설비와 센서를 연결하기', '''<p>오일 쿨러가 어느 설비에 속하고 어떤 센서로 보는지 그립니다. <a href="https://arrows.app" target="_blank" rel="noopener">ARROWS 열기 ↗</a>를 누르면 쿠키 안내와 도움말 창이 뜹니다. 쿠키 안내는 아무 단추로, 도움말 창은 아래 <b>Done</b>으로 닫으세요. 새 그림 가운데에는 빈 원이 하나 들어 있습니다.</p>
<p>이 원은 긴 이름을 넣기에 작아서 크기부터 키웁니다. 오른쪽 <b>STYLE</b> 아래 <b>Customize</b>를 누르고, <b>Nodes</b>의 <b>radius</b>를 <code>50</code>에서 <code>60</code>으로 바꾼 뒤 <b>Tab</b>으로 넘어가세요. 이 값은 그림 전체에 걸려서 앞으로 만드는 원도 모두 이 크기로 나옵니다.</p>'''+shot('ui-01-radius','STYLE의 Customize와 Nodes의 radius')+'''
<p>빈 원을 누르고 <b>Caption</b>에 이름을 적은 뒤, <b>+ Label</b>을 눌러 생긴 칸에 종류를 적고 <b>Tab</b>으로 마칩니다.</p>'''+shot('ui-02-caption','Caption 칸과 + Label')+'''
<p>원을 누르면 둘레에 하늘색 띠가 생깁니다. 이 띠를 잡고 빈 곳으로 끌면 새 원과 화살표가 함께 생깁니다. 띠 안쪽을 잡고 끌면 원만 옮겨집니다. 화살표는 끌기 시작한 원에서 새 원 쪽으로 나갑니다. 화살표를 선택하고 <b>Type</b>에 관계 이름을 넣으세요.</p>'''+shot('ui-03-type','화살표의 Type 칸')+table(['Caption · 이름','Label · 종류'], [('HYD-01 유압 파워팩','Asset'),('오일 쿨러','Component'),('유온 센서 TS1','Sensor')])+table(['출발','Type','도착'], [('HYD-01 유압 파워팩','HAS_COMPONENT','오일 쿨러'),('오일 쿨러','MONITORED_BY','유온 센서 TS1')])+photo('01','이 단계를 마친 그림 — 네모가 이번에 더한 곳')+check('원 3개 · 화살표 2개가 HYD-01 → 오일 쿨러 → 유온 센서 TS1 순서로 이어집니다.')))
    parts.append(section(2,'증상과 고장을 구분하기','''<p>온도가 오른다는 <b>증상</b>과 냉각 성능을 잃었다는 <b>고장 유형</b>을 따로 그립니다. 원 두 개를 더 만들어 아래 표대로 이으세요. 하늘색 띠를 끌어 이미 있는 원 위에 놓으면 화살표만 생기고, 방향은 화살표를 선택해 <b>Reverse</b>로 바꿉니다.</p>'''+shot('ui-04-reverse','Reverse 버튼')+table(['Caption','Label'], [('유온 상승','Symptom'),('쿨러 냉각 성능 상실','FailureMode')])+table(['출발','Type','도착'], [('유온 상승','OBSERVED_BY','유온 센서 TS1'),('유온 상승','INDICATES','쿨러 냉각 성능 상실'),('쿨러 냉각 성능 상실','OCCURS_IN','오일 쿨러')])+photo('02','이 단계를 마친 그림 — 네모가 이번에 더한 곳')+check('원 5개 · 화살표 5개. 유온 상승에서 센서와 고장으로 화살표가 하나씩 나갑니다.')))
    parts.append(section(3,'핀 오염의 조건과 조치 붙이기','''<p>같은 고장도 원인에 따라 조치가 다릅니다. <b>쿨러 핀 오염</b>을 더해 고장 쪽으로 <code>CAUSES</code>를 잇고, 이 원을 선택해 <b>+ Property</b>를 눌러 왼쪽 칸에 무엇을 볼지, 오른쪽 칸에 어떤 기준으로 가를지를 적으세요. 한 줄 더 적을 때는 <b>+ Property</b>를 한 번 더 누릅니다. 두 조건을 함께 만족해야 핀 오염입니다. 값에는 부등호와 단위 기호가 들어가니 아래 표에서 복사해 붙이면 편합니다.</p>'''+table(['Caption','Label'], [('쿨러 핀 오염','Cause')])+table(['왼쪽 칸(무엇을 볼지)','오른쪽 칸(기준)'], [('냉각 효율','30초 평균 < 70 %'),('팬 진동','2분 평균 < 0.9 mm/s')])+shot('ui-05-property','Properties의 두 줄과 + Property')+photo('03','이 단계를 마친 그림 — 네모가 이번에 더한 곳')+'''<p><b>팬 최대 운전</b>(온도를 낮추는 완화 조치)과 <b>쿨러 핀 세척</b>(오염을 없애는 근본 조치), 그 근거 매뉴얼을 더하세요.</p>'''+table(['Caption','Label'], [('팬 최대 운전','Skill'),('쿨러 핀 세척','Skill'),('HM-8.5 즉시 완화 조치','ManualSection'),('HM-8.7 근본 조치','ManualSection')])+table(['출발','Type','도착'], [('쿨러 핀 오염','CAUSES','쿨러 냉각 성능 상실'),('쿨러 냉각 성능 상실','MITIGATED_BY','팬 최대 운전'),('쿨러 냉각 성능 상실','REMEDIED_BY','쿨러 핀 세척'),('쿨러 핀 세척','ADDRESSES','쿨러 핀 오염'),('팬 최대 운전','REFERS_TO','HM-8.5 즉시 완화 조치'),('쿨러 핀 세척','REFERS_TO','HM-8.7 근본 조치')])+photo('04','이 단계를 마친 그림 — 네모가 이번에 더한 곳')+check('원 10개 · 화살표 11개. 핀 세척은 핀 오염을 가리키고, 팬 최대 운전은 HM-8.5로 이어집니다.')))
    parts.append(section(4,'다른 원인으로 가지 넓히기','''<p><b>팬 구동 불량</b>과 <b>주변 온도 상승</b>을 같은 고장의 원인으로 더하고, 원인마다 조치와 매뉴얼을 이으세요. HM-8.7은 있는 원을 씁니다.</p>'''+table(['Caption','Label'], [('팬 구동 불량','Cause'),('팬 점검','Skill'),('HM-8.1 팬 벨트 점검','ManualSection'),('주변 온도 상승','Cause'),('캐비닛 환기 보강','Skill')])+'<p>두 원인에도 가려낼 값을 적습니다. 밑줄 붙은 부등호(≥)는 키보드에 없으니 아래 표에서 복사해 붙이세요.</p>'+table(['원','왼쪽 칸','오른쪽 칸'], [('팬 구동 불량','팬 진동','2분 평균 ≥ 0.9 mm/s'),('주변 온도 상승','캐비닛 온도','2분 평균 ≥ 35 ℃')])+table(['출발','Type','도착'], [('팬 구동 불량','CAUSES','쿨러 냉각 성능 상실'),('쿨러 냉각 성능 상실','REMEDIED_BY','팬 점검'),('팬 점검','ADDRESSES','팬 구동 불량'),('팬 점검','REFERS_TO','HM-8.1 팬 벨트 점검')])+photo('05','이 단계를 마친 그림 — 네모가 이번에 더한 곳')+table(['출발','Type','도착'], [('주변 온도 상승','CAUSES','쿨러 냉각 성능 상실'),('캐비닛 환기 보강','ADDRESSES','주변 온도 상승'),('쿨러 냉각 성능 상실','REMEDIED_BY','캐비닛 환기 보강'),('캐비닛 환기 보강','REFERS_TO','HM-8.7 근본 조치')])+photo('06','이 단계를 마친 그림 — 네모가 이번에 더한 곳')+check('원 15개 · 화살표 19개. 고장으로 들어오는 CAUSES가 3개이고, 근본 조치는 각각의 원인을 가리킵니다.')))
    parts.append(section(5,'고장의 연결과 절차 번호 적기','''<p><b>팬 베어링 열화</b>와 이를 가리키는 <b>진동 증가</b>를 더하세요.</p>'''+table(['Caption','Label'], [('팬 베어링 열화','FailureMode'),('진동 증가','Symptom')])+table(['출발','Type','도착'], [('팬 베어링 열화','LEADS_TO','쿨러 냉각 성능 상실'),('진동 증가','INDICATES','팬 베어링 열화')])+'''<p>조치에서 매뉴얼로 가는 화살표를 선택하고 <b>+ Property</b>로 왼쪽 칸에 <code>절차</code>, 오른쪽 칸에 아래 번호를 넣으세요. 화살표에도 원처럼 Properties가 있습니다. 같은 매뉴얼 절이라도 실행할 절차는 다릅니다.</p>'''+table(['화살표 출발','도착','절차'], [('팬 최대 운전','HM-8.5','SOP-COOL-11'),('쿨러 핀 세척','HM-8.7','SOP-COOL-14'),('캐비닛 환기 보강','HM-8.7','SOP-COOL-15'),('팬 점검','HM-8.1','SOP-FAN-11')])+photo('07','이 단계를 마친 그림 — 네모가 이번에 더한 곳')+check('원 17개 · 화살표 21개. 매뉴얼로 이어지는 화살표 4개에 절차 번호가 표시됩니다.')))
    parts.append(section(6,'색칠하고 그림으로 판단하기','''<p>판단할 때 맞춰 볼 것은 원인과 조치의 짝이라 둘을 색으로 가릅니다. <b>쿨러 핀 오염</b>을 누르고 <b>Ctrl</b>을 누른 채 <b>팬 구동 불량</b>, <b>주변 온도 상승</b>을 누르세요. 오른쪽에 <b>nodes: 3</b>이 보이면 셋이 함께 골라진 것입니다. <b>node-color</b>의 <code>#ffffff</code> 대신 연한 빨강 <code>#fca5a5</code>를 적고 <b>Tab</b>으로 넘어갑니다. 조치 네 개(<b>팬 최대 운전</b> · <b>쿨러 핀 세척</b> · <b>팬 점검</b> · <b>캐비닛 환기 보강</b>)도 같은 식으로 골라 연한 초록 <code>#86efac</code>를 적으세요.</p>'''+shot('ui-06-color','함께 고른 원의 수와 node-color 칸')+'''<p>이론에서 본 쿨러 사건의 값은 냉각 효율 30초 평균 <b>46.2 %</b>, 팬 진동 2분 평균 <b>0.575 mm/s</b>, 캐비닛 온도 2분 평균 <b>28 ℃</b>입니다. <b>쿨러 냉각 성능 상실</b>로 들어오는 <code>CAUSES</code>를 거꾸로 따라가 원인 셋을 찾고, 원마다 붙인 조건과 이 값을 견주세요. 맞는 원인에서 조치와 매뉴얼까지 화살표를 따라 읽습니다.</p>'''+check('핀 오염의 두 조건만 맞습니다. 근본 조치는 쿨러 핀 세척 → HM-8.7, 세척 전에 유온을 낮추는 즉시 완화는 팬 최대 운전 → HM-8.5입니다.')+'''<p>값이 다르면 길도 달라집니다. 팬 진동이 2분 평균 <b>1.4 mm/s</b>라면 팬 구동 불량이 맞아 팬 점검 → HM-8.1로 갑니다. 처음 값에서 캐비닛 온도만 <b>38 ℃</b>라면 주변 온도 상승과 핀 오염이 둘 다 맞아, 캐비닛 환기 보강과 쿨러 핀 세척을 함께 봅니다. 팬 진동 값을 아직 못 받았다면 냉각 효율만으로 핀 오염이라고 정하지 말고, 진동 값을 받을 때까지 보류합니다.</p>'''))
    parts.append(section(7,'파일로 남기고 다시 열기','''<p>위쪽 <b>Download / Export</b>를 누르세요. 처음 열린 <b>PNG</b> 탭에서는 안내 글과 <b>Transparent background</b> 체크를 그대로 두고, 크기별 <b>Download</b> 가운데 맨 위 줄 하나만 받습니다. PNG는 보고서나 메신저에 붙이는 그림 파일입니다.</p>'''+shot('ui-07-export-png','PNG 탭과 맨 위 줄의 Download')+'''<p>이어서 <b>JSON</b> 탭의 <b>Download</b>로 다시 열어 고칠 수 있는 파일을 받고, <b>Done</b>으로 닫습니다. 아래에 나오는 글은 그 파일의 내용이라 읽지 않아도 됩니다.</p>'''+shot('ui-08-export-json','JSON 탭의 Download')+'''<p>받은 파일이 제대로 열리는지 새 그림에서 확인합니다. 왼쪽 위 로고를 누르고 <b>New → Web Browser storage</b>를 누르면 가운데에 빈 원 하나만 있는 새 그림이 열립니다. 방금 그린 그림은 이 브라우저에 그대로 남아 있습니다. 다시 로고에서 <b>Import</b>를 누르세요.</p>'''+shot('ui-09-menu','로고 메뉴의 New → Web Browser storage와 Import')+'''<p>위의 회색 안내 글은 넘어가고 <b>Choose File</b>을 눌러 내려받기 폴더의 <code>Untitled graph.json</code>을 고르세요. 아래 칸에 파일 내용이 채워지면 <b>Import</b>를 누릅니다.</p>'''+shot('ui-10-import','Choose File과 아래 Import')+'''<p>불러온 원과 화살표가 모두 골라진 채로 나타나서 오른쪽 위에 그 수가 보입니다. 새 그림에 처음부터 있던 빈 원은 남아 있으니, 그 원을 누르고 오른쪽 <b>Delete</b>로 지우세요.</p>'''+shot('ui-11-imported','다시 연 그림의 원 · 화살표 수')+check('nodes: 17 · relationships: 21로 그린 것과 같고, 원인 원 옆의 조건과 매뉴얼로 가는 화살표의 절차 번호 4개가 그대로 들어와 있습니다.')+'''<p>받은 두 파일은 이름이 <code>Untitled graph</code>라서 <code>쿨러_지식그래프.json</code>, <code>쿨러_지식그래프.png</code>로 바꿔 두세요.</p><p class="save">학교 PC는 껐다 켜면 받은 파일과 브라우저에 남은 그림이 지워집니다. 두 파일을 USB나 본인 클라우드에 옮겨 두세요.</p>
<p>마지막으로 이 그림을 데이터베이스에 넣는 명령으로 바꿔 봅니다. <b>Download / Export</b>를 다시 누르고 <b>Cypher</b> 탭을 누르면 <code>CREATE</code>로 시작하는 글이 나옵니다. 원과 화살표, 원인 조건, 절차 번호가 Neo4j에 넣을 수 있는 Cypher 명령으로 바뀐 것입니다. 명령은 다음 회차에서 직접 다루니 위의 고르는 칸과 파란 단추는 그대로 두고 <b>Done</b>으로 닫으세요.</p>'''+shot('ui-12-cypher','Cypher 탭과 CREATE로 시작하는 명령')))
    nav=''.join(f'<a href="#step{i}">{i:02} {t}</a>' for i,t in enumerate(['설비·센서','증상·고장','핀 오염·조치','원인 확장','고장·절차','색칠·판단','저장·다시 열기'],1))
    return '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>쿨러 지식 그래프 만들기 · 실습 가이드</title><style>
:root{--ink:#213330;--muted:#5a6c67;--line:#dce5df;--green:#216953;--paper:#fff;--bg:#f4f6f2}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:30px}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.85 "Malgun Gothic","Segoe UI",sans-serif}a{color:var(--green);text-underline-offset:4px}a:focus-visible,button:focus-visible{outline:3px solid #d18424;outline-offset:4px}.shell{max-width:1380px;margin:auto;padding:56px 36px}header{padding:40px 48px;background:#e6eee6;border-radius:22px;margin-bottom:36px}.eyebrow{font-size:13px;font-weight:700;letter-spacing:2px;color:var(--green)}h1{font-size:40px;letter-spacing:-1.8px;line-height:1.3;margin:16px 0}header p{max-width:820px;margin:0;color:#40584f}.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:26px}.button{display:inline-block;padding:11px 22px;background:var(--green);color:white;text-decoration:none;border-radius:9px;font-weight:700}.button.secondary{background:white;color:var(--green)}.layout{display:grid;grid-template-columns:170px minmax(0,1fr);gap:32px}nav{position:sticky;top:30px;align-self:start}nav span{display:block;color:var(--muted);font-size:12px;letter-spacing:2px;margin:8px 0 16px}nav a{display:block;padding:10px 12px;margin-bottom:5px;text-decoration:none;font-size:14px;border-radius:7px}nav a:hover{background:#e6eee6}section{background:var(--paper);border:1px solid var(--line);border-radius:16px;padding:36px;margin-bottom:32px}.step-head{display:flex;gap:16px;align-items:center;border-bottom:1px solid var(--line);padding-bottom:24px;margin-bottom:24px}.number{font:600 27px/1 Georgia,serif;color:var(--green)}h2{font-size:25px;line-height:1.4;margin:0;letter-spacing:-.7px}p{margin:18px 0}b,strong{font-weight:700}code{font-family:Consolas,monospace;background:#edf3ee;padding:3px 6px;border-radius:4px;user-select:all;font-size:.95em}.table-wrap{overflow:auto;margin:24px 0}table{width:100%;border-collapse:collapse;font-size:14px;line-height:1.7}th{text-align:left;background:#f0f4ef;color:#445e52;font-weight:600;white-space:nowrap}td,th{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top}td{user-select:text}figure{margin:28px 0}img{display:block;width:100%;border:1px solid var(--line);border-radius:9px}figcaption{font-size:13px;color:var(--muted);margin-top:10px}.check{padding:18px 20px;background:#edf5ee;border-left:3px solid #45846a;border-radius:0 8px 8px 0;font-size:15px}.check strong{display:block;color:var(--green);margin-bottom:4px}.save{padding:18px 20px;background:#faf4e6;border-radius:8px;font-size:15px}footer{color:var(--muted);font-size:13px;text-align:center;padding:16px}.top{display:inline-block;margin-top:12px}@media(max-width:850px){.shell{padding:20px 14px}header{padding:28px 22px}h1{font-size:30px}.layout{display:block}nav{position:static;display:flex;flex-wrap:wrap;margin-bottom:20px;gap:4px}nav span{display:none}nav a{padding:6px 9px;font-size:12px;background:white}section{padding:24px 18px}h2{font-size:22px}.step-head{gap:12px}}@media print{body{background:white}.shell{padding:0}nav,.actions,.top{display:none}.layout{display:block}section{break-before:page;border:0;padding:0}figure,table,.check{break-inside:avoid}a{color:inherit}}
</style></head><body><div class="shell"><header><div class="eyebrow">1회차 · 통합반 / 실전반 공통</div><h1>쿨러 지식 그래프 만들기</h1><p>설비와 센서에서 시작해 증상 · 고장 · 원인 · 조치를 연결합니다.<br>단계별 그림을 따라 만들고, 저장한 데이터를 다시 열어 확인합니다. 사진을 누르면 크게 볼 수 있습니다.</p><div class="actions"><a class="button" href="https://arrows.app" target="_blank" rel="noopener">ARROWS 열기 ↗</a><a class="button secondary" href="매뉴얼_발췌.md">매뉴얼 근거</a></div></header><div class="layout"><nav aria-label="실습 단계"><span>진행 순서</span>'''+nav+'</nav><main>'+''.join(parts)+'''<a class="top" href="#">맨 위로 ↑</a></main></div><footer>쿨러 지식 그래프 · 통합반 / 실전반 공통 실습</footer></div></body></html>'''

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
    """images/를 확정 영상의 UI_SHOTS · STAGE_SHOTS 프레임으로 새로 채우고 사진 근거를 고쳐 쓴다."""
    import imageio_ffmpeg, tempfile
    probe=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-i',str(video)],capture_output=True).stderr.decode('utf-8','replace')
    dur=[l.split('Duration:')[1].split(',')[0].strip() for l in probe.splitlines() if 'Duration:' in l]
    if dur!=[VIDEO_DURATION]:
        raise SystemExit(f'{video}: 확정 영상({VIDEO_DURATION})이 아니다 — Duration {dur}')
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
            if crop:im=im.crop(crop)
            im.save(images/f'{name}.png')
            manifest[kind].append({'file':f'images/{name}.png','seconds':sec,'frame_sha256':sha(raw),'crop':list(crop) if crop else None,
                                   'boxes':[{'target':list(b[:4]),'margin':b[4],'outer':o,'dark_px_under_line':n} for b,(o,n) in zip(boxes,outer)],'sha256':sha(images/f'{name}.png')})
    (Path(__file__).parent/'학생가이드_사진근거.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':main()
