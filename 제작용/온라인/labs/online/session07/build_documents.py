"""배포 문서와 입력자료 생성. 원본 학생 코드는 복사·정적 검사만 한다."""
from helpers import *
from labs import namesI,namesP,blank
from materials import materials,source_manifest
for root,folder,course,names,numbers in [(C,I,'통합반',namesI,[2,3,4,6,7]),(D,P,'실전반',namesP,[2,3,4,5])]:
 index=[f'# {course} 7회차 실습 자료\n\nZIP을 다운로드·압축 해제하고 VS Code에서 코드 폴더를 연다. 실제 실행·캡처는 미수행이다. 결과 기록은 수업에서 작성한다.\n']
 for idx,name in enumerate(names,1):
  lab=root/f'산출물/실습/{course}_온라인/07일차_실습{idx}_{name}';code=lab/'코드';code.mkdir(parents=True,exist_ok=True)
  text=(folder/f'{numbers[idx-1]:02}_실습_{name}.md').read_text('utf8');write(lab/'강사대본.md',text)
  write(code/'README.md',f'# {name}\n\n안내.html과 강사대본.md를 따른다. source는 제공 입력, input은 앞 단계 결과를 직접 넣을 자리, output은 수업에서 직접 만든 결과를 저장할 자리다. 빈 폴더나 기록 양식은 완료 결과가 아니다. 인증값을 자료에 넣지 않는다.\n')
  write(code/'input/README.md','대본에 지정한 앞 단계 결과를 복사하고 판본·ID·스키마를 확인한다.\n');write(code/'output/README.md','수업에서 직접 작성한 결과를 저장한다. 실행 결과는 제공하지 않는다.\n')
  write(code/'review.md',blank+'\n| 대상 | 원문·입력 근거 | 예상 | 실제 | 수정·재확인 | 미확인 |\n|---|---|---|---|---|---|\n| | | | | | |\n')
  materials(name,code)
  files=sorted(f for f in code.rglob('*') if f.is_file());links=''.join('<li><a href="'+html.escape(f.relative_to(lab).as_posix(),quote=True)+'">'+html.escape(f.relative_to(lab).as_posix())+'</a></li>' for f in files)
  css='body{font:17px/1.8 "Malgun Gothic",sans-serif;max-width:980px;margin:40px auto;padding:0 24px;color:#22303e}h1{font-size:28px}h2{margin-top:32px;font-size:23px}aside{background:#f0f4f7;padding:14px}p,aside{white-space:pre-wrap}'
  segments=[]
  for para in text.strip().split('\n\n'):
   tag='h1' if para.startswith('# ') else 'h2' if para.startswith('## ') else 'aside' if para.startswith('>') else 'p'
   segments.append('<'+tag+'>'+html.escape(re.sub(r'^(?:#{1,2} |> ?)', '',para))+'</'+tag+'>')
  write(lab/'안내.html','<!doctype html><html lang="ko"><meta charset="utf-8"><title>'+name+'</title><style>'+css+'</style><h2>작업 자료</h2><ul>'+links+'</ul>'+''.join(segments)+'</html>')
  reading=speech(text);write(folder/'낭독본'/f'{numbers[idx-1]:02}_실습_{name}.md',reading);pdf(reading,lab/'강사대본.pdf')
  with zipfile.ZipFile(lab.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
   for f in sorted(lab.rglob('*')):
    if f.is_file():z.write(f,f.relative_to(lab).as_posix())
  index.append(f'## 실습 {idx} — {name}\n\n[자료 ZIP]({lab.name}.zip) · [진행 안내]({lab.name}/안내.html) · [대본 PDF]({lab.name}/강사대본.pdf)\n')
 write(root/f'산출물/실습/{course}_온라인/07회차_실습_안내.md','\n'.join(index))
patch_notes();merge(C,I,False);merge(D,P,True)
for folder,course in [(I,'통합반'),(P,'실전반')]:
 pdf((folder.parent/'낭독본'/f'{course}_07일차_낭독본.md').read_text('utf8'),folder.parent/f'{course}_07일차_대본.pdf')
 alltext='\n\n'.join(speech(f.read_text('utf8')) for f in sorted(folder.glob('*_실습_*.md')));write(folder/'실습_낭독합본.md',alltext);pdf(alltext,folder/f'{course}_07일차_실습대본.pdf')
write(EV/'pdf-check.json',json.dumps(checks,ensure_ascii=False,indent=2));write(EV/'source-materials.json',json.dumps(source_manifest,ensure_ascii=False,indent=2))
print('documents complete',len(checks),'PDFs; no lab execution')
