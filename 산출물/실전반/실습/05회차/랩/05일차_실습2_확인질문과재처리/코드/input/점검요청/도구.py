"""도구. 원자료 파일을 읽어 물음에 맞는 것을 돌려주기만 하고, 판정하지 않는다.

원자료 폴더(기본: 이 폴더의 두 단계 위 `source/`)의 아래 파일을 읽는다.
- 온톨로지/graph.json      설비 진단 그래프(노드 · 관계)
- 입력/센서_입력.json       경보 사례마다 판단 시각에 읽은 값의 묶음
- 매뉴얼/*.md              원인별 관련 부품을 적은 매뉴얼 원문
"""
from __future__ import annotations

import json
import re
from pathlib import Path


class 조회_오류(Exception):
    """원자료를 읽지 못했다(파일 없음 · 형식 오류 등). 값이 없는 것과 다르다."""


def _json(경로: Path):
    try:
        with open(경로, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        raise 조회_오류(f"{경로}: {exc}") from exc


class 그래프:
    def __init__(self, 경로: Path):
        원본 = _json(경로)
        self.노드 = {n["props"]["id"]: n for n in 원본["nodes"]}
        self.관계 = 원본["rels"]

    def 속성(self, 식별자):
        return self.노드[식별자]["props"]

    def 이어진(self, 종류, a=None, b=None):
        return [r for r in self.관계
                if r["type"] == 종류 and (a is None or r["a"] == a) and (b is None or r["b"] == b)]


def 원인_후보(g: 그래프, 패턴_코드):
    """경보 패턴의 코드 → 그 패턴이 감지하는 증상이 가리키는 고장 유형과 원인 후보."""
    패턴 = next((n["props"] for n in g.노드.values()
               if "AnomalyPattern" in n["labels"] and n["props"].get("code") == 패턴_코드), None)
    if 패턴 is None:
        return {"패턴": None, "고장_유형": []}
    고장_유형 = []
    for 증상 in g.이어진("DETECTS", a=패턴["id"]):
        for 가리킴 in g.이어진("INDICATES", a=증상["b"]):
            if 가리킴["b"] not in [f["id"] for f in 고장_유형]:
                고장_유형.append({"id": 가리킴["b"], "name": g.속성(가리킴["b"])["name"]})
    for 고장 in 고장_유형:
        고장["원인"] = [{"id": r["a"], **{k: g.속성(r["a"]).get(k) for k in ("name", "aliases", "prior", "section")}}
                      for r in g.이어진("CAUSES", b=고장["id"])]
        고장["구성_요소"] = [g.속성(r["b"])["name"] for r in g.이어진("OCCURS_IN", a=고장["id"])]
    return {"패턴": {"id": 패턴["id"], "name": 패턴["name"], "code": 패턴["code"]}, "고장_유형": 고장_유형}


def 증거_기준(g: 그래프, 원인_식별자):
    """원인 → 그 원인의 증거(태그 · 집계 · 구간 · 비교 방향 · 기준값 · 근거 절)."""
    칸 = ("id", "name", "tag", "aggregate", "windowSeconds", "expect", "threshold", "section")
    return [{k: g.속성(r["b"]).get(k) for k in 칸} for r in g.이어진("EVIDENCED_BY", a=원인_식별자)]


def 조치_방법(g: 그래프, 고장_유형_식별자):
    """고장 유형 → 조치 방법(절차 번호 · 종류 · 단계 · 승인 역할 · 맞는 원인)."""
    조치 = []
    for r in g.관계:
        if r["type"] not in ("MITIGATED_BY", "REMEDIED_BY") or r["a"] != 고장_유형_식별자:
            continue
        스킬 = g.속성(r["b"])
        역할 = next((g.속성(a["b"]) for a in g.이어진("APPROVED_BY", a=스킬["id"])), None)
        조치.append({
            "id": 스킬["id"], "sopId": 스킬.get("sopId"), "name": 스킬.get("name"),
            "관계": r["type"], "steps": 스킬.get("steps", []),
            "승인_역할": 역할, "맞는_원인": [a["b"] for a in g.이어진("ADDRESSES", a=스킬["id"])],
        })
    return 조치


def 역할(g: 그래프, 이름):
    """역할 이름 → 역할 노드(이름 · 등급). 없으면 None."""
    return next((n["props"] for n in g.노드.values()
                 if "Role" in n["labels"] and n["props"].get("name") == 이름), None)


def 센서_사례(경로: Path, 번호):
    """사례 번호 → 센서 입력의 그 사례 한 건. 입력에 없으면 None. 파일을 못 읽으면 조회_오류."""
    return next((s for s in _json(경로) if s.get("번호") == 번호), None)


def 센서_집계(사례, tag, aggregate, windowSeconds):
    """사례 한 건에서 태그 · 집계 · 구간이 같은 값과 관측 충분성. 없으면 빈 dict."""
    return next((r for r in 사례.get("readings", [])
                 if r["tag"] == tag and r["aggregate"] == aggregate and r["windowSeconds"] == windowSeconds), {})


def 관련_부품(매뉴얼_폴더: Path, 원인):
    """원인 이름 · 별칭이 들어 있고 「관련 부품은 …다」가 적힌 매뉴얼 줄에서 부품 이름과 출처를 찾는다.
    부품 번호는 예비품 기준서 표의 「이름 (P-…)」에서 찾는다. 찾지 못하면 빈 목록."""
    if not 매뉴얼_폴더.is_dir():
        raise 조회_오류(f"{매뉴얼_폴더}: 매뉴얼 폴더 없음")
    이름들 = [원인["name"], *(원인.get("aliases") or [])]
    글들 = {p.name: p.read_text(encoding="utf-8") for p in sorted(매뉴얼_폴더.glob("*.md"))}
    찾음 = []
    for 파일, 글 in 글들.items():
        for 줄 in 글.splitlines():
            m = re.search(r"관련 부품은 (.+?)다\.", 줄)
            if m and any(이름 in 줄 for 이름 in 이름들):
                부품 = m.group(1).strip()
                번호 = None
                for 다른_글 in 글들.values():
                    n = re.search(re.escape(부품) + r" \((P-[A-Z-]+)\)", 다른_글)
                    if n:
                        번호 = n.group(1)
                        break
                찾음.append({"부품": 부품, "부품_번호": 번호, "출처": 파일})
    return 찾음
