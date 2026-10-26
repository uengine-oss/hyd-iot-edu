"""확정 영상에서 단계 사진을 추출하고 두 과정 학생 가이드/기존 ZIP을 갱신한다.
Usage: python build_student_guide.py --video <확정 mp4>
영상·대본·완성 참조 원본은 수정하지 않는다.
"""
from pathlib import Path
import argparse
import hashlib
import html
import json
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
LAB = '01일차_실습4_관계그림'
SHOTS = [('01-equipment', 162), ('02-symptom', 263), ('03-cause', 359),
         ('04-action', 506), ('05-fan', 630), ('06-air', 741),
         ('07-bearing', 826), ('08-layout', 1018), ('09-export', 1137), ('10-import', 1183)]

def table(headers, rows):
    return '<div class="table-wrap"><table><thead><tr>' + ''.join('<th>'+html.escape(x)+'</th>' for x in headers) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join('<td>'+html.escape(x)+'</td>' for x in row)+'</tr>' for row in rows) + '</tbody></table></div>'

def photo(name, caption):
    stages={'01-equipment':'01','02-symptom':'02','03-cause':'03','04-action':'04','05-fan':'05','06-air':'06','07-bearing':'07','08-layout':'07'}
    additions={'01':'설비 · 오일 쿨러 · 유온 센서','02':'유온 상승 · 냉각 성능 상실','03':'핀 오염 · 판별 조건','04':'팬 최대 운전 · 핀 세척 · 매뉴얼','05':'팬 구동 불량 · 팬 점검 · HM-8.1','06':'주변 온도 상승 · 캐비닛 환기 보강','07':'진동 증가 · 팬 베어링 열화 · 절차 번호'}
    file='images/stage-'+stages[name]+'.png' if name in stages else f'images/{name}.jpg'
    label=f'<p class="added"><b>이번에 추가</b> {additions[stages[name]]}</p>' if name in stages and name!='08-layout' else ''
    return label+f'<figure><a href="{file}" target="_blank"><img style="background:white" src="{file}" alt="{caption}" loading="lazy"></a><figcaption>{caption} · 사진을 누르면 크게 볼 수 있습니다.</figcaption></figure>'

def section(n, title, body):
    return f'<section id="step{n}"><div class="step-head"><span class="number">{n:02}</span><h2>{title}</h2></div>{body}</section>'

def check(text):
    return '<p class="check"><strong>확인</strong> '+text+'</p>'

def render():
    parts=[]
    parts.append(section(1,'설비와 센서를 연결하기', '''<p>오일 쿨러가 어느 설비에 속하고 어떤 센서로 상태를 보는지 그립니다. <a href="https://arrows.app" target="_blank" rel="noopener">ARROWS 열기 ↗</a>를 누르고 <b>Add Node</b>로 첫 원을 만드세요. 오른쪽 <b>Caption</b>에는 이름, <b>Label +</b>에는 종류를 입력합니다. 입력은 <b>Tab</b>으로 마칩니다.</p>
<p>선택한 원의 테두리를 빈 곳으로 끌면 새 원과 화살표가 함께 생깁니다. 화살표를 선택하고 오른쪽 <b>Type</b>에 관계 이름을 넣으세요. 원이 작으면 빈 곳을 누른 뒤 <b>STYLE → Customize → radius</b>를 <code>70</code>으로 맞춥니다.</p>'''+table(['Caption · 이름','Label · 종류'], [('HYD-01 유압 파워팩','Asset'),('오일 쿨러','Component'),('유온 센서 TS1','Sensor')])+table(['출발','Type','도착'], [('HYD-01 유압 파워팩','HAS_COMPONENT','오일 쿨러'),('오일 쿨러','MONITORED_BY','유온 센서 TS1')])+photo('01-equipment','설비 → 구성 요소 → 센서로 이어진 상태')+check('원 3개와 화살표 2개. HYD-01 → 오일 쿨러 → 유온 센서 TS1 순서로 화살표가 이어집니다.')))
    parts.append(section(2,'증상과 고장을 구분하기','''<p>온도가 오른다는 <b>증상</b>과 냉각 성능을 잃었다는 <b>고장 유형</b>을 구분합니다. 원 두 개를 더 만든 뒤 아래 방향으로 연결하세요. 이미 있는 원 위로 테두리를 끌면 화살표만 추가됩니다. 방향은 화살표를 선택한 뒤 <b>Reverse</b>로 바꿀 수 있습니다.</p>'''+table(['Caption','Label'], [('유온 상승','Symptom'),('쿨러 냉각 성능 상실','FailureMode')])+table(['출발','Type','도착'], [('유온 상승','OBSERVED_BY','유온 센서 TS1'),('유온 상승','INDICATES','쿨러 냉각 성능 상실'),('쿨러 냉각 성능 상실','OCCURS_IN','오일 쿨러')])+photo('02-symptom','센서에서 관측한 증상과, 그 증상이 가리키는 고장')+check('원 5개·화살표 5개. 유온 상승에서 센서와 고장으로 각각 화살표가 나갑니다.')))
    parts.append(section(3,'핀 오염의 조건과 조치 붙이기','''<p>같은 고장이라도 원인에 따라 조치가 달라집니다. 먼저 <b>쿨러 핀 오염</b>을 추가하고 고장 쪽으로 <code>CAUSES</code>를 연결합니다. 이 원을 선택해 <b>Property +</b>로 두 조건을 적으세요. 두 조건을 함께 만족해야 핀 오염에 해당합니다.</p>'''+table(['Caption','Label','Property'], [('쿨러 핀 오염','Cause','냉각 효율: 30초 평균 < 70 % / 팬 진동: 2분 평균 < 0.9 mm/s')])+photo('03-cause','핀 오염 원에 냉각 효율과 팬 진동 조건을 적은 상태')+'''<p><b>팬 최대 운전</b>은 온도를 낮추는 완화 조치이고, <b>쿨러 핀 세척</b>은 오염을 없애는 근본 조치입니다. 두 조치와 근거 매뉴얼을 추가하세요.</p>'''+table(['Caption','Label'], [('팬 최대 운전','Skill'),('쿨러 핀 세척','Skill'),('HM-8.5 즉시 완화 조치','ManualSection'),('HM-8.7 근본 조치','ManualSection')])+table(['출발','Type','도착'], [('쿨러 핀 오염','CAUSES','쿨러 냉각 성능 상실'),('쿨러 냉각 성능 상실','MITIGATED_BY','팬 최대 운전'),('쿨러 냉각 성능 상실','REMEDIED_BY','쿨러 핀 세척'),('쿨러 핀 세척','ADDRESSES','쿨러 핀 오염'),('팬 최대 운전','REFERS_TO','HM-8.5 즉시 완화 조치'),('쿨러 핀 세척','REFERS_TO','HM-8.7 근본 조치')])+photo('04-action','완화 조치·근본 조치와 각각의 매뉴얼 근거')+check('원 10개·화살표 11개. 핀 세척은 핀 오염을 가리키고, 팬 최대 운전은 HM-8.5로 이어집니다.')))
    parts.append(section(4,'다른 원인으로 가지 넓히기','''<p><b>팬 구동 불량</b>과 <b>주변 온도 상승</b>도 냉각 성능 상실을 일으킬 수 있습니다. 같은 고장 원에 두 가지를 더하고, 각 원인에 맞는 조치와 매뉴얼을 연결하세요. HM-8.7은 기존 원을 함께 사용합니다.</p>'''+table(['Caption','Label','Property'], [('팬 구동 불량','Cause','팬 진동: 2분 평균 ≥ 0.9 mm/s'),('팬 점검','Skill','—'),('HM-8.1 팬 벨트 점검','ManualSection','—'),('주변 온도 상승','Cause','캐비닛 온도: 2분 평균 ≥ 35 ℃'),('캐비닛 환기 보강','Skill','—')])+table(['출발','Type','도착'], [('팬 구동 불량','CAUSES','쿨러 냉각 성능 상실'),('쿨러 냉각 성능 상실','REMEDIED_BY','팬 점검'),('팬 점검','ADDRESSES','팬 구동 불량'),('팬 점검','REFERS_TO','HM-8.1 팬 벨트 점검')])+photo('05-fan','팬 구동 불량 → 고장, 팬 점검 → 원인·매뉴얼 연결')+table(['출발','Type','도착'], [('주변 온도 상승','CAUSES','쿨러 냉각 성능 상실'),('캐비닛 환기 보강','ADDRESSES','주변 온도 상승'),('쿨러 냉각 성능 상실','REMEDIED_BY','캐비닛 환기 보강'),('캐비닛 환기 보강','REFERS_TO','HM-8.7 근본 조치')])+photo('06-air','주변 온도 상승과 캐비닛 환기 보강을 추가한 상태')+check('원 15개·화살표 19개. 고장으로 들어오는 CAUSES가 3개이고, 근본 조치는 각각의 원인을 가리킵니다. 팬 점검 → HM-8.1의 Type에도 REFERS_TO를 입력합니다.')))
    parts.append(section(5,'고장의 연결과 절차 번호 적기','''<p>팬 베어링 열화는 냉각 성능 상실로 이어질 수 있습니다. <b>팬 베어링 열화</b>와 이를 가리키는 <b>진동 증가</b>를 추가하세요.</p>'''+table(['Caption','Label'], [('팬 베어링 열화','FailureMode'),('진동 증가','Symptom')])+table(['출발','Type','도착'], [('팬 베어링 열화','LEADS_TO','쿨러 냉각 성능 상실'),('진동 증가','INDICATES','팬 베어링 열화')])+photo('07-bearing','진동 증가 → 팬 베어링 열화 → 냉각 성능 상실')+'''<p>조치에서 매뉴얼로 향하는 화살표를 선택하고 <b>Property +</b>에 이름 <code>절차</code>와 아래 번호를 넣으세요. 같은 매뉴얼 절을 보더라도 실행할 절차는 다릅니다.</p>'''+table(['화살표 출발','도착','절차'], [('팬 최대 운전','HM-8.5','SOP-COOL-11'),('쿨러 핀 세척','HM-8.7','SOP-COOL-14'),('캐비닛 환기 보강','HM-8.7','SOP-COOL-15'),('팬 점검','HM-8.1','SOP-FAN-11')])+check('원 17개·화살표 21개. 매뉴얼로 이어지는 화살표 4개에 절차 번호가 표시됩니다.')))
    parts.append(section(6,'그림을 정리하고 경로 읽기','''<p>원의 가운데를 잡아 옮기고, 이름과 화살표가 겹치지 않게 정리하세요. 빈 곳을 누른 뒤 <b>STYLE → Customize → radius</b>를 <code>47</code>로 줄이면 공간을 확보할 수 있습니다. <b>Ctrl</b>을 누른 채 원들을 선택하고 <b>STYLE → node-color</b>에서 원인은 연한 빨강, 조치는 연한 초록으로 구분합니다.</p>'''+photo('08-layout','원인은 빨강, 조치는 초록으로 구분한 전체 구조')+'''<p>냉각 효율 <b>46.2 %</b>, 팬 진동 2분 평균 <b>0.575 mm/s</b>, 캐비닛 온도 <b>28 ℃</b>를 세 원인의 조건과 비교하세요. 핀 오염에서 조치와 매뉴얼까지 화살표를 따라 읽어 보세요.</p>'''+check('핀 오염의 두 조건에 해당합니다. 근본 조치는 핀 세척 → HM-8.7, 즉시 완화는 팬 최대 운전 → HM-8.5로 이어집니다. 팬 진동 값이 없으면 핀 오염 조건을 모두 확인한 것은 아닙니다.')))
    parts.append(section(7,'저장하고 다시 열기','''<p>위쪽 <b>Download / Export</b>에서 <b>JSON → Download</b>로 편집 데이터를, <b>PNG → Download</b>로 그림을 저장하세요. 파일 이름은 <code>쿨러_지식그래프.json</code>, <code>쿨러_지식그래프.png</code>로 알아보기 쉽게 정리합니다.</p>'''+photo('09-export','JSON 탭에서 다시 편집할 데이터를 다운로드')+'''<p>왼쪽 위 로고 메뉴에서 <b>New → Web Browser storage</b>로 새 그림을 연 뒤, <b>Import → Choose File</b>에서 저장한 JSON을 선택하고 <b>Import</b>를 누릅니다. 새 그림의 기본 빈 원이 남아 있으면 선택해 <b>Delete</b>로 지웁니다.</p>'''+photo('10-import','저장한 JSON을 새 그림에 불러온 상태')+check('다시 연 그림에 원 17개·화살표 21개, 원인 조건과 절차 번호 4개가 있습니다.')+'''<p class="save">학교 PC는 재부팅하면 수업 중 저장한 파일이 사라집니다. 본인 결과를 보관하려면 JSON과 PNG를 USB 또는 본인이 사용하는 클라우드에 복사하세요.</p><p>다음 실습에서는 이 관계를 스키마와 인스턴스 데이터로 정리합니다. 다음 실습의 제공 시작본을 사용하므로, 오늘 만든 파일이 없어도 시작할 수 있습니다.</p>'''))
    nav=''.join(f'<a href="#step{i}">{i:02} {t}</a>' for i,t in enumerate(['설비·센서','증상·고장','핀 오염·조치','원인 확장','고장·절차','정리·확인','저장'],1))
    return '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>쿨러 지식 그래프 만들기 · 실습 가이드</title><style>
:root{--ink:#213330;--muted:#5a6c67;--line:#dce5df;--green:#216953;--paper:#fff;--bg:#f4f6f2}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:30px}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.85 "Malgun Gothic","Segoe UI",sans-serif}a{color:var(--green);text-underline-offset:4px}a:focus-visible,button:focus-visible{outline:3px solid #d18424;outline-offset:4px}.shell{max-width:1380px;margin:auto;padding:56px 36px}header{padding:40px 48px;background:#e6eee6;border-radius:22px;margin-bottom:36px}.eyebrow{font-size:13px;font-weight:700;letter-spacing:2px;color:var(--green)}h1{font-size:40px;letter-spacing:-1.8px;line-height:1.3;margin:16px 0}header p{max-width:820px;margin:0;color:#40584f}.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:26px}.button{display:inline-block;padding:11px 22px;background:var(--green);color:white;text-decoration:none;border-radius:9px;font-weight:700}.button.secondary{background:white;color:var(--green)}.layout{display:grid;grid-template-columns:170px minmax(0,1fr);gap:32px}nav{position:sticky;top:30px;align-self:start}nav span{display:block;color:var(--muted);font-size:12px;letter-spacing:2px;margin:8px 0 16px}nav a{display:block;padding:10px 12px;margin-bottom:5px;text-decoration:none;font-size:14px;border-radius:7px}nav a:hover{background:#e6eee6}section{background:var(--paper);border:1px solid var(--line);border-radius:16px;padding:36px;margin-bottom:32px}.step-head{display:flex;gap:16px;align-items:center;border-bottom:1px solid var(--line);padding-bottom:24px;margin-bottom:24px}.number{font:600 27px/1 Georgia,serif;color:var(--green)}h2{font-size:25px;line-height:1.4;margin:0;letter-spacing:-.7px}p{margin:18px 0}b,strong{font-weight:700}code{font-family:Consolas,monospace;background:#edf3ee;padding:3px 6px;border-radius:4px;user-select:all;font-size:.95em}.table-wrap{overflow:auto;margin:24px 0}table{width:100%;border-collapse:collapse;font-size:14px;line-height:1.7}th{text-align:left;background:#f0f4ef;color:#445e52;font-weight:600;white-space:nowrap}td,th{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top}td{user-select:text}figure{margin:28px 0}img{display:block;width:100%;border:1px solid var(--line);border-radius:9px}figcaption{font-size:13px;color:var(--muted);margin-top:10px}.check{padding:18px 20px;background:#edf5ee;border-left:3px solid #45846a;border-radius:0 8px 8px 0;font-size:15px}.check strong{display:block;color:var(--green);margin-bottom:4px}.save{padding:18px 20px;background:#faf4e6;border-radius:8px;font-size:15px}footer{color:var(--muted);font-size:13px;text-align:center;padding:16px}.top{display:inline-block;margin-top:12px}@media(max-width:850px){.shell{padding:20px 14px}header{padding:28px 22px}h1{font-size:30px}.layout{display:block}nav{position:static;display:flex;flex-wrap:wrap;margin-bottom:20px;gap:4px}nav span{display:none}nav a{padding:6px 9px;font-size:12px;background:white}section{padding:24px 18px}h2{font-size:22px}.step-head{gap:12px}}@media print{body{background:white}.shell{padding:0}nav,.actions,.top{display:none}.layout{display:block}section{break-before:page;border:0;padding:0}figure,table,.check{break-inside:avoid}a{color:inherit}}
</style></head><body><div class="shell"><header><div class="eyebrow">OFFLINE 01 · ARROWS</div><h1>쿨러 지식 그래프 만들기</h1><p>설비와 센서에서 시작해 증상·고장·원인·조치를 연결합니다.<br>단계별 그림을 따라 만들고, 저장한 데이터를 다시 열어 확인합니다.</p><div class="actions"><a class="button" href="https://arrows.app" target="_blank" rel="noopener">ARROWS 열기 ↗</a><a class="button secondary" href="https://github.com/uengine-oss/hyd-iot-edu/blob/2df94d48/course/videos/통합반/통합반_01회차_08_실습_관계그림.mp4" target="_blank" rel="noopener">실습 영상 · 20분 20초 ↗</a><a class="button secondary" href="매뉴얼_발췌.md">매뉴얼 근거</a></div></header><div class="layout"><nav aria-label="실습 단계"><span>진행 순서</span>'''+nav+'</nav><main>'+''.join(parts)+'''<a class="top" href="#">맨 위로 ↑</a></main></div><footer>쿨러 지식 그래프 · 통합반 / 실전반 공통 실습</footer></div></body></html>'''

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--video',type=Path)
    parser.add_argument('--captures',type=Path,required=True)
    args=parser.parse_args()
    guide=render()
    guide=guide.replace('<style>','<style>.added{border-top:1px solid #dce5df;padding-top:18px;color:#216953;font-size:15px}.added b{display:inline-block;background:#e6eee6;padding:3px 10px;border-radius:5px;margin-right:8px}')
    guide=guide.replace('원을 작게', '원을 작게')
    guide=guide.replace('<code>70</code>','<code>78</code>')
    guide=guide.replace('원의 가운데를 잡아 옮기고, 이름과 화살표가 겹치지 않게 정리하세요. 빈 곳을 누른 뒤 <b>STYLE → Customize → radius</b>를 <code>47</code>로 줄이면 공간을 확보할 수 있습니다. <b>Ctrl</b>을 누른 채 원들을 선택하고 <b>STYLE → node-color</b>에서 원인은 연한 빨강, 조치는 연한 초록으로 구분합니다.', '기존 원의 위치를 유지하면서 위쪽에는 팬 구동 불량, 가운데에는 핀 오염, 아래쪽에는 주변 온도 상승 묶음을 놓습니다. 원인은 연한 빨강, 조치는 연한 초록으로 구분합니다. <b>Ctrl</b>을 누른 채 같은 종류의 원을 선택한 뒤 <b>STYLE → node-color</b>에서 색을 지정하세요.')
    source=ROOT/'산출물/통합반/실습/01회차/랩'/LAB
    images=source/'images';images.mkdir(exist_ok=True)
    if args.video:
        import imageio_ffmpeg
        for name,sec in SHOTS[-2:]:
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-ss',str(sec),'-i',str(args.video),'-frames:v','1','-q:v','2','-y',str(images/(name+'.jpg'))],check=True)
    for f in args.captures.glob('stage-*.png'):shutil.copyfile(f,images/f.name)
    manifest={'capture_method':'ARROWS実画面 canvas.toDataURL; ego task space 1; original fixed video preserved','frames':json.loads((args.captures/'stages-verified.json').read_text(encoding='utf-8')),'source_layout_sha256':hashlib.sha256((args.captures/'guide-final.json').read_bytes()).hexdigest(),'video_frames':[{'file':n+'.jpg','seconds':s} for n,s in SHOTS[-2:]]}
    (Path(__file__).parent/'학생가이드_사진근거.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    for course in ['통합반','실전반']:
        lab=ROOT/'산출물'/course/'실습/01회차/랩'/LAB
        if lab!=source:shutil.copytree(images,lab/'images',dirs_exist_ok=True)
        (lab/'가이드.html').write_text(guide,encoding='utf-8')
        path=lab.with_suffix('.zip')
        with zipfile.ZipFile(path) as old:
            prefix=next(n for n in old.namelist() if LAB+'/' in n).split(LAB+'/')[0]+LAB+'/'
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
            for f in sorted(lab.rglob('*')):
                if f.is_file():z.write(f,prefix+f.relative_to(lab).as_posix())
        with zipfile.ZipFile(path) as z:
            for f in lab.rglob('*'):
                if f.is_file():assert z.read(prefix+f.relative_to(lab).as_posix())==f.read_bytes()
    print('Wrote two guides, 10 frames each, and verified existing ZIP roots/bytes.')

if __name__=='__main__':main()
