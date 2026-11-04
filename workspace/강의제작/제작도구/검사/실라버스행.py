"""정본 실라버스 엑셀에서 한 회차의 행(구분 · 제목 · 상세 · 시간)과 앞 회차 마지막 행 · 다음 회차 첫 행의 제목만 찍는다. 읽기만 한다.
언제: 덱 · 대본 · 영상 · 코딩랩 · 가이드 · 실라버스 일을 시작할 때와 다 만든 뒤 대조할 때 — 시트를 통째로 읽지 않는다.
명령: <py> workspace/강의제작/제작도구/검사/실라버스행.py <통합반|실전반> <온라인|오프라인> <NN>
"""
import re
import sys
from pathlib import Path

import openpyxl

XLSX = Path(__file__).resolve().parents[2] / "산출물/실라버스/피지컬AI_실라버스_최종본.xlsx"
HEAD = re.compile(r"^(\d+)회차\s*\|")


def sessions(ws):
    """{회차: [(구분, 제목, 상세, 시간)]} — 「NN회차 | …」 머리 줄 다음 「구분」 줄부터 합계 줄 전까지."""
    out, cur = {}, None
    for row in ws.iter_rows(values_only=True):
        a = str(row[0]).strip() if row[0] is not None else ""
        m = HEAD.match(a)
        if m:
            cur = out.setdefault(int(m[1]), [])
            continue
        if cur is None or not a or a == "구분":
            continue
        if "합계" in a:
            cur = None
            continue
        cur.append(tuple("" if c is None else str(c).strip() for c in row[:4]))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 4 or sys.argv[1] not in ("통합반", "실전반") or sys.argv[2] not in ("온라인", "오프라인") or not sys.argv[3].isdigit():
        sys.exit(__doc__)
    course, mode, nn = sys.argv[1], sys.argv[2], int(sys.argv[3])
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    names = [n for n in wb.sheetnames if n.startswith(f"{course} {mode}")]
    if len(names) != 1:
        sys.exit(f"{XLSX.name}: 「{course} {mode}」로 시작하는 시트가 {len(names)}개 — {wb.sheetnames}")
    table = sessions(wb[names[0]])
    if nn not in table or not table[nn]:
        sys.exit(f"{names[0]}: {nn:02d}회차 행이 없음 — 있는 회차 {sorted(table)}")
    print(f"# {names[0]} · {nn:02d}회차")
    if table.get(nn - 1):
        print(f"앞 회차 마지막 행: [{table[nn - 1][-1][0]}] {table[nn - 1][-1][1]}")
    for kind, title, detail, minutes in table[nn]:
        print(f"\n## [{kind}] {title} ({minutes}분)\n{detail}")
    if table.get(nn + 1):
        print(f"\n다음 회차 첫 행: [{table[nn + 1][0][0]}] {table[nn + 1][0][1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
