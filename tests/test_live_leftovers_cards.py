"""라이브 3차 남은 것 1 — 카드 머리말: 예측은 고르는 근거일 때만, 업무 안은 그 안의 업무 값 (실제 포털 파일을 node vm 으로 그린다).

판단 엔진은 모든 안에 예측을 붙인다(순위 식의 예측 · 품질 성분, 규정의 예측 유온 검사, 승인 순간 재확인). 화면 머리말은 설비를 바꾸는 안
(kind control)이거나 안마다 예측이 달라 비교가 되는 때만 예측이고, 설비 명령이 없는 업무 안끼리 예측이 모두 같으면(C 발주 · B 정비 오더)
그 안의 업무 값(카드별 사실 · 작업지시의 정비 시점)이다. 시나리오 이름이 아니라 카드 칸(kind · forecast · facts · actions · window)으로 가른다.
A(쿨러) 화면은 바뀌지 않는다 — 고치기 전 코드(664d06c)로 그린 글을 tests/fixtures/a_cards_before.json 에 고정해 대조한다.
"""
import json
import re
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
WWW = ROOT / "it" / "portal" / "www"
A_BEFORE = ROOT / "tests" / "fixtures" / "a_cards_before.json"


def fc(ts1, ps1, sid):
    return [{"variable": "sv:ts1", "name": "평형 유온", "value": ts1, "unit": "℃", "method": "m; constant inputs", "id": f"m:{sid}:sv:ts1"},
            {"variable": "sv:ps1", "name": "토출 압력", "value": ps1, "unit": "bar", "method": "m; constant inputs", "id": f"m:{sid}:sv:ps1"},
            {"variable": "sv:fs1", "name": "유량", "value": 9.0, "unit": "l/min", "method": "m; constant inputs", "id": f"m:{sid}:sv:fs1"}]


def card(sid, name, kind, rank, score, ts1, ps1, actions, parts, approver="운전원", feasible=True, **more):
    facts = more.pop("facts", None) or {"forecast_ts1": ts1, "forecast_ps1": ps1, "skill_kind": kind, "skill_code": [a["code"] for a in actions],
                                        "supplier_avl": None, "supplier_fail_rate": None}
    return dict({"id": sid, "sopId": sid.split(":")[1].upper(), "name": name, "kind": kind, "rank": rank, "score": score, "feasible": feasible,
                 "approver": {"id": "role:x", "name": approver, "level": 1}, "actions": actions, "forecast": fc(ts1, ps1, sid), "facts": facts,
                 "scoreParts": parts, "gains": [], "losses": [], "warnings": [], "penalties": [], "violations": [], "steps": [],
                 "selectedBy": [], "tradeoffEvaluation": [], "precedent": None}, **more)


CMD = lambda code, value: {"code": code, "kind": "command", "value": value, "name": code}
WO = {"code": "WO_CREATE", "kind": "transaction", "value": "SOP", "name": "정비 작업지시 발행", "target": "sys:cmms"}
PR = lambda sup: {"code": "PR_CREATE", "kind": "transaction", "value": sup, "name": "부품 구매요청", "target": "sys:erp", "targetName": "ERP"}
IMMEDIATE = {"immediate": True, "name": "즉시 (지금 정지하고 시행)", "label": "즉시"}
P = lambda **k: dict({"bsc": 0.0, "warn": 0.0, "penalty": 0.0, "quality": 0.0, "delivery": 1.12, "forecast": 1.74, "precedent": 0.0}, **k)

# A 긴급 대응(라이브 3차 DEC-1010-002-408b 모양): 제어 안 셋 + 작업지시 안 하나(쿨러 핀 세척 — 설비를 당장 바꾸지 않아 예측이 62.5 ℃로 오른다)
A = {"id": "DEC-A", "recommended": "skill:sop-cool-11", "explanation": "쿨러 냉각 성능 상실 — 후보 4장 중 'SOP-COOL-11 팬 최대 운전'을(를) 권한다.",
     "facts": {"ts1": 61.4, "ce": 65.0, "plc_mode": "REMOTE_AUTO", "order_due_h": 5.98},
     "origin": {"kind": "alert", "cause": "cause:cooler-fin-fouling", "failureMode": "fm:cooler-performance-loss",
                "cause_basis": "ontology T1 (pattern → symptom → failure mode ← cause), same query as diagnose", "cause_route": "diagnosis"},
     "options": [
         card("skill:sop-cool-11", "팬 최대 운전", "control", 1, 3.38, 49.772, 182.0, [CMD("FAN_SET", 100)], P(),
              gains=[{"name": "인터록 여유", "conditional": False}], losses=[{"name": "전력 사용량", "conditional": False}],
              steps=[{"order": 1, "text": "팬을 100 %로", "manual": {"ref": "HM-8.5", "title": "즉시 완화 조치"}}],
              selectedBy=[{"rule": "rule:cool", "annotation": "냉각 성능 상실의 즉시 완화 후보(HM-8.5)", "sources": ["HM-8.5"]}],
              relation="MITIGATED_BY"),
         card("skill:sop-cool-13", "부하 70 %와 야간 핀 세척", "control", 2, 2.75, 47.7, 176.0, [CMD("LOAD_SET", 70), WO], P(delivery=0.45, bsc=-0.22, forecast=2.0)),
         card("skill:sop-cool-12", "팬 최대 운전과 부하 80 %", "control", 3, 2.75, 44.6, 179.0, [CMD("FAN_SET", 100), CMD("LOAD_SET", 80)],
              P(delivery=0.45, bsc=-0.22, forecast=2.0)),
         card("skill:sop-cool-14", "쿨러 핀 세척", "work_order", 4, -1.58, 62.5, 182.0, [WO], P(forecast=-2.0, quality=-1.5, bsc=0.78),
              approver="설비보전팀장", window=IMMEDIATE,
              warnings=[{"annotation": "조치 후 예측 유온이 55 ℃ 이상이면 경보 해제에 실패할 수 있으므로 다른 조치와 비교한다"}]),
     ]}

# C 예비품 구매(라이브 3차 C-decision.json DEC-1010-006-b837 의 칸 값): 발주 안 셋, 설비 명령 없음, 예측은 셋 다 지금 설비 그대로(48 ℃ · 182 bar)
# 칸 순서도 라이브 C-decision.json 그대로(화면은 칸 순서대로 적는다)
C_FACTS = lambda po, slack, fail, avl: {"facts": {"po_amount": po, "skill_code": ["PR_CREATE"], "skill_kind": "work_order", "forecast_ps1": 182.0,
                                                  "forecast_ts1": 48.001, "supplier_avl": avl, "lead_slack_days": slack, "supplier_fail_rate": fail}}
C = {"id": "DEC-C", "recommended": "skill:sop-pur-11", "explanation": "펌프 체적 효율 저하 — 후보 3장 중 'SOP-PUR-11 순정(OEM) 공급사 표준 발주'을(를) 권한다.",
     "facts": {"ts1": 48.0, "ps1": 182.43, "spare_gap": -1, "need_qty": 6, "spare_available": 1, "hours_at_next_window": 1959,
               "windows_by_variable": {"hours_at_next_window": {"id": "MW-1", "name": "이번 예정된 정비 시간"}}},
     "origin": {"kind": "alert", "cause": "cause:pump-shaft-seal-wear", "failureMode": "fm:pump-volumetric-efficiency-loss",
                "cause_basis": "ontology: cause -INVOLVES_PART-> part (ERP 재주문점 아래 부품), cause -CAUSES-> failure mode", "cause_route": "part"},
     "options": [
         card("skill:sop-pur-11", "순정(OEM) 공급사 표준 발주", "work_order", 1, 2.82, 48.001, 182.0, [PR("sup:b")], P(warn=-0.5, delivery=1.32, forecast=2.0),
              approver="구매 담당", window=IMMEDIATE, relation="REMEDIED_BY",
              gains=[{"name": "부품 품질", "conditional": False}], losses=[{"name": "재고량", "conditional": False}],
              warnings=[{"annotation": "발주 금액 300만 원 초과: 발주안에 전결 기준 초과를 표시한다."}],
              steps=[{"order": 1, "text": "발주 수량을 정한다", "manual": {"ref": "PR-7.6", "title": "발주 절차"}}],
              selectedBy=[{"rule": "rule:pur", "annotation": "재고 기준 이탈 경보로 열린 처리 건에서 발주 절차 셋을 후보로 낸다.", "sources": ["PR-7.6"]}],
              **C_FACTS(330.0, 1.0, 0.02, True)),
         card("skill:sop-pur-12", "대체 승인 공급사 발주", "work_order", 2, 1.32, 48.001, 182.0, [PR("sup:a")], P(bsc=-1.0, penalty=-1.0, delivery=1.32, forecast=2.0),
              approver="구매 담당", window=IMMEDIATE, penalties=[{"annotation": "불량률이 10 %를 넘는 승인 공급사는 전수 검사 비용 20만 원을 더한다.", "penalty": 20}],
              **C_FACTS(210.0, 4.0, 0.12, True)),
         card("skill:sop-pur-13", "최단 납기 긴급 발주", "work_order", 3, 2.32, 48.001, 182.0, [PR("sup:c")], P(bsc=-1.0, delivery=1.32, forecast=2.0),
              approver="구매 담당", window=IMMEDIATE, feasible=False, violations=[{"rule": "rule:avl", "annotation": "핵심 부품은 승인 공급사에서만 구매"}],
              **C_FACTS(120.0, 5.0, 0.3, False)),
     ]}

# B 정기 정비(라이브 3차 B 카드 모양): 정비 오더 안 넷, 설비 명령 없음, 예측 모두 같음, 카드마다 정비 시점(window · basis)
NEXT = {"id": "MW-HYD-02-N-1", "name": "이번 예정된 정비 시간", "starts_at": "2026-10-10T11:17:54+00:00", "basis": "hours_at_next_window"}
FOLLOW = {"id": "MW-HYD-02-M-1", "name": "그다음 예정된 정비 시간", "starts_at": "2026-10-21T18:17:54+00:00", "basis": "hours_at_following_window"}
B = {"id": "DEC-B", "recommended": "skill:sop-pm-11", "explanation": "펌프 체적 효율 저하 — 후보 4장 중 'SOP-PM-11 이번 예정된 정비 시간에 단독 시행'을(를) 권한다.",
     "facts": {"ts1": 48.0, "hours_since_pm": 1950, "hours_at_next_window": 1959, "hours_at_following_window": 2230, "pm_crew_available": 2},
     "origin": {"kind": "alert", "cause": "cause:pump-shaft-seal-wear", "failureMode": "fm:pump-volumetric-efficiency-loss",
                "cause_basis": "ontology: failure mode -PREVENTED_BY-> skill (정기 정비가 막는 고장), cause -CAUSES-> failure mode", "cause_route": "prevention"},
     "options": [
         card("skill:sop-pm-11", "이번 예정된 정비 시간에 단독 시행", "work_order", 1, 1.73, 48.001, 182.0, [WO], P(), approver="설비보전팀장", window=NEXT,
              relation="PREVENTED_BY"),
         card("skill:sop-pm-12", "지금 바로 정지하고 시행", "work_order", 2, -3.35, 48.001, 182.0, [WO], P(penalty=-4.0, bsc=-1.0), approver="설비보전팀장",
              window=IMMEDIATE),
         card("skill:sop-pm-13", "그다음 예정된 정비 시간으로 미루기", "work_order", 3, 0.27, 48.001, 182.0, [WO], P(), approver="설비보전팀장", window=FOLLOW,
              feasible=False, violations=[{"annotation": "그다음 예정된 정비 시간까지 미룰 때 운전시간이 2,200 h를 넘으면 미루지 않는다"}]),
         card("skill:sop-pm-14", "같은 기종 두 대 묶어 시행", "work_order", 4, -1.46, 48.001, 182.0, [WO], P(), approver="설비보전팀장", window=NEXT,
              feasible=False, violations=[{"annotation": "두 대를 묶으려면 씰 키트가 2개 이상 있어야 한다"}]),
     ]}
NAMES = {"cause:cooler-fin-fouling": "쿨러 핀 오염", "fm:cooler-performance-loss": "쿨러 냉각 성능 상실",
         "cause:pump-shaft-seal-wear": "축 씰 마모", "fm:pump-volumetric-efficiency-loss": "펌프 체적 효율 저하"}


def render(tmp_path, decisions, www=WWW):
    if NODE is None:
        pytest.skip("node 가 없어 포털 카드 시험을 돌릴 수 없습니다")
    fx = tmp_path / "fixture.json"
    fx.write_text(json.dumps({"decisions": decisions, "names": NAMES}, ensure_ascii=False), encoding="utf-8")
    out = subprocess.run([NODE, str(ROOT / "tests" / "js" / "render_decision_cards.js"), str(www), str(fx)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def text(html):
    """사람이 읽는 글: 태그를 지우고 빈칸을 하나로."""
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def hline(card_html):
    """조치 판단 카드의 머리 줄(접기 밖 한 줄) — 근거 접기 안의 예측 · 점수 성분은 보조 정보라 그대로 둔다."""
    m = re.search(r'<span class="hline">(.*?)</span>\s*\n', card_html, re.S)
    assert m, card_html[:300]
    return text(m.group(1))


def screens(r):
    return {"approval": text(r["approval"]), "alts": text(r["alts"]), "path": text(r["path"]), "cards": [text(c) for c in r["cards"]],
            "lines": [hline(c) for c in r["cards"]]}


def test_a_cooling_cards_read_exactly_as_before(tmp_path):
    """A 는 설비를 바꾸는 안이고 안마다 예측이 갈린다 — 머리말 · 진 이유 · 카드 줄이 고치기 전과 글자 하나 다르지 않다(작업지시 안 '쿨러 핀 세척'의
    예측 62.5 ℃ 포함). 고정본: 고치기 전 코드(664d06c)의 같은 파일로 그린 글."""
    now = screens(render(tmp_path, {"A": A})["A"])
    assert now == json.loads(A_BEFORE.read_text(encoding="utf-8"))
    assert "예측 평형 유온 49.8℃ · 토출 압력 182bar" in now["approval"] and "예측 평형 유온 62.5℃ · 토출 압력 182bar" in now["alts"]
    assert "이 안의 값" not in now["alts"] and "정비 시점" not in now["alts"]


def test_c_purchase_cards_lead_with_the_order_values_not_an_unchanged_plant_forecast(tmp_path):
    r = screens(render(tmp_path, {"C": C})["C"])
    head = "이 안의 값 발주 금액 330 만원 · 승인 공급사(AVL) 예 · 납기 여유 1 일 · 공급사 불량률(비율) 0.02"
    assert head in r["approval"] and r["approval"].index(head) < r["approval"].index("좋아지는 것 부품 품질")
    for screen in (r["approval"], r["alts"], *r["lines"]):
        assert "예측" not in screen and "48℃" not in screen and "48 ℃" not in screen, screen
    assert "이 안의 값 발주 금액 210 만원 · 승인 공급사(AVL) 예 · 납기 여유 4 일 · 공급사 불량률(비율) 0.12" in r["alts"]
    assert r["alts"].count(head) == 1                                     # 추천안의 이유 줄이 머리말을 다시 적지 않는다
    assert "정비 시점" not in r["alts"]                                  # 발주 안에는 작업지시 시점이 없다(카드의 즉시 창은 정비용)
    assert r["lines"][2].startswith("이 안의 값 발주 금액 120 만원") and "예측 +2.00" in r["cards"][2]     # 점수 성분은 근거 접기에 그대로


def test_b_maintenance_cards_lead_with_when_the_order_runs(tmp_path):
    r = screens(render(tmp_path, {"B": B})["B"])
    assert "예측" not in r["approval"] and "예측" not in r["alts"]
    assert re.search(r"이 안의 값 정비 시점 이번 예정된 정비 시간 \(.+?\) · 이번 정비 시간의 운전시간 1,959 h", r["approval"])
    assert "정비 시점 즉시 (지금 정지하고 시행)" in r["alts"] and re.search(r"정비 시점 그다음 예정된 정비 시간 \(.+?\) · 다음 정비 시간의 운전시간 2,230 h", r["alts"])


def test_a_lone_plant_command_card_keeps_its_forecast_even_when_every_forecast_is_equal(tmp_path):
    """같은 예측이어도 설비를 바꾸는 안(kind control)은 예측이 그 안의 효과다 — 업무 값으로 바꾸지 않는다."""
    d = deepcopy(C)
    d["options"][1] = dict(d["options"][1], kind="control", actions=[CMD("FAN_SET", 100)])
    r = screens(render(tmp_path, {"C": d})["C"])
    assert "예측 평형 유온 48℃ · 토출 압력 182bar" in r["alts"] and r["alts"].count("예측 평형 유온") == 1


def test_why_this_part_reads_as_the_reason_for_the_part_not_a_fault_diagnosis(tmp_path):
    """C 의 원인은 업무 근거(재주문점 아래 부품 → 그 부품이 고치는 원인)로 정해졌다 — 지식 경로는 '이 부품이 고치는 원인'으로 읽힌다.
    A(센서 진단)는 '원인 · 고장 유형' 그대로."""
    out = render(tmp_path, {"A": A, "C": C, "B": B})
    c, a, b = text(out["C"]["path"]), text(out["A"]["path"]), text(out["B"]["path"])
    assert "이 부품이 고치는 원인 축 씰 마모" in c and "그 원인이 일으키는 고장 펌프 체적 효율 저하" in c
    assert "원인을 정한 근거: 지식 그래프: 원인 → 쓰는 부품 → 부품" in c and "증상" not in c
    assert "정기 정비로 막는 원인 축 씰 마모" in b
    assert "원인 쿨러 핀 오염" in a and "고장 유형 쿨러 냉각 성능 상실" in a and "부품" not in a


def test_an_unknown_cause_route_fails_instead_of_guessing(tmp_path):
    d = deepcopy(C)
    d["origin"]["cause_route"] = "guess"
    if NODE is None:
        pytest.skip("node 가 없습니다")
    fx = tmp_path / "fixture.json"
    fx.write_text(json.dumps({"decisions": {"C": d}, "names": NAMES}, ensure_ascii=False), encoding="utf-8")
    out = subprocess.run([NODE, str(ROOT / "tests" / "js" / "render_decision_cards.js"), str(WWW), str(fx)], capture_output=True, text=True, timeout=60)
    assert out.returncode != 0 and "cause_route" in out.stderr
