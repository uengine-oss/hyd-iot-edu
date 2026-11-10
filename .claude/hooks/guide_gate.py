"""일 하나 = `공통.md` 전체 + 그 일 문서 전체(촬영은 + `촬영/README.md` + 그 도구 촬영준비)를 끝까지 읽어야 그 일의 산출물 · 도구를 고친다. Claude Code 훅이 부른다.
언제: settings.json 훅 — SessionStart(compact) `compact`, PostToolUse(Read · Edit · Write) `read`, PreToolUse(Edit · Write · NotebookEdit · Bash · PowerShell · Agent) `gate`.
명령: <py> .claude/hooks/guide_gate.py selftest
- 상태: 작업/_훅/<세션>__<에이전트>.json(git 밖). 서브에이전트는 따로 센다. 남이 바꾼 문서 · 요약 뒤에는 다시 읽어야 하고, 요약 뒤에는 이 세션이 편집한 작업 폴더의 스펙 · 기록도 요구한다.
- 자기 편집: 고치기 전 판을 끝까지 읽은 문서를 Edit · Write로 고치면 고친 판을 다 읽은 것으로 옮긴다(덜 읽었으면 옮기지 않는다).
- 작업 폴더는 이 PC에서 작업/<날짜>_<제목>/, 클라우드에서 workspace/강의제작/제작도구/근거/<날짜>_<제목>/이다(CLAUDE.md 7절) — 둘 다 같은 꼴로 세고, 상태 · 오래됨은 동기화.py `tasks` · `state` · `STALE_DAYS`와 같은 기준이다.
- 막는 것: 산출물 · 제작 재료 편집, 직접 부른 덱 · 영상 빌드(`--dry` 등 읽기 전용 제외), fable 모델. 지침 문서 자체 편집 · 셸 변수 · sed · 리다이렉션 쓰기는 막지 않는다.
"""
import hashlib, json, os, re, subprocess, sys, tempfile, time, unicodedata
from pathlib import Path

GUIDE = "workspace/강의제작/지침/{}.md"
COMMON = GUIDE.format("공통")
SHOOT = "workspace/강의제작/제작도구/촬영/{}/촬영준비.md"
SHOOT_COMMON = "workspace/강의제작/제작도구/촬영/README.md"
TASKS = ("작업", "workspace/강의제작/제작도구/근거")   # 작업 폴더의 부모: 이 PC · 클라우드
TASK_DOC = re.compile(r"^(?:작업|workspace/강의제작/제작도구/근거)/[^/]+/(스펙|기록)\.md$")
TASK_DIR = re.compile(r"^((?:작업|workspace/강의제작/제작도구/근거)/\d{4}-\d\d-\d\d_[^/]+)/")
STATES = ("진행", "중단", "끝")
STALE_DAYS = 3
TRACKED = re.compile(r"^(workspace/강의제작/지침/[^/]+\.md|workspace/강의제작/제작도구/촬영/README\.md|workspace/강의제작/제작도구/촬영/[^/]+/촬영준비\.md)$|" + TASK_DOC.pattern)
RUN = r"(?<![\w.])(?:python\S*|py)[\"']?\s+(?:-\S+\s+)*[\"']?[^\s\"']*"   # 파이썬의 첫 인자로 실행할 때만(이름이 글에 나온 것은 아님)
BUILD = [(re.compile(RUN + r"deck2pptx\.py"), "덱"), (re.compile(RUN + r"(강의영상|강조표시)\.py"), "영상")]
READ_ONLY = re.compile(r"(--dry|--check|--help|-h)(\s|$)")
GUIDE_TOOL = re.compile(r"(학생가이드|build_student_guide|build_전체과정_학생가이드|apply_student_guide|사진)")
DECK_OR_SCRIPT = (GUIDE.format("덱"), GUIDE.format("대본"))   # PPTX 노트는 대본 일도 고친다 — 둘 중 하나


def norm(path, root):
    """저장소 루트 기준 경로. 저장소 밖이면 None."""
    p = unicodedata.normalize("NFC", str(path)).replace("\\", "/")
    r = unicodedata.normalize("NFC", str(root)).replace("\\", "/").rstrip("/")
    if p.lower().startswith(r.lower() + "/"): return p[len(r) + 1:]
    return None if re.match(r"^([A-Za-z]:|/)", p) else p.removeprefix("./")


def work_guides(rel, root):
    """이 경로의 일이 읽을 문서(공통.md 빼고). 한 칸이 튜플이면 그중 하나. 해당 없으면 빈 목록."""
    lab = re.match(r"(workspace/강의제작/산출물/(?:통합반|실전반)/실습/[^/]+/랩/[^/]+)/(.*)", rel)
    if (rel.endswith("/README.md") and not lab) or rel.startswith("workspace/강의제작/지침/"): return []
    m = re.match(r"workspace/강의제작/제작도구/촬영/([^/]+)/(.*)", rel)
    if m:
        if GUIDE_TOOL.match(m[2]): return [GUIDE.format("가이드")]
        shoot = SHOOT.format(m[1])   # 촬영준비가 아직 없는 자리(길 뚫기 · 시간 계수 자료)는 영상 + 촬영 README만
        return [GUIDE.format("영상"), SHOOT_COMMON] + ([shoot] if (Path(root) / shoot).exists() else [])
    if rel.startswith("workspace/강의제작/산출물/실라버스/"): return [GUIDE.format("실라버스")]
    if rel.startswith(("workspace/강의제작/산출물/영상/", "workspace/강의제작/제작도구/기존제작/tools/video/")): return [GUIDE.format("영상")]
    m = re.match(r"workspace/강의제작/산출물/(통합반|실전반)/([^/]+)/", rel)
    if m:
        if m[2] == "이론": return [GUIDE.format("대본") if "/대본/" in rel else DECK_OR_SCRIPT]
        if m[2] == "이론_오프라인": return [GUIDE.format("덱")]
        if m[2] == "실습":
            if "/대본/" in rel: return [GUIDE.format("영상")]
            if rel.endswith((".zip", ".html", ".png", ".jpg", ".jpeg")): return [GUIDE.format("가이드")]
            if lab:
                folder = Path(root) / lab[1]
                if rel.endswith(("/입출력_계약.md", ".py", ".ipynb", ".js", ".mjs")) or any(
                    (folder / name).is_file() for name in ("check.py", "입출력_계약.md", "코드/입출력_계약.md")
                ): return [GUIDE.format("코딩랩")]
                # START와 원자료는 포털·작도용 학생 묶음과 코딩 랩이 같은 자리에 둔다.
                return [(GUIDE.format("가이드"), GUIDE.format("코딩랩"))]
    if re.match(r"workspace/강의제작/제작도구/구성/.*/강조_[^/]*\.json$", rel): return [GUIDE.format("영상")]
    if re.match(r"workspace/강의제작/제작도구/(구성|온라인/decks)/", rel): return [DECK_OR_SCRIPT]
    if rel.startswith(("workspace/강의제작/제작도구/오프라인/decks/", ".claude/skills/hyd-course-deck/")): return [GUIDE.format("덱")]
    if rel.startswith(("workspace/강의제작/제작도구/실습시작/", "workspace/강의제작/제작도구/온라인/labs/")): return [GUIDE.format("코딩랩")]
    if rel.startswith("workspace/강의제작/제작도구/배포/"): return [GUIDE.format("배포")]
    return []


def state_path(root, ev):
    d = Path(root) / "작업" / "_훅"; d.mkdir(parents=True, exist_ok=True)
    return d / f"{ev.get('session_id', 'none')}__{ev.get('agent_id') or 'main'}.json"


def load(p):
    st = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    for k, v in (("읽음", {}), ("이전", []), ("편집", []), ("편집전", {})): st.setdefault(k, v)
    return st


def save(p, st):
    tmp = p.with_suffix(".tmp"); tmp.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8"); tmp.replace(p)


def digest(f):
    return hashlib.sha256(f.read_bytes()).hexdigest()


def gaps(root, rel, st):
    """지금 판에서 안 읽은 줄 범위들. 읽은 뒤 파일이 바뀌었으면 그 기록은 버린다(바뀐 판은 다시 읽는다). 파일이 없으면 그 사실."""
    f = Path(root) / rel
    if not f.exists(): return ["파일 없음"]
    rec, data = st["읽음"].get(rel), f.read_bytes()
    out, at, total = [], 1, len(data.splitlines())
    for a, b in sorted(rec["줄"]) if isinstance(rec, dict) and rec.get("sha") == hashlib.sha256(data).hexdigest() else []:
        if a > at: out.append(f"{at}-{a - 1}")
        at = max(at, b + 1)
    return out + ([f"{at}-{total}"] if at <= total else [])


def task_state(d):
    """스펙.md의 `상태: <진행|중단|끝>`. 스펙이 없거나 꼴이 틀리면 그 사실(동기화.py state와 같은 기준)."""
    spec = d / "스펙.md"
    if not spec.is_file(): return "꼴 틀림 — 스펙.md 없음"
    m = re.search(r"상태:[ \t]*(\S+)", spec.read_text(encoding="utf-8"))
    return m[1] if m and m[1] in STATES else f"꼴 틀림 — `상태: {'|'.join(STATES)}` 줄 없음"


def task_age(d):
    """작업 폴더가 마지막으로 바뀐 뒤 지난 날 수: 폴더 바로 아래 파일의 가장 늦은 수정 시각(파일이 없을 때만 폴더 시각)."""
    t = max((f.stat().st_mtime for f in d.iterdir() if f.is_file()), default=d.stat().st_mtime)
    return (time.time() - t) / 86400


def on_compact(root, ev):
    p = state_path(root, ev); st = load(p)
    mine = sorted(set(st["편집"]))
    keep = [r for r in sorted(set(st["읽음"]) | set(st["이전"])) if not TASK_DOC.match(r)]   # 읽던 지침은 알리기만 한다
    before = keep + [f"{d}/{n}.md" for d in mine for n in ("스펙", "기록")]
    save(p, {"읽음": {}, "이전": before, "편집": mine, "편집전": {}})
    limit = time.time() - 7 * 86400
    for old in p.parent.glob("*.json"):
        if old.stat().st_mtime < limit: old.unlink()
    print("[요약 직후] 아래 문서를 Read로 처음부터 끝까지 다시 읽기 전에는 관련 산출물 편집이 막힌다.")
    for rel in keep: print(f"- 이 세션이 읽던 문서: {rel}")
    others = stale = 0
    for base in TASKS:
        for d in sorted((Path(root) / base).glob("[0-9]" * 4 + "-*_*")):
            if not d.is_dir(): continue
            rel = f"{base}/{d.name}"
            if rel in mine:
                print(f"- 이 세션이 편집한 작업: {rel} (상태 {task_state(d)}) — 스펙.md · 기록.md를 다시 읽는다")
            else:
                others += 1; stale += task_age(d) > STALE_DAYS
    print(f"- 그 밖의 열린 작업 폴더 {others}개(그중 {STALE_DAYS}일 넘게 바뀌지 않은 오래됨 {stale}개) — 목록은 `동기화.py status`")
    print("순서: 그 작업 폴더 스펙.md · 기록.md → 공통.md + 그 일 문서(촬영이면 촬영/README.md + 그 도구 촬영준비) → git 상태와 기록.md 대조. 요약의 「완료」는 실제 파일 · 숫자로 다시 확인한다.")
    return 0


def on_edited(root, ev, rel):
    """Edit · Write가 끝난 뒤: 고치기 전 판을 끝까지 읽었으면(gate가 적은 편집전 sha가 읽은 판과 같으면) 고친 판을 다 읽은 것으로 옮긴다.
    작업 폴더 안을 고쳤으면 그 폴더를 「이 세션이 편집한 작업」으로 적는다(요약 뒤 그 폴더 스펙 · 기록만 다시 요구한다)."""
    p = state_path(root, ev); st = load(p)
    m = TASK_DIR.match(rel)
    if m and m[1] not in st["편집"]: st["편집"].append(m[1])
    pre = st["편집전"].pop(rel, None)
    f = Path(root) / rel
    if pre is not None and TRACKED.match(rel) and f.exists():
        data = f.read_bytes()
        st["읽음"][rel] = {"sha": hashlib.sha256(data).hexdigest(), "줄": [[1, max(1, len(data.splitlines()))]]}
    save(p, st)
    return 0


def on_read(root, ev):
    rel = norm((ev.get("tool_input") or {}).get("file_path", ""), root)
    if ev.get("tool_name") in ("Edit", "Write"): return on_edited(root, ev, rel) if rel else 0
    if not rel or not TRACKED.match(rel): return 0
    res = ev.get("tool_response")
    f = res.get("file") if isinstance(res, dict) else None   # 도구가 실제로 돌려준 범위만 센다(잘린 읽기는 잘린 만큼)
    if not isinstance(f, dict) or not isinstance(f.get("startLine"), int) or not isinstance(f.get("numLines"), int):
        print(f"guide_gate: {rel}: Read 응답에서 읽은 줄 범위를 찾지 못해 적지 않았다(응답 키 {sorted(res) if isinstance(res, dict) else type(res).__name__})", file=sys.stderr)
        return 1
    p = state_path(root, ev); st = load(p)
    sha = digest(Path(root) / rel) if (Path(root) / rel).exists() else ""
    rec = st["읽음"].get(rel)
    if not isinstance(rec, dict) or rec.get("sha") != sha:     # 판이 바뀌었으면 그 판부터 다시 센다
        rec = st["읽음"][rel] = {"sha": sha, "줄": []}
    rec["줄"].append([f["startLine"], f["startLine"] + f["numLines"] - 1]); save(p, st)
    return 0


def on_gate(root, ev):
    tool, inp = ev.get("tool_name", ""), ev.get("tool_input") or {}
    if tool == "Agent":
        if "fable" in str(inp.get("model", "")).lower():
            print("fable 모델은 쓰지 않는다(CLAUDE.md 4절). 다른 모델로 호출한다.", file=sys.stderr); return 2
        return 0
    if tool in ("Bash", "PowerShell"):
        need = [GUIDE.format(d) for part in re.split(r"[;&|\n]+", inp.get("command", "")) for rx, d in BUILD if rx.search(part) and not READ_ONLY.search(part)]
        what = "이 빌드 명령"
    else:
        what = norm(inp.get("file_path") or inp.get("notebook_path") or "", root)
        need = work_guides(what, root) if what else []
        if tool in ("Edit", "Write") and what and TRACKED.match(what):
            p = state_path(root, ev); st = load(p)   # 고치기 전 판을 끝까지 읽었는지 적어 둔다 — 고친 뒤(on_edited) 그 판만 옮긴다
            f = Path(root) / what
            if not f.exists() or not gaps(root, what, st): st["편집전"][what] = digest(f) if f.exists() else ""
            else: st["편집전"].pop(what, None)
            save(p, st)
    if not need: return 0
    st = load(state_path(root, ev))
    need += [COMMON] + [r for r in st["이전"] if TASK_DOC.match(r) and (Path(root) / r).exists()]
    lack = []
    for req in dict.fromkeys(need):
        g = {r: gaps(root, r, st) for r in (req if isinstance(req, tuple) else (req,))}
        if all(g.values()):
            lack.append(" 또는 ".join(f"{r}(안 읽은 줄 {', '.join(x)})" for r, x in g.items()))
    if not lack: return 0
    print(f"{what}: 문서를 끝까지 읽기 전에는 진행하지 않는다. Read로 나눠 읽는다(잘려 나온 줄은 읽은 것으로 세지 않는다).\n" + "\n".join("- " + x for x in lack), file=sys.stderr)
    return 2


def selftest():
    """임시 저장소에서 실제 훅 호출로 막아야 할 때 막고 통과할 때 통과하는지 본다."""
    me = Path(__file__).resolve(); bad = []
    S = "workspace/강의제작/산출물/통합반/"
    DECK, SCRIPT, VIDEO, GD, LAB_G, DLV = (GUIDE.format(d) for d in ("덱", "대본", "영상", "가이드", "코딩랩", "배포"))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        CLOUD = "workspace/강의제작/제작도구/근거/2026-01-01_클라우드/기록.md"
        for rel in (COMMON, DECK, SCRIPT, VIDEO, GD, LAB_G, DLV, SHOOT_COMMON, SHOOT.format("포털"), "작업/2026-01-01_시험/스펙.md", "작업/2026-01-01_정리됨/기록.md", CLOUD, CLOUD.replace("기록", "스펙"),
                    "workspace/강의제작/제작도구/근거/2026-01-01_인계자료/인계.md"):
            f = root / rel; f.parent.mkdir(parents=True, exist_ok=True); f.write_text("가\n" * 99 + "끝\n", encoding="utf-8")

        def call(mode, ev, want, name, sid="s"):
            ev = dict({"session_id": sid, "cwd": str(root)}, **ev)
            r = subprocess.run([sys.executable, str(me), mode], input=json.dumps(ev, ensure_ascii=False).encode("utf-8"),
                               capture_output=True, env=dict(os.environ, CLAUDE_PROJECT_DIR=str(root)))
            if r.returncode != want: bad.append(f"{name}: 종료 코드 {r.returncode}, 기대 {want} · {r.stderr.decode('utf-8', 'replace')[:200]}")
            return r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
        def ed(rel, agent=None):
            return dict({"tool_name": "Edit", "tool_input": {"file_path": str(root / rel)}}, **({"agent_id": agent} if agent else {}))
        def sh(cmd): return {"tool_name": "Bash", "tool_input": {"command": cmd}}
        def rd(rel, start=1, n=100, agent=None):
            ev = {"tool_name": "Read", "tool_input": {"file_path": str(root / rel)}, "tool_response": {"type": "text", "file": {"startLine": start, "numLines": n, "totalLines": 100}}}
            return dict(ev, **({"agent_id": agent} if agent else {}))
        def says(msg, has, hasnt, name):
            if not all(h in msg for h in has) or any(h in msg for h in hasnt): bad.append(f"{name}: 막는 말이 다름 — {msg[:300]}")
        def self_edit(rel, text=None, agent=None, tool="Edit"):
            """훅을 거친 편집 한 번: PreToolUse gate → 파일 바꿈 → PostToolUse read(Edit)."""
            ev = dict(ed(rel, agent), tool_name=tool)
            call("gate", ev, 0, f"자기 편집 전 {rel}")
            if text is not None: (root / rel).parent.mkdir(parents=True, exist_ok=True); (root / rel).write_text(text, encoding="utf-8")
            call("read", dict(ev, tool_response={"filePath": str(root / rel)}), 0, f"자기 편집 뒤 {rel}")

        pptx = S + "이론/02회차/통합반_02일차.pptx"
        QUE = "workspace/강의제작/제작도구/촬영/포털/전체과정관찰_큐.json"
        graph = S + "실습/04회차/랩/04일차_실습3_그래프반영과검증"
        (root / graph).mkdir(parents=True)
        (root / graph / "입출력_계약.md").touch()
        call("gate", ed(pptx), 2, "안 읽고 덱 고치기")
        for rel in ("it/process/x.py", S + "이론/02회차/README.md", SHOOT_COMMON, "workspace/강의제작/제작도구/촬영/포털/README.md",
                    "workspace/강의제작/지침/사실표/통합반_01일차_기술사실표.md", COMMON, DECK):
            call("gate", ed(rel), 0, f"막지 않음: {rel}")
        call("read", rd(DECK, 1, 50), 0, "덱 앞 절반")
        says(call("gate", ed(pptx), 2, "덱 절반"), ["덱.md(안 읽은 줄 51-100)", "공통.md"], [], "덱 절반")
        call("read", rd(DECK, 51, 50), 0, "덱 나머지")
        says(call("gate", ed(pptx), 2, "덱만 읽고 공통.md 안 읽음"), ["공통.md(안 읽은 줄 1-100)"], ["덱.md"], "공통 빠짐")
        call("gate", sh("python deck2pptx.py a.md b.pptx"), 2, "빌드도 공통.md까지")
        call("read", rd(COMMON, 1, 99), 0, "공통 한 줄 덜")
        says(call("gate", ed(pptx), 2, "공통.md 마지막 줄 안 읽음"), ["공통.md(안 읽은 줄 100-100)"], [], "공통 끝 줄")
        call("read", rd(COMMON, 100, 1), 0, "공통 끝 줄")
        call("gate", ed(pptx), 0, "덱 · 공통 다 읽고 덱 고치기")
        call("gate", sh("python deck2pptx.py a.md b.pptx"), 0, "덱 빌드 통과")
        self_edit(COMMON, "가\n" * 99 + "고친 끝\n" + "더함\n")
        call("gate", ed(pptx), 0, "다 읽은 공통.md를 자기가 고친 뒤 통과")
        self_edit(DECK, "새 덱 문서\n" * 5, tool="Write")
        call("gate", ed(pptx), 0, "다 읽은 덱.md를 Write로 통째로 바꾼 뒤 통과")
        call("read", rd(COMMON, 1, 10, agent="a2"), 0, "a2 공통 앞 10줄")
        call("read", rd(DECK, 1, 5, agent="a2"), 0, "a2 덱")
        self_edit(COMMON, "가\n" * 99 + "a2가 고친 끝\n", agent="a2")
        says(call("gate", ed(pptx, "a2"), 2, "덜 읽고 고친 공통.md는 옮기지 않음"), ["공통.md(안 읽은 줄 1-100)"], [], "덜 읽은 자기 편집")
        (root / COMMON).write_text("가\n" * 99 + "끝\n", encoding="utf-8")
        says(call("gate", ed(pptx), 2, "다른 세션이 공통.md를 고친 뒤 막힘"), ["공통.md(안 읽은 줄 1-100)"], [], "다른 세션 편집")
        call("read", rd(COMMON), 0, "다른 세션 판 다시 읽기")
        call("gate", ed(pptx), 0, "다시 읽으면 통과")
        (root / COMMON).write_text("짧아짐\n" * 31, encoding="utf-8")
        says(call("gate", ed(pptx), 2, "공통.md가 바뀌면 다시 읽어야 함"), ["공통.md(안 읽은 줄 1-31)"], ["100", "덱.md"], "바뀐 판은 그 판 줄 수로")
        call("read", rd(COMMON, 1, 31), 0, "바뀐 공통 다시 읽기")
        call("gate", ed(pptx), 0, "바뀐 판을 다 읽으면 통과")
        (root / COMMON).write_text("가\n" * 99 + "끝\n", encoding="utf-8")
        call("read", rd(COMMON), 0, "공통 원래 판 다시 읽기")
        call("gate", ed(pptx, "a1"), 2, "서브에이전트는 따로 센다")
        call("read", rd(SCRIPT, agent="a1"), 0, "a1 대본 읽기")
        call("read", rd(COMMON, agent="a1"), 0, "a1 공통 읽기")
        call("gate", ed(pptx, "a1"), 0, "PPTX 노트는 대본 + 공통으로도 통과")
        call("gate", ed(S + "이론_오프라인/02회차/x.pptx", "a1"), 2, "오프라인 덱은 덱 문서")
        says(call("gate", ed("workspace/강의제작/제작도구/배포/클래스룸.js", "a1"), 2, "배포 도구"), ["배포.md"], [], "배포 도구는 배포 문서")
        call("read", rd(DLV, agent="a1"), 0, "a1 배포 읽기")
        call("gate", ed("workspace/강의제작/제작도구/배포/클래스룸.js", "a1"), 0, "배포 + 공통이면 배포 도구 통과")
        call("read", rd(VIDEO, 1, 40), 0, "영상 잘린 읽기")
        call("gate", sh("python 강의영상.py out s.md"), 2, "잘린 만큼만 세어 영상 빌드 막힘")
        call("read", {"tool_name": "Read", "tool_input": {"file_path": str(root / VIDEO)}, "tool_response": "문자열"}, 1, "범위를 모르는 응답은 실패로 알림")
        call("gate", sh("python 강의영상.py out s.md --dry"), 0, "--dry는 막지 않음")
        for cmd in ("python 강의영상.py out s.md && du -h out", "PYTHONUTF8=1 .venv314/Scripts/python.exe tools/video/강조표시.py a b c",
                    '"C:/x y/.venv314/Scripts/python.exe" "tools/video/강조표시.py" a b c'):
            call("gate", sh(cmd), 2, f"빌드 막음: {cmd!r}")
        for cmd in ("echo 강의영상.py; git log --grep 강조표시.py", "grep -n x 재편검사.py 강의영상.py", 'python workspace/동기화.py commit "m" --만 tools/video/강조표시.py'):
            call("gate", sh(cmd), 0, f"이름만 나온 명령은 막지 않음: {cmd!r}")
        call("read", rd(VIDEO, 41, 60), 0, "영상 나머지")
        says(call("gate", ed(QUE), 2, "촬영: 영상만 읽음"), [SHOOT_COMMON, SHOOT.format("포털")], [VIDEO], "촬영 README · 촬영준비")
        call("read", rd(SHOOT_COMMON), 0, "촬영 README")
        says(call("gate", ed(QUE), 2, "촬영: 촬영준비 남음"), [SHOOT.format("포털")], [SHOOT_COMMON], "촬영준비만")
        call("gate", ed("workspace/강의제작/제작도구/촬영/bpmn/촬영준비.md"), 0, "새 도구 촬영준비는 영상 + README로 만든다")
        call("read", rd(SHOOT.format("포털")), 0, "촬영준비")
        call("gate", ed(QUE), 0, "촬영 통과")
        call("gate", ed(S + "실습/02회차/대본/05_실습.md"), 0, "실습 대본은 영상 문서")
        call("gate", ed("workspace/강의제작/제작도구/촬영/포털/학생가이드_원고.md"), 2, "가이드 재료는 가이드 문서")
        call("gate", ed(S + "실습/01회차/랩/x/images/n.png"), 2, "실습 사진은 가이드 문서")
        for package in (graph + ".zip", S + "실습/01회차/오프라인1_가이드.zip"):
            says(call("gate", ed(package), 2, "학생 ZIP"), [GD], [LAB_G], "배포 묶음은 가이드")
        call("read", rd(GD), 0, "가이드")
        call("gate", ed(graph + ".zip"), 0, "가이드 읽고 학생 ZIP")
        call("gate", ed(S + "실습/09회차/랩/09일차_실습1_승인절차작도/START.md"), 0, "도구 실습 START는 가이드로 가능")
        for member in ("START.md", "입출력_계약.md", "입력/모델/graph.json", "결과/정한_것.csv", "입력/README.md"):
            says(call("gate", ed(graph + "/" + member), 2, member), [LAB_G], [GD], "코딩 랩 시작본·자료")
        call("gate", ed(S + "실습/01회차/랩/x/images/n.png"), 0, "가이드 + 공통이면 사진 통과")
        call("gate", ed(S + "실습/03회차/랩/x/main.py"), 2, "랩 코드는 코딩랩 문서")
        call("read", rd(LAB_G), 0, "코딩 랩")
        call("gate", ed(graph + "/입력/모델/graph.json"), 0, "코딩랩 읽고 시작본의 모델 수정")
        SPEC_T = "작업/2026-01-01_시험/스펙.md"
        (root / SPEC_T).write_text("# 시험\n\n- 시작: 2026-01-01 · 상태: 진행\n", encoding="utf-8")
        call("read", rd(SPEC_T), 0, "스펙")
        self_edit(SPEC_T, "# 시험\n\n- 시작: 2026-01-01 · 상태: 진행\n- 한 줄 고침\n")
        call("read", rd("작업/2026-01-01_정리됨/기록.md"), 0, "곧 지울 기록")
        self_edit("작업/2026-01-01_정리됨/기록.md")
        call("read", rd(CLOUD), 0, "클라우드 작업 폴더의 기록")
        self_edit(CLOUD)
        REF = "작업/2026-01-01_참고/기록.md"
        (root / REF).parent.mkdir(parents=True); (root / REF).write_text("가\n", encoding="utf-8")
        call("read", rd(REF, 1, 1), 0, "참고로만 연 다른 작업 폴더의 기록")
        old = time.time() - 5 * 86400
        for f in ((root / REF), (root / REF).parent): os.utime(f, (old, old))
        out = call("compact", {"source": "compact"}, 0, "요약")
        for h in (SHOOT_COMMON, "이 세션이 편집한 작업: 작업/2026-01-01_시험 (상태 진행)", "이 세션이 편집한 작업: workspace/강의제작/제작도구/근거/2026-01-01_클라우드 (상태 꼴 틀림",
                  "그 밖의 열린 작업 폴더 2개(그중 3일 넘게 바뀌지 않은 오래됨 1개)"):
            if h not in out: bad.append(f"요약 안내에 「{h}」가 없음: {out[:400]}")
        for h in ("2026-01-01_참고", "2026-01-01_인계자료", "읽던 문서: 작업/"):   # 편집하지 않은 폴더는 이름을 찍지 않고 개수로만(근거/의 스펙 없는 폴더도 센다)
            if h in out: bad.append(f"요약 안내가 편집하지 않은 작업 폴더 「{h}」를 찍음: {out[:400]}")
        (root / "작업/2026-01-01_정리됨/기록.md").unlink()
        call("gate", ed(pptx), 2, "요약 뒤에는 다시 막힘")
        call("read", rd(DECK), 0, "요약 뒤 덱")
        call("read", rd(COMMON), 0, "요약 뒤 공통")
        says(call("gate", ed(pptx), 2, "요약 뒤 스펙도 다시"), [SPEC_T, CLOUD, CLOUD.replace("기록", "스펙")], ["정리됨", "참고"], "요약 뒤 편집한 폴더의 스펙 · 기록만")
        call("read", rd("작업/2026-01-01_시험/스펙.md"), 0, "요약 뒤 스펙")
        call("read", rd(CLOUD), 0, "요약 뒤 클라우드 기록")
        call("read", rd(CLOUD.replace("기록", "스펙")), 0, "요약 뒤 클라우드 스펙")
        call("gate", ed(pptx), 0, "요약 뒤 다 읽으면 통과(지운 폴더 기록은 요구 안 함)")
        call("gate", {"tool_name": "Agent", "tool_input": {"model": "fable", "prompt": "x"}}, 2, "fable 호출")
        call("gate", {"tool_name": "Agent", "tool_input": {"model": "opus", "prompt": "x"}}, 0, "opus 호출")
    print("\n".join(bad) if bad else "자가시험 통과")
    return 1 if bad else 0


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    if mode == "selftest": return selftest()
    fn = {"compact": on_compact, "read": on_read, "gate": on_gate}.get(mode)
    if not fn: sys.exit(f"guide_gate.py: 모르는 동작 「{mode}」 — compact · read · gate · selftest")
    ev = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    return fn(os.environ.get("CLAUDE_PROJECT_DIR") or ev.get("cwd") or ".", ev)


if __name__ == "__main__":
    sys.exit(main())
