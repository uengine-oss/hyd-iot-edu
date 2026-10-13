"""결정표에 요청의 값을 대어 조치 후보의 허용과 제외를 가른다.

규칙과 기준값은 실행할 때마다 결정표/결정표.csv에서 읽는다.
"""

import csv
import json
import operator
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

폴더 = Path(__file__).resolve().parent
결정표_경로 = 폴더 / "결정표" / "결정표.csv"
요청_경로 = 폴더 / "입력" / "판정_요청.json"
결과_json_경로 = 폴더 / "결과" / "판정_결과.json"
결과_md_경로 = 폴더 / "결과" / "판정_결과.md"

필요한_열 = ("규칙", "입력", "비교", "기준값", "단위", "판정", "감점_만원", "대상", "근거_절", "원문")
비교_함수 = {
    "==": operator.eq,
    "!=": operator.ne,
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
}
글자에_쓰는_비교 = ("==", "!=")
제외, 감점, 경고 = "제외", "감점", "경고"
판정_종류 = (제외, 감점, 경고)
허용 = "허용"
모든_후보 = "모든 후보"
맞음, 확인되지_않음 = "맞음", "확인되지 않음"


class 멈춤(Exception):
    """추측하지 않고 멈춰야 하는 경우."""


def 숫자_읽기(글):
    try:
        수 = Decimal(글)
    except InvalidOperation:
        return None
    return 수 if 수.is_finite() else None


def 결정표_읽기():
    with open(결정표_경로, encoding="utf-8-sig", newline="") as 파일:
        표 = csv.DictReader(파일)
        없는_열 = [열 for 열 in 필요한_열 if 열 not in (표.fieldnames or [])]
        if 없는_열:
            raise 멈춤(f"결정표에 열이 없습니다: {', '.join(없는_열)}")
        행들 = [(표.line_num, 행) for 행 in 표]

    규칙들 = []
    for 줄, 행 in 행들:
        칸 = {열: (행.get(열) or "").strip() for 열 in 필요한_열}
        어디 = f"결정표 {줄}번째 줄({칸['규칙'] or '규칙 번호 없음'})"
        for 열 in ("규칙", "입력", "기준값", "대상"):
            if not 칸[열]:
                raise 멈춤(f"{어디}: '{열}' 칸이 비어 있습니다.")
        if 칸["비교"] not in 비교_함수:
            raise 멈춤(f"{어디}: 모르는 비교 기호 '{칸['비교']}'입니다.")
        if 칸["판정"] not in 판정_종류:
            raise 멈춤(f"{어디}: 모르는 판정 '{칸['판정']}'입니다.")

        기준값 = 숫자_읽기(칸["기준값"])
        숫자_비교 = 기준값 is not None
        if not 숫자_비교:
            기준값 = 칸["기준값"]
            if 칸["비교"] not in 글자에_쓰는_비교:
                raise 멈춤(f"{어디}: 글자 기준값 '{기준값}'은 '{칸['비교']}'로 견줄 수 없습니다.")

        감점_만원 = None
        if 칸["판정"] == 감점:
            감점_만원 = 숫자_읽기(칸["감점_만원"])
            if 감점_만원 is None:
                raise 멈춤(f"{어디}: 감점 금액 '{칸['감점_만원']}'이 숫자가 아닙니다.")

        if 칸["대상"] == 모든_후보:
            대상 = None
        else:
            대상 = [이름.strip() for 이름 in 칸["대상"].split(";") if 이름.strip()]

        규칙들.append({
            "규칙": 칸["규칙"],
            "입력": 칸["입력"],
            "비교": 칸["비교"],
            "기준값": 기준값,
            "숫자_비교": 숫자_비교,
            "단위": 칸["단위"],
            "판정": 칸["판정"],
            "감점_만원": 감점_만원,
            "대상": 대상,
            "근거_절": 칸["근거_절"],
            "원문": 칸["원문"],
        })
    return 규칙들


def 요청_읽기():
    with open(요청_경로, encoding="utf-8") as 파일:
        # 소수는 반올림 없이 견주려고 Decimal로 읽는다. NaN 같은 것은 글자로 남겨 숫자로 치지 않는다.
        자료 = json.load(파일, parse_float=Decimal, parse_constant=lambda 글: 글)

    요청들 = 자료.get("요청") if isinstance(자료, dict) else None
    if not isinstance(요청들, list):
        raise 멈춤("입력에 '요청' 목록이 없습니다.")
    for 순서, 요청 in enumerate(요청들, start=1):
        if not isinstance(요청, dict) or "번호" not in 요청:
            raise 멈춤(f"입력의 {순서}번째 요청에 '번호'가 없습니다.")
        if not isinstance(요청.get("후보"), list):
            raise 멈춤(f"요청 {요청['번호']}에 '후보' 목록이 없습니다.")
        for 후보 in 요청["후보"]:
            if not isinstance(후보, dict) or not isinstance(후보.get("sop"), str):
                raise 멈춤(f"요청 {요청['번호']}에 절차 번호(sop)가 없는 후보가 있습니다.")
    return 요청들


def 값_찾기(입력, 요청, 후보):
    """후보의 칸을 먼저 보고, 없으면 요청의 칸을 본다."""
    if 입력 in 후보:
        return 후보[입력]
    return 요청.get(입력)


def 대어_보기(규칙, 값):
    """조건이 맞으면 맞음, 값을 견줄 수 없으면 확인되지_않음, 맞지 않으면 None."""
    if 값 is None:
        return 확인되지_않음
    if 규칙["숫자_비교"]:
        if isinstance(값, bool) or not isinstance(값, (int, Decimal)):
            return 확인되지_않음
        값 = Decimal(값)
    elif not isinstance(값, str):
        return 확인되지_않음
    return 맞음 if 비교_함수[규칙["비교"]](값, 규칙["기준값"]) else None


def 후보_판정(규칙들, 요청, 후보):
    근거 = []
    for 규칙 in 규칙들:
        if 규칙["대상"] is not None and 후보["sop"] not in 규칙["대상"]:
            continue
        값 = 값_찾기(규칙["입력"], 요청, 후보)
        상태 = 대어_보기(규칙, 값)
        if 상태 is None:
            continue
        항목 = {
            "규칙": 규칙["규칙"],
            "판정": 규칙["판정"],
            "상태": 상태,
            "조건": {
                "입력": 규칙["입력"],
                "비교": 규칙["비교"],
                "기준값": 규칙["기준값"],
                "단위": 규칙["단위"],
            },
            "대어_본_값": 값,
        }
        if 규칙["판정"] == 감점:
            항목["감점_만원"] = 규칙["감점_만원"]
        항목["근거_절"] = 규칙["근거_절"]
        항목["원문"] = 규칙["원문"]
        근거.append(항목)

    제외됨 = any(
        (항목["상태"] == 맞음 and 항목["판정"] == 제외)
        or (항목["상태"] == 확인되지_않음 and 항목["판정"] in (제외, 감점))
        for 항목 in 근거
    )
    return {
        "후보": 후보["sop"],
        "판정": 제외 if 제외됨 else 허용,
        "맞은_규칙": [항목["규칙"] for 항목 in 근거 if 항목["상태"] == 맞음],
        "근거": 근거,
    }


def 요청_판정(규칙들, 요청):
    후보별_판정 = [후보_판정(규칙들, 요청, 후보) for 후보 in 요청["후보"]]
    return {
        "번호": 요청["번호"],
        "후보별_판정": 후보별_판정,
        "남은_후보": [판정["후보"] for 판정 in 후보별_판정 if 판정["판정"] == 허용],
    }


def 숫자_내보내기(값):
    if isinstance(값, Decimal):
        return int(값) if 값.as_tuple().exponent >= 0 else float(값)
    raise TypeError(f"JSON으로 적을 수 없는 값입니다: {값!r}")


def 값_보이기(값):
    if 값 is None:
        return "없음"
    if isinstance(값, str):
        return 값
    return json.dumps(값, ensure_ascii=False, default=숫자_내보내기)


def 칸에_넣기(글):
    return str(글).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def 근거_한_줄(항목):
    조건 = 항목["조건"]
    줄 = f"{항목['규칙']} {항목['판정']}"
    if "감점_만원" in 항목:
        줄 += f" {값_보이기(항목['감점_만원'])}만 원"
    if 항목["상태"] == 확인되지_않음:
        줄 += " (확인되지 않은 조건)"
    줄 += f" — {조건['입력']} {조건['비교']} {값_보이기(조건['기준값'])}"
    if 조건["단위"]:
        줄 += f" {조건['단위']}"
    줄 += f", 대어 본 값 {값_보이기(항목['대어_본_값'])}, {항목['근거_절']}, 「{항목['원문']}」"
    return 줄


def 제외_까닭(후보):
    """이미 나온 근거에서 제외의 까닭이 된 규칙만 골라 적는다."""
    까닭 = []
    for 항목 in 후보["근거"]:
        if 항목["상태"] == 맞음 and 항목["판정"] == 제외:
            까닭.append(항목["규칙"])
        elif 항목["상태"] == 확인되지_않음 and 항목["판정"] in (제외, 감점):
            까닭.append(f"{항목['규칙']} {확인되지_않음}")
    return ", ".join(까닭)


def 요약_만들기(결과):
    줄들 = ["## 요약", "", "| 요청 번호 | 남은 후보 | 제외된 후보 |", "|---|---|---|"]
    for 판정 in 결과:
        남은 = ", ".join(판정["남은_후보"]) if 판정["남은_후보"] else "조치 불가"
        제외된 = ", ".join(
            f"{후보['후보']} ({제외_까닭(후보)})"
            for 후보 in 판정["후보별_판정"]
            if 후보["판정"] == 제외
        ) or "없음"
        줄들.append(f"| {칸에_넣기(판정['번호'])} | {칸에_넣기(남은)} | {칸에_넣기(제외된)} |")
    줄들.append("")
    return 줄들


def md_만들기(요청들, 결과):
    줄들 = ["# 판정 결과", ""]
    줄들.extend(요약_만들기(결과))
    for 요청, 판정 in zip(요청들, 결과):
        줄들.append(f"## {판정['번호']}")
        줄들.append("")
        if isinstance(요청.get("메모"), str):
            줄들.append(f"- 메모: {요청['메모']}")
        남은 = ", ".join(판정["남은_후보"]) if 판정["남은_후보"] else "조치 불가"
        줄들.append(f"- 남은 후보: {남은}")
        줄들.append("")
        줄들.append("| 후보 | 판정 | 맞은 규칙 | 확인되지 않은 규칙 | 근거 |")
        줄들.append("|---|---|---|---|---|")
        for 후보 in 판정["후보별_판정"]:
            맞은 = ", ".join(후보["맞은_규칙"]) or "없음"
            확인_안_된 = ", ".join(
                항목["규칙"] for 항목 in 후보["근거"] if 항목["상태"] == 확인되지_않음
            ) or "없음"
            근거 = "<br>".join(칸에_넣기(근거_한_줄(항목)) for 항목 in 후보["근거"]) or "없음"
            줄들.append(
                f"| {칸에_넣기(후보['후보'])} | {후보['판정']} | {칸에_넣기(맞은)} "
                f"| {칸에_넣기(확인_안_된)} | {근거} |"
            )
        줄들.append("")
    return "\n".join(줄들)


def main():
    try:
        규칙들 = 결정표_읽기()
        요청들 = 요청_읽기()
    except 멈춤 as 까닭:
        print(f"판정을 멈춥니다: {까닭}", file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError, csv.Error) as 까닭:
        print(f"판정을 멈춥니다: 파일을 읽지 못했습니다. {까닭}", file=sys.stderr)
        return 1

    결과 = [요청_판정(규칙들, 요청) for 요청 in 요청들]
    json_글 = json.dumps(결과, ensure_ascii=False, indent=2, default=숫자_내보내기) + "\n"
    md_글 = md_만들기(요청들, 결과)

    결과_json_경로.parent.mkdir(exist_ok=True)
    with open(결과_json_경로, "w", encoding="utf-8", newline="\n") as 파일:
        파일.write(json_글)
    with open(결과_md_경로, "w", encoding="utf-8", newline="\n") as 파일:
        파일.write(md_글)
    return 0


if __name__ == "__main__":
    sys.exit(main())
