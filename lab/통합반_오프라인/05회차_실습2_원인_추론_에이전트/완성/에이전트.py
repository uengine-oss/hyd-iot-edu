"""실행 고리. 모델이 허용 목록의 도구를 골라 부르고, 읽은 것으로 후보 원인을 가려 점검 순서를 낸다.

    python 에이전트.py        모든 사례
    python 에이전트.py S01    그 사례만
"""
import inspect
import json
import operator
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # __pycache__를 만들지 않는다

import 도구  # noqa: E402
import 모델  # noqa: E402

_폴더 = Path(__file__).resolve().parent
_정의_경로 = _폴더 / "에이전트_정의.json"
_입력_경로 = _폴더 / "입력" / "센서_입력.json"
_결과_폴더 = _폴더 / "결과"

_비교 = {"lt": operator.lt, "gt": operator.gt, "gte": operator.ge}
_자료형 = {str: "string", int: "integer", float: "number"}

_답의_모양 = """모든 도구 호출을 마친 뒤, 다른 말 없이 아래 모양의 JSON 하나만 답한다.
{"번호": "사례 번호",
 "근거_상태": "SUPPORTED | UNKNOWN | UNSUPPORTED",
 "후보_원인": [{"원인": "원인의 식별자", "이름": "원인의 이름", "구분": "확인됨 | 가설 | 해당_없음",
              "증거": [{"증거": "증거의 식별자", "판정": "맞음 | 아님 | 확인하지_못함", "읽은_값": 숫자 또는 null}]}],
 "점검_순서": [{"순번": 1, "점검": "무엇을 점검하는지 한 문장", "근거": ["증거의 식별자"], "조치": ["절차 번호"]}]}"""


def _읽기(경로):
    with open(경로, encoding="utf-8") as f:
        return json.load(f)


def _도구_설명(허용):
    """허용 목록의 도구를 모델에게 알려 줄 모양으로 바꾼다. 설명은 도구.py의 함수에 적힌 글을 그대로 쓴다."""
    설명 = []
    for 이름 in 허용:
        함수 = getattr(도구, 이름, None)
        if 함수 is None:
            raise SystemExit(f"허용 목록에는 있으나 도구.py에 없는 도구: {이름}")
        인자 = inspect.signature(함수).parameters
        설명.append({"type": "function", "function": {
            "name": 이름,
            "description": inspect.getdoc(함수),
            "parameters": {
                "type": "object",
                "properties": {k: {"type": _자료형.get(v.annotation, "string")} for k, v in 인자.items()},
                "required": [k for k, v in 인자.items() if v.default is inspect.Parameter.empty],
            },
        }})
    return 설명


def _고리(사례, 정의):
    """모델에게 묻고, 모델이 부른 도구를 대신 실행해 돌려주기를 되풀이한다. (모델의 마지막 답, 호출 기록, 멈춘 까닭)"""
    허용 = 정의["도구"]
    지시 = "\n".join([f"당신은 {정의['이름']}입니다.", f"목표: {정의['목표']}", "작업 규칙:"]
                   + [f"- {규칙}" for 규칙 in 정의["작업_규칙"]] + ["", _답의_모양])
    대화 = [{"role": "system", "content": 지시},
          {"role": "user", "content": f"사례 번호 {사례['번호']}, 경보 패턴 {사례['경보_패턴']}"}]
    기록, 본_물음, 도구_거둠 = [], set(), False

    for _ in range(정의["멈춤_조건"]["최대_횟수"]):
        답 = 모델.묻기(대화, None if 도구_거둠 else _도구_설명(허용))
        부름 = 답.get("tool_calls") or []
        if not 부름:
            return 답.get("content") or "", 기록, "같은 물음을 되풀이해 도구를 거두고 답을 받음" if 도구_거둠 else "답을 냄"
        대화.append({"role": "assistant", "content": 답.get("content") or "", "tool_calls": 부름})
        for 한_건 in 부름:
            이름, 물음_글 = 한_건["function"]["name"], 한_건["function"]["arguments"]
            if (이름, 물음_글) in 본_물음:
                도구_거둠 = True
            본_물음.add((이름, 물음_글))
            if 이름 not in 허용:
                물음, 받음 = 물음_글, {"거절": f"허용 목록에 없는 도구는 부르지 않는다: {이름}"}
            else:
                try:
                    물음 = json.loads(물음_글)
                    받음 = getattr(도구, 이름)(**물음)
                except (TypeError, ValueError) as 오류:
                    물음, 받음 = 물음_글, {"오류": f"물음의 모양이 맞지 않는다: {오류}"}
            기록.append({"도구": 이름, "물음": 물음, "받음": 받음})
            대화.append({"role": "tool", "tool_call_id": 한_건["id"], "content": json.dumps(받음, ensure_ascii=False)})
        if 도구_거둠:
            대화.append({"role": "user", "content": "같은 물음을 되풀이했습니다. 필요한 값은 이미 받았습니다. 이제 도구를 부르지 말고 정해진 모양의 JSON만 답하세요."})
    return "", 기록, "횟수 한도에 닿아 멈춤"


def _대조(답, 기록):
    """모델의 답을 호출 기록에 대어 본다. 기록에 없는 것을 적었거나 값과 판정이 어긋나면 그 목록을 돌려준다."""
    기준들, 값들, 절차들, 원인들, 신선함 = {}, {}, set(), set(), None
    for 한_건 in 기록:
        받음, 물음 = 한_건["받음"], 한_건["물음"]
        if not isinstance(받음, dict) or not isinstance(물음, dict):
            continue
        if 한_건["도구"] == "원인_후보":
            원인들 |= {원인["id"] for 고장 in 받음.get("고장_유형", []) for 원인 in 고장["원인"]}
        elif 한_건["도구"] == "증거_기준":
            기준들.update({증거["id"]: 증거 for 증거 in 받음.get("증거", [])})
        elif 한_건["도구"] == "센서_집계":
            if "freshness" in 받음:
                신선함 = (받음["freshness"] or {}).get("ok") is True
            else:
                값들[(받음["tag"], 받음["aggregate"], 받음["windowSeconds"])] = 받음
        elif 한_건["도구"] == "조치_방법":
            절차들 |= {조치["sopId"] for 조치 in 받음.get("조치", [])}

    어긋남 = []
    for 원인 in 답.get("후보_원인", []):
        if 원인.get("원인") not in 원인들:
            어긋남.append(f"호출 기록에 없는 원인: {원인.get('원인')}")
        for 증거 in 원인.get("증거", []):
            기준 = 기준들.get(증거.get("증거"))
            if 기준 is None:
                어긋남.append(f"호출 기록에 없는 증거: {증거.get('증거')}")
                continue
            읽음 = 값들.get((기준["tag"], 기준["aggregate"], 기준["windowSeconds"]))
            if 읽음 is None:
                if 증거.get("판정") != "확인하지_못함":
                    어긋남.append(f"{증거['증거']}: 값을 읽은 기록이 없는데 판정이 {증거.get('판정')}")
                continue
            값, 관측 = 읽음.get("value"), 읽음.get("coverage") or {}
            if 값 is None or 관측.get("covered") is not True or 신선함 is not True:
                continue  # 값이 없거나 관측이 모자라거나 신선하지 않은 것은 사람이 정한 규칙의 몫이라 대조하지 않는다
            맞는_판정 = "맞음" if _비교[기준["expect"]](값, 기준["threshold"]) else "아님"
            if 증거.get("읽은_값") != 값:
                어긋남.append(f"{증거['증거']}: 읽은_값 {증거.get('읽은_값')}, 호출 기록의 값 {값}")
            if 증거.get("판정") != 맞는_판정:
                어긋남.append(f"{증거['증거']}: 판정 {증거.get('판정')}, 값 {값}을 기준({기준['expect']} {기준['threshold']})에 대면 {맞는_판정}")
    # 근거_상태는 사람이 정한 규칙(확인됨이 하나라도 있으면 SUPPORTED, 모두 해당_없음이면 UNSUPPORTED, 그 밖은 UNKNOWN)에 대어 본다
    구분들 = [원인.get("구분") for 원인 in 답.get("후보_원인", [])]
    if "확인됨" in 구분들:
        맞는_상태 = "SUPPORTED"
    elif 구분들 and all(구분 == "해당_없음" for 구분 in 구분들):
        맞는_상태 = "UNSUPPORTED"
    else:
        맞는_상태 = "UNKNOWN"
    if 답.get("근거_상태") != 맞는_상태:
        어긋남.append(f"근거_상태 {답.get('근거_상태')}, 원인의 구분({', '.join(map(str, 구분들)) or '후보 없음'})에 대면 {맞는_상태}")
    for 점검 in 답.get("점검_순서", []):
        for 절차 in 점검.get("조치") or []:
            if 절차 not in 절차들:
                어긋남.append(f"호출 기록에 없는 절차 번호: {절차}")
    return 어긋남


def 사례_처리(사례, 정의):
    글, 기록, 멈춤 = _고리(사례, 정의)
    찾음 = re.search(r"\{[\s\S]*\}", 글)
    try:
        답 = json.loads(찾음.group(0)) if 찾음 else None
    except ValueError:
        답 = None
    if not isinstance(답, dict):
        return {
            "번호": 사례["번호"], "근거_상태": "UNKNOWN", "후보_원인": [],
            "점검_순서": [{"순번": 1, "점검": "에이전트가 답을 내지 못했다. 사람이 직접 확인한다.", "근거": [], "조치": []}],
            "호출_기록": 기록, "대조": [], "멈춤": 멈춤 if 멈춤.startswith("횟수") else "답이 정해진 모양이 아님",
        }
    return {
        "번호": 사례["번호"],
        "근거_상태": 답.get("근거_상태"),
        "후보_원인": 답.get("후보_원인", []),
        "점검_순서": 답.get("점검_순서", []),
        "호출_기록": 기록,
        "대조": _대조(답, 기록),
        "멈춤": 멈춤,
    }


def _글(값):
    return json.dumps(값, ensure_ascii=False)


def 마크다운(결과들):
    줄 = ["# 점검 계획", ""]
    for 결과 in 결과들:
        줄 += [f"## {결과['번호']}", "", f"**근거 상태: {결과['근거_상태']}** · 멈춤: {결과['멈춤']}", ""]
        줄 += ["### 대조", ""]
        줄 += [f"- {한_줄}" for 한_줄 in 결과["대조"]] or ["어긋남 없음"]
        줄.append("")
        for 구분, 제목 in (("확인됨", "확인된 원인"), ("가설", "가설"), ("해당_없음", "해당 없음")):
            줄 += [f"### {제목}", ""]
            원인들 = [c for c in 결과["후보_원인"] if c.get("구분") == 구분]
            if not 원인들:
                줄 += ["없음", ""]
                continue
            for 원인 in 원인들:
                줄.append(f"- {원인.get('이름')} (`{원인.get('원인')}`)")
                for e in 원인.get("증거") or []:
                    줄.append(f"  - `{e.get('증거')}`: {e.get('판정')} · 읽은 값 {_글(e.get('읽은_값'))}")
                if not 원인.get("증거"):
                    줄.append("  - 증거: 없음")
            줄.append("")
        줄 += ["### 점검 순서", ""]
        for 점검 in 결과["점검_순서"]:
            줄.append(f"{점검.get('순번')}. {점검.get('점검')}")
            if 점검.get("근거"):
                줄.append("   - 근거: " + ", ".join(f"`{g}`" for g in 점검["근거"]))
            if 점검.get("조치"):
                줄.append("   - 조치: " + ", ".join(점검["조치"]))
        if not 결과["점검_순서"]:
            줄.append("없음")
        줄 += ["", "### 호출 기록", ""]
        for i, 한_건 in enumerate(결과["호출_기록"], 1):
            줄.append(f"{i}. `{한_건['도구']}` 물음 `{_글(한_건['물음'])}`")
        줄.append("")
    return "\n".join(줄)


def main(인자):
    if len(인자) > 1:
        raise SystemExit("쓰는 법: python 에이전트.py [사례 번호]")
    정의 = _읽기(_정의_경로)
    사례들 = _읽기(_입력_경로)
    if 인자:
        사례들 = [s for s in 사례들 if s["번호"] == 인자[0]]
        if not 사례들:
            raise SystemExit(f"입력에 없는 사례 번호: {인자[0]}")

    결과들 = []
    for 사례 in 사례들:
        결과 = 사례_처리(사례, 정의)
        결과들.append(결과)
        print(f"{결과['번호']}  {결과['근거_상태']}  도구 호출 {len(결과['호출_기록'])}번  대조 어긋남 {len(결과['대조'])}건  ({결과['멈춤']})")

    with open(_결과_폴더 / "점검_계획.json", "w", encoding="utf-8") as f:
        json.dump(결과들, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(_결과_폴더 / "점검_계획.md", "w", encoding="utf-8") as f:
        f.write(마크다운(결과들))


if __name__ == "__main__":
    main(sys.argv[1:])
