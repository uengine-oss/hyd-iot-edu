"""통합반 오프라인 8회차 덱 MD를 통합반 9일차 덱 MD와 새장_08회차.md에서 조립한다.

오프라인 8회차(BPM · BPMN · 오케스트레이션 이론 25분 + 실습 넷)는 통합반 9일차를 줄인 것이다.
내용을 두 벌로 관리하지 않도록 장을 제목으로 찾아 그대로 가져오고, 오프라인의 회차 구성과 실라버스 때문에
달라지는 곳만 아래 바꾸기 목록으로 고친다. 통합반 원고나 새장을 고치면 다시 돌린다.

    python3 production/decks/integrated-offline/session08/조립.py
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent                       # production/decks
SRC = {d: ROOT / "integrated" / f"day{d}" / f"통합반_{d}일차.md" for d in ("09",)}
NEW = HERE / "새장_08회차.md"
OUT = HERE / "통합반_오프라인_08회차.md"


def blocks(path):
    """덱 MD를 {제목 또는 [표지]: (제목, 장 블록)}으로 나눈다. 같은 열쇠가 둘이면 멈춘다."""
    text = path.read_text(encoding="utf-8")
    out = {}
    for part in re.split(r"(?m)^(?=## SLIDE )", text)[1:]:
        m = re.match(r"## SLIDE (\S+) — (.*)\n", part)
        assert m, f"{path.name}: 장 머리를 읽지 못함: {part[:40]!r}"
        title = m.group(2).strip()
        key = title if not m.group(1).startswith("[") else m.group(1)
        assert key not in out, f"{path.name}: 제목이 겹침: {key}"
        out[key] = (title, part.rstrip() + "\n")
    return out


def G(day, title, *edits, 새제목=None):
    """가져오는 장. edits는 (찾을 말, 바꿀 말)이며 장 안에 정확히 한 번 있어야 한다."""
    return ("가져옴", day, title, edits, 새제목)


def N(tag):
    return ("새로", None, tag, (), None)


ORDER = [
    N("[N1]"), N("[N2]"), N("[N3]"),

    # ── 01 비즈니스 프로세스 (본문 5장) ─────────────────────────────────────
    G("09", "비즈니스 프로세스: / 작업 하나에서 업무 전체로"),
    # 통합반의 「앞 일차」는 이 과정의 앞 회차다
    G("09", "추천이 나온 뒤에 남은 일",
      ("묶은 것이 앞 일차에서 본 추천안입니다.", "묶은 것이 앞 회차에서 본 추천안입니다.")),
    G("09", "에이전트의 판단과 정해 두어야 하는 순서"),
    G("09", "비즈니스 프로세스: 결과를 내기 위한 작업의 순서 있는 묶음"),
    # 8회차부터 처리 건의 식별자와 값이 프로세스가 처리한 다른 한 건의 것으로 바뀐다. 원문이 이 장의 화면과 노트에서 밝힌다
    G("09", "Task와 End-to-End: 작업 하나와 종단 간 전체",
      ("앞 일차에서 본 경보와 같은 종류의 다른 한 건이어서", "7회차까지 본 경보와 같은 종류의 다른 한 건이어서")),
    G("09", "BPM: 프로세스를 관리하는 방법"),

    # ── 02 BPMN (본문 11장) ─────────────────────────────────────────────────
    G("09", "BPMN: 프로세스를 그리는 / 표준 표기법"),
    G("09", "문장으로 적은 프로세스"),
    G("09", "BPMN: 업무 프로세스의 표기 표준"),
    G("09", "긴급 대응 프로세스의 BPMN 그림"),
    G("09", "이벤트: 프로세스를 여는 사건과 닫는 사건"),
    G("09", "작업: 사용자 작업과 서비스 작업"),
    G("09", "시퀀스 흐름과 배타 게이트웨이"),
    # 과정 전체 맞춤에서 더한 장: 그림의 기본 흐름 빗금, 실습 4의 「갈림의 조건」, 9회차 「프로세스 변수」와 10회차 「승인 블록」의 approval · recovered를 받친다
    G("09", "갈림의 조건과 기본 흐름"),
    G("09", "풀과 레인: 참여자와 책임의 칸"),
    G("09", "경계 이벤트와 타이머"),
    G("09", "승인을 받는 자리의 그림"),
    # SCADA와 CMMS가 과정에서 처음 나오는 자리다(오프라인 1회차는 SCADA 장을 가져오지 않았다). 맡는 쪽 칸의 둘째 줄에
    # 풀네임을 붙인다(전체 점검 반영. 표기는 통합반 1일차와 9일차 용어 정리 표의 것)
    G("09", "사람, 에이전트, 시스템의 책임 배치",
      ("  3. 냉각 명령 | SCADA · sys:scada | 시스템",
       "  3. 냉각 명령 | SCADA · sys:scada / Supervisory Control and Data Acquisition | 시스템"),
      ("  5. 작업지시 등록 | CMMS · sys:cmms | 시스템",
       "  5. 작업지시 등록 | CMMS · sys:cmms / Computerized Maintenance Management System | 시스템"),
      ("명령과 재관측과 작업지시 등록과 결과 보고는 시스템들이 맡았습니다.",
       "명령과 재관측과 작업지시 등록과 결과 보고는 시스템들이 맡았습니다. SCADA는 설비를 감시하고 명령을 PLC에 전하는 시스템이고, CMMS는 정비 작업지시를 관리하는 시스템입니다.")),

    # ── 03 프로세스 오케스트레이션 (본문 4장) ───────────────────────────────
    G("09", "프로세스 오케스트레이션: / 설계한 프로세스의 실행", ("- 구분: 이론 · 실습", "- 구분: 이론")),
    G("09", "그림만으로는 일어나지 않는 일"),
    G("09", "프로세스 엔진과 오케스트레이션"),
    G("09", "프로세스 정의와 프로세스 인스턴스"),
    # 실습 4의 등록 · 배포를 받친다(9회차는 이 장을 전제한다)
    G("09", "판본과 배포: 고친 프로세스가 적용되는 시점"),

    # ── 실습 넷 ─────────────────────────────────────────────────────────────
    G("09", "실습: 간단한 승인 절차 그리기"),
    G("09", "실습에서 그리는 것과 만들어지는 것"),
    # 실습 2 · 3: 통합반 9일차의 둘째 실습(레인 · 순서 · 갈림 · 타이머)이 오프라인에서는 두 실습으로 나뉜다
    G("09", "실습: 긴급 대응 프로세스 그리기",
      ("- 부제: 역할과 승인 조건을 갖춘 설비 이상 대응의 흐름을 그린다",
       "- 부제: 쿨러 성능 저하 경보에서 결과 보고까지의 작업을 레인별로 놓아 설비 이상 대응의 흐름을 그린다")),
    N("[N4]"),
    N("[N5]"), N("[N6]"),
    G("09", "실습: 그린 흐름을 에이전트와 시스템에 연결하기"),
    G("09", "실습에서 정하는 것과 배포되는 것",
      ("셋째 실습에서는 그린 그림을", "넷째 실습에서는 그린 그림을")),

    # ── 용어 정리와 퀴즈 ────────────────────────────────────────────────────
    # 이 회차에 싣지 않은 장의 용어(AS-IS와 TO-BE, 토큰, 프로세스 변수, 감사 기록)를 노트에서 뺀다
    # SCADA의 풀네임은 「책임 배치」 표에 붙였고, 용어 정리 표에도 CMMS와 나란히 싣는다(표기는 통합반 1일차 용어 정리 표의 것)
    G("09", "오늘 다룬 핵심 개념과 주요 용어 정리",
      ("  3. CMMS | Computerized Maintenance Management System | 작업지시를 등록하는 시스템\n",
       "  3. SCADA | Supervisory Control and Data Acquisition | 냉각 명령을 PLC에 전하는 시스템\n"
       "  4. CMMS | Computerized Maintenance Management System | 작업지시를 등록하는 시스템\n"),
      ("이 셋과 함께 비즈니스 프로세스, Task와 End-to-End, AS-IS와 TO-BE, 이벤트, 게이트웨이, 풀과 레인, 경계 이벤트, "
       "프로세스 정의와 인스턴스, 토큰, 프로세스 변수, 감사 기록이 오늘의 용어입니다.",
       "이 넷과 함께 비즈니스 프로세스, Task와 End-to-End, 이벤트, 게이트웨이, 풀과 레인, 경계 이벤트, "
       "프로세스 엔진과 오케스트레이션, 프로세스 정의와 인스턴스가 오늘의 용어입니다.")),
    G("09", "Review Quiz: 핵심 흐름 되짚어보기"),
    # 정답 2 · 1 · 4
    N("[N7]"), N("[N8]"),
    G("09", "Quiz 3. 냉각 명령을 시작시키는 쪽"),
    N("[N9]"),
]

HEAD = (
    "<!-- 이 파일은 조립.py가 만든다. 직접 고치지 않는다. "
    "새 장은 새장_08회차.md, 가져오는 장의 순서와 손질은 조립.py에서 고친다. -->\n"
    "# 통합반 오프라인 8회차 — 설비 이상 대응 업무의 프로세스 설계와 실행 준비\n\n"
    "통합반 9일차에서 장을 가져와 조립했다. 그림은 통합반 폴더의 것을 그대로 쓴다. "
    "기술 사실의 근거는 `production/standards/통합반_09-11일차_기술사실표.md`다.\n\n"
)


def main():
    src = {d: blocks(p) for d, p in SRC.items()}
    new = blocks(NEW)
    out, count = [HEAD], {"가져옴": 0, "손질": 0, "새로": 0}
    for no, (kind, day, key, edits, title) in enumerate(ORDER, 1):
        if kind == "새로":
            assert key in new, f"새장에 {key}가 없음"
            head_title, block = new[key]
            count["새로"] += 1
        else:
            assert key in src[day], f"{SRC[day].name}에서 장을 찾지 못함: {key}"
            head_title, block = src[day][key]
            for old, rep in edits:
                assert block.count(old) == 1, f"{no}번 「{key}」: 바꿀 말이 {block.count(old)}번 있음: {old}"
                block = block.replace(old, rep)
            for fig in re.findall(r"(?m)^- 그림: (figures/\S+)$", block):
                assert (SRC[day].parent / fig).exists(), f"{no}번 「{key}」: 그림이 없음: {fig}"
            block = block.replace("- 그림: figures/", f"- 그림: ../../integrated/day{day}/figures/")
            head_title = title or head_title
            count["손질" if (edits or title) else "가져옴"] += 1
        body = block.split("\n", 1)[1]
        out.append(f"## SLIDE {no:02d} — {head_title}\n{body}\n")
    OUT.write_text("".join(out), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT.parent.parent)} 만듦: 전체 {len(ORDER)}장 "
          f"(가져옴 {count['가져옴']}, 가져옴·손질 {count['손질']}, 새로 {count['새로']})")


if __name__ == "__main__":
    main()
