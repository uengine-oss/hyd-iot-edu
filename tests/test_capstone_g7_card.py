"""캡스톤 G7 — 일반 사람 승인(안 고르기)의 "추천 1 + 지는 안 펼치기" 카드. 실제 런타임(G1 시험의 학생 흐름)이 만든 처리 건 view · 단계 상세를
포털의 실제 ui.js · approvalCard.js · taskDetail.js(node vm, tests/js/render_task_detail.js)에 넣어 그린다.
약속(options[{slot, reason, score}] · recommended · losers[{slot, why}] · docs[{title, link}])을 지키면 카드, 벗어나면 무엇이 다른지 + 받은 값 JSON."""
import html
import json
import re
from copy import deepcopy

from procsvc import approval_part as AP
from test_capstone_g1_approve import PROPOSAL, ORG, OTHER, ROLE, case  # noqa: F401  (case 는 fixture)
from test_instance_mode import world, NOW, _row  # noqa: F401
from test_u1_task_detail import _render


def _scenario(rt, inst, wi, name):
    return {"name": name, "view": rt.instance_view(inst["proc_inst_id"]), "wid": wi["id"],
            "people": rt.repo.list_users(tenant_id=rt.tenant_id),
            "http": {f"/api/todolist/{wi['id']}": rt.workitem_view(wi["id"])}}


def _text(panel):
    return html.unescape(panel)


def test_card_shows_the_recommendation_the_losers_the_docs_and_who_approved_which(tmp_path, case):
    rt, _, start = case
    inst, wi = start(event="QBR-G7-1")
    pending = _scenario(rt, inst, wi, "pending")
    rt.approve(wi["id"], AP.APPROVE, "다음 주 화 15:00", ORG, ROLE, "고객이 다음 주를 원함", now=NOW)
    out = _render(tmp_path, [pending, _scenario(rt, inst, wi, "approved")])
    before, after = _text(out["pending"]["panel"]), _text(out["approved"]["panel"])
    assert "AI 에이전트 추천" in before and "금 10:00" in before and "필수 참석자 전원" in before and "0.82점" in before
    assert "다른 안 1개 · 빠진 안 2개는 왜 졌나" in before and "자료 공유 48시간 규칙 위반" in before and "필수 참석자(고객 담당 임원) 불가" in before
    assert 'href="https://drive.example/q3"' in out["pending"]["panel"] and "Q3 회의록" in before
    assert "칸 약속과 다릅니다" not in before and "이 안으로 바꾸기" not in before            # 상세 패널은 보기만(고르기는 승인 패널)
    # 승인 뒤: 담당자가 바꾼 안이 카드 머리 · 결정 · 사유 · 승인자(이름 · 역할)
    assert "담당자가 바꾼 안" in after and "다음 주 화 15:00" in after and "고객이 다음 주를 원함" in after
    # U10: 실제 인물 목록과 정의 역할명을 사용한다. API 감사 식별자는 바꾸지 않는다.
    view = rt.instance_view(inst["proc_inst_id"])
    role_name = next(r["name"] for r in view["definition"]["roles"] if r["endpoint"] == ROLE)
    actor_name = next(u["username"] for u in rt.repo.list_users() if u["id"] == ORG)
    assert f"{actor_name} ({role_name})" in after and "결정" in after and "다른 안 1개 · 빠진 안 2개" in after
    approval = next(e for e in rt.workitem_view(wi["id"])["events"] if e["job_id"] == "APPROVAL_ACCEPTED")
    assert approval["data"]["by"] == ORG and approval["data"]["role"] == ROLE
    approver = re.search(r'<div class="ro-value">([^<]*' + re.escape(actor_name) + r'[^<]*)</div>', after).group(1)
    assert ORG not in approver and ROLE not in approver


def test_approval_names_and_choice_stay_with_their_own_case_and_event(tmp_path, case):
    rt, _, start = case
    first, first_wi = start(event="QBR-names-first")
    rt.approve(first_wi["id"], AP.APPROVE, "다음 주 화 15:00", ORG, ROLE, "첫 회의 사유", now=NOW)
    historical = _scenario(rt, first, first_wi, "first")
    rt.repo.set_role_member(rt.tenant_id, ROLE, OTHER, True)
    second, second_wi = start(event="QBR-names-second")
    rt.approve(second_wi["id"], AP.APPROVE, "금 10:00", OTHER, ROLE, "두 번째 회의 사유", now=NOW)
    # 현재 처리 건 값이 다음 회차 값으로 달라도 단계의 접수 기록으로 표시해야 한다.
    for row in historical["view"]["instance"]["variables_data"]:
        if row["key"] == "approved_by": row["value"] = OTHER
        if row["key"] == "approved_option": row["value"] = {"slot": "금 10:00"}
    copy_of_first = deepcopy(historical)
    copy_of_first["name"] = "first_again"
    result = _render(tmp_path, [historical, _scenario(rt, second, second_wi, "second"), copy_of_first])
    for key, person, wrong, chosen in [("first", "한주관", "유주관", "다음 주 화 15:00"), ("second", "유주관", "한주관", "금 10:00"), ("first_again", "한주관", "유주관", "다음 주 화 15:00")]:
        panel = _text(result[key]["panel"])
        assert f"{person} (주관자)" in panel and f"{wrong} (주관자)" not in panel
        assert f'<span class="kv">{chosen}</span>' in panel
        assert f"{ORG} ({ROLE})" not in panel and f"{OTHER} ({ROLE})" not in panel


def test_off_contract_proposal_is_shown_raw_with_what_is_off_not_hidden(tmp_path, case):
    rt, _, start = case
    broken = {"options": [{"slot": "금 10:00", "room": "B"}, {"slot": "월 09:00", "score": "높음", "reason": "빈 방"}],
              "recommended": "토 09:00", "losers": [{"slot": "내일"}], "docs": [{"title": "회의록", "link": "javascript:alert(1)"}]}
    inst, wi = start(broken, event="QBR-G7-2")
    missing, mwi = start({"recommended": "x"}, event="QBR-G7-3")
    out = _render(tmp_path, [_scenario(rt, inst, wi, "broken"), _scenario(rt, missing, mwi, "missing")])
    b, m = _text(out["broken"]["panel"]), _text(out["missing"]["panel"])
    assert "에이전트 제안이 칸 약속과 다릅니다" in b and "받은 값 그대로 (JSON)" in b
    for why in ("1번째 안(금 10:00)에 이유 칸 'reason' 이(가) 없습니다", "2번째 안(월 09:00)의 점수 칸 'score' 가 숫자가 아닙니다",
                "추천 '토 09:00' 이(가) 고를 안 목록에 없습니다", "지는 안 1번째: 진 이유 칸 'why' 가 없습니다",
                "근거 자료 1번째: 링크 칸 'link' 가 http(s) 주소가 아닙니다"):
        assert why in b, why
    assert 'href="javascript' not in out["broken"]["panel"]                                  # 약속 밖 링크는 링크로 만들지 않는다(글자로만)
    assert '"room": "B"' in b                                                               # 받은 값이 그대로 보인다
    assert "고를 안 'proposal.options' 이(가) 받은 값에 없습니다" in m and "고를 안이 없습니다" in m
    assert json.dumps({"proposal.options": None, "proposal.recommended": "x"}, ensure_ascii=False, indent=2).split("\n")[1].strip() in m \
        or '"proposal.recommended": "x"' in m
