"""포털 화면의 원문 id(fm:… · cause:… · rule:… · skill:… 등) → 이름 사전 it/portal/www/names.json 을 만든다.

    PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/개발/scripts/portal_names.py            # → it/portal/www/names.json
    PYTHONUTF8=1 .venv314/Scripts/python.exe workspace/개발/scripts/portal_names.py --check    # 쓰지 않고 지금 파일과 같은지만(다르면 종료 코드 1)

어떤 id 를 담는가는 고정 재료가 정한다 — 그래서 누가 언제 돌려도 같은 파일이 나온다(테스트 test_portal_names 가 시작이 끝난 그래프로 잰다):
  ① 구조판 시드: kg-seed 가 넣는 파일(it/neo4j/seed.sh 의 SEED_FILES)에 글자로 적힌 id
  ② 수업 지식: 강사 서명 추출 묶음(it/process/procsvc/course_extractions.json) 중 시작 7단계가 넣는 문서의 고장 유형 · 원인 · 근거 · 규칙 id 와
     절차의 조치 방법 id(procsvc.kgadmin.skill_id)
  ③ 업무 스킬: enterprise-sim 의 SKILL_NAMES(그래프에 없다)
이름은 그 id 의 그래프 노드(이 PC 의 수업 그래프)에서 읽는다 — Rule 은 name 이 없어 annotation(TESTS 에서 만든 규칙 설명). 실행 기록(스키마 record 층 ·
FlowNode), 학생이 만든 노드, 적재마다 바뀌는 문서 출처 id(ks:manual:…)는 고정 재료에 없으므로 들어가지 않는다. 재료의 id 가 그래프에 없으면
수업 시작이 끝난 그래프가 아니므로 까닭과 함께 멈춘다. 포털(ui.js UI.loadNames)은 응답에 이름이 없을 때만 이 사전을 쓴다.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "it" / "process"), str(ROOT / "common"), str(ROOT / "it" / "enterprise-sim"), str(Path(__file__).resolve().parent)]

OUT = ROOT / "it" / "portal" / "www" / "names.json"
V2 = ROOT / "it" / "neo4j" / "v2"
BUNDLE = ROOT / "it" / "process" / "procsvc" / "course_extractions.json"
_ID = re.compile(r"'([a-z][a-z0-9]*:[A-Za-z0-9][A-Za-z0-9_.%:-]*)'")


def seed_files() -> list[Path]:
    """kg-seed 가 넣는 파일 — seed.sh 의 SEED_FILES 줄이 정본이다."""
    m = re.search(r"^SEED_FILES=\(([^)]*)\)", (ROOT / "it" / "neo4j" / "seed.sh").read_text(encoding="utf-8"), re.M)
    if not m:
        raise RuntimeError("it/neo4j/seed.sh 에 SEED_FILES=(…) 줄이 없습니다 — 시드 파일 목록을 읽지 못했습니다")
    return [V2 / f for f in m.group(1).split()]


def start_documents(bundle: Path | None = None) -> list[dict]:
    """서명 묶음 중 시작 7단계(scripts/class_knowledge.py ensure)가 넣는 문서 — 그 파일의 ORDER(HM-8 · PM-02 · PR-07)가 정본이다.
    묶음의 다른 문서(HI-01 보충 자료)는 학생이 실습 중에 넣으므로 시작이 끝난 그래프에 없다."""
    from class_knowledge import ORDER
    docs = json.loads((bundle or BUNDLE).read_text(encoding="utf-8"))["payload"]["documents"].values()
    return [d for d in docs if d["filename"].split("_")[0] in ORDER]


def seed_statements(text: str) -> list[str]:
    """시드 파일의 문장(주석 줄 빼고 「;」로 나눔)."""
    body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))
    return [st for st in body.split(";") if st.strip()]


def seed_ids() -> set[str]:
    """시드가 만드는(MERGE · CREATE) 문장에 적힌 id — 옛 노드를 지우는 문장(MATCH … DETACH DELETE — 만들기 없음)의 id는 넣지 않는다."""
    return {m for f in seed_files() for st in seed_statements(f.read_text(encoding="utf-8"))
            if re.search(r"\b(MERGE|CREATE)\b", st) for m in _ID.findall(st)}


def material_ids() -> set[str]:
    """고정 재료(시드 파일 · 서명 묶음의 시작 문서)가 정한 id."""
    from procsvc.kgadmin import skill_id
    ids = seed_ids()
    for doc in start_documents():
        k = doc["proposal"]["knowledge"]
        ids |= {x["id"] for kind in ("failure_modes", "causes", "evidence", "rules") for x in k.get(kind) or []}
        ids |= {skill_id(p["id"]) for p in doc["proposal"]["procedures"]}
    return ids


def skipped_labels() -> list[str]:
    """이름 사전에 넣지 않는 레이블: 스키마의 실행 기록(record 층)과 흐름 노드(FlowNode — 화면에 id 로 나오지 않음)."""
    schema = json.loads((V2 / "schema.json").read_text(encoding="utf-8"))
    return sorted({c["name"] for c in schema["classes"] if c["layer"] == "record"} | {"FlowNode"})


QUERY = """
MATCH (n) WHERE n.id IN $ids AND none(l IN labels(n) WHERE l IN $skip)
RETURN n.id AS id, CASE WHEN n.name IS NOT NULL AND n.name <> '' THEN n.name
                        WHEN 'Rule' IN labels(n) THEN n.annotation END AS name
"""


#: 화면 이름이 그래프 이름과 다른 id → 화면 이름(UIUX 화면 명칭 정책). 열쇠는 id 라 시드가 이름을 바꿔도 맞는다 — 고정 재료에 없는 id 가
#: 열쇠면 build 가 멈춘다(옛 이름을 열쇠로 써 시드가 바뀐 뒤 조용히 안 맞았다 — 넘김 「FW → FT」). 그래프 · 업무 원문은 고치지 않는다.
PLAIN = {
    "sys:scada": "설비 제어", "sys:historian": "센서 기록", "sys:process": "업무 처리", "sys:cep": "센서 경보 감지기",
    "sys:mes": "생산 관리", "sys:erp": "구매 · 재고 관리", "sys:cmms": "정비 관리", "sys:scm": "공급망 관리", "sys:qms": "품질 시스템",
    "ks:strategy-map": "경남유압 성과 목표", "in:plc-mode": "설비 운전 모드", "in:plc-state": "설비 상태",
    "actr:pump-drive": "펌프 구동부", "actr:fan-drive": "쿨러 팬 구동부",
}
#: 이름 · 설명 문장 속 낱말 바꾸기(같은 정책) — 차례대로. 바꿀 것이 하나도 없는 줄이면 build 가 멈춘다(시드 문장이 바뀌어 낡은 줄).
WORDS = [
    ("정비 작업지시", "정비 오더"),
    ("high 1 · medium 0.6 · low 0.3", "높음 1 · 중간 0.6 · 낮음 0.3"),
]


def display_names(names: dict[str, str]) -> dict[str, str]:
    """그래프 이름 → 화면 이름: PLAIN 의 id 는 그 이름, 나머지는 WORDS 낱말 바꾸기. 낡은 열쇠 · 낡은 줄은 까닭과 함께 멈춘다."""
    stale = sorted(set(PLAIN) - set(names))
    if stale:
        raise RuntimeError(f"portal_names.PLAIN 의 id {stale} 가 고정 재료(시드 · 수업 지식)에 없습니다 — 시드에서 지운 id 면 표에서 지웁니다")
    out, used = {}, set()
    for i, label in names.items():
        if i in PLAIN:
            out[i] = PLAIN[i]
            continue
        for old, new in WORDS:
            if old in label:
                label = label.replace(old, new)
                used.add(old)
        out[i] = label
    unused = [old for old, _ in WORDS if old not in used]
    if unused:
        raise RuntimeError(f"portal_names.WORDS 의 {unused} 가 어느 이름에도 없습니다 — 시드 문장이 바뀌었으면 표를 지금 문장에 맞춥니다")
    return out


def build(session) -> dict[str, str]:
    """session = Neo4j 세션(run 이 있는 것). 고정 재료의 id → 화면 이름."""
    ids = material_ids()
    rows = {r["id"]: r["name"] for r in session.run(QUERY, ids=sorted(ids), skip=skipped_labels())}
    present = {r["id"] for r in session.run("MATCH (n) WHERE n.id IN $ids RETURN DISTINCT n.id AS id", ids=sorted(ids))}
    seeds = seed_ids()
    missing_seed = sorted(i for i in seeds if i not in present)
    if missing_seed:
        raise RuntimeError(f"시드가 만드는 id {len(missing_seed)}개가 그래프에 없습니다(예 {missing_seed[:5]}) — 지금 시드(kg-seed)를 넣은 그래프에서 돌리세요")
    missing = sorted(i for i in ids - seeds if i not in present)
    if missing:
        raise RuntimeError(f"수업 지식 id {len(missing)}개가 그래프에 없습니다(예 {missing[:5]}) — 시작(class_knowledge.py ensure)이 끝난 수업 그래프에서 돌리세요")
    names = {i: n for i, n in rows.items() if n and n != i}
    from entsim.state import SKILL_NAMES                                  # 업무 스킬은 그래프에 없고 enterprise-sim 이 정본이다
    for sid, label in SKILL_NAMES.items():
        names.setdefault(sid, label)
    return dict(sorted(display_names(names).items()))


def render(names: dict[str, str]) -> str:
    return json.dumps(names, ensure_ascii=False, indent=0, sort_keys=True) + "\n"


def main(argv=None) -> int:
    from hydcommon import graphdb
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--check", action="store_true", help="파일을 쓰지 않고 지금 파일과 같은지만 본다")
    a = ap.parse_args(argv)
    from ontology_v2 import stack_graph_env
    stack_graph_env()   # 이 PC 수업 스택의 바깥 포트 · compose 의 neo4j 인증(환경에 있으면 그대로)
    with graphdb.connect() as driver, driver.session() as s:
        text = render(build(s))
    if a.check:
        same = Path(a.out).exists() and Path(a.out).read_text(encoding="utf-8") == text
        print(f"{a.out}: {'생성기 결과와 같음' if same else '생성기 결과와 다름 — 다시 만드세요'}")
        return 0 if same else 1
    Path(a.out).write_text(text, encoding="utf-8")
    print(f"wrote {a.out} ({len(json.loads(text))} 이름)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
