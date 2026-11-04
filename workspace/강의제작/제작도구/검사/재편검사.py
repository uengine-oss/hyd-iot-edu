"""지침 일곱(공통 + 일 여섯)의 꼴과 규칙 문서 전체의 끊긴 경로를 잰다. 오류마다 파일:줄, 하나라도 있으면 종료 1.
언제: 지침 · CLAUDE.md · AGENTS.md · workspace/README.md · 스킬을 고친 뒤(`동기화.py commit`이 그런 커밋마다 부른다).
명령: <py> workspace/강의제작/제작도구/검사/재편검사.py [--자가시험]
"""
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
GUIDES = "workspace/강의제작/지침"
LETTER = {"공통": "C", "실라버스": "L", "덱": "D", "대본": "S", "영상": "V", "코딩랩": "K", "가이드": "P"}
WORKS = tuple(d for d in LETTER if d != "공통")
SECTIONS = ["반드시", "길", "자료", "함정"]
LIMIT = {"공통": 8000, "영상": 26000}          # 그 밖의 일 문서는 20,000자 — 읽기 쉬운 문장이 먼저, 상한은 다시 부풀지 않게만
MAX_RULES = 15
WEAK = re.compile(r"가능하면|적절히|충분히|필요 ?시(?:에)?(?![가-힣])")
OLD_NO = re.compile(r"[A-Z]규-\d+|[A-Z](?:요|목|맥)-\d+")
BT_OLD = re.compile(r"`[A-Z]-\d+`")
NEW_REF = re.compile(r"(?<![A-Za-z0-9_\-:./])([CLDSVKP])-(\d+)(?![0-9A-Za-z\-_]|\.\d)")
RULE = re.compile(r"^(\d+)\. (.*)$")
MD_LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
BT_PATH = re.compile(r"`((?:workspace|\.claude|\.codex)/[^`\s]*)`")
PLACEHOLDER = re.compile(r"[<>{}*…|]|NN|\.\.\.")


def rules(p):
    """`## 반드시`의 규칙: [(번호, 줄, 글, [세부 줄])]. 절이 없으면 빈 목록."""
    out, inside = [], False
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("## "):
            inside = line[3:].strip() == "반드시"
            continue
        if not inside or not line.strip():
            continue
        m = RULE.match(line)
        if m:
            out.append((int(m[1]), i, m[2], []))
        elif out:
            out[-1][3].append((i, line))
        else:
            out.append((None, i, line, []))
    return out


def rule_ids(guide_dir, work):
    """그 일의 판정 대상 규칙 번호: 그 일 문서의 규칙 + 공통 규칙(C-n). 일이 「공통」이면 공통만."""
    names = [work] + ([] if work == "공통" else ["공통"])
    return [f"{LETTER[d]}-{n}" for d in names for n, *_ in rules(guide_dir / f"{d}.md") if n is not None]


def check_guide(p, d, errs):
    text = p.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# "):
        errs.append(f"{p}:1: 첫 줄이 `# <일 이름>`이 아님")
    heads = [(i, l[3:].strip()) for i, l in enumerate(lines, 1) if l.startswith("## ")]
    names = [h for _, h in heads]
    if d == "공통":
        if names[:1] != ["반드시"] or [s for s in SECTIONS if s in names] != names:
            errs.append(f"{p}: 절이 `## 반드시`로 시작해 {SECTIONS} 순서 안에 있지 않음 — {names}")
    elif names != SECTIONS:
        errs.append(f"{p}: 절이 정확히 {SECTIONS}가 아님 — {names}")
    limit = LIMIT.get(d, 20000)
    if len(text) > limit:
        errs.append(f"{p}: {len(text):,}자 — 상한 {limit:,}자")
    found = rules(p)
    if not found:
        errs.append(f"{p}: `## 반드시`에 번호 규칙이 없음")
    if len(found) > MAX_RULES:
        errs.append(f"{p}: 규칙 {len(found)}개 — 상한 {MAX_RULES}개")
    for k, (n, i, body, details) in enumerate(found, 1):
        if n is None:
            errs.append(f"{p}:{i}: `## 반드시`에 번호 규칙 밖의 줄 — 「{body[:40]}」")
            continue
        if n != k:
            errs.append(f"{p}:{i}: 규칙 번호 {n} — {k}여야 한다(1부터 빈틈 · 겹침 없이)")
        m = re.match(r"\*\*([A-Z])-(\d+)\. [^*].*?\*\* — 판정: \S", body)
        if not m:
            errs.append(f"{p}:{i}: 규칙 꼴이 `{n}. **{LETTER[d]}-{n}. 규칙** — 판정: …`이 아님")
        elif (m[1], int(m[2])) != (LETTER[d], n):
            errs.append(f"{p}:{i}: 규칙 ID {m[1]}-{m[2]} — 목록 번호 · 문서 글자로 {LETTER[d]}-{n}이어야 한다")
        if len(details) > 5:
            errs.append(f"{p}:{i}: 세부 {len(details)}줄 — 5줄까지")
        for j, l in details:
            if l.startswith("#"):
                errs.append(f"{p}:{j}: `## 반드시` 안 소제목 — 규칙 목록만 둔다")
            elif not l.startswith(("   ", "\t")):
                errs.append(f"{p}:{j}: 규칙 세부가 들여쓰지 않음")
    for i, l in enumerate(lines, 1):
        for m in WEAK.finditer(l):
            errs.append(f"{p}:{i}: 약한 말 「{m[0]}」")
        for m in OLD_NO.finditer(l):
            errs.append(f"{p}:{i}: 옛 번호 「{m[0]}」")
        for m in BT_OLD.finditer(l):
            errs.append(f"{p}:{i}: 백틱 안 옛 번호 {m[0]}")


def check_refs(guide_dir, errs):
    """문서 안의 규칙 번호(D-3 · C-2)가 그 문서의 실제 규칙을 가리킨다."""
    have = {LETTER[d]: {n for n, *_ in rules(guide_dir / f"{d}.md") if n} for d in LETTER if (guide_dir / f"{d}.md").exists()}
    for d in LETTER:
        p = guide_dir / f"{d}.md"
        if not p.exists():
            continue
        for i, l in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for m in NEW_REF.finditer(BT_OLD.sub("", l)):
                if m[1] in have and int(m[2]) not in have[m[1]]:
                    errs.append(f"{p}:{i}: 없는 규칙 {m[0]}을 가리킴")


def check_paths(p, root, errs):
    """마크다운 링크(문서 기준)와 백틱 안 저장소 경로(자리표시 없는 것)가 실제로 있다."""
    for i, l in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        for t in MD_LINK.findall(re.sub(r"`[^`]*`", "", l)):      # 백틱 안은 보기 글이다
            if not re.match(r"^[a-z]+:", t) and "<" not in t and not (p.parent / t).resolve().exists():
                errs.append(f"{p}:{i}: 끊긴 링크 {t}")
        for t in BT_PATH.findall(l):
            if not PLACEHOLDER.search(t) and not (root / t.rstrip("/")).exists():
                errs.append(f"{p}:{i}: 없는 경로 {t}")


def run(root):
    errs, guide_dir = [], root / GUIDES
    for d in LETTER:
        p = guide_dir / f"{d}.md"
        if not p.exists():
            errs.append(f"{p}: 문서 없음")
            continue
        check_guide(p, d, errs)
        check_paths(p, root, errs)
    check_refs(guide_dir, errs)
    others = [root / n for n in ("CLAUDE.md", "AGENTS.md", "workspace/README.md")] + sorted((root / ".claude/skills").rglob("*.md"))
    for p in others:
        if p.exists():
            check_paths(p, root, errs)
    return errs


def selftest():
    """바른 사본이 통과하고, 하나씩 깨뜨린 사본이 그 오류로 잡히는지 본다."""
    tmp = Path(tempfile.mkdtemp())
    g = tmp / GUIDES
    g.mkdir(parents=True)
    (tmp / ".claude/skills/hyd-x").mkdir(parents=True)

    def doc(d, n=2):
        L = LETTER[d]
        body = f"# {d}\n\n## 반드시\n" + "".join(f"{k}. **{LETTER[d]}-{k}. {d} 규칙 {k}** — 판정: 본다 {k}\n" for k in range(1, n + 1))
        body += "   세부 숫자 3 · 값은 `P-PMP-SEAL`처럼 · HM-8.1 · 필요 시간 10분\n"
        if d == "공통":
            return body
        return body + f"\n## 길\n1. 만든다 — `workspace/README.md` · {L}-1 · C-2\n\n## 자료\n| 무엇 | 경로 |\n|---|---|\n| 공통 | [공통](공통.md) |\n\n## 함정\n- 한 줄\n"

    def write_all():
        for d in LETTER:
            (g / f"{d}.md").write_text(doc(d), encoding="utf-8")
        (tmp / "workspace/README.md").write_text("`workspace/강의제작/지침/덱.md`\n", encoding="utf-8")
        (tmp / "CLAUDE.md").write_text("`workspace/README.md` · `workspace/<날짜>/` · `작업/x`\n", encoding="utf-8")
        (tmp / "AGENTS.md").write_text("[색인](workspace/README.md)\n", encoding="utf-8")
        (tmp / ".claude/skills/hyd-x/SKILL.md").write_text("`.claude/skills/hyd-x/SKILL.md`\n", encoding="utf-8")

    cases = []

    def check(name, change, expect):
        write_all()
        change()
        e = run(tmp)
        hit = [x for x in e if expect in x] if expect else e
        cases.append((name, bool(hit) if expect else not e, (hit or e)[:2]))

    def sub(rel, a, b):
        def f():
            p = tmp / rel
            t = p.read_text(encoding="utf-8")
            if a not in t:
                raise SystemExit(f"자가시험 준비: {rel}에 「{a}」 없음")
            p.write_text(t.replace(a, b, 1), encoding="utf-8")
        return f

    D = f"{GUIDES}/덱.md"
    check("바른 사본 통과", lambda: None, None)
    check("절 이름이 틀림", sub(D, "## 길", "## 작업 요령"), "절이 정확히")
    check("절이 하나 더", sub(D, "## 함정", "## 가치\n\n## 함정"), "절이 정확히")
    check("절 순서가 틀림", lambda: (g / "덱.md").write_text(doc("덱").replace("## 자료", "## 임시").replace("## 함정", "## 자료").replace("## 임시", "## 함정"), encoding="utf-8"), "절이 정확히")
    check("공통이 반드시로 시작하지 않음", sub(f"{GUIDES}/공통.md", "## 반드시", "## 목적\n\n## 반드시"), "`## 반드시`로 시작")
    check("규칙 번호 빈틈", sub(D, "2. **D-2. 덱 규칙 2**", "3. **D-3. 덱 규칙 2**"), "규칙 번호 3")
    check("규칙 번호 겹침", sub(D, "2. **D-2. 덱 규칙 2**", "1. **D-1. 덱 규칙 2**"), "규칙 번호 1")
    check("판정 없는 규칙", sub(D, "** — 판정: 본다 2", "**"), "규칙 꼴이")
    check("굵은 글씨 없는 규칙", sub(D, "**D-2. 덱 규칙 2**", "D-2. 덱 규칙 2"), "규칙 꼴이")
    check("굵게 안 ID가 빠짐", sub(D, "**D-2. 덱", "**덱"), "규칙 꼴이")
    check("굵게 안 ID가 목록 번호와 다름", sub(D, "**D-2. 덱", "**D-3. 덱"), "규칙 ID D-3")
    check("굵게 안 ID 글자가 문서와 다름", sub(D, "**D-2. 덱", "**S-2. 덱"), "규칙 ID S-2")
    check("세부 6줄", sub(D, "   세부", "   가\n   나\n   다\n   라\n   마\n   세부"), "세부 6줄")
    check("세부를 들여쓰지 않음", sub(D, "   세부", "세부"), "들여쓰지 않음")
    check("규칙 16개", lambda: (g / "가이드.md").write_text(doc("가이드", 16), encoding="utf-8"), "규칙 16개")
    check("일 문서 20,000자 넘음", sub(D, "## 함정\n- 한 줄", "## 함정\n- " + "가" * 20000), "상한 20,000자")
    check("영상은 26,000자까지", sub(f"{GUIDES}/영상.md", "## 함정\n- 한 줄", "## 함정\n- " + "가" * 25000), None)
    check("공통 8,000자 넘음", sub(f"{GUIDES}/공통.md", "   세부", "   " + "가" * 8000), "상한 8,000자")
    for w in ("가능하면", "적절히", "충분히", "필요시", "필요 시"):
        check(f"약한 말 {w}", sub(D, "- 한 줄", f"- {w} 본다"), "약한 말")
    check("「필요 시간」은 약한 말이 아님", lambda: None, None)
    check("옛 규칙 번호 S규-2", sub(D, "- 한 줄", "- S규-2를 본다"), "옛 번호 「S규-2」")
    check("옛 요령 번호 V요-3", sub(D, "- 한 줄", "- V요-3 그대로"), "옛 번호 「V요-3」")
    check("백틱 안 옛 번호", sub(D, "- 한 줄", "- 본다 `S-37`"), "백틱 안 옛 번호")
    check("없는 규칙 번호를 가리킴", sub(D, "- 한 줄", "- D-9를 본다"), "없는 규칙 D-9")
    check("없는 공통 규칙을 가리킴", sub(D, "- 한 줄", "- C-7을 본다"), "없는 규칙 C-7")
    check("끊긴 링크", sub(D, "[공통](공통.md)", "[공통](없음.md)"), "끊긴 링크 없음.md")
    check("백틱 안 링크 꼴은 보기 글", sub(D, "- 한 줄", "- `[열기](blob)` 꼴"), None)
    check("반드시 안 소제목", sub(D, "2. **D-2.", "### 이론\n2. **D-2."), "안 소제목")
    check("없는 백틱 경로", sub(D, "`workspace/README.md`", "`workspace/없는.md`"), "없는 경로 workspace/없는.md")
    check("CLAUDE.md의 끊긴 경로", sub("CLAUDE.md", "`workspace/README.md`", "`workspace/옛.md`"), "CLAUDE.md:1: 없는 경로")
    check("AGENTS.md의 끊긴 링크", sub("AGENTS.md", "(workspace/README.md)", "(workspace/옛.md)"), "AGENTS.md:1: 끊긴 링크")
    check("스킬의 끊긴 경로", sub(".claude/skills/hyd-x/SKILL.md", "SKILL.md`", "옛.md`"), "SKILL.md:1: 없는 경로")
    check("README의 끊긴 경로", sub("workspace/README.md", "덱.md", "옛덱.md"), "README.md:1: 없는 경로")
    check("지침 하나가 없음", lambda: (g / "코딩랩.md").unlink(), "코딩랩.md: 문서 없음")
    write_all()
    ids = rule_ids(g, "덱")
    cases.append(("판정 대상 = 그 일 규칙 + 공통 규칙", ids == ["D-1", "D-2", "C-1", "C-2"], ids))
    shutil.rmtree(tmp)
    for name, ok, detail in cases:
        print(f"{'통과' if ok else '실패'}: {name}" + ("" if ok else f" — {detail}"))
    bad = sum(not c[1] for c in cases)
    print(f"자가시험 {len(cases)}건 · 실패 {bad}")
    return bad == 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1:] == ["--자가시험"]:
        sys.exit(0 if selftest() else 1)
    if sys.argv[1:]:
        sys.exit(__doc__)
    found = run(ROOT)
    print("\n".join(found + [f"오류 {len(found)}"]))
    sys.exit(1 if found else 0)
