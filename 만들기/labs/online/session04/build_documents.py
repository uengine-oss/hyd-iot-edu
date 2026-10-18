"""배포 문서와 입력자료 생성. 원본 학생 코드는 복사·정적 검사만 한다."""
from helpers import *
from labs import namesI,namesP,blank
raw=C/'산출물/실습/통합반_오프라인';docs=raw/'04회차_실습2_지식_추출/코드/문서';source_manifest=[]
def copy(src,dest):
 dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);source_manifest.append(dict(source=str(src),destination=str(dest),sha256=hashlib.sha256(src.read_bytes()).hexdigest()))
def copytree(src,dest):
 for f in src.rglob('*'):
  if f.is_file() and '__pycache__' not in f.parts:copy(f,dest/f.relative_to(src))
for root,folder,course,names,offset in [(C,I,'통합반',namesI,2),(D,P,'실전반',namesP,3)]:
 index=[f'# {course} 4회차 실습 자료\n\nZIP을 다운로드·압축 해제하고 VS Code에서 코드 폴더를 연다. 실제 실행·캡처는 미수행이다. 결과 기록은 수업에서 작성한다.\n']
 for idx,name in enumerate(names,1):
  lab=root/f'산출물/실습/{course}_온라인/04일차_실습{idx}_{name}';code=lab/'코드';code.mkdir(parents=True,exist_ok=True)
  text=(folder/f'{idx+offset:02}_실습_{name}.md').read_text('utf8');write(lab/'강사대본.md',text)
  write(code/'README.md',f'# {name}\n\n안내.html과 강사대본.md를 따른다. source는 제공 입력, input은 앞 단계 결과를 직접 넣을 자리, output은 수업에서 직접 만든 결과를 저장할 자리다. 빈 폴더나 기록 양식은 완료 결과가 아니다. 인증값을 자료에 넣지 않는다.\n')
  write(code/'input/README.md','대본에 지정한 앞 단계 결과를 복사하고 판본·ID·스키마를 확인한다.\n');write(code/'output/README.md','수업에서 직접 작성한 결과를 저장한다. 실행 결과는 제공하지 않는다.\n')
  write(code/'review.md',blank+'\n| 대상 | 원문·입력 근거 | 예상 | 실제 | 수정·재확인 | 미확인 |\n|---|---|---|---|---|---|\n| | | | | | |\n')
  if course=='통합반':
   copytree(docs,code/'source');copy(docs/'문서_목록.csv',code/'source/documents.csv')
   if name=='문서지식추출':write(code/'prompt.md','# 추출 지시문 작성\n\n## 대상과 출력 형식\n\n## 원문 보존·금지 사항\n\n## 기존 ID와 매핑\n\n## 인용과 경고\n')
   if name=='그래프반영과검증':write(code/'mapping.md',blank+'\n| 후보 ID | 기존 ID | 관계·방향 | 근거 | 미해결 |\n|---|---|---|---|---|\n| | | | | |\n')
  if name=='업무에이전트구성':write(code/'design.md','# 에이전트 설정 기록\n\n## 목표와 역할\n\n## 지침과 멈춤 조건\n\n## 서버와 허용 도구\n\n## 기본 제공 항목과 변경점\n')
  if name=='원인추론과점검계획':
   src=raw/'05회차_실습2_원인_추론_에이전트/코드'
   copytree(src/'ontology',code/'source/ontology');copytree(src/'cases',code/'source/cases');copytree(docs,code/'source/manuals')
   write(code/'expected.md',blank+'\n| 사례 | 후보 ID | 필요한 증거 | 예상 상태 | 추가 점검 | 실제 결과 |\n|---|---|---|---|---|---|\n| | | | | | |\n')
  if name=='회의록스킬작성':copytree(raw/'06회차_실습3_회의록_스킬/코드/회의록',code/'source')
  if name=='MCP도구연결':
   src=raw/'06회차_실습2_MCP_서버_연결/코드'
   for sub in ['서버','도구','구매팀_자료']:copytree(src/sub,code/sub)
   write(code/'config-notes.md','# 연결 설정 기록\n\n## HYD: 등록 서버·도구·검사·호출 기록\n\n## 로컬: Python·Git·VS Code 지원 상태\n\n| 서버 | 실행 파일·인자 | 대상·권한 | 도구 목록 | 오류·수정 |\n|---|---|---|---|---|\n| filesystem | | | | |\n| git | | | | |\n| time | | | | |\n')
   write(code/'설정_작성.md','''# 수업에서 작성할 VS Code 설정

코드 폴더를 작업 공간으로 열고 `.vscode/mcp.json`을 직접 만든다. 다음은 경로를 채워야 하는 형식 예시이며 실행한 설정이 아니다. 실제 Python과 자료 폴더 절대경로를 사용한다. Windows JSON 경로는 `/` 또는 이스케이프한 역슬래시로 적는다.

```json
{
  "servers": {
    "filesystem": {"type": "stdio", "command": "PYTHON_ABSOLUTE_PATH", "args": ["CODE_ABSOLUTE_PATH/서버/파일시스템_서버.py", "--read-only", "CODE_ABSOLUTE_PATH/업무자료"]},
    "git": {"type": "stdio", "command": "PYTHON_ABSOLUTE_PATH", "args": ["CODE_ABSOLUTE_PATH/서버/깃_서버.py", "--repository", "CODE_ABSOLUTE_PATH/업무자료"]},
    "time": {"type": "stdio", "command": "PYTHON_ABSOLUTE_PATH", "args": ["CODE_ABSOLUTE_PATH/서버/시간_서버.py"]}
  }
}
```

업무자료는 수업에서 `python 도구/자료_준비.py` 기본 실행으로 준비한다. 기존 업무자료는 보존하며 `--다시`는 사용하지 않는다. 제공 도구/연결_점검.py는 참고 코드이며 이번 제작에서는 실행하지 않았다. 도우미의 목록과 호출 기록으로 연결을 확인한다. `구매팀_자료`는 허용 범위 밖 접근 확인에 쓰는 연습 자료다.

참조: [VS Code MCP 서버 설정](https://code.visualstudio.com/docs/agent-customization/mcp-servers). HYD의 mcpServers와 이 파일의 servers는 서로 다른 호스트 설정이다.
''')
  files=sorted(f for f in code.rglob('*') if f.is_file());links=''.join('<li><a href="'+html.escape(f.relative_to(lab).as_posix(),quote=True)+'">'+html.escape(f.relative_to(lab).as_posix())+'</a></li>' for f in files)
  css='body{font:17px/1.8 "Malgun Gothic",sans-serif;max-width:980px;margin:40px auto;padding:0 24px;color:#22303e}h1{font-size:28px}h2{margin-top:32px;font-size:23px}aside{background:#f0f4f7;padding:14px}p,aside{white-space:pre-wrap}'
  segments=[]
  for para in text.strip().split('\n\n'):
   tag='h1' if para.startswith('# ') else 'h2' if para.startswith('## ') else 'aside' if para.startswith('>') else 'p'
   segments.append('<'+tag+'>'+html.escape(re.sub(r'^(?:#{1,2} |> ?)', '',para))+'</'+tag+'>')
  write(lab/'안내.html','<!doctype html><html lang="ko"><meta charset="utf-8"><title>'+name+'</title><style>'+css+'</style><h2>작업 자료</h2><ul>'+links+'</ul>'+''.join(segments)+'</html>')
  reading=speech(text);write(folder/'낭독본'/f'{idx+offset:02}_실습_{name}.md',reading);pdf(reading,lab/'강사대본.pdf')
  with zipfile.ZipFile(lab.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
   for f in sorted(lab.rglob('*')):
    if f.is_file():z.write(f,f.relative_to(lab).as_posix())
  index.append(f'## 실습 {idx} — {name}\n\n[자료 ZIP]({lab.name}.zip) · [진행 안내]({lab.name}/안내.html) · [대본 PDF]({lab.name}/강사대본.pdf)\n')
 write(root/f'산출물/실습/{course}_온라인/04회차_실습_안내.md','\n'.join(index))
patch_notes();merge(C,I,False);merge(D,P,True)
for folder,course in [(I,'통합반'),(P,'실전반')]:
 pdf((folder.parent/'낭독본'/f'{course}_04일차_낭독본.md').read_text('utf8'),folder.parent/f'{course}_04일차_대본.pdf')
 alltext='\n\n'.join(speech(f.read_text('utf8')) for f in sorted(folder.glob('*_실습_*.md')));write(folder/'실습_낭독합본.md',alltext);pdf(alltext,folder/f'{course}_04일차_실습대본.pdf')
write(EV/'pdf-check.json',json.dumps(checks,ensure_ascii=False,indent=2));write(EV/'source-materials.json',json.dumps(source_manifest,ensure_ascii=False,indent=2))
print('documents complete',len(checks),'PDFs; no lab execution')
