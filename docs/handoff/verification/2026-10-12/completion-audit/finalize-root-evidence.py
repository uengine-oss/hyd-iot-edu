"""Freeze this source scope and render preserved references beside actual screenshots."""
import hashlib,json,subprocess,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
T=Path('D:/work/study/hyd-iot-edu/.claude/worktrees/codex-portal-20261011')
H=Path(__file__).parent
V=T/'docs/handoff/verification/2026-10-12/completion-audit'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def names(*args):return subprocess.check_output(['git','-C',str(T),*args],encoding='utf-8').splitlines()
def source(p):return p.startswith(('common/','it/','scripts/','tests/','students/','docs/samples/','docs/ontology/')) or ('/' not in p and p.endswith(('.py','.toml','.yml','.yaml','.json','.txt')) and not p.startswith('.env'))
def actual():return {p:sha(T/p) for p in sorted(set(names('ls-files')+names('ls-files','--others','--exclude-standard'))) if source(p) and (T/p).is_file()}
def freeze():
    current=actual()
    previous=json.loads((H.parent/'k3-preparation-20261012/F27-final-source-manifest.json').read_text(encoding='utf-8'))['source_sha256']
    delta=sorted(p for p in set(previous)|set(current) if previous.get(p)!=current.get(p))
    assert delta==['it/portal/www/hitl.js','it/portal/www/index.html','tests/test_portal_manual_document_selection_ui.py'],delta
    owned=set(names('diff','HEAD','--name-only')+names('ls-files','--others','--exclude-standard'))
    protected=[p for p in owned if p.startswith(('docs/교재/','.claude/skills/lecture-deck/'))]
    assert not protected,protected
    save(H/'source-manifest.json',{'scope':'Source freeze for document selector changes; previous whole-suite evidence remains historical','source_files':len(current),'source_sha256':current,'changed_since_F27':delta,'protected_changes':protected,'whole_reruns':0,'llm_reruns':0})
    (V/'source-manifest.json').write_bytes((H/'source-manifest.json').read_bytes())
    print(json.dumps({'source_files':len(current),'changed_since_F27':delta,'protected_changes':protected}))
def verify():
    expected=json.loads((H/'source-manifest.json').read_text(encoding='utf-8'))['source_sha256']
    current=actual()
    delta=sorted(p for p in set(expected)|set(current) if expected.get(p)!=current.get(p))
    result={'passed':not delta,'source_files':len(current),'changed_after_freeze':delta,'whole_reruns':0,'llm_reruns':0}
    save(H/'source-verification.json',result)
    (V/'source-verification.json').write_bytes((H/'source-verification.json').read_bytes())
    print(json.dumps(result));assert not delta,delta
def compare():
    html='''<!doctype html><html lang="ko"><meta charset="utf-8"><title>참고 화면과 실제 HYD 화면</title><style>*{box-sizing:border-box}body{margin:0;padding:24px;background:#f5f6f8;color:#222;font:15px/1.5 "Malgun Gothic",sans-serif}h1{font-size:24px}h2{font-size:18px}section{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:24px 0}article{min-width:0;background:white;padding:16px;border:1px solid #ddd;border-radius:8px}img{width:100%;display:block}p{margin:8px 0}</style>
<h1>참고 화면과 실제 HYD 화면</h1><p>왼쪽은 보존한 참고 화면, 오른쪽은 실제 포털 캡처입니다. 기능의 종류와 자료는 서로 다르며, 카드·폼·상태·근거의 배치를 비교합니다.</p>
<section><article><h2>ProcessGPT Vue 원본 폼 구성요소</h2><p>867e8cf 소스의 PgCard·PgField·PgTextField·PgAlert 등을 직접 컴파일한 참고 화면입니다. 입력값은 비교용이며 전체 앱 실행 화면은 아닙니다.</p><img src="../final-delegated/reference-vue-components-1440.png" alt="ProcessGPT 원본 컴파일 폼"></article><article><h2>HYD 실제 문서 등록 · 이름 선택</h2><p>실제1440px. 현재 문서 이름으로 선택하며 정확한 문서 지정은 보존합니다. <a href="manual-selection/native-final/form-review-document-locked-1024.png">검토 중 대상 잠금1024px</a></p><img src="manual-selection/native-final/form-named-document-1440.png" alt="HYD 실제 문서 선택 폼"></article></section>
<section><article><h2>Dify 공식 실행 기록 참고</h2><p>기존 조사에서 보존한 공식 문서 화면입니다. 출처와 SHA는 <a href="../final-delegated/reference-provenance.json">원본 기록</a>에 있습니다.</p><img src="../final-delegated/reference-dify.png" alt="Dify 공식 실행 기록"></article><article><h2>HYD 실제 처리 기록 · 도구 원문과 결과</h2><p>F27 검증 때 보존한 실제 C 처리 기록1440px입니다. 현재 문서 선택 변경의 새 업무 실행으로 표시하지 않습니다. <a href="../k3-and-record-followup/README.md">검증 범위</a></p><img src="../k3-and-record-followup/F27-native-final-C-record-tool-1440.png" alt="HYD 실제 처리 기록"></article></section><p><a href="README.md">실제 요구별 판정과 남은 조건</a></p></html>'''
    pagefile=V/'reference-comparison.html';pagefile.write_text(html,encoding='utf-8')
    proof={'images':[],'pageerrors':[],'consoleErrors':[],'external_requests':[],'method':'Offline side-by-side of preserved exact screenshots; no live portal or service calls'}
    with sync_playwright() as p:
        browser=p.chromium.launch()
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.on('pageerror',lambda e:proof['pageerrors'].append(str(e)))
        page.on('console',lambda m:proof['consoleErrors'].append(m.text) if m.type=='error' else None)
        def guard(route):
            if route.request.url.startswith(('http://','https://')):proof['external_requests'].append(route.request.url);route.abort()
            else:route.continue_()
        page.route('**/*',guard)
        page.goto(pagefile.as_uri(),wait_until='load')
        for item in page.locator('img').evaluate_all('(xs)=>xs.map(x=>({src:x.getAttribute("src"),ok:x.complete&&x.naturalWidth>0}))'):
            imagepath=(pagefile.parent/item['src']).resolve();proof['images'].append({**item,'sha256':sha(imagepath)})
        page.screenshot(path=str(V/'reference-comparison.png'),full_page=True)
        browser.close()
    proof['passed']=all(x['ok'] for x in proof['images']) and len(proof['images'])==4 and not proof['pageerrors'] and not proof['consoleErrors'] and not proof['external_requests']
    proof['html_sha256']=sha(pagefile);proof['screenshot_sha256']=sha(V/'reference-comparison.png')
    save(H/'reference-comparison-result.json',proof);(V/'reference-comparison-result.json').write_bytes((H/'reference-comparison-result.json').read_bytes())
    print(json.dumps(proof,ensure_ascii=False));assert proof['passed']
def document():
    now=T/'docs/handoff/NOW.md'
    text=now.read_text(encoding='utf-8')
    text=text.replace('U16/U20/F13·173쌍ledger UNVERIFIED·외부인증/회의·전체사용자시각인수는 여전히 열림이다.','U16/U20/F13·외부인증/회의·전체사용자시각인수는 열림이다. 과거173쌍 원장은 현재 후속 대조에서 복구했다.')
    text=text.replace('K3외부인증/실제회의와173쌍ledger coverage UNVERIFIED·최종사용자시각인수는 남음','K3외부인증/실제회의·현재 전체173시각재검토/최종사용자시각인수는 남음. 과거173쌍 검수 원장은 복구됨')
    text=text.replace('PENDING。실제8GET','PENDING. 실제8GET')
    text=text.replace('[후속 기록](verification/2026-10-12/k3-and-record-followup/README.md).\n- [x] K4.', '[후속 기록](verification/2026-10-12/k3-and-record-followup/README.md). 현재 앱 Drive 인증 읽기 성공과 HYD Google 등록0/지원 인증전달 경로 없음은 [현재 인증 경계](verification/2026-10-12/completion-audit/k3-auth/findings.md)에 있다. 실제 인증된 서버 설정이 준비되면 기존 준비 도구로 매핑 사본을 만들고 Google일정→확인→보고를 한 번 검증한다.\n- [x] K4.')
    now.write_text(text,encoding='utf-8')
    readme=V/'README.md';text=readme.read_text(encoding='utf-8')
    old='| F12 근본 조사/현재 알려진 검사 | producer/consumer F27 수정과 source/업무상태 불변 native96, 추가Trace14, 현재B lineage/source 검토 | 현재 알려진 원인 조사·집중 확인 완료. 이번 조사에서 새 코드 수정이나 새 전체시험 통과를 주장하지 않음 |'
    new='| F12 기동 지연/고아 문서 | [기존 원인 대조](../final-manual-infrastructure-audit.md): 옛16분 컨테이너 생성 대기와 현재seed59.719291초/read-back17/0, 현재 원천80개 접두어match0 | 조사 완료. 옛16분의 원인을 해결했다고 주장하지 않으며 이번에seed/삭제/전체시험을 반복하지 않음 |'
    assert old in text;text=text.replace(old,new)
    text+='\n## 현재 판본과 참고 비교\n\n[현재 source808 동결](source-manifest.json)·[변경0 확인](source-verification.json)은 이전 F27 source807 이후 제품 변경이 문서 선택3경로임을 기록한다. 과거 전체2673개 결과를 현재 전체 회귀 결과로 승격하지 않는다. [참고/실제 화면 나란히 보기](reference-comparison.html)·[캡처](reference-comparison.png)·[이미지4개 렌더 결과](reference-comparison-result.json)를 보존했다. 루트가 비교PNG를 직접 확인했다. ProcessGPT 쪽은 원본 컴포넌트를 컴파일한 비교용 폼이며 전체 앱 캡처라고 주장하지 않는다.\n\n새 선택 시험의 [메모리 결함 주입](manual-selection/fault-injection/result.json)은 선택을 새 문서로 초기화했을 때 기존 새 시험32행이 예상대로 실패함을 확인했다(1실패2.33초). 제품3파일 SHA는 불변이며 첫 수집경로 오류도 보존한다. 구현 당시 보존 비교 문서를 참고했고, ProcessGPT 모노레포README와 ontology-studio FilePanel 원본 파일 직접 확인은 후속 검토에서 수행했다. 원본 파일을 수정 전에 읽었다는 주장으로 바꾸지 않는다.\n'
    readme.write_text(text,encoding='utf-8')
    provenance=[]
    src=H/'manual-selection/fault-injection';dest=V/'manual-selection/fault-injection';dest.mkdir(exist_ok=True)
    for p in src.iterdir():
        if p.is_file() and p.suffix in ('.py','.json','.log'):
            target=dest/p.name;target.write_bytes(p.read_bytes());assert sha(target)==sha(p)
            provenance.append({'file':p.name,'sha256':sha(p),'bytes':p.stat().st_size})
    save(dest/'copy-provenance.json',provenance)
    backup=H/'frozen-product-bytes';backup.mkdir(exist_ok=True)
    for p in ['it/portal/www/index.html','it/portal/www/hitl.js','tests/test_portal_manual_document_selection_ui.py']:
        (backup/Path(p).name).write_bytes((T/p).read_bytes())
    (V/'finalize-root-evidence.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'updated':['NOW.md','README.md'],'fault_files':len(provenance)},ensure_ascii=False))
if sys.argv[1]=='freeze':freeze()
elif sys.argv[1]=='verify':verify()
elif sys.argv[1]=='compare':compare()
elif sys.argv[1]=='document':document()
