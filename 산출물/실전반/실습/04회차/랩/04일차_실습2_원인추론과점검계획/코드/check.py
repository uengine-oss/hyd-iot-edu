"""output/점검요청_초안.json·.md의 구조 검사(입출력_계약.md). 원인 판정의 옳고 그름은 검사하지 않는다.

    python 코드/check.py                 output/점검요청_초안.json 검사
    python 코드/check.py <다른 JSON>     같은 계약으로 다른 파일 검사

보는 것: 사례 구성과 순서, 상태와 칸의 짝, graph.json에 없는 식별자, 원문에 없는 부품 번호,
근거가 가리키는 호출이 호출 기록에 있고 성공했는지, 적은 값이 사례 입력의 값과 같은지, expected.md의 기대 시각.
뜻(원인이 맞는지, 확인 항목이 적절한지)은 원자료·원문과 직접 대조한다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

코드 = Path(__file__).resolve().parent
STATES = {"요청 초안", "보류"}
EVIDENCE_STATES = {"SUPPORTED", "UNKNOWN", "UNSUPPORTED"}
RESULTS = {"맞음", "안 맞음", "확인 못함"}
STOPS = {"답을 냄", "반복 한도", "같은 호출 반복", "오류"}


def load_inputs():
    cases = json.loads((코드 / "source/cases/cases.json").read_text(encoding="utf-8"))
    graph = json.loads((코드 / "source/ontology/graph.json").read_text(encoding="utf-8"))
    ids = {n["props"]["id"] for n in graph["nodes"]}
    manuals = " ".join(p.read_text(encoding="utf-8") for p in sorted((코드 / "source/manuals").glob("*.md")))
    parts = set(re.findall(r"\bP-[A-Z0-9-]+\b", manuals))
    return cases, ids, parts


def calls_ok(calls, at, errs):
    """번호 → 성공 여부. 형식이 틀리면 errs에 적는다."""
    table = {}
    if not isinstance(calls, list) or not calls:
        errs.append(f"{at}: calls(호출 기록)가 비었습니다. 에이전트가 부른 도구를 순서대로 적습니다.")
        return table
    prev = 0
    for k, c in enumerate(calls):
        if not isinstance(c, dict):
            errs.append(f"{at}.calls[{k}]: 객체가 아닙니다.")
            continue
        n = c.get("번호")
        if not isinstance(n, int) or n <= prev:
            errs.append(f"{at}.calls[{k}]: 번호는 1부터 커지는 정수입니다({n}).")
        else:
            prev = n
        if not str(c.get("도구") or "").strip():
            errs.append(f"{at}.calls[{k}]: 도구 이름이 없습니다.")
        if not isinstance(c.get("입력"), dict):
            errs.append(f"{at}.calls[{k}]: 입력은 객체입니다.")
        if "결과" not in c or "오류" not in c:
            errs.append(f"{at}.calls[{k}]: 결과와 오류 칸이 모두 있어야 합니다(오류가 없으면 null).")
        if isinstance(n, int):
            table[n] = c.get("오류") in (None, "")
    return table


def cite(refs, table, at, errs):
    if not isinstance(refs, list) or not refs:
        errs.append(f"{at}: 호출(근거가 된 호출 번호)이 비었습니다.")
        return
    for r in refs:
        if r not in table:
            errs.append(f"{at}: 호출 {r}이 호출 기록에 없습니다.")
        elif not table[r]:
            errs.append(f"{at}: 호출 {r}은 오류가 난 호출입니다. 실패한 호출을 근거로 쓰지 않습니다.")


def reading(case, tag, agg, win):
    for r in case.get("readings", []):
        if (r.get("tag"), r.get("aggregate"), r.get("windowSeconds")) == (tag, agg, win):
            return True, r.get("value")
    return False, None


def check_value(case, item, at, errs):
    found, value = reading(case, item.get("tag"), item.get("aggregate"), item.get("windowSeconds"))
    if not found:
        errs.append(f"{at}: 사례 {case['id']}에 {item.get('tag')} {item.get('aggregate')} {item.get('windowSeconds')}초 집계가 없습니다.")
    elif item.get("값") is not None and item.get("값") != value:
        errs.append(f"{at}: 값 {item.get('값')}이 사례 입력의 값 {value}과 다릅니다.")


def check_case(case, item, ids, parts, errs):
    at = f"사례 {case['id']}"
    for key in ("설비", "경보", "판단_시각"):
        expected = {"설비": case["equipment"], "경보": case["alarm"], "판단_시각": case["time"]}[key]
        if item.get(key) != expected:
            errs.append(f"{at}: {key}가 cases.json({expected})과 다릅니다: {item.get(key)}")
    table = calls_ok(item.get("calls"), at, errs)
    if item.get("멈춘_까닭") not in STOPS:
        errs.append(f"{at}: 멈춘_까닭은 {' · '.join(sorted(STOPS))} 가운데 하나입니다: {item.get('멈춘_까닭')}")
    cands = item.get("원인_후보")
    if not isinstance(cands, list):
        errs.append(f"{at}: 원인_후보 목록이 없습니다.")
        cands = []
    for i, c in enumerate(cands):
        a = f"{at}.원인_후보[{i}]"
        if c.get("cause") not in ids:
            errs.append(f"{a}: graph.json에 없는 원인 {c.get('cause')}")
        if c.get("근거_상태") not in EVIDENCE_STATES:
            errs.append(f"{a}: 근거_상태는 SUPPORTED · UNKNOWN · UNSUPPORTED: {c.get('근거_상태')}")
        for j, e in enumerate(c.get("증거") or []):
            b = f"{a}.증거[{j}]"
            if e.get("evd") not in ids:
                errs.append(f"{b}: graph.json에 없는 증거 {e.get('evd')}")
            if e.get("결과") not in RESULTS:
                errs.append(f"{b}: 결과는 맞음 · 안 맞음 · 확인 못함: {e.get('결과')}")
            if e.get("결과") == "확인 못함" and not str(e.get("확인_못한_이유") or "").strip():
                errs.append(f"{b}: 확인 못함인데 확인_못한_이유가 없습니다.")
            if e.get("값") is None and e.get("결과") != "확인 못함":
                errs.append(f"{b}: 값이 없는데 결과가 {e.get('결과')}입니다.")
            check_value(case, e, b, errs)
            cite(e.get("호출"), table, b, errs)
    state, req, hold = item.get("상태"), item.get("점검_요청"), item.get("보류")
    if state not in STATES:
        errs.append(f"{at}: 상태는 요청 초안 · 보류 가운데 하나입니다: {state}")
    elif state == "요청 초안" and (not isinstance(req, dict) or hold is not None):
        errs.append(f"{at}: 요청 초안이면 점검_요청을 채우고 보류는 null입니다.")
    elif state == "보류" and (req is not None or not isinstance(hold, dict) or not str(hold.get("이유") or "").strip()):
        errs.append(f"{at}: 보류이면 점검_요청은 null, 보류.이유를 적습니다.")
    if isinstance(req, dict):
        a = f"{at}.점검_요청"
        if req.get("대상_설비") != case["equipment"]:
            errs.append(f"{a}: 대상_설비가 경보의 설비({case['equipment']})와 다릅니다: {req.get('대상_설비')}")
        if req.get("구성_요소") not in ids or not str(req.get("구성_요소", "")).startswith("comp:"):
            errs.append(f"{a}: 구성_요소는 graph.json의 comp: 식별자입니다: {req.get('구성_요소')}")
        if not str(req.get("관측_시각") or "").strip():
            errs.append(f"{a}: 관측_시각이 비었습니다.")
        for key in ("부품", "관측값", "확인_항목"):
            if not isinstance(req.get(key), list) or not req.get(key):
                errs.append(f"{a}: {key} 칸이 비었습니다.")
        for k, p in enumerate(req.get("부품") or []):
            if not str(p.get("이름") or "").strip() or not str(p.get("출처") or "").strip():
                errs.append(f"{a}.부품[{k}]: 이름과 출처가 필요합니다.")
            if p.get("번호") is not None and p.get("번호") not in parts:
                errs.append(f"{a}.부품[{k}]: 원문에 없는 부품 번호 {p.get('번호')}")
            cite(p.get("호출"), table, f"{a}.부품[{k}]", errs)
        for k, v in enumerate(req.get("관측값") or []):
            check_value(case, v, f"{a}.관측값[{k}]", errs)
            cite(v.get("호출"), table, f"{a}.관측값[{k}]", errs)
        for k, c in enumerate(req.get("확인_항목") or []):
            if not str(c.get("항목") or "").strip() or not str(c.get("이유") or "").strip():
                errs.append(f"{a}.확인_항목[{k}]: 항목과 이유가 필요합니다.")
            cite(c.get("호출"), table, f"{a}.확인_항목[{k}]", errs)
        for o in req.get("다른_후보") or []:
            if o not in ids:
                errs.append(f"{a}: graph.json에 없는 다른_후보 {o}")
        if not str(req.get("표시") or "").strip():
            errs.append(f"{a}: 표시(점검 요청 초안이며 확정 원인·작업지시가 아니라는 문장)가 비었습니다.")
    text = json.dumps(item, ensure_ascii=False)
    for wo in sorted(set(re.findall(r"\bWO-[A-Z0-9-]+", text))):
        errs.append(f"{at}: 작업지시 번호 {wo}가 들어 있습니다. 이 실습은 작업지시를 만들지 않습니다.")


def check_expected(path, errs):
    if not path.is_file():
        errs.append("output/expected.md가 없습니다.")
        return
    text = path.read_text(encoding="utf-8-sig")

    def when(label):
        m = re.search(r"^- " + label + r"[^:\n]*:[ \t]*(.*)$", text, re.M)
        if not m or not m.group(1).strip():
            return None
        x = re.search(r"(\d{4}-\d{2}-\d{2})[ T](\d{1,2}):(\d{2})", m.group(1))
        return f"{x.group(1)} {int(x.group(2)):02d}:{x.group(3)}" if x else m.group(1).strip()

    e, r = when("기대 칸을 쓴 시각"), when("실행 시각")
    if not e:
        errs.append("expected.md 「기대 칸을 쓴 시각」이 비었습니다. 실행 전에 기대 칸을 쓰고 그 시각을 적습니다.")
    elif r and re.match(r"\d{4}-", e) and re.match(r"\d{4}-", r) and e > r:
        errs.append(f"expected.md: 기대 칸을 쓴 시각({e})이 실행 시각({r})보다 뒤입니다.")


def main(argv) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    target = Path(argv[0]) if argv else 코드 / "output/점검요청_초안.json"
    cases, ids, parts = load_inputs()
    errs: list[str] = []
    if not target.is_file():
        print(f"없음: {target}")
        return 1
    try:
        data = json.loads(target.read_text(encoding="utf-8-sig"))
    except ValueError as e:
        print(f"JSON 읽기 실패: {target}: {e}")
        return 1
    if not isinstance(data, dict):
        print(f"형식 오류: {target}: 맨 위가 객체({{…}})여야 합니다. 지금은 {type(data).__name__}입니다.")
        return 1
    if not str(data.get("모델") or "").strip():
        errs.append("모델(사용한 모델 이름)이 비었습니다.")
    items = data.get("사례")
    if not isinstance(items, list):
        errs.append("사례 목록이 없습니다.")
        items = []
    got = [i.get("id") for i in items if isinstance(i, dict)]
    want = [c["id"] for c in cases]
    if got != want:
        errs.append(f"사례 구성·순서가 cases.json과 다릅니다. 빠짐 {sorted(set(want) - set(got))}, 더함 {sorted(set(got) - set(want))}")
    by_id = {c["id"]: c for c in cases}
    for item in items:
        if isinstance(item, dict) and item.get("id") in by_id:
            check_case(by_id[item["id"]], item, ids, parts, errs)
    md = target.with_suffix(".md")
    if not md.is_file():
        errs.append(f"{md.name}가 없습니다.")
    else:
        heads = "\n".join(l for l in md.read_text(encoding="utf-8-sig").splitlines() if l.startswith("#"))
        lost = [i for i in got if i and i not in heads]
        if lost:
            errs.append(f"{md.name}: 절 제목에 사례 id가 없습니다: {lost}")
    if target == 코드 / "output/점검요청_초안.json":
        check_expected(코드 / "output/expected.md", errs)
    for e in errs:
        print("확인 필요:", e)
    print(f"구조 검사: 사례 {len(got)}건, 확인 필요 {len(errs)}건")
    print("참고: 원인·확인 항목이 맞는지는 이 검사가 판정하지 않습니다. 원자료·원문과 직접 대조합니다.")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
