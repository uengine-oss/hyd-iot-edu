"""8회차만 문서 마감한다. 기존 기록의 바이트는 접두 기록 뒤에 그대로 둔다."""
from helpers import *
import subprocess,collections
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,obj):write(p,json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def prepend(p,s):
 old=p.read_bytes() if p.exists() else b''
 if old.startswith(s.encode('utf8')):return
 p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(s.encode('utf8')+old)
# HTML 자료 목록에 참조 예제도 노출한다. PDF 내용·낭독 추정은 바꾸지 않는다.
for root,course in [(C,'통합반'),(D,'실전반')]:
 for lab in (root/f'산출물/실습/{course}_온라인').glob('08일차_실습*'):
  if not lab.is_dir():continue
  files=sorted(f for base in [lab/'코드',lab/'reference'] for f in base.rglob('*') if f.is_file())
  links=''.join('<li><a href="'+html.escape(f.relative_to(lab).as_posix(),quote=True)+'">'+html.escape(f.relative_to(lab).as_posix())+'</a></li>' for f in files)
  p=lab/'안내.html';write(p,re.sub(r'<ul>.*?</ul>','<ul>'+links+'</ul>',p.read_text('utf8'),count=1,flags=re.S))
  with zipfile.ZipFile(lab.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
   for f in sorted(lab.rglob('*')):
    if f.is_file():z.write(f,f.relative_to(lab).as_posix())
# 시작 기준은 다시 측정하지 않는다. 불변 원본에서 두 작업 폴더별 목록만 별도 기록한다.
before=json.loads((EV/'before.json').read_text('utf8'))
for root,kind in [(C,'integrated'),(D,'practical')]:
 target=root/'.evidence/session08';target.mkdir(parents=True,exist_ok=True)
 p=target/f'baseline-{kind}.json'
 if not p.exists():dump(p,{k:v for k,v in before.items() if Path(k).is_relative_to(root)})
 if root==C and not (target/'git-integrated.txt').exists():shutil.copy2(EV/'git-integrated.txt',target/'git-integrated.txt')
# 최종 PDF 텍스트를 원본 덱 PDF 전쪽과 비교한다.
pdf_result=[]
for course,day in [('통합반',8),('실전반',11)]:
 a=PdfReader(EV/f'source-render/통합반_{day:02}일차.pdf');b=PdfReader(EV/f'final-render/{course}_08일차.pdf');diff=[]
 for i,(x,y) in enumerate(zip(a.pages,b.pages),1):
  xx=re.sub(r'\s+','',x.extract_text());yy=re.sub(r'\s+','',y.extract_text())
  if xx!=yy:diff.append(i)
 assert diff==([] if course=='통합반' else [1])
 pdf_result.append(dict(course=course,pages=len(b.pages),source_text_differences=diff))
dump(EV/'visual-review.json',dict(deck_pages=125,document_pages=71,total_pdf_pages=196,reviewed_deck_contact_sheets=15,reviewed_document_contact_sheets=18,method='전쪽 렌더를 이미지로 시각 확인. 제목·본문·표·그림·여백·쪽나눔 확인; 내용 잘림·겹침 발견 없음.',source_text_comparison=pdf_result,actual_lab_execution=False))
print('HTML/ZIP links synchronized; baseline split; PDF source text and visual review recorded')
