"""검토한 공통 43·45·47장만 반영한다. 실습 실행 없이 ZIP XML을 수정한다.
먼저 조립.py --source-root 로 최신 공통 원본과 실전반 대본을 조립한다.
그 뒤 refresh_notes.py, add_fixed_references.py, package_labs.py를 실행한다.
"""
from pathlib import Path
import re,io,zipfile,json
from lxml import etree as E
R=Path(__file__).resolve().parents[4]
p=R/'산출물/교재/PPTX/실전반_온라인/실전반_01일차.pptx'
replacements={43:[('파일 편집과 터미널 작업을 하는 도구이다','파일을 열고 편집하며'),('파일 편집과 실행을 한곳에서 진행한다','터미널에서 명령을 실행한다'),('HYD 서비스와 랩 코드를 작성하는 프로그래밍 언어이다','HYD의 자체 서비스와 일부 랩에 쓰는 언어이다')],45:[('쿨러 사건의 처리 기록','교재 예시의 처리 기록')],47:[('경보는 조건을 벗어났다는 사실만 알리므로, 조치를 정하려면','교재에 보관한 사건 기록이다. 경보 뒤'),('을 먼저 가려야 한다.','을 가려 조치를 정하고, 조치 뒤 변화를 확인한다.')]}
out=io.BytesIO();changed=[]
with zipfile.ZipFile(p) as z,zipfile.ZipFile(out,'w') as target:
    for info in z.infolist():
        data=z.read(info.filename);m=re.fullmatch(r'ppt/slides/slide(\d+)\.xml',info.filename)
        if m and int(m[1]) in replacements:
            tree=E.fromstring(data);ts=tree.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}t')
            for old,new in replacements[int(m[1])]:
                hits=[t for t in ts if old in (t.text or '')]
                if hits:
                    assert len(hits)==1;hits[0].text=hits[0].text.replace(old,new)
                else:assert any(new in (t.text or '') for t in ts),(m[1],old)
            data=E.tostring(tree,xml_declaration=True,encoding='UTF-8',standalone=True)
            if data!=z.read(info.filename):changed.append(int(m[1]))
        target.writestr(info,data)
with zipfile.ZipFile(io.BytesIO(out.getvalue())) as z:assert z.testzip() is None
p.write_bytes(out.getvalue())
print(json.dumps({'changed_screen_slides':changed,'other_parts_preserved':True}))
