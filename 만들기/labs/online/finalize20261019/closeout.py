"""Document closeout. Leaves historical evidence and user edits intact."""
from helpers import *
import subprocess
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
audit=json.loads((EV/'whole-audit.json').read_text('utf8'));assert not audit['issues']
static=json.loads((EV/'whole-doc-static.json').read_text('utf8'));assert not static['issues']
title='2026-10-19_온라인_두과정_최종마감.md';index='온라인_최종산출물_목록.md'
summary='''## 2026-10-19 온라인 두 과정 문서 마감 완료 — 최신 상태

통합반1~11회차와 실전반1~8회차의 온라인 문서 작업을 함께 마감했다. 통합반10~11 랩이 비어 있던 상태를 해소했고, 통합반9↔실전반6 및 통합반10~11↔실전반7~8의 대응을 보완했다. 전체19회차·1,477장·84랩의 덱/노트/대본, 합본·낭독본, 배포ZIP·로컬 링크를 감사했다. 아래 과거 기록의 미착수·남은 제작·다음 회차 표시는 당시 상태다.

최신 통합반은 `D:/work/study/hyd-integrated-recovered-20261018`, 실전반은 `D:/work/study/hyd-portal-latest-20261014`다. 두 루트를 분리 유지한다. 옛 C 경로는 역사적 근거 대조 시에만 통합반 D 경로로 매핑한다. 다른 루트 안의 옛 과정은 최신 원본이 아니다.

실제 실습·학생 코드/테스트·AI·HYD/DB·브라우저 실습·캡처·녹음은 수행하지 않았다. 문서 제작·정적 검사·PDF 렌더 범위의 마감이다. 실환경 리허설과 촬영은 완료로 표시하지 않는다. 이번 요청에서 커밋·푸시하지 않았다. 오프라인 제작·포털·시스템의 별도 남은 일은 이 문서 마감으로 종료되지 않는다.

[전체 상세 결과](근거/2026-10-19_온라인_두과정_최종마감.md) · [최종 산출물 목록](온라인_최종산출물_목록.md)

재개 시 이 최신 인계→Git 상태→해당 회차 구성표·분할 원본→불변 시작 근거→새 검증 결과 순서로 읽는다. 결과물 중심의 문서 기록을 정본으로 삼고 대화 요약은 보조로 쓴다. 1_목적과_방향.md·2_기준.md 및 사용자의 최신 기준을 유지한다. 회차 하나의 마감을 전체 종료로 혼동하지 않는다.

---

'''
manifest=json.loads((EV/'whole-artifacts.json').read_text('utf8'))
for root,course,total in [(C,'통합반',11),(D,'실전반',8)]:
 for name in ['인계_통합반_회차별_점검.md','3_현황.md','6_남은_일.md']:
  p=root/'문서/교재'/name;write(p,summary+p.read_text('utf8'))
 for day in range(1,total+1):
  p=root/f'산출물/교재/대본/{course}_온라인/{day:02}회차/제작기록.md'
  old=p.read_text('utf8') if p.exists() else ''
  if p.exists():
   dst=EV/'audit-meta-before'/('integrated' if root==C else 'practical')/p.relative_to(root);dst.parent.mkdir(parents=True,exist_ok=True);assert not dst.exists();shutil.copy2(p,dst)
  text=f'## 2026-10-19 전체 온라인 문서 마감 감사\n\n현재 {course}{day}회차의 구성·노트·합본/낭독본·덱 PDF 원문·배포 ZIP 바이트 및 안내 링크 검사를 통과했다. 이번 전체 감사에서 이 회차의 이론 발화를 추가 수정하지 않았다. 실전반1의 누락 노트 보완 및 통합반 PDF 배포 위치 동기화는 전체 보고서에 별도 기록했다. 실제 실습을 실행했다는 뜻이 아니다. 최신 원본 루트는 `{root.as_posix()}`이며 아래 이전 C 경로는 역사적 기록이다. [전체 상세 결과]({(root/"문서/교재/근거"/title).as_posix()}).\n\n---\n\n'
  write(p,text+old);manifest[str(p)]=sha(p)
# Manifest records the current delivery state, not historical snapshot files.
manifest={p:sha(Path(p)) for p in manifest};write(EV/'whole-artifacts.json',json.dumps(manifest,ensure_ascii=False,indent=2))
pres=[]
for root,kind in [(C,'integrated'),(D,'practical')]:
 before=json.loads((EV/f'before-{kind}.json').read_text('utf8'));changed=[];missing=[];historical=[];unexpected=[]
 for name,h in before.items():
  p=Path(name)
  if not p.exists():missing.append(name)
  elif sha(p)!=h:
   rel=p.relative_to(root).as_posix();changed.append(rel)
   if '.evidence' in p.parts:historical.append(name)
   if not rel.startswith(('산출물/교재/','산출물/실습/','만들기/decks/','만들기/labs/','문서/교재/')):unexpected.append(rel)
 start=json.loads((EV/f'git-start-{kind}.json').read_text('utf8'));head=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip();branch=subprocess.check_output(['git','-C',str(root),'branch','--show-current'],text=True).strip();status=subprocess.check_output(['git','-C',str(root),'-c','core.quotepath=false','status','--porcelain=v1','--untracked-files=all'],text=True,encoding='utf8')
 assert not missing and not historical and not unexpected and head==start['head'] and branch==start['branch']
 unrelated={name:h for name,h in before.items() if Path(name).relative_to(root).as_posix().startswith(('portal/','it/','문서/시스템/')) or Path(name).name=='CLAUDE.md'}
 assert all(sha(Path(p))==h for p,h in unrelated.items())
 item=dict(root=str(root),before_files=len(before),unchanged=len(before)-len(changed),changed=changed,missing=missing,historical_changed=historical,unexpected_changes=unexpected,protected_files_unchanged=len(unrelated),head=head,branch=branch,commit_or_push=False)
 write(EV/f'preservation-{kind}.json',json.dumps(item,ensure_ascii=False,indent=2));write(EV/f'git-final-{kind}.json',json.dumps(dict(root=str(root),head=head,branch=branch,status=status),ensure_ascii=False,indent=2));pres.append(item)
rows=audit['sessions'];zcount=sum(r['zip_files'] for r in rows);lcount=sum(r['html_links'] for r in rows)
report=f'''# 통합반·실전반 온라인 문서 최종 마감 — 2026-10-19

통합반1~11회차와 실전반1~8회차의 온라인 교재 문서 작업을 마무리했다. 회차별 완료를 전체 완료로 취급하던 중단을 바로잡고, 남아 있던 원본 대응·빈 랩·파생물 동기화와 두 과정 전체 감사를 끝냈다.

| 범위 | 회차 | 덱 장수 | 랩 |
|---|---:|---:|---:|
'''
for course in ['통합반','실전반']:
 r=[x for x in rows if x['course']==course];report+=f"| {course} 온라인 | {len(r)} | {sum(x['slides'] for x in r)} | {sum(x['labs'] for x in r)} |\n"
report+=f'''
전체19회차·1,477장·84랩이며 이번 최종 보완 전후 덱 장수는 동일하다. 현재 배포 산출물 {len(manifest)}개를 SHA-256 목록으로 남겼다(덱 작성 자료·도형, PPTX/PDF, 대본·구성·제작 기록, 랩 안내·입력자료·ZIP 포함; 역사적 근거와 옛 미배정 랩은 제외). 목록에 포함된 PDF143개2,608쪽은 같은 내용을 배포 위치별로 복사한 PDF도 각각 센 수다. 화면·본문의 새 의미 수정 범위는 아래 회차별 보고서에 제한했다.

## 이번 재개에서 끝낸 수정

- [통합반9↔실전반6 및 학습코치 정합성 보완](2026-10-19_6회차_정합성보완.md): 실전반6 이론2발화·랩4개, 통합반6 랩1개. 강제 실패·의도적 오답을 없애고 실제 조건·근거·수정·재확인으로 연결했다. 실전반6 낭독 추정96.536000→96.699636분. PDF9개126쪽 확인.
- [통합반10·실전반7](2026-10-19_통합반10_실전반7_마감.md): 이론7/6발화, 통합반 랩4개 신규·실전반 랩4개 보완. 낭독 추정87.225455→87.485818분 / 87.392727→87.450909분. PDF14개196쪽 확인.
- [통합반11·실전반8](2026-10-19_통합반11_실전반8_마감.md): 이론6/1발화, 통합반 랩6개 신규·실전반 랩3개 보완. 낭독 추정94.743273→94.757818분 / 94.757818→94.757818분. PDF18개206쪽 확인.
- 전체 감사 보완: 실전반1의11·43·45·71장 누락 발표자 노트를 현재 대본에 연결했다. 화면과 발화는 변경0개, 장수78→78, 낭독 추정 변화0이다. 양쪽1회차 덱 PDF2개156쪽을 새 배포 위치에 생성해 전쪽 배치를 확인했다. 통합반78쪽과 실전반 표지를 직접 보고, 나머지77쪽은 렌더 픽셀 동일을 확인했다. 양쪽2회차는 기존 검증된 덱 PDF를 현재 PDF 배포 위치에 그대로 추가했다.
- 통합반의 별도 `대본/통합반_온라인/PDF/`에 남아 있던2~11회차 옛 대본 PDF10개는 이전 바이트를 `.evidence/finalize20261019/audit-before/`에 보관한 뒤 현재 검증본과 동기화했다. 새로 내용을 작성한 것이 아니며 새 원문 대조를 통과했다. 옛 배포 폴더를 삭제하지 않았다.

이번 재개의 의미 수정 이론은 총22발화, 랩은 신규10개·기존12개 보완이다. PDF 새 생성·재생성 검토는43개684쪽(6회차126+10/7회차196+11/8회차206+1회차156)이다. 복사만 한2회차 덱2개와 옛 위치 대본10개는 이43개에 더하지 않았다. 이전8·9회차 결과는 각 당시 상세 보고서에 있으며 이번 재개 수치와 중복 합산하지 않았다.

낭독 추정은 한글1·숫자1.6·영문0.6 가중음절/275, 괄호 속 한국어 발음 치환 등 같은 산식이다. 학습 대기·조작·AI 응답 시간은 별도이며 실측 또는 전체 수업 시간으로 해석하지 않는다. 장수·시간에 맞추기 위한 축약·늘리기는 하지 않았다.

## 원본 대응과 보존

실전반 원배정은1←통합반1, 2←통합반2 및3의 절차·판단, 3←통합반3의 성과평가 및4, 4←통합반5·6, 5←통합반7·8, 6←통합반9, 7←통합반10, 8←통합반11이다. 최신 실라버스·구성표와 저장된 원본대응을 대조했다. 현재 덱의 원본과 실전반 텍스트 차이도 전부 추출해 검토했다. 본론을 실전 압축이라는 이유로 생략하지 않았고 복습·용어·퀴즈·정답을 보존했다. 합친 회차의 표지·목차·학습목표·퀴즈 번호, 실제 배정된 실습 소개와 연결 발화는 조정했다. 통합반7의 다른 AI 검토와 통합반8의 인수인계 같은 미배정 실습, 겹치는 메타 안내의 처리 이유는 기존 원본대응에 보존했다. 회차가 다르다는 이유만으로 중복 처리하지 않았다.

전체19회차의 슬라이드 범위·순서·노트1,477장과 분할→합본→낭독본 일치, 덱PDF 전쪽 화면 텍스트를 새로 검사했다. 이론 낭독PDF19개도 현재 낭독 원문과 대조했다. ZIP84개 내부 {zcount}파일의 목록·바이트가 배포 폴더와 일치하며 안내 HTML 로컬 참조 {lcount}개를 검사했다. 학생 자료 Python41개는 AST 구문만, JSON168개·XML/BPMN/SVG27개는 정적 구문을 검사했다. 수정 회차의 매핑·식별자·참조·복사 해시는 상세 근거에서 별도 확인했다. 초기 회차의 `가이드.html`·`다운로드/` 구조를 유지했고 옛 미배정 랩2개는 삭제하지 않았다.

앞 회차의 의미·배치 검토는 당시 검증 기록과 이번 시작 해시를 함께 사용했다. 이번에 수정하지 않은 모든 앞 회차를 새로 전쪽 시각 검토했다고 주장하지 않는다. 이번 변경 PDF는 위43개684쪽을 확인했고, 그대로 복사한 PDF는 검증본과 바이트 일치로 확인했다. 역사적 `.evidence`나 `before.json`은 재생성하거나 경로 치환하지 않았다.

'''
for item in pres:report+=f"- `{item['root']}`: 시작 {item['before_files']}파일 중 {item['unchanged']}파일 바이트 동일, 요청 범위의 기존파일 {len(item['changed'])}개 변경. 삭제0·역사적 근거 변경0·범위 밖 변경0. CLAUDE·포털/IT·시스템 문서 보호대상 {item['protected_files_unchanged']}파일 동일. 브랜치 `{item['branch']}`, HEAD `{item['head']}` 유지.\n"
report+=f'''
변경 대상의 기존 미커밋 작업을 초기화하지 않고 현재 원본 위에서 보완했다. 별도 CLAUDE.md·포털·시스템 미커밋 수정은 그대로다. 두 작업 폴더를 합치거나 덮어쓰지 않았다. 추가 커밋·푸시는 없다.

## 산출물과 재개 기준

[전체 산출물 목록](../{index})에서 각 회차의 PPTX·덱 PDF·구성표·대본·랩 ZIP 안내로 바로 이동한다. 전체 현재 해시 목록은 [whole-artifacts.json]({(EV/'whole-artifacts.json').as_posix()}), 검사 결과는 [whole-audit.json]({(EV/'whole-audit.json').as_posix()}), 원본대응 비교는 [source-audit.json]({(EV/'source-audit.json').as_posix()})이다. `preservation-integrated.json`·`preservation-practical.json`에 시작 대비 변경·보존 목록, `git-final-*.json`에 최종 Git 상태가 있다.

문서 검사는 실전반 루트에서 `python 만들기/labs/online/finalize20261019/audit.py D:/work/study/hyd-integrated-recovered-20261018`로 수행한다. `start.py`, `repair06.py`, `finish10.py`, `sequence10.py`, `finish11.py`, `repair_audit.py`, `record11.py`, `closeout.py`는 이미 실행한 일회성 기록이므로 그대로 재실행하지 않는다. 이후 변경은 분할 원본을 고치고 해당 파생물·새 검증 기록을 갱신한다. 기존 시작 스냅샷과 역사적 근거는 불변이다.

실제 실습·학생 코드 및 테스트 실행·AI 시연·HYD/DB 접속·브라우저 실습·캡처·녹음은 하지 않았다. 실제 연결·권한·배포·수업 리허설·촬영은 이번 문서 마감 범위 밖의 미실행 항목이다. 제공 예제와 강사가 수업에서 만들 결과는 구별한다. 실라버스의 과거 실패 재현 준비 문구보다 최신 ‘억지 실패 재현 금지’ 기준을 우선한다. 오프라인 과정·포털/시스템의 별도 업무는 완료로 처리하지 않았다.
'''
links='# 온라인 최종 산출물 목록 — 2026-10-19\n\n통합반과 실전반의 최신 원본 루트를 분리해 연결한다. 각 랩 안내에서 개별 HTML과 ZIP을 연다. 실제 실습 검증 완료를 뜻하지 않는다.\n\n| 과정·회차 | 장수/랩 | 덱 | 대본·구성 | 랩 |\n|---|---:|---|---|---|\n'
for r in rows:
 root=C if r['course']=='통합반' else D;course=r['course'];day=r['day'];base=root.as_posix()
 links+=f'| {course}{day} | {r["slides"]}/{r["labs"]} | [PPTX]({base}/산출물/교재/PPTX/{course}_온라인/{course}_{day:02}일차.pptx) · [PDF]({base}/산출물/교재/PDF/{course}_온라인/{course}_{day:02}일차.pdf) | [구성표]({base}/산출물/교재/대본/{course}_온라인/{day:02}회차/구성표.md) · [합본]({base}/산출물/교재/대본/{course}_온라인/{course}_{day:02}일차_대본.md) | [자료·ZIP]({base}/산출물/실습/{course}_온라인/{day:02}회차_실습_안내.md) |\n'
for root in [C,D]:write(root/'문서/교재/근거'/title,report);write(root/'문서/교재'/index,links)
write(EV/'progress.md',(EV/'progress.md').read_text('utf8')+'\n\n## 두 과정 온라인 문서 마감 완료\n통합반1~11·실전반1~8,19회차1477장84랩 감사 통과. 전체 보고서·산출물 목록·양쪽 최신 인계/현황/남은 일·19회차 제작 기록 갱신. 문서만 검증, 실제 실행 없음. 기존 evidence/CLAUDE/포털/시스템 보존, HEAD 동일, 커밋·푸시 없음.\n')
print(json.dumps(dict(artifacts=len(manifest),zip_files=zcount,links=lcount,preservation=[dict(root=x['root'],before=x['before_files'],unchanged=x['unchanged'],changed=len(x['changed'])) for x in pres]),ensure_ascii=False))
