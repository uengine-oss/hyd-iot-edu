"""실행 고리. 허용 목록에 있는 도구만 불러 사례마다 후보 원인을 가리고 점검 순서를 낸다.

    python 에이전트.py        모든 사례
    python 에이전트.py S01    그 사례만
"""
import json
import operator
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # __pycache__를 만들지 않는다

import 도구  # noqa: E402

_폴더 = Path(__file__).resolve().parent
_정의_경로 = _폴더 / "에이전트_정의.json"
_입력_경로 = _폴더 / "입력" / "센서_입력.json"
_결과_폴더 = _폴더 / "결과"

_비교 = {"lt": operator.lt, "gt": operator.gt, "gte": operator.ge}
_구분_순서 = {"확인됨": 0, "가설": 1, "해당_없음": 2}
_조치_종류 = {"MITIGATED_BY": "즉시_완화", "REMEDIED_BY": "근본_조치"}


def _읽기(경로):
    with open(경로, encoding="utf-8") as f:
        return json.load(f)


class 호출:
    """허용 목록에 있는 도구만 부르고, 부른 순서대로 적어 둔다."""

    def __init__(self, 허용):
        self.허용 = 허용
        self.기록 = []

    def 있음(self, 이름):
        return 이름 in self.허용

    def 부르기(self, 이름, **물음):
        if 이름 not in self.허용:
            raise SystemExit(f"허용 목록에 없는 도구는 부르지 않는다: {이름}")
        함수 = getattr(도구, 이름, None)
        if 함수 is None:
            raise SystemExit(f"허용 목록에는 있으나 도구.py에 없는 도구: {이름}")
        받음 = 함수(**물음)
        self.기록.append({"도구": 이름, "물음": 물음, "받음": 받음})
        return 받음


def _증거_판정(호출기, 번호, 기준, 신선함):
    """증거 한 건의 (판정, 읽은_값). 비교는 expect와 threshold 그대로 한다."""
    if not 신선함:
        return "확인하지_못함", None
    받음 = 호출기.부르기(
        "센서_집계", 사례=번호, tag=기준["tag"],
        aggregate=기준["aggregate"], windowSeconds=기준["windowSeconds"],
    ) or {}
    값 = 받음.get("value")
    관측 = 받음.get("coverage") or {}
    if 값 is None or 관측.get("covered") is not True:
        return "확인하지_못함", None
    return ("맞음" if _비교[기준["expect"]](값, 기준["threshold"]) else "아님"), 값


def _구분(판정들):
    if 판정들 and all(p == "맞음" for p in 판정들):
        return "확인됨"
    if 판정들 and all(p == "아님" for p in 판정들):
        return "해당_없음"
    return "가설"


def _근거_상태(구분들):
    if any(g == "확인됨" for g in 구분들):
        return "SUPPORTED"
    if 구분들 and all(g == "해당_없음" for g in 구분들):
        return "UNSUPPORTED"
    return "UNKNOWN"


def _붙일_조치(원인_id, 구분, 고장_유형들, 받은_조치):
    """원인 항목에 붙일 조치. 확인됨은 즉시 완화와 근본 조치, 가설은 근본 조치만."""
    붙임 = {}
    for 고장 in 고장_유형들:
        for 조치 in 받은_조치.get(고장, []):
            if 조치["맞는_원인"] and 원인_id not in 조치["맞는_원인"]:
                continue
            if 구분 == "가설" and 조치["관계"] != "REMEDIED_BY":
                continue
            첫_단계 = 조치["steps"][0] if 조치["steps"] else None
            붙임.setdefault(조치["id"], {
                "시점": "확인된 원인의 조치" if 구분 == "확인됨" else "확인된 뒤에 할 조치",
                "절차_번호": 조치["sopId"],
                "이름": 조치["name"],
                "종류": _조치_종류[조치["관계"]],
                "첫_단계": 첫_단계 and {"글": 첫_단계.get("text"), "근거_절": 첫_단계.get("section")},
                "승인_역할": 조치["승인_역할"]["name"] if 조치["승인_역할"] else "등록되지 않음",
            })
    # 즉시 완화를 앞에, 근본 조치를 뒤에 둔다(같은 종류 안에서는 온톨로지에 적힌 순서)
    return sorted(붙임.values(), key=lambda j: j["종류"] != "즉시_완화")


def 사례_처리(사례, 허용):
    번호 = 사례["번호"]
    호출기 = 호출(허용)

    # 후보 모으기: 원인이 없는 고장 유형은 지나가고, 같은 원인은 한 번만 적는다
    후보 = 호출기.부르기("원인_후보", 패턴_코드=사례["경보_패턴"])
    원인들 = {}
    원인의_고장_유형 = {}
    for 고장 in 후보["고장_유형"]:
        for 원인 in 고장["원인"]:
            원인들.setdefault(원인["id"], 원인)
            원인의_고장_유형.setdefault(원인["id"], []).append(고장["id"])

    # 센서 값을 읽는 도구가 목록에 없거나 신선도가 한도를 넘으면 증거는 모두 확인하지 못한다
    신선함 = False
    if 호출기.있음("센서_집계"):
        신선도 = (호출기.부르기("센서_집계", 사례=번호) or {}).get("freshness") or {}
        신선함 = 신선도.get("ok") is True

    후보_원인 = []
    사전_확률 = {}
    다시_확인 = {}  # (태그, 집계, 구간) → 근거 목록
    for 원인 in 원인들.values():
        증거 = []
        for 기준 in 호출기.부르기("증거_기준", 원인_식별자=원인["id"])["증거"]:
            판정, 값 = _증거_판정(호출기, 번호, 기준, 신선함)
            증거.append({
                "증거": 기준["id"],
                "판정": 판정,
                "읽은_값": 값,
                "기준": {k: 기준[k] for k in
                       ("tag", "aggregate", "windowSeconds", "expect", "threshold", "section")},
            })
            if 판정 == "확인하지_못함":
                열쇠 = (기준["tag"], 기준["aggregate"], 기준["windowSeconds"])
                다시_확인.setdefault(열쇠, []).append(
                    {"증거": 기준["id"], "읽은_값": 값, "근거_절": 기준["section"]})
        사전_확률[원인["id"]] = 원인["prior"]
        후보_원인.append({
            "원인": 원인["id"],
            "이름": 원인["name"],
            "구분": _구분([e["판정"] for e in 증거]),
            "증거": 증거,
        })

    # 확인됨 → 가설 → 해당_없음, 묶음 안에서는 사전 확률이 큰 순서(같으면 온톨로지에 적힌 순서)
    후보_원인.sort(key=lambda c: (_구분_순서[c["구분"]], -사전_확률[c["원인"]]))

    # 조치 방법은 후보 원인이 나온 고장 유형마다 묻는다
    받은_조치 = {}
    if 호출기.있음("조치_방법"):
        for 고장 in 후보["고장_유형"]:
            if 고장["원인"]:
                받은_조치[고장["id"]] = 호출기.부르기(
                    "조치_방법", 고장_유형_식별자=고장["id"])["조치"]

    점검 = [
        {"점검": {"내용": f"확인하지 못한 값 다시 확인: {태그} {집계} {구간}초 구간", "조치": []},
         "근거": 근거}
        for (태그, 집계, 구간), 근거 in 다시_확인.items()
    ]
    for 원인 in 후보_원인:
        if 원인["구분"] == "해당_없음":
            continue
        머리 = "확인된 원인" if 원인["구분"] == "확인됨" else "가설인 원인"
        점검.append({
            "점검": {
                "내용": f"{머리} 점검: {원인['이름']} ({원인['원인']})",
                "조치": _붙일_조치(원인["원인"], 원인["구분"],
                               원인의_고장_유형[원인["원인"]], 받은_조치),
            },
            "근거": [
                {"증거": e["증거"], "읽은_값": e["읽은_값"], "근거_절": e["기준"]["section"]}
                for e in 원인["증거"]
            ],
        })

    return {
        "번호": 번호,
        "근거_상태": _근거_상태([c["구분"] for c in 후보_원인]),
        "후보_원인": 후보_원인,
        "점검_순서": [{"순번": i, **p} for i, p in enumerate(점검, 1)],
        "호출_기록": 호출기.기록,
    }


def _글(값):
    return json.dumps(값, ensure_ascii=False)


def _기준_글(기준):
    return (f"{기준['aggregate']}({기준['tag']}) {기준['windowSeconds']}초 "
            f"{기준['expect']} {_글(기준['threshold'])} · 근거 절 {_글(기준['section'])}")


def 마크다운(결과들):
    줄 = ["# 점검 계획", ""]
    for 결과 in 결과들:
        줄 += [f"## {결과['번호']}", "", f"**근거 상태: {결과['근거_상태']}**", ""]
        for 구분, 제목 in (("확인됨", "확인된 원인"), ("가설", "가설"), ("해당_없음", "해당 없음")):
            줄 += [f"### {제목}", ""]
            원인들 = [c for c in 결과["후보_원인"] if c["구분"] == 구분]
            if not 원인들:
                줄 += ["없음", ""]
                continue
            for 원인 in 원인들:
                줄.append(f"- {원인['이름']} (`{원인['원인']}`)")
                if not 원인["증거"]:
                    줄.append("  - 증거: 없음")
                for e in 원인["증거"]:
                    줄.append(f"  - `{e['증거']}`: {e['판정']} · 읽은 값 {_글(e['읽은_값'])}"
                             f" · 기준 {_기준_글(e['기준'])}")
            줄.append("")
        줄 += ["### 점검 순서", ""]
        # 조치의 단계 전체는 호출 기록에 받아 둔 것에서 찾는다
        단계들 = {
            조치["sopId"]: 조치["steps"]
            for 호출_한_건 in 결과["호출_기록"] if 호출_한_건["도구"] == "조치_방법"
            for 조치 in 호출_한_건["받음"]["조치"]
        }
        if not 결과["점검_순서"]:
            줄.append("없음")
        for 점검 in 결과["점검_순서"]:
            줄.append(f"{점검['순번']}. {점검['점검']['내용']}")
            for g in 점검["근거"]:
                줄.append(f"   - 근거: `{g['증거']}` · 읽은 값 {_글(g['읽은_값'])}"
                         f" · 근거 절 {_글(g['근거_절'])}")
            for j in 점검["점검"]["조치"]:
                첫 = j["첫_단계"] or {}
                금지_단계 = [s for s in 단계들.get(j["절차_번호"], [])
                         if "금지" in (s.get("text") or "")]
                표시 = "[단계에 금지 문구 있음 · 원문 확인] " if 금지_단계 else ""
                줄.append(f"   - {표시}[{j['시점']}] {j['절차_번호']} {j['이름']} · {j['종류']}"
                         f" · 첫 단계 {_글(첫.get('글'))} (근거 절 {_글(첫.get('근거_절'))})"
                         f" · 승인 역할 {j['승인_역할']}")
                for s in 금지_단계:
                    줄.append(f"     - 금지 문구가 있는 단계 {s.get('order')}: {_글(s.get('text'))}"
                             f" (근거 절 {_글(s.get('section'))})")
        줄 += ["", "### 호출 기록", ""]
        for i, 호출_한_건 in enumerate(결과["호출_기록"], 1):
            줄.append(f"{i}. `{호출_한_건['도구']}` 물음 `{_글(호출_한_건['물음'])}`")
            줄.append(f"   - 받음: `{_글(호출_한_건['받음'])}`")
        줄.append("")
    return "\n".join(줄)


def main(인자):
    if len(인자) > 1:
        raise SystemExit("쓰는 법: python 에이전트.py [사례 번호]")
    허용 = _읽기(_정의_경로)["도구"]
    사례들 = _읽기(_입력_경로)
    if 인자:
        사례들 = [s for s in 사례들 if s["번호"] == 인자[0]]
        if not 사례들:
            raise SystemExit(f"입력에 없는 사례 번호: {인자[0]}")

    결과들 = [사례_처리(사례, 허용) for 사례 in 사례들]

    with open(_결과_폴더 / "점검_계획.json", "w", encoding="utf-8") as f:
        json.dump(결과들, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(_결과_폴더 / "점검_계획.md", "w", encoding="utf-8") as f:
        f.write(마크다운(결과들))


if __name__ == "__main__":
    main(sys.argv[1:])
