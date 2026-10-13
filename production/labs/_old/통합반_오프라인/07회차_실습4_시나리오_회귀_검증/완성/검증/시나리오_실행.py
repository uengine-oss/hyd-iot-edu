"""시나리오 실행. 검증/시나리오.feature의 문장마다 그 문장이 뜻하는 일을 하거나 확인한다.
요청은 요청_처리.py의 요청_처리 함수를 그대로 불러 처리한다. 시나리오에 적힌 사람의 답과 결정은
파일에 쓰지 않고 함수에 넘기며, 사람/ 폴더의 두 파일은 읽지 않는다.

    python 검증/시나리오_실행.py         모든 시나리오
    python 검증/시나리오_실행.py 긴급    이름에 그 글자가 든 시나리오만
"""
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # __pycache__를 만들지 않는다

_폴더 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_폴더))

import 견주기  # noqa: E402
import 도구  # noqa: E402
import 요청_처리  # noqa: E402

_시나리오_경로 = _폴더 / "검증" / "시나리오.feature"
_결과_폴더 = _폴더 / "결과"
_이력_머리 = ["| 차례 | 실행한 시나리오 수 | 통과 | 실패 | 실패한 시나리오 |", "|---|---|---|---|---|"]

_머리_낱말 = "Scenario:"
_낱말 = ("Given", "When", "Then", "And")
_끝 = r"(?:이다|다)"
_참거짓 = {"true": True, "false": False, "null": None}


def _글(값):
    return json.dumps(값, ensure_ascii=False)


def _값(글):
    """문장에 적힌 「없음」과 null은 None이다."""
    return None if 글 in ("없음", "null") else 글


# Given: 주어진 것을 확인하거나 함수에 넘길 것으로 둔다. 어긋나면 실제로 본 것을 돌려준다.

def _요청에_적힌_것(상황, m):
    번호 = m[1]
    적힌 = {"설비": _값(m[2]), "경보_패턴": _값(m[3]), "사례": _값(m[4])}
    요청 = next((r for r in 요청_처리._목록_읽기(요청_처리._요청_경로)
               if isinstance(r, dict) and r.get("번호") == 번호), None)
    if 요청 is None:
        return f"입력/점검_요청.json에 {번호}가 없음"
    입력에 = {칸: 요청.get(칸) for 칸 in 적힌}
    if 입력에 != 적힌:
        return f"입력/점검_요청.json의 {번호}에 적힌 것: {_글(입력에)}"
    상황["요청"] = 요청
    return None


def _답(상황, m):
    상황["답들"].append({"요청": m[1], "질문": int(m[2]), "답": m[3], "답한_사람": m[4]})
    return None


def _답한_사람_없는_답(상황, m):
    상황["답들"].append({"요청": m[1], "질문": int(m[2]), "답": m[3], "답한_사람": None})
    return None


def _답_없음(상황, m):
    if 상황["답들"]:
        return f"앞 문장에서 주어진 답이 있음: {_글(상황['답들'])}"
    return None


def _그_질문의_답_없음(상황, m):
    있는_답 = [a for a in 상황["답들"] if a["요청"] == m[1] and a["질문"] == int(m[2])]
    if 있는_답:
        return f"앞 문장에서 주어진 답이 있음: {_글(있는_답)}"
    return None


def _결정_없음(상황, m):
    if 상황["결정들"]:
        return f"앞 문장에서 주어진 결정이 있음: {_글(상황['결정들'])}"
    return None


def _승인(상황, m):
    상황["결정들"].append({"요청": m[3], "결정": "승인", "절차_번호": m[4],
                       "역할": m[1], "이름": m[2], "사유": None})
    return None


def _거절(상황, m):
    상황["결정들"].append({"요청": m[3], "결정": "거절", "절차_번호": None,
                       "역할": m[1], "이름": m[2], "사유": m[4]})
    return None


def _사례의_경보_패턴(상황, m):
    사례 = next((s for s in 요청_처리._목록_읽기(요청_처리._입력_경로)
               if isinstance(s, dict) and s.get("번호") == m[1]), None)
    if 사례 is None:
        return f"입력/센서_입력.json에 {m[1]}이 없음"
    if 사례.get("경보_패턴") != m[2]:
        return f"입력/센서_입력.json의 {m[1]}의 경보 패턴: {_글(사례.get('경보_패턴'))}"
    return None


def _집계(m):
    return 도구.센서_집계(사례=m[1], tag=m[2], aggregate=m[3], windowSeconds=int(m[4])) or {}


def _센서_값(상황, m):
    값 = _집계(m).get("value")
    if isinstance(값, bool) or not isinstance(값, (int, float)) or 값 != float(m[5]):
        return f"센서_집계가 돌려준 value: {_글(값)}"
    return None


def _관측_충분(상황, m):
    관측 = _집계(m).get("coverage")
    if (관측 or {}).get("covered") is not True:
        return f"센서_집계가 돌려준 coverage: {_글(관측)}"
    return None


def _신선도(상황, m):
    신선도 = (도구.센서_집계(사례=m[1]) or {}).get("freshness")
    if (신선도 or {}).get("ok") is not True:
        return f"센서_집계가 돌려준 freshness: {_글(신선도)}"
    return None


def _신선도_넘음(상황, m):
    신선도 = (도구.센서_집계(사례=m[1]) or {}).get("freshness")
    if (신선도 or {}).get("ok") is True:
        return f"센서_집계가 돌려준 freshness: {_글(신선도)}"
    return None


# When: 요청_처리.py의 함수를 그대로 부른다. 넘기는 것은 main()이 넘기는 것과 같은 모양이다.

def _처리(상황, m):
    요청 = 상황["요청"]
    if 요청 is None:
        return "Given에서 확인한 요청이 없음"
    if 요청["번호"] != m[1]:
        return f"Given에서 확인한 요청은 {요청['번호']}"
    사례들 = [{칸: s[칸] for 칸 in 요청_처리._사례_칸}
           for s in 요청_처리._목록_읽기(요청_처리._입력_경로)]
    허용 = 요청_처리._읽기(요청_처리._정의_경로)["도구"]
    기준 = 요청_처리._기준_읽기(요청_처리._기준_경로)
    상황["결과"], _ = 요청_처리.요청_처리(요청, 사례들, 상황["답들"], 상황["결정들"], 허용, 기준)
    return None


# Then: 함수가 돌려준 결과 항목에서 확인한다.

def _칸이_같다(칸):
    def 확인(상황, m):
        실제 = 상황["결과"].get(칸)
        return None if 실제 == _값(m[1]) else f"{칸}: {_글(실제)}"
    return 확인


def _확정_아님(상황, m):
    실제 = 상황["결과"].get("상태")
    return f"상태: {_글(실제)}" if 실제 == "확정" else None


def _긴급(상황, m):
    실제 = 상황["결과"].get("긴급", "칸이 없음")
    return None if 실제 is _참거짓[m[1]] else f"긴급: {_글(실제)}"


def _승인_비어_있음(상황, m):
    실제 = 상황["결과"].get("승인", "칸이 없음")
    return None if 실제 is None else f"승인: {_글(실제)}"


def _질문_한_건(상황, m):
    질문 = 상황["결과"].get("질문")
    if not isinstance(질문, list) or len(질문) != 1:
        return f"질문: {_글(질문)}"
    return None


def _선택지(상황, m):
    순번 = int(m[1])
    기대 = [] if m.lastindex == 1 else m[2].split(", ")
    질문 = 상황["결과"].get("질문") or []
    한_건 = next((q for q in 질문 if isinstance(q, dict) and q.get("순번") == 순번), None)
    if 한_건 is None:
        return f"질문 {순번}번이 없음 (낸 질문 {len(질문)}건)"
    if 한_건.get("선택지") != 기대:
        return f"질문 {순번}번의 선택지: {_글(한_건.get('선택지'))}"
    return None


def _질문의_답_비어_있음(상황, m):
    순번 = int(m[1])
    질문 = 상황["결과"].get("질문") or []
    한_건 = next((q for q in 질문 if isinstance(q, dict) and q.get("순번") == 순번), None)
    if 한_건 is None:
        return f"질문 {순번}번이 없음 (낸 질문 {len(질문)}건)"
    실제 = 한_건.get("답", "칸이 없음")
    return None if 실제 is None else f"질문 {순번}번의 답: {_글(실제)}"


def _마지막_까닭(상황, m):
    기록 = 상황["결과"].get("상태_기록") or []
    까닭 = 기록[-1].get("까닭") if 기록 and isinstance(기록[-1], dict) else None
    if not isinstance(까닭, str) or m[1] not in 까닭:
        return f"상태 기록의 마지막 까닭: {_글(까닭)}"
    return None


# 회귀: 사람/ 폴더의 답과 결정을 읽기만 해서 입력의 모든 요청을 main()과 같은 차례로 처리한다.

_모두_처리_전 = "입력의 모든 요청을 아직 처리하지 않음"


def _사람_폴더_읽기(상황, m):
    if 상황["답들"] or 상황["결정들"]:
        return "앞 문장에서 주어진 답이나 결정이 있음"
    상황["답들"] = 요청_처리._목록_읽기(요청_처리._답변_경로)
    상황["결정들"] = 요청_처리._목록_읽기(요청_처리._승인_경로)
    상황["사람_읽음"] = True
    return None


def _모두_처리(상황, m):
    if not 상황["사람_읽음"]:
        return "사람 폴더의 답과 결정을 읽지 않음"
    요청들 = 요청_처리._목록_읽기(요청_처리._요청_경로)
    사례들 = [{칸: s[칸] for 칸 in 요청_처리._사례_칸}
           for s in 요청_처리._목록_읽기(요청_처리._입력_경로)]
    허용 = 요청_처리._읽기(요청_처리._정의_경로)["도구"]
    기준 = 요청_처리._기준_읽기(요청_처리._기준_경로)
    결과들 = []
    for 요청 in 요청들:
        결과, _ = 요청_처리.요청_처리(요청, 사례들, 상황["답들"], 상황["결정들"], 허용, 기준)
        결과들.append(결과)
    상황["요청들"], 상황["결과들"] = 요청들, 결과들
    return None


def _번호의_순서(상황, m):
    if 상황["결과들"] is None:
        return _모두_처리_전
    처음, 끝 = re.fullmatch(r"(\D*)(\d+)", m[1]), re.fullmatch(r"(\D*)(\d+)", m[2])
    if 처음 is None or 끝 is None or 처음[1] != 끝[1]:
        return "뜻을 모르는 문장"
    기대 = [f"{처음[1]}{i:0{len(처음[2])}d}" for i in range(int(처음[2]), int(끝[2]) + 1)]
    실제 = [결과.get("번호") for 결과 in 상황["결과들"]]
    입력에 = [요청.get("번호") for 요청 in 상황["요청들"]]
    if 실제 != 기대 or 실제 != 입력에:
        return f"결과의 번호: {_글(실제)} · 입력에 적힌 순서: {_글(입력에)}"
    return None


def _변경_전과_같다(상황, m):
    """칸을 대어 보는 일은 검증/견주기.py의 _다른_곳을 그대로 부른다."""
    if 상황["결과들"] is None:
        return _모두_처리_전
    전 = 견주기._읽기(_폴더 / m[1])
    후 = {결과.get("번호"): 결과 for 결과 in 상황["결과들"]}
    다름 = []
    for 한_건 in 전:
        번호 = 한_건.get("번호")
        뒤 = 후.get(번호)
        if 뒤 is None:
            다름.append(f"{번호}: 결과에 없음")
            continue
        칸들 = [칸 for 칸 in 한_건 if 칸 != "긴급"]
        if len(칸들) != 7:
            다름.append(f"{번호}: 변경 전의 칸이 {len(칸들)}개")
        for 칸 in 칸들:
            if 칸 not in 뒤:
                다름.append(f"{번호}.{칸}: 없어짐")
                continue
            다름 += [f"{번호}.{자리}: {견주기._글(a)} → {견주기._글(b)}"
                   for 자리, a, b in 견주기._다른_곳(한_건[칸], 뒤[칸], 칸)]
    전_번호 = [한_건.get("번호") for 한_건 in 전]
    다름 += [f"{번호}: 변경 전에 없던 항목" for 번호 in 후 if 번호 not in 전_번호]
    if 다름:
        return ("달라진 곳: " + " / ".join(다름[:6])
                + (f" / … 그 밖에 {len(다름) - 6}곳" if len(다름) > 6 else ""))
    return None


def _긴급인_요청(상황, m):
    if 상황["결과들"] is None:
        return _모두_처리_전
    실제 = [결과.get("번호") for 결과 in 상황["결과들"] if 결과.get("긴급") is True]
    return None if 실제 == m[1].split(", ") else f"긴급이 true인 요청: {_글(실제)}"


def _그_상태인_요청(상황, m):
    if 상황["결과들"] is None:
        return _모두_처리_전
    실제 = [결과.get("번호") for 결과 in 상황["결과들"] if 결과.get("상태") == m[1]]
    return None if 실제 == m[2].split(", ") else f"상태가 {m[1]}인 요청: {_글(실제)}"


_문장_꼴 = [
    ("Given", rf"요청 (\S+)에 적힌 것은 설비 (\S+), 경보 패턴 (\S+), 사례 (\S+?){_끝}", _요청에_적힌_것),
    ("Given", r"사람이 (\S+)의 질문 (\d+)번에 (\S+?)(?:이라고|라고) 답했다 \(답한 사람 (.+)\)", _답),
    ("Given", r"(\S+)의 질문에 대한 사람의 답은 없다", _답_없음),
    ("Given", r"(\S+)에 대한 사람의 결정은 없다", _결정_없음),
    ("Given", r"(\S+) (\S+?)(?:이|가) (\S+)의 조치 (\S+?)(?:을|를) 승인했다 \(사유 없음\)", _승인),
    ("Given", r"(\S+) (\S+?)(?:이|가) (\S+?)(?:을|를) 거절했다 \(절차 번호 없음, 사유 「(.+)」\)", _거절),
    ("Given", rf"사례 (\S+)의 경보 패턴은 (\S+?){_끝}", _사례의_경보_패턴),
    ("Given", rf"사례 (\S+)의 (\S+) (\S+) (\d+)초 값은 (-?\d+(?:\.\d+)?){_끝}", _센서_값),
    ("Given", r"사례 (\S+)의 (\S+) (\S+) (\d+)초 관측은 충분하다", _관측_충분),
    ("Given", r"사례 (\S+)의 신선도는 한도 안이다", _신선도),
    ("When", r"요청 (\S+?)(?:을|를) 처리한다", _처리),
    ("Then", r"상태는 확정이 아니다", _확정_아님),
    ("Then", rf"상태는 (\S+?){_끝}", _칸이_같다("상태")),
    ("Then", rf"긴급은 (true|false|null){_끝}", _긴급),
    ("Then", rf"사례는 (\S+?){_끝}", _칸이_같다("사례")),
    ("Then", rf"근거 상태는 (\S+?){_끝}", _칸이_같다("근거_상태")),
    ("Then", r"승인 칸은 비어 있다", _승인_비어_있음),
    ("Then", r"질문은 한 건이다", _질문_한_건),
    ("Then", r"질문 (\d+)번의 선택지는 없다", _선택지),
    ("Then", rf"질문 (\d+)번의 선택지는 (.+?){_끝}", _선택지),
    ("Given", r"사람이 (\S+)의 질문 (\d+)번에 (\S+?)(?:이라고|라고) 답했다", _답한_사람_없는_답),
    ("Given", r"(\S+)의 질문 (\d+)번에 대한 사람의 답은 없다", _그_질문의_답_없음),
    ("Given", r"사례 (\S+)의 신선도는 한도를 넘었다", _신선도_넘음),
    ("Then", r"질문 (\d+)번의 답은 비어 있다", _질문의_답_비어_있음),
    ("Then", r"상태 기록의 마지막 까닭에 「(.+)」(?:이|가) 들어 있다", _마지막_까닭),
    ("Given", r"사람 폴더의 답과 결정을 지금 그대로 읽는다", _사람_폴더_읽기),
    ("When", r"입력의 모든 요청을 차례로 처리한다", _모두_처리),
    ("Then", r"결과의 번호는 (\S+)부터 (\S+)까지 입력에 적힌 순서다", _번호의_순서),
    ("Then", r"모든 항목에서 긴급을 뺀 일곱 칸은 (\S+)의 같은 번호의 항목과 같다", _변경_전과_같다),
    ("Then", r"긴급이 true인 요청은 (.+?)뿐이다", _긴급인_요청),
    ("Then", r"상태가 (\S+)인 요청은 (.+?)뿐이다", _그_상태인_요청),
]
_문장_꼴 = [(종류, re.compile(꼴), 하는_일) for 종류, 꼴, 하는_일 in _문장_꼴]


def 읽기(경로):
    """(시나리오의 목록, 서식에 어긋난 줄의 목록). 시나리오는 이름과 (낱말, 문장)의 목록이다."""
    시나리오들, 어긋남 = [], []
    for 줄_번호, 줄 in enumerate(경로.read_text(encoding="utf-8").splitlines(), 1):
        줄 = 줄.strip()
        if not 줄:
            continue
        if 줄.startswith(_머리_낱말):
            시나리오들.append({"이름": 줄[len(_머리_낱말):].strip(), "단계": []})
            continue
        낱말, _, 문장 = 줄.partition(" ")
        if 낱말 not in _낱말:
            어긋남.append(f"{줄_번호}번째 줄이 다섯 낱말로 시작하지 않음: {줄}")
        elif not 시나리오들:
            어긋남.append(f"{줄_번호}번째 줄이 {_머리_낱말} 앞에 있음: {줄}")
        elif 낱말 == "And" and not 시나리오들[-1]["단계"]:
            어긋남.append(f"{줄_번호}번째 줄의 And 앞에 Given, When, Then이 없음: {줄}")
        else:
            시나리오들[-1]["단계"].append((낱말, 문장.strip()))
    for 시나리오 in 시나리오들:
        if not 시나리오["단계"]:
            어긋남.append(f"문장이 없는 시나리오: {시나리오['이름']}")
    return 시나리오들, 어긋남


def _한_문장(상황, 종류, 문장):
    """문장 한 줄을 실행한다. 통과면 None, 실패면 실제로 관찰한 것."""
    for 꼴_종류, 꼴, 하는_일 in _문장_꼴:
        m = 꼴.fullmatch(문장) if 꼴_종류 == 종류 else None
        if m is None:
            continue
        if 종류 == "Then" and 상황["결과"] is None and 상황["결과들"] is None:
            return "요청을 아직 처리하지 않음"
        try:
            return 하는_일(상황, m)
        except (Exception, SystemExit) as 까닭:
            return f"{type(까닭).__name__}: {까닭}"
    return "뜻을 모르는 문장"


def 실행(시나리오):
    """시나리오 한 편. 새로 시작하고, 한 문장이 실패하면 남은 문장은 실행하지 않는다."""
    상황 = {"요청": None, "답들": [], "결정들": [], "결과": None,
          "사람_읽음": False, "요청들": None, "결과들": None}
    단계들 = []
    종류 = None
    실패함 = False
    for 낱말, 문장 in 시나리오["단계"]:
        if 낱말 != "And":
            종류 = 낱말
        if 실패함:
            결과, 실제 = "실행_안_함", None
        else:
            실제 = _한_문장(상황, 종류, 문장)
            결과 = "통과" if 실제 is None else "실패"
            실패함 = 실제 is not None
        단계들.append({"구분": 낱말, "문장": 문장, "결과": 결과, "실제": 실제})
    return {"시나리오": 시나리오["이름"], "결과": "실패" if 실패함 else "통과", "단계": 단계들}


def _칸_글(글):
    return "" if 글 is None else str(글).replace("|", "\\|").replace("\n", " ")


_금지_수 = 18  # spec.md의 금지 조건은 열여덟 줄이다
_금지_꼴 = re.compile(r"\s*\(금지 (\d+(?:, \d+)*)\)$")


def _금지_표(결과들):
    """금지 조건마다, 이름 끝의 (금지 …)에 그 번호를 적은 편과 그 편의 결과."""
    줄 = ["## 금지 조건마다 확인하는 편", "",
         f"이번에 실행한 {len(결과들)}편의 이름 끝에 적힌 번호로 적는다.", "",
         "| 금지 조건 | 확인하는 편 · 결과 |", "|---|---|"]
    for 번호 in range(1, _금지_수 + 1):
        편들 = []
        for 결과 in 결과들:
            m = _금지_꼴.search(결과["시나리오"])
            if m and str(번호) in m[1].split(", "):
                이름 = 결과["시나리오"][:m.start()]
                편들.append(f"{_칸_글(이름)} · {결과['결과']}")
        줄.append(f"| {번호} | {'<br>'.join(편들) or '시나리오 없음'} |")
    줄.append("")
    return 줄


def 마크다운(결과들):
    통과 = sum(1 for 결과 in 결과들 if 결과["결과"] == "통과")
    줄 = ["# 검증 결과", "",
         f"시나리오 {len(결과들)}편 · 통과 {통과} · 실패 {len(결과들) - 통과}", ""]
    줄 += _금지_표(결과들)
    for 결과 in 결과들:
        줄 += [f"## {결과['시나리오']}", "", f"- 결과: **{결과['결과']}**", "",
              "| 구분 | 문장 | 결과 | 실제 |", "|---|---|---|---|"]
        for 단계 in 결과["단계"]:
            줄.append(f"| {단계['구분']} | {_칸_글(단계['문장'])} | {단계['결과']}"
                     f" | {_칸_글(단계['실제'])} |")
        줄.append("")
    return "\n".join(줄)


def _이력_더하기(경로, 결과들):
    있던_글 = 경로.read_text(encoding="utf-8") if 경로.exists() else ""
    차례 = sum(1 for 줄 in 있던_글.splitlines() if re.match(r"\|\s*\d+\s*\|", 줄)) + 1
    실패한_것 = [결과["시나리오"] for 결과 in 결과들 if 결과["결과"] == "실패"]
    새_줄 = (f"| {차례} | {len(결과들)} | {len(결과들) - len(실패한_것)} | {len(실패한_것)}"
           f" | {', '.join(_칸_글(이름) for 이름 in 실패한_것) or '없음'} |")
    with open(경로, "a", encoding="utf-8") as f:
        if not 있던_글:
            f.write("\n".join(_이력_머리) + "\n")
        elif not 있던_글.endswith("\n"):
            f.write("\n")
        f.write(새_줄 + "\n")


def main(인자):
    if len(인자) > 1:
        raise SystemExit("쓰는 법: python 검증/시나리오_실행.py [시나리오 이름에 든 글자]")
    try:
        시나리오들, 어긋남 = 읽기(_시나리오_경로)
    except OSError as 까닭:
        raise SystemExit(f"{_시나리오_경로.name}을(를) 읽지 못해 실행하지 않는다: {까닭}")
    if 어긋남:
        raise SystemExit("서식에 어긋난 줄이 있어 실행하지 않는다\n" + "\n".join(어긋남))
    if 인자:
        시나리오들 = [시나리오 for 시나리오 in 시나리오들 if 인자[0] in 시나리오["이름"]]
    if not 시나리오들:
        raise SystemExit("실행할 시나리오가 없어 결과를 쓰지 않는다")

    결과들 = [실행(시나리오) for 시나리오 in 시나리오들]

    with open(_결과_폴더 / "검증_결과.json", "w", encoding="utf-8") as f:
        json.dump(결과들, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(_결과_폴더 / "검증_결과.md", "w", encoding="utf-8") as f:
        f.write(마크다운(결과들))
    _이력_더하기(_결과_폴더 / "검증_이력.md", 결과들)

    for 결과 in 결과들:
        print(f"{결과['결과']} · {결과['시나리오']}")
        for 단계 in 결과["단계"]:
            if 단계["결과"] == "실패":
                print(f"  실패한 문장: {단계['구분']} {단계['문장']}")
                print(f"  실제: {단계['실제']}")
    실패 = sum(1 for 결과 in 결과들 if 결과["결과"] == "실패")
    print(f"시나리오 {len(결과들)}편 · 통과 {len(결과들) - 실패} · 실패 {실패}")
    return 1 if 실패 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
