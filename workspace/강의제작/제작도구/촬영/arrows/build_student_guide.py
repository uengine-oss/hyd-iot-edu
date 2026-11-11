"""확정 영상에서 조작 화면 사진을 뽑고 단계 결과 그림에 네모를 그려, 두 과정 학생 가이드와 한 파일 가이드(<랩>.html, lab_package.pack_page)를 갱신한다.
Usage: python build_student_guide.py [--video <확정 mp4> --captures <투명 배경 stage-NN.png 원본 폴더>]
  --video · --captures를 함께 주면 images/를 UI_SHOTS · STAGE_BOXES대로 새로 만들고 사진 근거(학생가이드_사진근거.json)를 고쳐 쓴다.
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
# 확정 실습 영상(Release 영상 int-01-08-lab.mp4, 1525.07초)에서 뽑는 ARROWS 화면. 시각은 말 시각 기록
# (산출물/영상/_작업/영상_자막_기록/통합반_01회차_08_실습_관계그림.srt)의 그 조작 큐 안이다.
# boxes: (x0, y0, x1, y1, margin) — 대상 경계(프레임 px)와 대상 바깥 간격. crop: 그림 영역만 자를 때.
UI_SHOTS = [
    ('ui-01-start', 72.0, None, [(1747, 113, 1890, 153, 6), (1634, 252, 1769, 296, 6), (1585, 718, 1672, 740, 6)]),   # Add Node · Customize · radius
    ('ui-02-caption', 126.0, None, [(1407, 325, 1890, 371, 2), (1407, 419, 1890, 463, 2), (1789, 481, 1890, 519, (6, 2, 6, 0))]),  # Caption · Labels 칸 · + Label(아래 Properties 글자와 7px)
    ('ui-03-type', 185.0, None, [(1407, 367, 1890, 413, (4, 1, 4, 4))]),                                                        # 화살표의 Type
    ('ui-04-reverse', 296.0, None, [(1490, 156, 1619, 197, 3)]),                                                       # Reverse
    ('ui-05-property', 495.0, None, [(1409, 550, 1892, 650, (4, 2, 4, 4))]),                                                    # Properties 줄과 + Property
    ('ui-06-color', 1232.0, None, [(1407, 101, 1551, 138, 4), (1550, 920, 1766, 942, 6)]),                            # nodes: 3 · node-color
    ('ui-07-export-json', 1399.0, None, [(1333, 5, 1553, 48, 2), (573, 181, 650, 225, 6), (330, 264, 487, 309, 6)]),  # Download / Export · JSON · Download
    ('ui-08-export-png', 1405.0, None, [(311, 181, 381, 225, 6), (345, 503, 550, 522, 6)]),                           # PNG · @1x Download
    ('ui-09-menu', 1418.0, None, [(16, 10, 50, 42, 2), (12, 60, 98, 92, 2), (110, 150, 338, 190, 6), (14, 214, 80, 242, 6)]),  # 로고 · New · Web Browser storage · Import
    ('ui-10-import', 1434.0, None, [(312, 382, 500, 426, 6), (1507, 859, 1613, 904, 6)]),                             # Choose File · Import
    ('ui-11-imported', 1448.0, (330, 70, 1610, 1010), [(1166, 917, 1292, 950, 6)]),                                                           # 다시 연 그림(그림 영역) · 절차 번호 하나
]
# 단계 결과 그림(stage-NN.png, 2400×1692 투명 배경)에 「이번에 추가」한 곳 하나 — 원 채움 경계 + 테두리 5px.
STAGE_BOXES = {
    '01': (871, 479, 1533, 1217, 6),     # 설비 · 쿨러 · 센서 전체
    '02': (1515, 479, 1757, 1217, 6),    # 냉각 성능 상실 · 유온 상승
    '03': (1643, 555, 2224, 797, 6),     # 쿨러 핀 오염과 두 조건
    '04': (1271, 1419, 1877, 1621, 6),   # 팬 최대 운전 → HM-8.5
    '05': (1078, 72, 1415, 229, 6),      # 팬 구동 불량과 조건
    '06': (1591, 1115, 1749, 1273, 6),   # 캐비닛 환기 보강
    '07': (355, 75, 777, 229, 6),        # 진동 증가 → 팬 베어링 열화
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
    parts.append(section(1,'설비와 센서를 연결하기', '''<p>오일 쿨러가 어느 설비에 속하고 어떤 센서로 보는지 그립니다. <a href="https://arrows.app" target="_blank" rel="noopener">ARROWS 열기 ↗</a>를 누르고 <b>Add Node</b>로 첫 원을 만드세요. 오른쪽 <b>Caption</b>에 이름, <b>Label +</b>에 종류를 넣고 <b>Tab</b>으로 마칩니다.</p>'''+shot('ui-01-start','Add Node와 STYLE의 Customize · radius')+shot('ui-02-caption','Caption 칸, Labels 칸과 Label 더하기')+'''
<p>선택한 원의 테두리를 빈 곳으로 끌면 새 원과 화살표가 생깁니다. 화살표를 선택하고 <b>Type</b>에 관계 이름을 넣으세요. 원이 작으면 빈 곳을 누른 뒤 <b>STYLE → Customize → radius</b>를 <code>70</code>으로 맞춥니다.</p>'''+shot('ui-03-type','화살표의 Type 칸')+table(['Caption · 이름','Label · 종류'], [('HYD-01 유압 파워팩','Asset'),('오일 쿨러','Component'),('유온 센서 TS1','Sensor')])+table(['출발','Type','도착'], [('HYD-01 유압 파워팩','HAS_COMPONENT','오일 쿨러'),('오일 쿨러','MONITORED_BY','유온 센서 TS1')])+photo('01','이 단계를 마친 그림 — 네모가 이번에 더한 곳')+check('원 3개 · 화살표 2개가 HYD-01 → 오일 쿨러 → 유온 센서 TS1 순서로 이어집니다.')))
    parts.append(section(2,'증상과 고장을 구분하기','''<p>온도가 오른다는 <b>증상</b>과 냉각 성능을 잃었다는 <b>고장 유형</b>을 따로 그립니다. 원 두 개를 더 만들어 아래 표대로 이으세요. 이미 있는 원 위로 테두리를 끌면 화살표만 생기고, 방향은 화살표를 선택해 <b>Reverse</b>로 바꿉니다.</p>'''+shot('ui-04-reverse','Reverse 버튼')+table(['Caption','Label'], [('유온 상승','Symptom'),('쿨러 냉각 성능 상실','FailureMode')])+table(['출발','Type','도착'], [('유온 상승','OBSERVED_BY','유온 센서 TS1'),('유온 상승','INDICATES','쿨러 냉각 성능 상실'),('쿨러 냉각 성능 상실','OCCURS_IN','오일 쿨러')])+photo('02','이 단계를 마친 그림 — 네모가 이번에 더한 곳')+check('원 5개 · 화살표 5개. 유온 상승에서 센서와 고장으로 화살표가 하나씩 나갑니다.')))
    parts.append(section(3,'핀 오염의 조건과 조치 붙이기','''<p>같은 고장도 원인에 따라 조치가 다릅니다. <b>쿨러 핀 오염</b>을 더해 고장 쪽으로 <code>CAUSES</code>를 잇고, 이 원을 선택해 <b>Property +</b>로 두 조건을 적으세요. 두 조건을 함께 만족해야 핀 오염입니다.</p>'''+shot('ui-05-property','Properties의 항목 · 값 칸과 Property 더하기')+table(['Caption','Label','Property'], [('쿨러 핀 오염','Cause','냉각 효율: 30초 평균 < 70 % / 팬 진동: 2분 평균 < 0.9 mm/s')])+photo('03','이 단계를 마친 그림 — 네모가 이번에 더한 곳')+'''<p><b>팬 최대 운전</b>(온도를 낮추는 완화 조치)과 <b>쿨러 핀 세척</b>(오염을 없애는 근본 조치), 그 근거 매뉴얼을 더하세요.</p>'''+table(['Caption','Label'], [('팬 최대 운전','Skill'),('쿨러 핀 세척','Skill'),('HM-8.5 즉시 완화 조치','ManualSection'),('HM-8.7 근본 조치','ManualSection')])+table(['출발','Type','도착'], [('쿨러 핀 오염','CAUSES','쿨러 냉각 성능 상실'),('쿨러 냉각 성능 상실','MITIGATED_BY','팬 최대 운전'),('쿨러 냉각 성능 상실','REMEDIED_BY','쿨러 핀 세척'),('쿨러 핀 세척','ADDRESSES','쿨러 핀 오염'),('팬 최대 운전','REFERS_TO','HM-8.5 즉시 완화 조치'),('쿨러 핀 세척','REFERS_TO','HM-8.7 근본 조치')])+photo('04','이 단계를 마친 그림 — 네모가 이번에 더한 곳')+check('원 10개 · 화살표 11개. 핀 세척은 핀 오염을 가리키고, 팬 최대 운전은 HM-8.5로 이어집니다.')))
    parts.append(section(4,'다른 원인으로 가지 넓히기','''<p><b>팬 구동 불량</b>과 <b>주변 온도 상승</b>을 같은 고장의 원인으로 더하고, 원인마다 조치와 매뉴얼을 이으세요. HM-8.7은 있는 원을 씁니다.</p>'''+table(['Caption','Label','Property'], [('팬 구동 불량','Cause','팬 진동: 2분 평균 ≥ 0.9 mm/s'),('팬 점검','Skill','—'),('HM-8.1 팬 벨트 점검','ManualSection','—'),('주변 온도 상승','Cause','캐비닛 온도: 2분 평균 ≥ 35 ℃'),('캐비닛 환기 보강','Skill','—')])+table(['출발','Type','도착'], [('팬 구동 불량','CAUSES','쿨러 냉각 성능 상실'),('쿨러 냉각 성능 상실','REMEDIED_BY','팬 점검'),('팬 점검','ADDRESSES','팬 구동 불량'),('팬 점검','REFERS_TO','HM-8.1 팬 벨트 점검')])+photo('05','이 단계를 마친 그림 — 네모가 이번에 더한 곳')+table(['출발','Type','도착'], [('주변 온도 상승','CAUSES','쿨러 냉각 성능 상실'),('캐비닛 환기 보강','ADDRESSES','주변 온도 상승'),('쿨러 냉각 성능 상실','REMEDIED_BY','캐비닛 환기 보강'),('캐비닛 환기 보강','REFERS_TO','HM-8.7 근본 조치')])+photo('06','이 단계를 마친 그림 — 네모가 이번에 더한 곳')+check('원 15개 · 화살표 19개. 고장으로 들어오는 CAUSES가 3개이고, 근본 조치는 각각의 원인을 가리킵니다. 팬 점검 → HM-8.1의 Type에도 REFERS_TO를 입력합니다.')))
    parts.append(section(5,'고장의 연결과 절차 번호 적기','''<p><b>팬 베어링 열화</b>와 이를 가리키는 <b>진동 증가</b>를 더하세요.</p>'''+table(['Caption','Label'], [('팬 베어링 열화','FailureMode'),('진동 증가','Symptom')])+table(['출발','Type','도착'], [('팬 베어링 열화','LEADS_TO','쿨러 냉각 성능 상실'),('진동 증가','INDICATES','팬 베어링 열화')])+photo('07','이 단계를 마친 그림 — 네모가 이번에 더한 곳')+'''<p>조치에서 매뉴얼로 가는 화살표를 선택하고 <b>Property +</b>에 이름 <code>절차</code>와 아래 번호를 넣으세요. 같은 매뉴얼 절이라도 실행할 절차는 다릅니다.</p>'''+table(['화살표 출발','도착','절차'], [('팬 최대 운전','HM-8.5','SOP-COOL-11'),('쿨러 핀 세척','HM-8.7','SOP-COOL-14'),('캐비닛 환기 보강','HM-8.7','SOP-COOL-15'),('팬 점검','HM-8.1','SOP-FAN-11')])+check('원 17개 · 화살표 21개. 매뉴얼로 이어지는 화살표 4개에 절차 번호가 표시됩니다.')))
    parts.append(section(6,'그림을 정리하고 경로 읽기','''<p>원 가운데를 잡아 옮겨 이름과 화살표가 겹치지 않게 하세요. 자리가 모자라면 빈 곳을 누르고 <b>STYLE → Customize → radius</b>를 <code>47</code>로 줄입니다. <b>Ctrl</b>을 누른 채 원들을 고르고 <b>STYLE → node-color</b>에서 원인은 연한 빨강, 조치는 연한 초록으로 칠하세요.</p>'''+shot('ui-06-color','선택한 원의 수와 node-color 칸')+'''<p>냉각 효율 <b>46.2 %</b>, 팬 진동 2분 평균 <b>0.575 mm/s</b>, 캐비닛 온도 <b>28 ℃</b>를 세 원인의 조건과 비교하고, 맞는 원인에서 조치와 매뉴얼까지 화살표를 따라 읽으세요.</p>'''+check('핀 오염의 두 조건에 해당합니다. 근본 조치는 핀 세척 → HM-8.7, 즉시 완화는 팬 최대 운전 → HM-8.5로 이어집니다. 팬 진동 값이 없으면 핀 오염 조건을 모두 확인한 것은 아닙니다.')))
    parts.append(section(7,'저장하고 다시 열기','''<p>위쪽 <b>Download / Export</b>에서 <b>JSON → Download</b>로 편집 데이터를, <b>PNG → Download</b>로 그림을 저장하세요. 파일 이름은 <code>쿨러_지식그래프.json</code>, <code>쿨러_지식그래프.png</code>로 바꿉니다.</p>'''+shot('ui-07-export-json','Download / Export → JSON 탭의 Download')+shot('ui-08-export-png','PNG 탭 맨 위 줄의 Download')+'''<p>왼쪽 위 로고 메뉴에서 <b>New → Web Browser storage</b>로 새 그림을 열고, <b>Import → Choose File</b>로 저장한 JSON을 골라 <b>Import</b>를 누르세요. 기본 빈 원이 남아 있으면 선택해 <b>Delete</b>로 지웁니다.</p>'''+shot('ui-09-menu','로고 메뉴의 New → Web Browser storage와 Import')+shot('ui-10-import','Choose File과 아래 Import')+shot('ui-11-imported','다시 열린 그림의 절차 번호')+check('다시 연 그림에 원 17개 · 화살표 21개, 원인 조건과 절차 번호 4개가 있습니다.')+'''<p class="save">학교 PC는 재부팅하면 저장한 파일이 사라집니다. JSON과 PNG를 USB나 본인 클라우드에 복사해 두세요.</p>'''))
    nav=''.join(f'<a href="#step{i}">{i:02} {t}</a>' for i,t in enumerate(['설비·센서','증상·고장','핀 오염·조치','원인 확장','고장·절차','정리·확인','저장'],1))
    return '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>쿨러 지식 그래프 만들기 · 실습 가이드</title><style>
:root{--ink:#213330;--muted:#5a6c67;--line:#dce5df;--green:#216953;--paper:#fff;--bg:#f4f6f2}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:30px}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.85 "Malgun Gothic","Segoe UI",sans-serif}a{color:var(--green);text-underline-offset:4px}a:focus-visible,button:focus-visible{outline:3px solid #d18424;outline-offset:4px}.shell{max-width:1380px;margin:auto;padding:56px 36px}header{padding:40px 48px;background:#e6eee6;border-radius:22px;margin-bottom:36px}.eyebrow{font-size:13px;font-weight:700;letter-spacing:2px;color:var(--green)}h1{font-size:40px;letter-spacing:-1.8px;line-height:1.3;margin:16px 0}header p{max-width:820px;margin:0;color:#40584f}.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:26px}.button{display:inline-block;padding:11px 22px;background:var(--green);color:white;text-decoration:none;border-radius:9px;font-weight:700}.button.secondary{background:white;color:var(--green)}.layout{display:grid;grid-template-columns:170px minmax(0,1fr);gap:32px}nav{position:sticky;top:30px;align-self:start}nav span{display:block;color:var(--muted);font-size:12px;letter-spacing:2px;margin:8px 0 16px}nav a{display:block;padding:10px 12px;margin-bottom:5px;text-decoration:none;font-size:14px;border-radius:7px}nav a:hover{background:#e6eee6}section{background:var(--paper);border:1px solid var(--line);border-radius:16px;padding:36px;margin-bottom:32px}.step-head{display:flex;gap:16px;align-items:center;border-bottom:1px solid var(--line);padding-bottom:24px;margin-bottom:24px}.number{font:600 27px/1 Georgia,serif;color:var(--green)}h2{font-size:25px;line-height:1.4;margin:0;letter-spacing:-.7px}p{margin:18px 0}b,strong{font-weight:700}code{font-family:Consolas,monospace;background:#edf3ee;padding:3px 6px;border-radius:4px;user-select:all;font-size:.95em}.table-wrap{overflow:auto;margin:24px 0}table{width:100%;border-collapse:collapse;font-size:14px;line-height:1.7}th{text-align:left;background:#f0f4ef;color:#445e52;font-weight:600;white-space:nowrap}td,th{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top}td{user-select:text}figure{margin:28px 0}img{display:block;width:100%;border:1px solid var(--line);border-radius:9px}figcaption{font-size:13px;color:var(--muted);margin-top:10px}.check{padding:18px 20px;background:#edf5ee;border-left:3px solid #45846a;border-radius:0 8px 8px 0;font-size:15px}.check strong{display:block;color:var(--green);margin-bottom:4px}.save{padding:18px 20px;background:#faf4e6;border-radius:8px;font-size:15px}footer{color:var(--muted);font-size:13px;text-align:center;padding:16px}.top{display:inline-block;margin-top:12px}@media(max-width:850px){.shell{padding:20px 14px}header{padding:28px 22px}h1{font-size:30px}.layout{display:block}nav{position:static;display:flex;flex-wrap:wrap;margin-bottom:20px;gap:4px}nav span{display:none}nav a{padding:6px 9px;font-size:12px;background:white}section{padding:24px 18px}h2{font-size:22px}.step-head{gap:12px}}@media print{body{background:white}.shell{padding:0}nav,.actions,.top{display:none}.layout{display:block}section{break-before:page;border:0;padding:0}figure,table,.check{break-inside:avoid}a{color:inherit}}
</style></head><body><div class="shell"><header><div class="eyebrow">1회차 · 통합반 / 실전반 공통</div><h1>쿨러 지식 그래프 만들기</h1><p>설비와 센서에서 시작해 증상 · 고장 · 원인 · 조치를 연결합니다.<br>단계별 그림을 따라 만들고, 저장한 데이터를 다시 열어 확인합니다. 사진을 누르면 크게 볼 수 있습니다.</p><div class="actions"><a class="button" href="https://arrows.app" target="_blank" rel="noopener">ARROWS 열기 ↗</a><a class="button secondary" href="매뉴얼_발췌.md">매뉴얼 근거</a></div></header><div class="layout"><nav aria-label="실습 단계"><span>진행 순서</span>'''+nav+'</nav><main>'+''.join(parts)+'''<a class="top" href="#">맨 위로 ↑</a></main></div><footer>쿨러 지식 그래프 · 통합반 / 실전반 공통 실습</footer></div></body></html>'''

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--video',type=Path)
    parser.add_argument('--captures',type=Path)   # 없으면 지금 사진 · 사진 근거를 그대로 두고 가이드 · 한 파일 가이드만 다시 만든다
    args=parser.parse_args()
    sys.path.insert(0,str(ROOT/'workspace/강의제작/제작도구/실습시작'))
    from lab_package import pack_page
    guide=render()
    guide=guide.replace('<style>','<style>.added{border-top:1px solid #dce5df;padding-top:18px;color:#216953;font-size:15px}.added b{display:inline-block;background:#e6eee6;padding:3px 10px;border-radius:5px;margin-right:8px}')
    source=ROOT/'workspace/강의제작/산출물/통합반/실습/01회차/랩'/LAB
    images=source/'images'
    if bool(args.video)!=bool(args.captures):
        raise SystemExit('--video와 --captures는 함께 준다(사진 근거 하나에 두 원본을 함께 적는다).')
    if args.video:
        build_images(args.video, args.captures, images)
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

def build_images(video, captures, images):
    """images/를 UI_SHOTS(영상 프레임) · STAGE_BOXES(단계 결과 그림)로 새로 채우고 사진 근거를 고쳐 쓴다."""
    import imageio_ffmpeg, tempfile
    from PIL import Image
    probe=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-i',str(video)],capture_output=True).stderr.decode('utf-8','replace')
    dur=[l.split('Duration:')[1].split(',')[0].strip() for l in probe.splitlines() if 'Duration:' in l]
    if dur!=['00:25:25.07']:
        raise SystemExit(f'{video}: 확정 영상(25:25.07)이 아니다 — Duration {dur}')
    stages={}
    for n in STAGE_BOXES:
        f=Path(captures)/f'stage-{n}.png'
        with Image.open(f) as im:
            if im.mode!='RGBA' or im.getchannel('A').getextrema()[0]!=0:
                raise SystemExit(f'{f}: 투명 배경 원본이 아니다(이미 흰 바탕 · 네모를 넣은 사진을 다시 넣으면 네모가 겹친다)')
            stages[n]=Image.alpha_composite(Image.new('RGBA',im.size,'white'),im.convert('RGBA')).convert('RGB')
    if images.exists():shutil.rmtree(images)
    images.mkdir()
    old=json.loads((Path(__file__).parent/'학생가이드_사진근거.json').read_text(encoding='utf-8'))
    manifest={'video':{'file':'Release 영상 int-01-08-lab.mp4 (이 PC 사본: 작업/촬영/arrows/통합반_01회차_08_실습_관계그림.mp4)','duration':'25:25.07','sha256':sha(video)},
              'box':{'color':'#e60000','width':LINE,'note':'대상 경계 바깥 margin px에서 굵기 6 선이 바깥으로 그려진다. outer는 네모 바깥 경계다'},
              'ui_frames':[],'stage_frames':[],'stage_capture':old.get('stage_capture') or {k:old[k] for k in ('capture_method','frames','source_layout_sha256')}}
    with tempfile.TemporaryDirectory() as tmp:
        for name,sec,crop,boxes in UI_SHOTS:
            raw=Path(tmp)/f'{name}.png'
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-ss',f'{sec:.2f}','-i',str(video),'-frames:v','1','-y',str(raw)],check=True)
            im=Image.open(raw).convert('RGB')
            if im.size!=(1920,1080):raise SystemExit(f'{name}: 프레임 크기 {im.size}')
            outer=draw_boxes(im,boxes)
            if crop:im=im.crop(crop)
            im.save(images/f'{name}.png')
            manifest['ui_frames'].append({'file':f'images/{name}.png','seconds':sec,'frame_sha256':sha(raw),'crop':list(crop) if crop else None,
                                          'boxes':[{'target':list(b[:4]),'margin':b[4],'outer':o,'dark_px_under_line':n} for b,(o,n) in zip(boxes,outer)],'sha256':sha(images/f'{name}.png')})
    for n,box in STAGE_BOXES.items():
        im=stages[n]; outer=draw_boxes(im,[box]); im.save(images/f'stage-{n}.png')
        manifest['stage_frames'].append({'file':f'images/stage-{n}.png','source_sha256':sha(Path(captures)/f'stage-{n}.png'),'background':'white',
                                         'boxes':[{'target':list(box[:4]),'margin':box[4],'outer':outer[0][0],'dark_px_under_line':outer[0][1]}],'sha256':sha(images/f'stage-{n}.png')})
    (Path(__file__).parent/'학생가이드_사진근거.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':main()
