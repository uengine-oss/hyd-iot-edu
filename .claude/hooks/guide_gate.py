"""지침을 읽기 전에는 그 산출물을 고치지 못하게 한다(hyd-task 2절을 안내가 아니라 동작으로). Claude Code 훅이 부른다.

    guide_gate.py compact   SessionStart(compact): 이 세션이 읽은 기록을 비우고, 다시 읽을 문서를 대화에 넣는다
    guide_gate.py read      PostToolUse(Read): 지침 · 촬영준비 · 스펙 · 기록을 실제로 읽은 줄 범위를 적는다
    guide_gate.py gate      PreToolUse(Edit · Write · NotebookEdit · Bash · PowerShell · Agent): 안 읽었으면 종료 코드 2로 막는다
    guide_gate.py lines <일> 그 일(실라버스 · 덱 · 대본 · 영상 · 코딩랩 · 가이드)이 읽을 공통.md 줄 범위를 찍는다
    guide_gate.py selftest  일부러 깨뜨린 입력으로 위 동작이 잡는지 확인한다

- 상태: 작업/_훅/<세션>__<에이전트>.json(git 밖). 서브에이전트는 따로 센다 — 맥락이 따로이기 때문이다.
- 막는 것: Edit · Write · NotebookEdit로 산출물 · 제작 재료를 고치는 것, `python` 등으로 직접 부른 덱 · 영상 빌드, fable 모델 호출.
  셸 변수로 부른 실행 · sed · 리다이렉션 · 파이썬 스크립트의 직접 쓰기 · `만들기.sh`는 잡지 못한다.
- 지침을 요구하는 자리에는 `공통.md`에서 그 일의 절(표시 없는 절 + `(대상: …)`에 그 일이 적힌 절, 인수검사.py가 읽는 표시)을 함께 요구한다.
  덱 · 대본 중 어느 일인지 아직 모르면(둘 다 안 읽었으면) `공통.md` 전체, `공통.md` 자체를 고칠 때는 `공통.md` 전체만이다.
- 경로만으로 지침이 갈리지 않는 자리는 막지 않는다. 틀린 문서를 강제하는 것이 안 막는 것보다 나쁘다.
"""
import json, os, re, subprocess, sys, tempfile, time, unicodedata
from pathlib import Path

GUIDE = "workspace/강의제작/지침/{}.md"
COMMON = GUIDE.format("공통")
SHOOT ="workspace/강의제작/제작도구/촬영/{}/촬영준비.md"
TRACKED = re.compile(r"^(workspace/강의제작/지침/[^/]+\.md|workspace/강의제작/제작도구/촬영/[^/]+/촬영준비\.md|작업/[^/]+/(스펙|기록)\.md)$")
TASK_DOC = re.compile(r"^작업/[^/]+/(스펙|기록)\.md$")
RUN = r"(?<![\w.])(?:python\S*|py)[\"']?\s+(?:-\S+\s+)*[\"']?[^\s\"']*"   # 이름이 글에 나온 것(echo · git diff · 커밋 경로)이 아니라 파이썬의 첫 인자로 실행할 때만
BUILD = [(re.compile(RUN + r"deck2pptx\.py"), "덱"), (re.compile(RUN + r"(강의영상|강조표시)\.py"), "영상")]
READ_ONLY = re.compile(r"(--dry|--check|--help|-h)(\s|$)")
GUIDE_TOOL = re.compile(r"(학생가이드|build_student_guide|build_전체과정_학생가이드|apply_student_guide|사진)")
DECK_OR_SCRIPT = (GUIDE.format("덱"), GUIDE.format("대본"))   # 노트는 대본 작업도 고친다 — 둘 중 하나면 된다
WORK = re.compile(r"workspace/강의제작/지침/(실라버스|덱|대본|영상|코딩랩|가이드)\.md")
TOOLS = Path(__file__).resolve().parents[2] / "workspace" / "강의제작" / "제작도구" / "검사"   # 대상 표시를 읽는 곳은 인수검사.py 하나다


def norm(path, root):
    """저장소 루트 기준 경로로. 저장소 밖이면 None."""
    p = unicodedata.normalize("NFC", str(path)).replace("\\", "/")
    r = unicodedata.normalize("NFC", str(root)).replace("\\", "/").rstrip("/")
    if p.lower().startswith(r.lower() + "/"): return p[len(r) + 1:]
    return None if re.match(r"^([A-Za-z]:|/)", p) else p.removeprefix("./")


def guides_for(rel, root):
    """이 경로를 고치려면 읽어야 할 문서들(공통.md 포함). 한 칸이 튜플이면 그중 하나를 읽으면 된다. 해당 없으면 빈 목록."""
    if rel == COMMON: return [COMMON]
    need = work_guides(rel, root)
    return need + [COMMON] if need else []


def work_guides(rel, root):
    """이 경로의 일이 정하는 지침들(공통.md 빼고)."""
    if rel.endswith("/README.md"): return []
    m = re.fullmatch(r"workspace/강의제작/지침/(실라버스|덱|대본|영상|코딩랩|가이드)\.md", rel)
    if m: return [rel]
    m = re.match(r"workspace/강의제작/제작도구/촬영/([^/]+)/(.*)", rel)
    if m:
        if GUIDE_TOOL.match(m[2]): return [GUIDE.format("가이드")]
        shoot = SHOOT.format(m[1])   # 촬영준비가 아직 없는 자리(길 뚫기 · 시간 계수 자료)는 영상 지침만 요구한다
        return [GUIDE.format("영상")] + ([shoot] if (Path(root) / shoot).exists() else [])
    if rel.startswith("workspace/강의제작/산출물/실라버스/"): return [GUIDE.format("실라버스")]
    if rel.startswith("workspace/강의제작/산출물/영상/") or rel.startswith("workspace/강의제작/제작도구/기존제작/tools/video/"):
        return [GUIDE.format("영상")]
    m = re.match(r"workspace/강의제작/산출물/(통합반|실전반)/([^/]+)/", rel)
    if m:
        if m[2] == "이론": return [GUIDE.format("대본") if "/대본/" in rel else DECK_OR_SCRIPT]
        if m[2] == "이론_오프라인": return [GUIDE.format("덱")]
        if m[2] == "실습":
            if "/대본/" in rel: return [GUIDE.format("영상")]
            if rel.endswith((".html", ".png", ".jpg", ".jpeg")): return [GUIDE.format("가이드")]
            return [GUIDE.format("코딩랩")] if "/랩/" in rel and rel.endswith((".py", ".ipynb", ".js", ".mjs")) else []
    if re.match(r"workspace/강의제작/제작도구/구성/.*/강조_[^/]*\.json$", rel): return [GUIDE.format("영상")]
    if re.match(r"workspace/강의제작/제작도구/(구성|온라인/decks)/", rel): return [DECK_OR_SCRIPT]
    if rel.startswith("workspace/강의제작/제작도구/오프라인/decks/") or rel.startswith(".claude/skills/hyd-course-deck/"): return [GUIDE.format("덱")]
    if rel.startswith("workspace/강의제작/제작도구/실습시작/") or rel.startswith("workspace/강의제작/제작도구/온라인/labs/"): return [GUIDE.format("코딩랩")]
    return []


def state_path(root, ev):
    d = Path(root) / "작업" / "_훅"; d.mkdir(parents=True, exist_ok=True)
    return d / f"{ev.get('session_id', 'none')}__{ev.get('agent_id') or 'main'}.json"


def load(p):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"읽음": {}, "이전": []}


def save(p, st):
    tmp = p.with_suffix(".tmp"); tmp.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8"); tmp.replace(p)


def missing(root, rel, ranges, want=None):
    """읽지 않은 줄 범위 문자열들. want(읽어야 할 줄 범위)가 없으면 파일 전체다. 파일이 없으면 그 사실을 돌려준다."""
    f = Path(root) / rel
    if not f.exists(): return ["파일 없음"]
    out = []
    for lo, hi in want or [(1, len(f.read_bytes().splitlines()))]:
        at = lo
        for a, b in sorted(ranges):
            if b < at: continue
            if a > hi: break
            if a > at: out.append(f"{at}-{a - 1}")
            at = max(at, b + 1)
        if at <= hi: out.append(f"{at}-{hi}")
    return out


def common_lines(root, works):
    """그 일들이 읽을 공통.md 줄 범위. works가 비면 전체."""
    if str(TOOLS) not in sys.path: sys.path.insert(0, str(TOOLS))
    from 인수검사 import common_ranges
    return common_ranges(Path(root) / COMMON, works)


def common_gaps(root, need, st):
    """공통.md에서 이 일이 읽을 줄 중 안 읽은 줄. 덱 · 대본 중 어느 일인지 모르면(둘 다 안 읽었으면) 전체를 본다."""
    read, works, choices = st["읽음"].get(COMMON, []), [], [[]]
    for req in need:
        if isinstance(req, tuple):
            done = [WORK.fullmatch(r)[1] for r in req if not missing(root, r, st["읽음"].get(r, []))]
            if not done: return missing(root, COMMON, read)
            choices = [c + [d] for c in choices for d in done]
        elif WORK.fullmatch(req):
            works.append(WORK.fullmatch(req)[1])
    if not (Path(root) / COMMON).exists(): return ["파일 없음"]
    return min((missing(root, COMMON, read, common_lines(root, works + c)) for c in choices), key=len)


def on_compact(root, ev):
    p = state_path(root, ev); st = load(p)
    before = sorted(set(st["읽음"]) | set(st["이전"]))
    save(p, {"읽음": {}, "이전": before})
    limit = time.time() - 7 * 86400
    for old in p.parent.glob("*.json"):
        if old.stat().st_mtime < limit: old.unlink()
    print("[요약 직후 — 작업을 잇기 전에 반드시]")
    print("대화가 요약됐다. 요약은 기준의 일부만 남긴다. 아래 문서를 Read로 처음부터 끝까지(공통.md는 그 일의 줄만) 다시 읽기 전에는 관련 산출물 편집이 막힌다.")
    for rel in before: print(f"- 이 세션이 읽던 문서: {rel}")
    for d in sorted((Path(root) / "작업").glob("[0-9]" * 4 + "-*_*")):
        spec = d / "스펙.md"
        m = re.search(r"상태: *(\S+)", spec.read_text(encoding="utf-8")) if spec.exists() else None
        print(f"- 열린 작업: 작업/{d.name} (상태 {m[1] if m else '스펙 없음'})")
    print("1. 하던 작업 폴더의 스펙.md · 기록.md를 다시 읽는다.")
    print("2. 다루는 산출물의 규칙 문서를 다시 읽는다: 공통.md의 그 일 줄(`guide_gate.py lines <일>`) + 그 일의 문서 하나(workspace/README.md 색인, 촬영이면 그 도구 촬영준비, 덱이면 형식 문서를 더). 사실표 · 포털 기능 표는 필요한 대목만 찾아본다.")
    print("3. git 상태와 기록.md의 차이를 확인한다. 요약에 적힌 「완료」 「확인됨」은 실제 파일 · 숫자로 다시 확인하기 전에는 믿지 않는다.")
    return 0


def on_read(root, ev):
    inp = ev.get("tool_input") or {}
    rel = norm(inp.get("file_path", ""), root)
    if not rel or not TRACKED.match(rel): return 0
    res = ev.get("tool_response")
    f = res.get("file") if isinstance(res, dict) else None   # 도구가 실제로 돌려준 범위만 센다 — 잘린 읽기를 다 읽은 것으로 적지 않는다
    if not isinstance(f, dict) or not isinstance(f.get("startLine"), int) or not isinstance(f.get("numLines"), int):
        print(f"guide_gate: {rel}: Read 응답에서 읽은 줄 범위를 찾지 못해 적지 않았다(응답 키 {sorted(res) if isinstance(res, dict) else type(res).__name__})", file=sys.stderr)
        return 1
    p = state_path(root, ev); st = load(p)
    st["읽음"].setdefault(rel, []).append([f["startLine"], f["startLine"] + f["numLines"] - 1]); save(p, st)
    return 0


def block(msg):
    print(msg, file=sys.stderr); return 2


def on_gate(root, ev):
    tool, inp = ev.get("tool_name", ""), ev.get("tool_input") or {}
    if tool == "Agent":
        if "fable" in str(inp.get("model", "")).lower():
            return block("fable 모델은 쓰지 않는다(CLAUDE.md 4절). 다른 모델로 호출한다.")
        return 0
    if tool in ("Bash", "PowerShell"):
        need = []
        for part in re.split(r"[;&|\n]+", inp.get("command", "")):
            need += [GUIDE.format(d) for rx, d in BUILD if rx.search(part) and not READ_ONLY.search(part)]
        need += [COMMON] if need else []
        what = "이 빌드 명령"
    else:
        rel = norm(inp.get("file_path") or inp.get("notebook_path") or "", root)
        need = guides_for(rel, root) if rel else []
        what = rel
    if not need: return 0
    st = load(state_path(root, ev))
    need = need + [r for r in st["이전"] if TASK_DOC.match(r) and (Path(root) / r).exists()]
    lack = []
    for req in need:
        if req == COMMON:      # 공통.md 자체를 고칠 때는 일이 없어 전체다
            gaps = {COMMON: common_gaps(root, need, st)}
        else:
            alts = req if isinstance(req, tuple) else (req,)
            gaps = {r: missing(root, r, st["읽음"].get(r, [])) for r in alts}
        if all(gaps.values()):
            lack.append(" 또는 ".join(f"{r}(안 읽은 줄 {', '.join(g)})" for r, g in gaps.items()))
    if not lack: return 0
    return block(f"{what}: 지침을 끝까지 읽기 전에는 진행하지 않는다(hyd-task 2절). Read로 나눠 읽는다(잘려 나온 줄은 읽은 것으로 세지 않는다).\n" + "\n".join("- " + x for x in lack))


def selftest():
    """실제 명령 줄을 임시 저장소에 돌려 막아야 할 때 막고 통과할 때 통과하는지 본다."""
    me = Path(__file__).resolve(); bad = []
    S = "workspace/강의제작/산출물/통합반/"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs = {f"workspace/강의제작/지침/{d}.md" for d in ("공통", "덱", "대본", "영상", "가이드", "코딩랩")}
        docs |= {"workspace/강의제작/제작도구/촬영/포털/촬영준비.md", "작업/2026-01-01_시험/스펙.md", "작업/2026-01-01_정리됨/기록.md"}
        for rel in docs:
            f = root / rel; f.parent.mkdir(parents=True, exist_ok=True); f.write_text("가\n" * 99 + "끝\n", encoding="utf-8")
        def call(mode, ev, want, name):
            ev = dict({"session_id": "s", "cwd": str(root)}, **ev)
            r = subprocess.run([sys.executable, str(me), mode], input=json.dumps(ev, ensure_ascii=False).encode("utf-8"),
                               capture_output=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=str(root)))
            if r.returncode != want: bad.append(f"{name}: 종료 코드 {r.returncode}, 기대 {want} · {r.stderr.decode('utf-8', 'replace')[:200]}")
            return r
        def ed(rel, agent=None):
            ev = {"tool_name": "Edit", "tool_input": {"file_path": str(root / rel)}}
            return dict(ev, agent_id=agent) if agent else ev
        def sh(cmd): return {"tool_name": "Bash", "tool_input": {"command": cmd}}
        def rd(rel, start=1, n=100):
            return {"tool_name": "Read", "tool_input": {"file_path": str(root / rel)}, "tool_response": {"type": "text", "file": {"startLine": start, "numLines": n, "totalLines": 100}}}
        DECK, SCRIPT, VIDEO, GD = (GUIDE.format(d) for d in ("덱", "대본", "영상", "가이드"))
        pptx = S + "이론/02회차/통합반_02일차.pptx"
        call("gate", ed(pptx), 2, "안 읽고 덱 고치기")
        call("gate", ed("it/process/x.py"), 0, "시스템 코드는 막지 않음")
        call("gate", ed(S + "이론/02회차/README.md"), 0, "README는 막지 않음")
        call("gate", ed("workspace/강의제작/제작도구/촬영/README.md"), 0, "촬영 README는 막지 않음")
        call("gate", ed("workspace/강의제작/지침/사실표/통합반_01일차_기술사실표.md"), 0, "사실표는 막지 않음(공통.md를 요구하지 않음)")
        call("gate", ed(COMMON), 2, "공통.md를 안 읽고 공통.md 고치기")
        call("gate", ed(DECK), 2, "안 읽고 덱 지침 고치기")
        call("read", rd(DECK, 1, 50), 0, "앞부분 읽기")
        call("gate", ed(pptx), 2, "절반만 읽고 덱 고치기")
        call("read", rd(DECK, 51, 50), 0, "실제 줄 수까지 읽기")
        r = call("gate", ed(pptx), 2, "덱을 다 읽어도 공통.md를 안 읽으면 막힘")
        if "공통.md" not in r.stderr.decode("utf-8", "replace") or "덱.md" in r.stderr.decode("utf-8", "replace"): bad.append(f"막는 말이 안 읽은 공통.md만 가리키지 않음: {r.stderr.decode('utf-8', 'replace')[:200]}")
        call("gate", ed(DECK), 2, "덱 지침 고치기도 공통.md까지")
        call("gate", sh("python deck2pptx.py a.md b.pptx"), 2, "빌드도 공통.md까지")
        call("read", rd(COMMON, 1, 50), 0, "공통.md 앞부분 읽기")
        call("gate", ed(pptx), 2, "공통.md를 절반만 읽으면 막힘")
        call("read", rd(COMMON, 51, 50), 0, "공통.md 끝까지 읽기")
        call("gate", ed(pptx), 0, "덱 · 공통.md를 다 읽고 덱 고치기")
        call("gate", ed(DECK), 0, "덱 · 공통.md를 다 읽고 덱 지침 고치기")
        call("gate", ed(COMMON), 0, "공통.md를 읽고 공통.md 고치기")
        call("gate", ed(COMMON, "a2"), 2, "서브에이전트의 공통.md 고치기는 따로 센다")
        call("read", dict(rd(COMMON), agent_id="a2"), 0, "서브에이전트가 공통.md만 읽기")
        call("gate", ed(COMMON, "a2"), 0, "공통.md 자체는 공통.md만 읽으면 통과")
        call("gate", ed(pptx, "a2"), 2, "공통.md만 읽고 덱 고치기는 막힘")
        call("gate", ed(pptx, "a1"), 2, "서브에이전트는 따로 센다")
        call("read", dict(rd(SCRIPT), agent_id="a1"), 0, "서브에이전트가 대본 읽기")
        call("gate", ed(pptx, "a1"), 2, "노트 작업도 공통.md까지")
        call("read", dict(rd(COMMON), agent_id="a1"), 0, "서브에이전트가 공통.md 읽기")
        call("gate", ed(pptx, "a1"), 0, "노트 작업은 대본 · 공통.md만 읽어도 PPTX 통과")
        call("gate", ed(S + "이론_오프라인/02회차/x.pptx", "a1"), 2, "오프라인 덱은 덱 지침")
        call("read", dict(rd(VIDEO, 1, 40), tool_response={"type": "text", "file": {"startLine": 1, "numLines": 40, "totalLines": 100}}), 0, "잘린 읽기")
        call("gate", sh("python 강의영상.py out s.md"), 2, "잘린 만큼만 세어 영상 빌드 막힘")
        call("read", {"tool_name": "Read", "tool_input": {"file_path": str(root / VIDEO), "offset": 41}, "tool_response": "문자열 응답"}, 1, "범위를 모르는 응답은 실패로 알림")
        call("gate", sh("python 강의영상.py out s.md"), 2, "범위를 모르는 응답은 세지 않음")
        call("gate", sh("python deck2pptx.py a.md b.pptx"), 0, "덱을 읽었으면 빌드 통과")
        call("gate", sh("python 강의영상.py out s.md --dry"), 0, "--dry는 막지 않음")
        call("gate", sh("python 강의영상.py out s.md && du -h out"), 2, "뒤에 다른 명령이 붙어도 막음")
        call("gate", sh("PYTHONUTF8=1 .venv314/Scripts/python.exe tools/video/강조표시.py a.mp4 b.json c.mp4"), 2, "경로가 붙은 실행도 막음")
        call("gate", sh('"C:/x y/.venv314/Scripts/python.exe" "tools/video/강조표시.py" a.mp4 b.json c.mp4'), 2, "따옴표로 묶은 실행도 막음")
        for cmd in ("echo 강의영상.py; git log --grep 강조표시.py", "git diff a.py 강조표시.py", "grep -n x 재편검사.py 강의영상.py", "cat 동기화.py\n강조표시.py",
                    'python workspace/동기화.py commit "메시지" --만 tools/video/강조표시.py'):
            call("gate", sh(cmd), 0, f"이름만 나온 명령은 막지 않음: {cmd!r}")
        call("gate", ed("workspace/강의제작/제작도구/촬영/포털/큐.json"), 2, "촬영은 영상 · 촬영준비 둘 다")
        call("read", rd(VIDEO, 41, 60), 0, "영상 나머지 읽기")
        call("gate", ed("workspace/강의제작/제작도구/촬영/포털/큐.json"), 2, "촬영준비는 아직")
        call("gate", ed("workspace/강의제작/제작도구/촬영/bpmn/촬영준비.md"), 0, "새 도구의 촬영준비는 만들 수 있음")
        call("gate", ed("workspace/강의제작/제작도구/촬영/시간계수_자료/a.json"), 0, "촬영준비가 없는 자료 폴더")
        call("gate", ed(S + "실습/02회차/대본/05_실습_지식지도탐색.md"), 0, "실습 대본은 영상 지침")
        call("gate", ed("workspace/강의제작/제작도구/촬영/포털/학생가이드_원고.md"), 2, "가이드 재료는 가이드 지침")
        call("gate", ed(S + "실습/01회차/랩/01일차_실습1_학습노트/images/n01-01.png"), 2, "도구 실습 사진은 가이드 지침")
        call("read", rd(GD), 0, "가이드 읽기")
        call("gate", ed("workspace/강의제작/제작도구/촬영/포털/학생가이드_원고.md"), 0, "가이드만 읽으면 가이드 재료 통과")
        call("gate", ed(S + "실습/01회차/랩/01일차_실습1_학습노트/images/n01-01.png"), 0, "가이드만 읽으면 사진 통과")
        call("gate", ed(S + "실습/03회차/랩/x/코드/main.py"), 2, "랩 코드는 코딩랩 지침")
        call("read", rd("작업/2026-01-01_시험/스펙.md"), 0, "스펙 읽기")
        call("read", rd("작업/2026-01-01_정리됨/기록.md"), 0, "곧 정리할 기록 읽기")
        r = call("compact", {"source": "compact"}, 0, "요약")
        if "덱.md" not in r.stdout.decode("utf-8") or "2026-01-01_시험" not in r.stdout.decode("utf-8"): bad.append("요약: 읽던 문서 · 열린 작업을 안내하지 않음")
        (root / "작업/2026-01-01_정리됨/기록.md").unlink()
        if "공통.md" not in r.stdout.decode("utf-8"): bad.append("요약: 읽던 공통.md를 안내하지 않음")
        call("gate", ed(pptx), 2, "요약 뒤에는 다시 막힘")
        call("read", rd(DECK), 0, "요약 뒤 덱 다시 읽기")
        call("gate", ed(pptx), 2, "요약 뒤 공통.md도 다시 읽어야 함")
        call("read", rd(COMMON), 0, "요약 뒤 공통.md 다시 읽기")
        call("gate", ed(pptx), 2, "요약 뒤 스펙도 다시 읽어야 함")
        call("read", rd("작업/2026-01-01_시험/스펙.md"), 0, "요약 뒤 스펙 다시 읽기")
        call("gate", ed(pptx), 0, "정리된 폴더의 기록은 요구하지 않음")
        call("gate", {"tool_name": "Agent", "tool_input": {"model": "fable", "prompt": "x"}}, 2, "fable 호출")
        call("gate", {"tool_name": "Agent", "tool_input": {"model": "opus", "prompt": "x"}}, 0, "opus 호출")
        # 공통.md의 대상 절: 그 일의 줄만 읽으면 통과하고, 그 일의 절을 빠뜨리면 막고, 공통.md 자체는 전체다
        (root / COMMON).write_text("\n".join(["# 공통", "", "## 반드시 — 어기면 불통과", "1. 규칙", "## 작업 컨텍스트", "### 회 표 (대상: 실라버스 · 덱)", "표",
                                              "### 근거", "근거", "## 인수 조건", "### 원리", "| C-1 | 기준 | 본다 |", "### 패키지 (대상: 코딩랩 · 가이드)", "| C-50 | 기준 | 본다 |",
                                              "### 말 (대상: 덱 · 대본 · 영상)", "| C-13 | 기준 | 본다 |", "### 대본 말 (대상: 대본 · 영상)", "| C-19 | 기준 | 본다 |", "### 보고", "| C-60 | 기준 | 본다 |"]) + "\n", encoding="utf-8")
        def who(ev, name): return dict(ev, session_id=name)
        LAB = S + "실습/03회차/랩/x/코드/main.py"
        def lines_of(work):
            r = subprocess.run([sys.executable, str(me), "lines", work], capture_output=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=str(root)))
            return r.returncode, r.stdout.decode("utf-8", "replace").strip()
        for work, want in (("덱", "1-12, 15-16, 19-20"), ("대본", "1-5, 8-12, 15-20"), ("코딩랩", "1-5, 8-14, 19-20"), ("영상", "1-5, 8-12, 15-20")):
            if lines_of(work) != (0, want): bad.append(f"lines {work}: {lines_of(work)}, 기대 {want}")
        if lines_of("코딩 랩")[0] == 0: bad.append("lines: 없는 일 이름을 통과시킴")
        call("read", who(rd(DECK), "t"), 0, "덱 읽기")
        call("read", who(rd(COMMON, 1, 12), "t"), 0, "공통 1-12 읽기")
        call("read", who(rd(COMMON, 19, 2), "t"), 0, "공통 19-20 읽기")
        r = call("gate", who(ed(pptx), "t"), 2, "덱 일의 공통 절을 빠뜨리면 막힘")
        msg = r.stderr.decode("utf-8", "replace")
        if "15-16" not in msg or "13-14" in msg or "17-18" in msg: bad.append(f"막는 말이 그 일의 안 읽은 줄만 가리키지 않음: {msg[:200]}")
        call("read", who(rd(COMMON, 15, 2), "t"), 0, "공통 15-16 읽기")
        call("gate", who(ed(pptx), "t"), 0, "덱 일은 코딩랩 · 대본 절 없이 통과")
        call("gate", who(ed(DECK), "t"), 0, "덱 지침 고치기도 그 일 절만")
        call("gate", who(sh("python deck2pptx.py a.md b.pptx"), "t"), 0, "덱 빌드도 그 일 절만")
        r = call("gate", who(ed(COMMON), "t"), 2, "공통.md 자체를 고칠 때는 전체")
        msg = r.stderr.decode("utf-8", "replace")
        if "13-14" not in msg or "17-18" not in msg: bad.append(f"공통.md 자체: 안 읽은 줄 전체를 말하지 않음: {msg[:200]}")
        call("read", who(rd("workspace/강의제작/지침/코딩랩.md"), "t"), 0, "코딩랩 읽기")
        r = call("gate", who(ed(LAB), "t"), 2, "덱 절만 읽고 랩 코드는 막힘")
        msg = r.stderr.decode("utf-8", "replace")
        if "13-14" not in msg or "15-16" in msg: bad.append(f"코딩랩 일의 막는 말: {msg[:200]}")
        call("read", who(rd(COMMON, 13, 2), "t"), 0, "공통 13-14 읽기")
        call("gate", who(ed(LAB), "t"), 0, "코딩랩 절까지 읽으면 랩 코드 통과")
        call("read", who(rd(COMMON, 17, 2), "t"), 0, "공통 17-18 읽기")
        call("gate", who(ed(COMMON), "t"), 0, "전체를 읽으면 공통.md 고치기 통과")
        r = call("gate", who(ed(pptx), "u"), 2, "덱 · 대본 중 어느 일인지 모르면 막힘")
        msg = r.stderr.decode("utf-8", "replace")
        if "공통.md(안 읽은 줄 1-20)" not in msg: bad.append(f"일을 정할 수 없을 때 공통.md 전체를 요구하지 않음: {msg[:200]}")
        call("read", who(rd(SCRIPT), "u"), 0, "대본 읽기")
        call("read", who(rd(COMMON, 1, 5), "u"), 0, "공통 1-5 읽기")
        call("read", who(rd(COMMON, 8, 13), "u"), 0, "공통 8-20 읽기")
        call("gate", who(ed(pptx), "u"), 0, "노트 작업은 대본 절만 읽으면 통과(회 표 없이)")
        call("read", who(rd(DECK), "v"), 0, "덱 읽기")
        call("read", who(rd(SCRIPT), "v"), 0, "대본도 읽기")
        call("read", who(rd(COMMON, 1, 5), "v"), 0, "공통 1-5 읽기")
        call("read", who(rd(COMMON, 8, 5), "v"), 0, "공통 8-12 읽기")
        call("read", who(rd(COMMON, 15, 6), "v"), 0, "공통 15-20 읽기")
        call("gate", who(ed(pptx), "v"), 0, "덱 · 대본을 다 읽었으면 어느 한 일의 절만 다 읽어도 통과")
        call("read", who(rd(VIDEO), "w"), 0, "영상 읽기")
        call("read", who(rd(COMMON, 1, 5), "w"), 0, "공통 1-5 읽기")
        call("read", who(rd(COMMON, 8, 5), "w"), 0, "공통 8-12 읽기")
        call("read", who(rd(COMMON, 19, 2), "w"), 0, "공통 19-20 읽기")
        call("gate", who(sh("python 강의영상.py out s.md"), "w"), 2, "영상 일에 대상 절이 빠지면 막힘")
        call("read", who(rd(COMMON, 15, 4), "w"), 0, "공통 15-18 읽기")
        call("gate", who(sh("python 강의영상.py out s.md"), "w"), 0, "영상 일은 회 표 · 패키지 절 없이 통과")
    print("\n".join(bad) if bad else "자가시험 통과")
    return 1 if bad else 0


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    if mode == "selftest": return selftest()
    if mode == "lines":
        work = sys.argv[2] if len(sys.argv) > 2 else ""
        if not WORK.fullmatch(GUIDE.format(work)): sys.exit(f"guide_gate.py lines: 일 이름은 실라버스 · 덱 · 대본 · 영상 · 코딩랩 · 가이드 — 받은 것 「{work}」")
        print(", ".join(f"{a}-{b}" for a, b in common_lines(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2], [work])))
        return 0
    ev = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    root = os.environ.get("CLAUDE_PROJECT_DIR") or ev.get("cwd") or "."
    fn = {"compact": on_compact, "read": on_read, "gate": on_gate}.get(mode)
    if not fn: sys.exit(f"guide_gate.py: 모르는 동작 「{mode}」")
    return fn(root, ev)


if __name__ == "__main__":
    sys.exit(main())
