"""B7 (확정 TODO B7, DECISIONS 110 ⑤) — 사람 입력 경보: 사람이 입력한 분석 결과를 센서 경보와 같은 계약의 경보로 만든다.

작동유 열화에는 실시간 센서가 없다(지식 `sym:oil-analysis-out-of-spec` note — 정기 오일 분석 결과를 사람이 입력한다).
그래서 "오일 분석 결과 입력"(설비 · 분석 항목 · 측정값 · 기준 이탈 여부 · 메모 · 입력자)을 서버가 감지기 경보와 **같은 모양**
(`alertId · asset · pattern · severity · state=RAISE · t · evidence`, det/cep.py `_alert`)으로 만들고 출처를 표시해
(`source: "human_input"`, `enteredBy`) 기존 경보 경로(원천 접수 → `alert_policy` → `start_definition` → Incident)로 보낸다.

  - 기준 이탈이 아니면 경보를 만들지 않는다(사유를 돌려주고 감사만 남김). 지식의 패턴 검사(`pattern:oil-analysis -TESTS-> in:oil-analysis`
    `== true`)와 같은 조건이다.
  - 어느 흐름이 여는지는 정하지 않는다: 경보 정책(B4 `flow_deploy.route_definition`)이 정한다. OIL_ANALYSIS 를 받는 배포 흐름이 없으면
    기준 흐름의 `unsupported` → 사람 검토(alert_triage). 작동유 흐름은 학생이 만든다(정답을 박지 않음).
  - B3 흐름 가져오기의 "경보 시작" 패턴 목록에 이 패턴을 보탠다(`policy_patterns`). 회복 기준(재관측 기준)은 아래 계약 그대로.

사람 입력 패턴은 이 표에만 있다(감지기 패턴의 회복 기준 `definition.RECOVERY` 처럼 명시 계약). 표의 지식 id · 입력 변수는 시드
`it/neo4j/v2/knowledge_a098.cypher` 와 시험으로 대조한다(tests/test_b7_oil.py).
"""
from __future__ import annotations

import math
import secrets
from copy import deepcopy
from datetime import datetime, timezone

from hydcommon import topics

HUMAN_SOURCE = "human_input"

# 사람 입력 경보 패턴 계약. items = 분석 항목(지식 sym:oil-analysis-out-of-spec 의 aliases · 교육용 매뉴얼 HM-9.1 표의 항목).
# policy = 흐름 정의 alertPolicy.patterns 에 들어갈 회복 기준(alert_policy.validate 계약: tag · op · limit · requireClear).
#   작동유는 센서 해제(CLEAR)가 없다 — 정비형 흐름(작업지시)에서는 쓰이지 않고, 누가 설비 명령 · 재관측을 넣은 흐름을 만들면
#   재관측이 "해제 없음"으로 상급자에게 간다(사람 재분석이 회복 판단). 유온 기준은 HM-9.1 표의 정상(55 ℃ 이하)과 같은 값.
PATTERNS: dict[str, dict] = {
    "OIL_ANALYSIS": {
        "name": "오일 분석 기준 이탈 (사람 입력)",
        "knowledge": {"pattern": "pattern:oil-analysis", "symptom": "sym:oil-analysis-out-of-spec", "input": "in:oil-analysis",
                      "variable": "oil_analysis_out_of_spec"},
        "severity": "warning",
        "items": [
            {"key": "tan", "text": "산가 TAN", "unit": "mgKOH/g"},
            {"key": "water", "text": "수분 함량", "unit": "ppm"},
            {"key": "cleanliness", "text": "청정도 (NAS · ISO 4406)", "unit": "등급"},
            {"key": "viscosity", "text": "점도 변화", "unit": "%"},
        ],
        "policy": {"tag": "TS1", "op": "<", "limit": 55.0, "requireClear": True},
    },
}


def policy_patterns() -> dict[str, dict]:
    """B3 가져오기의 경보 시작 패턴에 보탤 {패턴: 회복 기준} (흐름 정의 alertPolicy.patterns 모양)."""
    return {code: deepcopy(p["policy"]) for code, p in PATTERNS.items()}


def form() -> dict:
    """포털 입력 화면이 쓰는 칸 — 패턴 · 이름 · 분석 항목 · 설비."""
    return {"patterns": [{"code": code, "name": p["name"], "items": deepcopy(p["items"]), "knowledge": deepcopy(p["knowledge"])}
                         for code, p in PATTERNS.items()],
            "assets": list(topics.ASSETS)}


def _text(body: dict, key: str, label: str, limit: int, required: bool = True) -> str:
    v = body.get(key)
    if v is None or (isinstance(v, str) and not v.strip()):
        if required:
            raise ValueError(f"{label}을(를) 입력하세요 ({key})")
        return ""
    if not isinstance(v, str):
        raise ValueError(f"{label}은(는) 글이어야 합니다 ({key})")
    v = " ".join(v.split()) if key != "memo" else v.strip()
    if len(v) > limit:
        raise ValueError(f"{label}은(는) {limit}자 이내로 입력하세요 ({key})")
    return v


def build_alert(body: dict, now: datetime | None = None) -> tuple[dict | None, str]:
    """입력 하나 → (경보 또는 None, 사유). 형식이 틀리면 ValueError(칸 이름 포함)."""
    if not isinstance(body, dict):
        raise ValueError("입력은 객체여야 합니다")
    code = _text(body, "pattern", "입력 종류", 64)
    spec = PATTERNS.get(code)
    if spec is None:
        raise ValueError(f"사람 입력 경보로 받지 않는 종류입니다: {code} (pattern)")
    asset = _text(body, "asset", "설비", 32)
    if asset not in topics.ASSETS:
        raise ValueError(f"없는 설비입니다: {asset} (asset — {', '.join(topics.ASSETS)})")
    item_key = _text(body, "item", "분석 항목", 32)
    item = next((i for i in spec["items"] if i["key"] == item_key), None)
    if item is None:
        raise ValueError(f"분석 항목 {item_key} 은(는) 목록에 없습니다 (item — {', '.join(i['key'] for i in spec['items'])})")
    out_of_spec = body.get("out_of_spec")
    if type(out_of_spec) is not bool:
        raise ValueError("기준 이탈 여부를 예/아니요로 고르세요 (out_of_spec)")
    value = body.get("value")
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
        raise ValueError("측정값은 숫자여야 합니다 (value)")
    by = _text(body, "by", "입력자", 120)
    by_name = _text(body, "by_name", "입력자 이름", 120, required=False) or by
    role = _text(body, "role", "입력자 역할", 120, required=False) or None
    memo = _text(body, "memo", "메모", 2000, required=False)
    if not out_of_spec:
        return None, (f"{item['text']} 이(가) 기준 안이라 경보를 만들지 않았습니다 — 지식의 패턴 검사(오일 분석 결과 기준 이탈 == 예)를 "
                      "충족하지 않습니다. 처리 건은 열리지 않습니다")
    clock = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    t = clock.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    alert_id = f"{asset}-{code}-H{clock.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(2)}"
    evidence = {"item": item["key"], "item_name": item["text"], "unit": item["unit"], "out_of_spec": True,
                spec["knowledge"]["variable"]: True}
    if value is not None:
        evidence["value"] = value
    if memo:
        evidence["memo"] = memo
    alert = {"alertId": alert_id, "asset": asset, "pattern": code, "severity": spec["severity"], "state": "RAISE", "t": t,
             "evidence": evidence, "source": HUMAN_SOURCE,
             "enteredBy": {"id": by, "name": by_name, **({"role": role} if role else {})}}
    return alert, f"{item['text']} 기준 이탈 — 센서 경보와 같은 경로로 경보를 보냈습니다"


def is_human_alert(alert) -> bool:
    return isinstance(alert, dict) and alert.get("source") == HUMAN_SOURCE and alert.get("pattern") in PATTERNS


def register(app, *, runtime_factory, admit, open_alerts=lambda: [], audit=lambda *a, **k: None):
    """API 3개. admit(alert) = 기존 경보 경로로 보내는 비동기 함수(main.py 가 원천 접수 경로로 준다).
    open_alerts() = 지금 사건이 있는 경보 목록[(alert, incident 상태)] — dmn-mcp diagnose 가 사람 입력 결과를 서버에서 읽는다."""
    import asyncio

    from fastapi import HTTPException

    def runtime():
        rt = runtime_factory()
        if rt is None:
            raise HTTPException(409, "사람 입력 경보는 instance 실행 서비스에서 받습니다 (PROCESS_MODE=instance)")
        return rt

    @app.get("/api/human-alerts/form")
    def human_alert_form():
        """입력 칸: 사람 입력 패턴 · 분석 항목 · 설비."""
        return form()

    @app.post("/api/human-alerts")
    async def raise_human_alert(body: dict):
        """오일 분석 결과 입력 → 기준 이탈이면 센서 경보와 같은 경로(원천 접수 → 경보 정책 → 처리 건 · 사건), 아니면 경보 없음 + 사유."""
        rt = runtime()
        try:
            alert, reason = build_alert(body)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        loop = asyncio.get_running_loop()
        if alert is None:
            await loop.run_in_executor(None, lambda: audit(body.get("asset") or "-", str(body.get("by") or "-"), "HUMAN_INPUT_IN_SPEC",
                                                           {"pattern": body.get("pattern"), "item": body.get("item"), "reason": reason}))
            return {"raised": False, "reason": reason}
        policy = await loop.run_in_executor(None, rt.alert_policy, alert["pattern"])
        try:
            await admit(alert)
        except (ValueError, LookupError) as e:
            raise HTTPException(409, f"경보를 접수하지 못했습니다: {e}") from e
        except TimeoutError as e:
            raise HTTPException(503, f"경보 접수 확인 시간이 지났습니다: {e}") from e
        target = policy["target"]
        inst = await loop.run_in_executor(None, rt.repo.find_event_instance, rt.tenant_id, target["definition"], alert["alertId"])
        try:
            name = (await loop.run_in_executor(None, rt.definition_for, {"proc_def_id": target["definition"], "proc_def_version": target["version"],
                                                                          "tenant_id": rt.tenant_id})).name
        except Exception:  # noqa: BLE001 — 이름은 표시용
            name = None
        from . import engine
        values = engine.variables(inst) if inst is not None else {}
        await loop.run_in_executor(None, lambda: audit(alert["asset"], alert["enteredBy"]["id"], "HUMAN_ALERT_RAISED",
                                                       {"alertId": alert["alertId"], "pattern": alert["pattern"], "route": policy["route"],
                                                        "definition": target}, incident=values.get("incident")))
        return {"raised": True, "reason": reason, "alert": alert,
                "route": policy["route"], "definition": dict(target, name=name),
                "route_text": ("배포된 흐름이 이 경보를 엽니다" if policy["route"] == "response"
                               else "이 경보를 여는 배포 흐름이 없어 사람 검토(경보 분류)로 갔습니다"),
                "instance": (inst or {}).get("proc_inst_id"), "incident": values.get("incident")}

    @app.get("/api/human-alerts/current")
    def current_human_alert(asset: str, pattern: str, alert_id: str | None = None):
        """사건이 열려 있는 사람 입력 경보(가장 최근) — 진단 도구가 사람이 입력한 결과를 근거로 읽는다. 없으면 404."""
        rows = [(a, state) for a, state in open_alerts() if is_human_alert(a) and a.get("asset") == asset and a.get("pattern") == pattern
                and (alert_id is None or a.get("alertId") == alert_id)]
        if not rows:
            raise HTTPException(404, f"{asset} 의 {pattern} 사람 입력 경보 중 처리 중인 것이 없습니다")
        alert, state = max(rows, key=lambda r: str(r[0].get("t") or ""))
        return {"alert": alert, "incident_state": state}
