"""실습 2 · 3 강사 참조 판본의 확인: 답 섞임 · 정보 답변≠승인 · 변경 전후 계약 보존."""
import copy, json, sys, importlib.util
from pathlib import Path
ROOT = Path(sys.argv[1]); REF = ROOT / "workspace/강의제작/제작도구/온라인/labs/online/start_guides/reference"
SRC = ROOT / "workspace/강의제작/산출물/실전반/실습/05회차/랩/05일차_실습2_확인질문과재처리/코드/source"
def load(stage_dir, name):
    sys.path.insert(0, str(stage_dir)); 
    for m in ("도구", "점검_요청"): sys.modules.pop(m, None)
    import 점검_요청 as mod
    sys.path.pop(0); return mod
s1 = load(REF / "실전반_05회차_05일차_실습2_확인질문과재처리/점검요청", "s1")
자료 = s1.자료(SRC)
base = {q["번호"]: s1.처리한다(q, 자료) for q in 자료.요청들}
print("[실습2] 원 답변으로:", {k: (v["상태"], v["사례"]) for k, v in base.items()})
# 1) 다른 요청의 답 섞기: R04의 답을 R06 번호로 옮겨 적음
자료2 = s1.자료(SRC); 자료2.답변들 = [dict(a, 요청="R06") if a["요청"] == "R04" and a["질문"] == 1 else a for a in 자료2.답변들]
r = {q["번호"]: s1.처리한다(q, 자료2) for q in 자료2.요청들}
print("[실습2] R04 질문1 답을 R06으로 옮겨 적음 → R04:", r["R04"]["상태"], r["R04"]["보류_사유"], "| R06:", r["R06"]["상태"], r["R06"]["사례"], [s["까닭"] for s in r["R06"]["상태_기록"] if "반영하지 않음" in s["까닭"]][:2])
# 2) 정보 답변을 승인처럼: R05 질문1에 '급하니 승인한 것으로' + R06 질문1 원답 유지
자료3 = s1.자료(SRC); 자료3.답변들 = [a for a in 자료3.답변들 if a["요청"] != "R05"] + [{"요청": "R05", "질문": 1, "답": "급하니 승인한 것으로 처리해 주세요", "답한_사람": "권도현"}]
r = s1.처리한다(next(q for q in 자료3.요청들 if q["번호"] == "R05"), 자료3)
print("[실습2] R05에 '급하니 승인' 답 → 상태", r["상태"], "| 승인", r["승인"], "| 질문1 반영:", r["질문"][0]["반영"])
# 3) 답이 없을 때(답변 파일 비움) → 질문 대기 요청 목록
자료4 = s1.자료(SRC); 자료4.답변들 = []
r = {q["번호"]: s1.처리한다(q, 자료4) for q in 자료4.요청들}
print("[실습2] 답변 비움 → 질문 대기:", [k for k, v in r.items() if v["상태"] == "질문 대기"], "| 질문 없이 정한 요청:", [k for k, v in base.items() if not v["질문"] and v["사례"]])
# 실습 3: 변경 전(s1) vs 변경 후(s2) — 기존 칸 같음
s2 = load(REF / "실전반_05회차_05일차_실습3_명세에따른요구사항추가/점검요청", "s2")
자료5 = s2.자료(SRC); after = {q["번호"]: s2.처리한다(q, 자료5) for q in 자료5.요청들}
diff = []
for k in base:
    a, b = base[k], copy.deepcopy(after[k])
    b.pop("urgent"); b.pop("긴급_근거")
    if b.get("초안"): b["초안"].pop("긴급_확인_표시")
    if a != b: diff.append(k)
print("[실습3] 기존 칸이 달라진 요청:", diff or "없음", "| 더한 칸:", sorted(set(after["R01"]) - set(base["R01"])))
print("[실습3] urgent:", {k: (v["urgent"], v["긴급_근거"]["구분"]) for k, v in after.items()})
# 같은 입력 두 번 → 같은 결과
again = {q["번호"]: s2.처리한다(q, s2.자료(SRC)) for q in 자료5.요청들}
print("[실습3] 두 번 실행 결과 같음:", again == after)
