from pathlib import Path
import re,json,hashlib
from openpyxl import load_workbook
D=Path(__file__).resolve().parents[4];C=Path('D:/work/study/hyd-integrated-recovered-20261018');E=D/'.evidence/session09';base=Path(__file__).parent
t=(base.parent/'session08/helpers.py').read_text('utf8').replace('session08','session09').replace('08회차','09회차').replace('08일차','09일차').replace('day08','day09').replace('count=61','count=74')
(base/'helpers.py').write_text(t,encoding='utf8')
rows=[]
for root,label in [(C,'integrated'),(D,'practical')]:
 p=root/'문서/교재/실라버스/피지컬AI_실라버스_최종본.xlsx';w=load_workbook(p,data_only=True)
 for s in w:
  if '온라인' not in s.title:continue
  for n,row in enumerate(s.values,1):
   vals=[str(x) if x is not None else '' for x in row]
   if ('통합' in s.title and 85<=n<=99) or ('실전' in s.title and 85<=n<=103):rows.append(dict(root=label,sheet=s.title,row=n,values=vals))
 print(label,hashlib.sha256(p.read_bytes()).hexdigest())
(E/'syllabus.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
p=C/'만들기/decks/integrated/day09/통합반_09일차.md'
t=re.sub(r'^- 노트:.*$','',p.read_text('utf8'),flags=re.M)
(E/'deck-review.txt').write_text(t,encoding='utf8')
print('prepared; no lab execution')
