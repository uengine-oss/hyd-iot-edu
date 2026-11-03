"""지침을 읽기 전에는 그 산출물을 고치지 못하게 한다(hyd-task 2절을 안내가 아니라 동작으로). Claude Code 훅이 부른다.

    guide_gate.py compact   SessionStart(compact): 이 세션이 읽은 기록을 비우고, 다시 읽을 문서를 대화에 넣는다
    guide_gate.py read      PostToolUse(Read): 지침 · 촬영준비 · 스펙 · 기록을 실제로 읽은 줄 범위를 적는다
    guide_gate.py gate      PreToolUse(Edit · Write · NotebookEdit · Bash · PowerShell · Agent): 안 읽었으면 종료 코드 2로 막는다
    guide_gate.py selftest  일부러 깨뜨린 입력으로 위 동작이 잡는지 확인한다

- 상태: 작업/_훅/<세션>__<에이전트>.json(git 밖). 서브에이전트는 따로 센다 — 맥락이 따로이기 때문이다.
- 막는 것: Edit · Write · NotebookEdit로 산출물 · 제작 재료를 고치는 것, `python` 등으로 직접 부른 덱 · 영상 빌드, fable 모델 호출.
  셸 변수로 부른 실행 · sed · 리다이렉션 · 파이썬 스크립트의 직접 쓰기 · `만들기.sh`는 잡지 못한다.
- 경로만으로 지침이 갈리지 않는 자리는 막지 않는다. 틀린 문서를 강제하는 것이 안 막는 것보다 나쁘다.
"""
import json, os, re, subprocess, sys, tempfile, time, unicodedata
from pathlib import Path

GUIDE = "workspace/강의제작/지침/{}.md"
SHOOT = "workspace/강의제작/제작도구/촬영/{}/촬영준비.md"
TRACKED = re.compile(r"^(workspace/강의제작/지침/[^/]+\.md|workspace/강의제작/제작도구/촬영/[^/]+/촬영준비\.md|작업/[^/]+/(스펙|기록)\.md)$")
TASK_DOC = re.compile(r"^작업/[^/]+/(스펙|기록)\.md$")
RUN = r"(?<![\w.])(?:python\S*|py)[\"']?\s+(?:-\S+\s+)*[\"']?[^\s\"']*"   # 이름이 글에 나온 것(echo · git diff · 커밋 경로)이 아니라 파이썬의 첫 인자로 실행할 때만
BUILD = [(re.compile(RUN + r"deck2pptx\.py"), "덱"), (re.compile(RUN + r"(강의영상|강조표시)\.py"), "영상")]
READ_ONLY = re.compile(r"(--dry|--check|--help|-h)(\s|$)")
GUIDE_TOOL = re.compile(r"(학생가이드|build_student_guide|build_전체과정_학생가이드|apply_student_guide|사진)")
DECK_OR_SCRIPT = (GUIDE.format("덱"), GUIDE.format("대본"))   # 노트는 대본 작업도 고친다 — 둘 중 하나면 된다


def norm(path, root):
    """저장소 루트 기준 경로로. 저장소 밖이면 None."""
    p = unicodedata.normalize("NFC", str(path)).replace("\\", "/")
    r = unicodedata.normalize("NFC", str(root)).replace("\\", "/").rstrip("/")
    if p.lower().startswith(r.lower() + "/"): return p[len(r) + 1:]
    return None if re.match(r"^([A-Za-z]:|/)", p) else p.removeprefix("./")


def guides_for(rel, root):
    """이 경로를 고치려면 읽어야 할 지침들. 한 칸이 튜플이면 그중 하나를 읽으면 된다. 해당 없으면 빈 목록."""
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


def missing(root, rel, ranges):
    """읽지 않은 줄 범위 문자열들. 파일이 없으면 그 사실을 돌려준다."""
    f = Path(root) / rel
    if not f.exists(): return ["파일 없음"]
    n = len(f.read_bytes().splitlines()); out, at = [], 1
    for a, b in sorted(ranges):
        if a > at: out.append(f"{at}-{a - 1}")
        at = max(at, b + 1)
    if at <= n: out.append(f"{at}-{n}")
    return out


def on_compact(root, ev):
    p = state_path(root, ev); st = load(p)
    before = sorted(set(st["읽음"]) | set(st["이전"]))
    save(p, {"읽음": {}, "이전": before})
    limit = time.time() - 7 * 86400
    for old in p.parent.glob("*.json"):
        if old.stat().st_mtime < limit: old.unlink()
    print("[요약 직후 — 작업을 잇기 전에 반드시]")
    print("대화가 요약됐다. 요약은 기준의 일부만 남긴다. 아래 문서를 Read로 처음부터 끝까지 다시 읽기 전에는 관련 산출물 편집이 막힌다.")
    for rel in before: print(f"- 이 세션이 읽던 문서: {rel}")
    for d in sorted((Path(root) / "작업").glob("[0-9]" * 4 + "-*_*")):
        spec = d / "스펙.md"
        m = re.search(r"상태: *(\S+)", spec.read_text(encoding="utf-8")) if spec.exists() else None
        print(f"- 열린 작업: 작업/{d.name} (상태 {m[1] if m else '스펙 없음'})")
    print("1. 하던 작업 폴더의 스펙.md · 기록.md를 다시 읽는다.")
    print("2. 다루는 산출물의 지침을 다시 읽는다(workspace/README.md 색인, 많아야 2개). 사실표 · 포털 기능 표는 필요한 대목만 찾아본다.")
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
        docs = {f"workspace/강의제작/지침/{d}.md" for d in ("덱", "대본", "영상", "가이드", "코딩랩")}
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
        DECK, SCRIPT, VIDEO, GD = (f"workspace/강의제작/지침/{d}.md" for d in ("덱", "대본", "영상", "가이드"))
        pptx = S + "이론/02회차/통합반_02일차.pptx"
        call("gate", ed(pptx), 2, "안 읽고 덱 고치기")
        call("gate", ed("it/process/x.py"), 0, "시스템 코드는 막지 않음")
        call("gate", ed(S + "이론/02회차/README.md"), 0, "README는 막지 않음")
        call("gate", ed("workspace/강의제작/제작도구/촬영/README.md"), 0, "촬영 README는 막지 않음")
        call("read", rd(DECK, 1, 50), 0, "앞부분 읽기")
        call("gate", ed(pptx), 2, "절반만 읽고 덱 고치기")
        call("read", rd(DECK, 51, 50), 0, "실제 줄 수까지 읽기")
        call("gate", ed(pptx), 0, "다 읽고 덱 고치기")
        call("gate", ed(pptx, "a1"), 2, "서브에이전트는 따로 센다")
        call("read", dict(rd(SCRIPT), agent_id="a1"), 0, "서브에이전트가 대본 읽기")
        call("gate", ed(pptx, "a1"), 0, "노트 작업은 대본만 읽어도 PPTX 통과")
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
        call("gate", ed(pptx), 2, "요약 뒤에는 다시 막힘")
        call("read", rd(DECK), 0, "요약 뒤 덱 다시 읽기")
        call("gate", ed(pptx), 2, "요약 뒤 스펙도 다시 읽어야 함")
        call("read", rd("작업/2026-01-01_시험/스펙.md"), 0, "요약 뒤 스펙 다시 읽기")
        call("gate", ed(pptx), 0, "정리된 폴더의 기록은 요구하지 않음")
        call("gate", {"tool_name": "Agent", "tool_input": {"model": "fable", "prompt": "x"}}, 2, "fable 호출")
        call("gate", {"tool_name": "Agent", "tool_input": {"model": "opus", "prompt": "x"}}, 0, "opus 호출")
    print("\n".join(bad) if bad else "자가시험 통과")
    return 1 if bad else 0


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    if mode == "selftest": return selftest()
    ev = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    root = os.environ.get("CLAUDE_PROJECT_DIR") or ev.get("cwd") or "."
    fn = {"compact": on_compact, "read": on_read, "gate": on_gate}.get(mode)
    if not fn: sys.exit(f"guide_gate.py: 모르는 동작 「{mode}」")
    return fn(root, ev)


if __name__ == "__main__":
    sys.exit(main())
