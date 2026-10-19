"""기존 편집 가능한 OOXML 전체를 보존하고 표지 과정명과 노트만 교체."""
from helpers import *
def build_practical():
 src=EV/'before/산출물/교재/PPTX/통합반_온라인/통합반_11일차.pptx'
 dst=D/'산출물/교재/PPTX/실전반_온라인/실전반_08일차.pptx';dst.parent.mkdir(parents=True,exist_ok=True)
 old='온톨로지 · 에이전트 · 프로세스를 내 주제에 적용하고 마무리하기';new='실전반 8회차 · 내 주제에 적용하고 지식 자산으로 마무리하기'
 with zipfile.ZipFile(src) as z,zipfile.ZipFile(dst,'w') as out:
  count=0
  for entry in z.infolist():
   data=z.read(entry)
   if entry.filename=='ppt/slides/slide1.xml':
    root=E.fromstring(data)
    for node in root.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'):
     if node.text and old in node.text:node.text=node.text.replace(old,new);count+=1
    assert count==1,('cover match',count)
    data=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
   out.writestr(entry,data)
 patch_notes(P,64,D/'만들기/decks/practical/day08/실전반_08일차.md',dst)
