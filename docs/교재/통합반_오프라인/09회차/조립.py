"""통합반 오프라인 9회차 덱 MD를 통합반 9 · 10 · 11일차 덱 MD와 새장_09회차.md에서 조립한다.

오프라인 9회차(실행 중인 프로세스의 통제 이론 20분 + 실습 넷)는 통합반 9 · 10 · 11일차에서 고른 것이다.
내용을 두 벌로 관리하지 않도록 장을 제목으로 찾아 그대로 가져오고, 오프라인의 회차 구성과 실라버스 때문에
달라지는 곳만 아래 바꾸기 목록으로 고친다. 통합반 원고나 새장을 고치면 다시 돌린다.

    python3 docs/교재/통합반_오프라인/09회차/조립.py
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent                       # docs/교재
SRC = {d: ROOT / "통합반" / f"{d}일차" / f"통합반_{d}일차.md" for d in ("09", "10", "11")}
NEW = HERE / "새장_09회차.md"
OUT = HERE / "통합반_오프라인_09회차.md"


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

    # ── 01 실행 중인 프로세스의 통제 (본문 14장) ────────────────────────────
    N("[N4]"),
    # 여는 장: 8회차에 그린 그림의 세 경로. 그림이 화면에 없으므로 제목과 메시지의 「같은 그림」을 고친다
    G("09", "같은 그림 위의 세 가지 경로",
      ("- 메시지: 같은 그림에서 승인하면 끝에,", "- 메시지: 긴급 대응 프로세스는 승인하면 끝에,"),
      ("그림 하나가 여러 경우를 담고 있습니다.", "8회차에 그린 긴급 대응 프로세스의 그림 하나가 여러 경우를 담고 있습니다."),
      새제목="긴급 대응 프로세스의 세 가지 경로"),
    G("09", "토큰: 프로세스의 현재 위치"),
    G("09", "승인 대기: 토큰이 사용자 작업에 머문 상태"),
    G("09", "토큰이 둘이 되는 순간"),
    G("09", "실행 상태: 처리 건의 상태와 단계의 상태"),
    G("09", "COMPLETED는 성공을 뜻하지 않는다"),
    # 「갈림의 조건과 기본 흐름」 장은 8회차에 실었다(과정 전체 맞춤에서 더함)
    G("09", "프로세스 변수: 인스턴스가 지니는 데이터",
      ("앞 단원에서 본 갈림의 조건이 읽던 approval과 recovered가 이 변수입니다.",
       "8회차에 본 갈림의 조건이 읽던 approval과 recovered가 이 변수입니다.")),
    G("09", "프로세스가 에이전트의 결과를 잇는 순서"),
    G("10", "실행 기록과 모니터링: 단계마다 남는 시작과 끝"),
    G("09", "감사 기록(Audit Log): 누가 무엇을 결정했는가"),
    # 「종료 기록」은 10회차에 나오는 말이다
    G("10", "처리 건 한 건을 잇는 식별자",
      ("끝난 업무의 종료 기록이 뜻하는 것은", "끝난 처리 건의 기록이 뜻하는 것은")),
    # 「판본과 배포」 장은 8회차에 실었다
    G("09", "처리 건 한 건에 남는 기록"),
    # 책임 구분의 앞에 세 영역의 몫을 세운다(단원의 끝 장이 아니어서 제목과 노트 첫 문장을 고친다)
    G("09", "단원 정리: 지식, 에이전트, 프로세스가 맡는 것",
      ("셋째 단원과 오늘의 내용을 정리합니다.", "처리 건 한 건에서 지식과 에이전트와 프로세스가 맡는 것을 나누어 보겠습니다."),
      새제목="지식, 에이전트, 프로세스가 맡는 것"),
    G("11", "결과가 기대와 다를 때 먼저 살펴볼 영역"),

    # ── 실습 넷 ─────────────────────────────────────────────────────────────
    # 실습 1: 통합반 9일차의 넷째 실습. 흐름의 비교 대신 단계 상태의 기록을 둔다(실라버스)
    G("09", "실습: 설비 이벤트로 프로세스 실행하기"),
    G("09", "실습에서 실행하는 것과 확인하는 기록",
      ("- 아이콘: player-play, hourglass, list-check, arrows-right-left", "- 아이콘: player-play, hourglass, list-check, pencil"),
      ("  4. **흐름의 비교** | 직접 배포한 흐름과 처음부터 배포되어 있던 흐름이 어떻게 다른지 견준다 | 비교",
       "  4. **단계 상태의 기록** | 단계마다 누가 맡았고 어떤 상태로 끝났는지를 적어 둔다 | 기록"),
      ("마지막 실습에서는 배포한 프로세스를 실제로 실행합니다.", "첫 실습에서는 8회차에 배포한 프로세스를 실제로 실행합니다."),
      ("승인을 기다리는 상태와 끝난 상태를 처리 건의 기록으로 구분해 보시기 바랍니다.",
       "단계마다의 담당과 상태를 적어 두고, 승인을 기다리는 상태와 끝난 상태를 처리 건의 기록으로 구분해 보시기 바랍니다.")),
    N("[N5]"), N("[N6]"),
    N("[N7]"), N("[N8]"),
    N("[N9]"), N("[N10]"),

    # ── 용어 정리와 퀴즈 ────────────────────────────────────────────────────
    N("[N11]"),
    G("09", "Review Quiz: 핵심 흐름 되짚어보기"),
    # 정답 3 · 1 · 4
    G("09", "Quiz 1. 승인 지연 알림이 나간 처리 건"),
    G("09", "Quiz 2. 설비 명령이 나갔는지를 판단하는 근거"),
    # 통합반 10일차의 Quiz 2. 정기 점검 프로세스와 「병목」은 이 회차에 없어 긴급 대응과 「늦어지는 단계」로 고친다
    G("10", "Quiz 2. 병목을 판단하는 근거",
      ("- 메시지: 정기 점검 프로세스가 느리다는 말이 나와,", "- 메시지: 긴급 대응 프로세스가 느리다는 말이 나와,"),
      ("- 문장: 병목을 판단하는 근거로 삼을 기록은?", "- 문장: 늦어지는 단계를 판단하는 근거로 삼을 기록은?"),
      새제목="Quiz 3. 늦어지는 단계를 판단하는 근거"),
    N("[N12]"),
]

HEAD = (
    "<!-- 이 파일은 조립.py가 만든다. 직접 고치지 않는다. "
    "새 장은 새장_09회차.md, 가져오는 장의 순서와 손질은 조립.py에서 고친다. -->\n"
    "# 통합반 오프라인 9회차 — 설비 이벤트로 검증하는 프로세스의 실행과 안전성\n\n"
    "통합반 9 · 10 · 11일차에서 장을 가져와 조립했다. 그림은 통합반 폴더의 것을 그대로 쓴다. "
    "기술 사실의 근거는 `docs/교재/기준/통합반_09-11일차_기술사실표.md`다.\n\n"
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
            for fig in re.findall(r"(?m)^- 그림: (그림/\S+)$", block):
                assert (SRC[day].parent / fig).exists(), f"{no}번 「{key}」: 그림이 없음: {fig}"
            block = block.replace("- 그림: 그림/", f"- 그림: ../../통합반/{day}일차/그림/")
            head_title = title or head_title
            count["손질" if (edits or title) else "가져옴"] += 1
        body = block.split("\n", 1)[1]
        out.append(f"## SLIDE {no:02d} — {head_title}\n{body}\n")
    OUT.write_text("".join(out), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT.parent.parent)} 만듦: 전체 {len(ORDER)}장 "
          f"(가져옴 {count['가져옴']}, 가져옴·손질 {count['손질']}, 새로 {count['새로']})")


if __name__ == "__main__":
    main()
