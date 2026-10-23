"""승인된 덱 글 수정을 배포 PPTX에 적용한다(화면 글의 런만 바꾼다. 발표자 노트는 건드리지 않는다).

    python3 deck_edit.py <저장소 루트>

바꾸기 전 글이 그 장에 정확히 한 번 있어야 한다. 바꾼 장 번호를 PPTX마다 출력한다.
"""
import sys
from pathlib import Path
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

ROOT = Path(sys.argv[1])
D1 = [f"산출물/{c}/이론/01회차/{c}_01일차.pptx" for c in ("통합반", "실전반")]
D2 = [f"산출물/{c}/이론/02회차/{c}_02일차.pptx" for c in ("통합반", "실전반")]
S2 = ["산출물/실전반/이론/02회차/실전반_02일차.pptx"]
T3 = ["산출물/통합반/이론/03회차/통합반_03일차.pptx"]
BR = "\x0b"   # 문단 안 줄바꿈(a:br)
EDITS = [  # (덱 목록, 장, 전, 후)
    # 2회차 덱1~6(두 덱 같은 장)
    (D2, 12, "• sign: -1 → 팬 속도 증가, 유온 감소", "• sign: -1 (팬 속도가 오르면 유온은 내려간다)"),
    (D2, 19, "작업(Task)", "하위 클래스(Subclass)"),
    (D2, 19, "규정 검토", "Task(작업)"),
    (D2, 10, "쿨러 핀 오염은 그 원인에 해당한다.", "쿨러 핀 오염은 그 원인 후보에 해당한다."),
    (D2, 15, "부품 ↔ 공급사", "부품 → 공급사"),
    (D2, 33, "질문을 정한다", "역량 질문을 정한다"),
    (D2, 27, "자료형은 글자이고", "자료형은 문자열이고"),
    # 2회차 덱7~11(실전반 2회차, 같은 장이 있는 통합반 3회차 덱)
    (S2, 97, "• 원문 절과 검토 기록을 저장하고 다시 연다", "• 판단 결과에서 원문 절까지 되짚을 수 있게 남긴다"),
    (S2, 105, "현장 모드가 수동으로", "운전 모드가 원격 수동으로"),
    (S2, 107, "수동이면 원격 조치를", "원격 수동이면 원격 조치를"),
    (S2, 100, "실행 기록의 역할", "실행 동작의 역할"),
    (S2, 80, "납기 일시에서 조회 시각까지 남은 시간", "조회 시각부터 납기 일시까지 남은 시간"),
    (T3, 18, "납기 일시에서 조회 시각까지 남은 시간", "조회 시각부터 납기 일시까지 남은 시간"),
    (S2, 85, "다른 점수로 되살아나지 않는다", "점수로 되살리지 않는다"),
    (T3, 23, "다른 점수로 되살아나지 않는다", "점수로 되살리지 않는다"),
    # 1회차 덱1~4(두 덱 같은 장)
    (D1, 11, "세 구획과 작성 규칙을 둔다", "세 구획과 목차를 둔다"),
    (D1, 34, "증상·원인·조치의 관계와 판별 기준을 지식으로 보관한다.", "증상·고장 유형·원인·조치의 관계와 판별 기준을 지식으로 보관한다."),
    (D1, 34, "쿨러 성능 저하 → 원인 후보와 증거", "냉각 성능 상실(고장 유형) → 원인 후보와 증거"),
    (D1, 45, "교재 예시의 처리 기록", "포털에서 처리한 쿨러 사건"),
    (D1, 45, "경보: TS1 55.71\xa0℃ · CE 46.2\xa0%", "경보 당시 값(교재 예: TS1 55.71\xa0℃ · CE 46.2\xa0%)"),
    (D1, 47, "교재에 보관한 사건 기록이다. 경보 뒤 ", "교재에 보관한 사건 기록으로, 경보 뒤 "),
    (D1, 47, "을 가려 조치를 정하고, 조치 뒤 변화를 확인한다.", "을 가려 조치를 정하고 조치 뒤 변화를 확인한다."),
]
SLASH_TO_BR = [(S2, 85), (T3, 23)]   # 표 첫 칸 「출력 / 결정표」의 빗금을 줄바꿈으로


def walk(shapes):
    for sh in shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP: yield from walk(sh.shapes)
        else: yield sh


def runs(slide):
    for sh in walk(slide.shapes):
        frames = [sh.text_frame] if sh.has_text_frame else []
        if getattr(sh, "has_table", False) and sh.has_table:
            frames += [c.text_frame for r in sh.table.rows for c in r.cells]
        for tf in frames:
            for p in tf.paragraphs:
                for r in p.runs: yield p, r


decks = {}
def deck(path):
    if path not in decks: decks[path] = Presentation(ROOT / path)
    return decks[path]


log = {}
for paths, n, old, new in EDITS:
    for path in paths:
        hits = [r for _, r in runs(deck(path).slides[n - 1]) if old in r.text]
        if len(hits) != 1: sys.exit(f"{path} {n}장: 「{old}」 런이 {len(hits)}개")
        hits[0].text = hits[0].text.replace(old, new)
        log.setdefault(path, set()).add(n)
for paths, n in SLASH_TO_BR:
    for path in paths:
        k = 0
        for p, r in list(runs(deck(path).slides[n - 1])):
            if " / " in r.text and __import__("re").search(r"[A-Z]{3,}\s*/ ", p.text):
                left, right = r.text.split(" / ", 1)
                r.text = left
                br = r._r.makeelement(qn("a:br"), {})
                r._r.addnext(br)
                r2 = r._r.makeelement(qn("a:r"), {})
                rpr = r._r.find(qn("a:rPr"))
                if rpr is not None: r2.append(__import__("copy").deepcopy(rpr))
                t = r2.makeelement(qn("a:t"), {}); t.text = right; r2.append(t)
                br.addnext(r2); k += 1
        if not k: sys.exit(f"{path} {n}장: 빗금 칸을 찾지 못했다")
        log.setdefault(path, set()).add(n)
for path, prs in decks.items():
    prs.save(ROOT / path)
    print(path, "바꾼 장", sorted(log.get(path, [])))
