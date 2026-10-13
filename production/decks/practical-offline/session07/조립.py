"""실전반 오프라인 7회차 덱 MD를 통합반 9일차 덱 MD와 새장_07회차.md에서 조립한다.

오프라인 7회차(이론 25분 + 실습 넷)는 통합반 9일차의 세 단원(비즈니스 프로세스, BPMN, 프로세스 오케스트레이션)을
한 단원으로 줄인 것이다. 실행 상태와 판본은 8회차가 다룬다. 내용을 두 벌로 관리하지 않도록 장을 제목으로 찾아
그대로 가져오고, 오프라인의 회차 구성과 빠진 장 때문에 달라지는 곳만 아래 바꾸기 목록으로 고친다.
통합반 원고나 새장을 고치면 다시 돌린다.

    python3 production/decks/practical-offline/session07/조립.py
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent                       # production/decks
SRC = {d: ROOT / "integrated" / f"day{d}" / f"통합반_{d}일차.md" for d in ("09",)}
NEW = HERE / "새장_07회차.md"
OUT = HERE / "실전반_오프라인_07회차.md"


def blocks(path):
    """덱 MD를 {제목: 장 블록}으로 나눈다. 같은 제목이 둘이면 그 제목은 쓸 수 없게 표시한다."""
    text = path.read_text(encoding="utf-8")
    out = {}
    for part in re.split(r"(?m)^(?=## SLIDE )", text)[1:]:
        m = re.match(r"## SLIDE (\S+) — (.*)\n", part)
        assert m, f"{path.name}: 장 머리를 읽지 못함: {part[:40]!r}"
        key = m.group(2).strip() if not m.group(1).startswith("[") else m.group(1)
        out[key] = None if key in out else part.rstrip() + "\n"
    return out


def G(day, title, *edits, 새제목=None):
    """가져오는 장. edits는 (찾을 말, 바꿀 말)이며 장 안에 정확히 한 번 있어야 한다."""
    return ("가져옴", day, title, edits, 새제목)


def N(tag):
    return ("새로", None, tag, (), None)


ORDER = [
    N("[N1]"), N("[N2]"), N("[N3]"),

    # ── 01 프로세스의 정의, 표기, 실행: BPM, BPMN, 오케스트레이션 (본문 18장 / 25분) ──
    N("[N4]"),
    # 필요와 정의. 앞의 두 장은 6회차 Wrap-up이 끝에 예고로 보인 장이며 여기서 이어받는다
    G("09", "추천이 나온 뒤에 남은 일",
      ("앞 일차에서 본 추천안입니다.", "앞 회차에서 본 추천안입니다.")),
    G("09", "에이전트의 판단과 정해 두어야 하는 순서"),
    G("09", "비즈니스 프로세스: 결과를 내기 위한 작업의 순서 있는 묶음"),
    G("09", "BPM: 프로세스를 관리하는 방법"),
    # BPMN: Event · Task · Gateway · Lane, 승인과 거절
    G("09", "문장으로 적은 프로세스"),
    G("09", "BPMN: 업무 프로세스의 표기 표준"),
    # 「BPMN 요소의 세 묶음」은 메시지 흐름을 정의하는 장 없이 그 라벨이 남아 싣지 않는다(검토 반영)
    G("09", "긴급 대응 프로세스의 BPMN 그림"),
    G("09", "이벤트: 프로세스를 여는 사건과 닫는 사건"),
    G("09", "작업: 사용자 작업과 서비스 작업"),
    G("09", "시퀀스 흐름과 배타 게이트웨이"),
    G("09", "풀과 레인: 참여자와 책임의 칸"),
    G("09", "경계 이벤트와 타이머"),
    G("09", "승인을 받는 자리의 그림"),
    G("09", "같은 그림 위의 세 가지 경로"),
    # 냉각 명령 = SCADA, 작업지시 등록 = CMMS를 본문에 세운다(검토 반영)
    # SCADA · CMMS는 오프라인 과정에서 이 장이 처음이다. 풀네임을 표의 그 칸에 붙이고 하는 일을 노트에서 푼다(과정 맞춤)
    G("09", "사람, 에이전트, 시스템의 책임 배치",
      ("  3. 냉각 명령 | SCADA · sys:scada | 시스템",
       "  3. 냉각 명령 | SCADA(Supervisory Control and Data Acquisition) · sys:scada | 시스템"),
      ("  5. 작업지시 등록 | CMMS · sys:cmms | 시스템",
       "  5. 작업지시 등록 | CMMS(Computerized Maintenance Management System) · sys:cmms | 시스템"),
      ("명령과 재관측과 작업지시 등록과 결과 보고는 시스템들이 맡았습니다.",
       "명령과 재관측과 작업지시 등록과 결과 보고는 시스템들이 맡았습니다. SCADA는 설비를 감시하고 제어하는 시스템으로 "
       "승인된 냉각 명령을 PLC에 전하고, CMMS는 정비 작업을 관리하는 시스템으로 작업지시가 여기에 등록됩니다.")),
    # 오케스트레이션: 엔진, 정의와 인스턴스
    G("09", "그림만으로는 일어나지 않는 일"),
    G("09", "프로세스 엔진과 오케스트레이션"),
    G("09", "프로세스 정의와 프로세스 인스턴스"),

    # ── 실습 넷 ─────────────────────────────────────────────────────────────
    G("09", "실습: 간단한 승인 절차 그리기"),
    G("09", "실습에서 그리는 것과 만들어지는 것"),
    # 실습 2는 레인과 작업의 순서까지다. 승인 · 거절 · 지연은 실습 3이 맡는다
    G("09", "실습: 긴급 대응 프로세스 그리기",
      ("역할과 승인 조건을 갖춘 설비 이상 대응의 흐름을 그린다", "쿨러 성능 저하 경보에서 종료까지를 역할별 레인에 그린다")),
    N("[N5]"),
    N("[N6]"), N("[N7]"),
    G("09", "실습: 그린 흐름을 에이전트와 시스템에 연결하기"),
    G("09", "실습에서 정하는 것과 배포되는 것",
      # 「판본」의 뜻은 8회차가 세운다(검토 반영)
      ("판본으로 등록하고 / 경보를 받도록 / 배포한다", "프로세스 정의를 등록하고 / 경보를 받도록 / 배포한다"),
      ("셋째 실습에서는 그린 그림을", "넷째 실습에서는 그린 그림을")),

    # ── 용어 정리와 퀴즈 ────────────────────────────────────────────────────
    N("[N8]"),
    G("09", "Review Quiz: 핵심 흐름 되짚어보기"),
    # 처리 건의 상태 이름(RUNNING)과 단계의 상태는 8회차가 다룬다
    G("09", "Quiz 1. 승인 지연 알림이 나간 처리 건",
      ("긴급 대응 처리 건의 상태가 RUNNING이고 열려 있는 단계가 운전원 승인이며, 승인 지연 알림은 이미 나갔다.",
       "긴급 대응 처리 건이 운전원 승인에서 기다리고 있으며, 승인 지연 알림은 이미 나갔다."),
      ("그림과 기록으로 처리 건의 상태를 읽는 문항입니다. 승인 지연 타이머가 중단형인지 비중단형인지, 그리고 처리 건의 상태가 무엇인지를 떠올려 보시기 바랍니다.",
       "그림으로 처리 건의 진행을 읽는 문항입니다. 승인 지연 타이머가 중단형인지 비중단형인지, 그리고 알림이 나간 뒤 승인 작업이 어떻게 남는지를 떠올려 보시기 바랍니다.")),
    N("[N9]"),
    G("09", "Quiz 3. 냉각 명령을 시작시키는 쪽"),
    N("[N10]"),
]

HEAD = (
    "<!-- 이 파일은 조립.py가 만든다. 직접 고치지 않는다. "
    "새 장은 새장_07회차.md, 가져오는 장의 순서와 손질은 조립.py에서 고친다. -->\n"
    "# 실전반 오프라인 7회차 — 다양한 업무를 연결하는 AI 프로세스의 설계와 배포\n\n"
    "통합반 9일차에서 장을 가져와 조립했다. 그림은 통합반 폴더의 것을 그대로 쓴다. "
    "기술 사실의 근거는 `production/standards/통합반_09-11일차_기술사실표.md`다.\n\n"
)


def main():
    src = {d: blocks(p) for d, p in SRC.items()}
    new = blocks(NEW)
    out, count = [HEAD], {"가져옴": 0, "손질": 0, "새로": 0}
    for no, (kind, day, key, edits, title) in enumerate(ORDER, 1):
        if kind == "새로":
            assert new.get(key), f"새장에 {key}가 없음"
            block = new[key]
            head_title = re.match(r"## SLIDE \S+ — (.*)\n", block).group(1)
            count["새로"] += 1
        else:
            assert key in src[day], f"통합반 {day}일차에서 장을 찾지 못함: {key}"
            assert src[day][key], f"통합반 {day}일차에 같은 제목의 장이 둘 있음: {key}"
            block = src[day][key]
            for old, rep in edits:
                assert block.count(old) == 1, f"{no}번 「{key}」: 바꿀 말이 {block.count(old)}번 있음: {old}"
                block = block.replace(old, rep)
            for pic in re.findall(r"(?m)^- 그림: (figures/\S+)", block):
                assert (SRC[day].parent / pic).exists(), f"{no}번 「{key}」: 그림 파일이 없음: {pic}"
            block = block.replace("- 그림: figures/", f"- 그림: ../../integrated/day{day}/figures/")
            head_title = title or key
            count["손질" if (edits or title) else "가져옴"] += 1
        body = block.split("\n", 1)[1]
        out.append(f"## SLIDE {no:02d} — {head_title}\n{body}\n")
    OUT.write_text("".join(out), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT.parent.parent)} 만듦: 전체 {len(ORDER)}장 "
          f"(가져옴 {count['가져옴']}, 가져옴·손질 {count['손질']}, 새로 {count['새로']})")


if __name__ == "__main__":
    main()
