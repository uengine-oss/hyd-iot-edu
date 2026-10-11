"""덱 MD `아이콘:` 줄에 쓸 아이콘 이름을 낱말로 찾는다(Tabler Icons outline, ../assets/icons).

사용: python find_icon.py <낱말> [<낱말> ...] [--preview <미리보기.png>] [--limit N]
낱말은 영어 이름·태그·분류, 또는 아래 한국어 별칭으로 찾는다. 이름에 낱말이 들어간 것이 먼저 나온다.
--preview를 주면 찾은 아이콘을 이름표와 함께 한 장에 그려 눈으로 고를 수 있게 한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ICONS = Path(__file__).resolve().parent.parent / "assets" / "icons"
SVG_DIR = ICONS / "tabler-outline"

# 강의에 자주 나오는 한국어 낱말 → 영어 검색어
KO = {
    "온도": "temperature", "냉각": "snowflake", "쿨러": "snowflake", "열": "flame", "경보": "bell", "알람": "alarm",
    "경고": "alert", "고장": "alert-triangle", "사람": "user", "작업자": "user", "운전원": "user", "관리자": "user-shield",
    "승인": "check", "거절": "x", "권한": "shield", "보안": "lock", "설비": "engine", "공장": "building-factory",
    "기계": "settings", "자동": "settings-automation", "ai": "robot", "에이전트": "robot", "로봇": "robot",
    "질문": "message-question", "답": "message-check", "대화": "message", "데이터": "database", "db": "database",
    "그래프": "topology", "관계": "link", "연결": "plug", "검색": "search", "조회": "search", "문서": "file-text",
    "보고서": "report", "표": "table", "차트": "chart", "지표": "chart-line", "추세": "trending", "센서": "activity",
    "신호": "activity", "시간": "clock", "기록": "history", "일정": "calendar", "점검": "checklist", "정비": "tool",
    "수리": "tool", "조치": "tool", "명령": "terminal", "코드": "code", "규칙": "list-check", "판단": "scale",
    "비교": "arrows-left-right", "흐름": "arrow-right", "분기": "arrows-split", "중지": "hand-stop", "실행": "player-play",
    "다시": "refresh", "확인": "circle-check", "목표": "target", "아이디어": "bulb", "서버": "server",
    "클라우드": "cloud", "배송": "truck", "재고": "package", "비용": "coin", "돈": "cash", "팀": "users",
    "화면": "device-desktop", "눈": "eye", "관찰": "eye", "지식": "brain", "학습": "school",
}


def search(words: list[str], limit: int) -> list[str]:
    index = json.loads((ICONS / "tabler-tags.json").read_text(encoding="utf-8"))
    terms = [KO.get(w.lower(), w.lower()) for w in words]
    scored = []
    for name, meta in index.items():
        hay_tags = " ".join(str(t) for t in meta["t"] + [meta["c"]] if t).lower()   # 원본 태그에 빈 값·숫자가 섞여 있다
        score = 0
        for t in terms:
            if name == t:
                score += 100
            elif name.startswith(t + "-") or f"-{t}" in name:   # 낱말 단위로 맞으면 앞에
                score += 10 - min(len(name) - len(t), 9) / 10
            elif t in name:
                score += 5
            elif t in hay_tags:
                score += 3
            else:
                score = 0
                break
        if score:
            scored.append((-score, len(name), name))
    return [n for _, _, n in sorted(scored)[:limit]]


def preview(names: list[str], out: Path) -> None:
    import pymupdf
    from PIL import Image, ImageDraw, ImageFont

    cell, cols = 150, 6
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * cell), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    for i, name in enumerate(names):
        svg = (SVG_DIR / f"{name}.svg").read_text(encoding="utf-8").replace("currentColor", "#13294B")
        pix = pymupdf.open(stream=svg.encode("utf-8"), filetype="svg")[0].get_pixmap(matrix=pymupdf.Matrix(4, 4))
        icon = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        x, y = (i % cols) * cell, (i // cols) * cell
        sheet.paste(icon, (x + (cell - icon.width) // 2, y + 18))
        draw.text((x + 6, y + cell - 26), name[:22], fill="#333333", font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("words", nargs="+")
    ap.add_argument("--preview")
    ap.add_argument("--limit", type=int, default=24)
    a = ap.parse_args()
    names = search(a.words, a.limit)
    if not names:
        print(f"찾은 아이콘 없음: {' '.join(a.words)} (영어 낱말로 다시 찾는다)", file=sys.stderr)
        return 1
    print("\n".join(names))
    if a.preview:
        preview(names, Path(a.preview))
        print(f"[미리보기] {a.preview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
