"""아스트라가 낸 「고칠 것」 목록(JSON)을 대본 · 덱 MD에 그대로 넣는다(2_기준 45-2번).

    python3 만들기/tools/deck/고칠것넣기.py <고칠것.json> <대본.md> [<덱.md>] [--dry]

- 항목: {"번호", "장", "종류": 바꾸기|넣기|지우기, "원문", "새 글", "까닭", "근거", "범위"}
- 「장」이 「덱 NN」이면 덱 MD에, 아니면 대본에 넣는다.
- 바꿀 글은 고쳐 쓰지 않는다. 원문이 파일 안에 정확히 한 번 있을 때만 넣고, 없거나 여러 번이면
  그 항목만 넣지 않고 번호 · 장 · 까닭을 알린다(나머지는 넣는다). 끝에 넣은 수와 못 넣은 수를 적는다.
- --dry: 파일을 쓰지 않고 넣을 수 있는지만 본다.
"""
import json
import sys
from pathlib import Path


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--dry"]
    dry = "--dry" in sys.argv
    if len(args) < 2:
        print(__doc__)
        return 2
    items = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    files = {"대본": Path(args[1]), "덱": Path(args[2]) if len(args) > 2 else None}
    text = {k: p.read_text(encoding="utf-8") for k, p in files.items() if p}
    done, failed = 0, []
    for it in items:
        target = "덱" if str(it.get("장", "")).startswith("덱") else "대본"
        if target not in text:
            failed.append((it, "덱 MD 경로를 주지 않았다"))
            continue
        s, old, new, kind = text[target], it.get("원문", ""), it.get("새 글", ""), it.get("종류")
        n = s.count(old) if old else 0
        if n != 1:
            failed.append((it, f"원문이 {target}에 {n}번 있다"))
            continue
        if kind == "바꾸기":
            s = s.replace(old, new)
        elif kind == "넣기":
            s = s.replace(old, old + new)
        elif kind == "지우기":
            s = s.replace(old, "")
        else:
            failed.append((it, f"알 수 없는 종류 {kind!r}"))
            continue
        text[target] = s
        done += 1
    if not dry:
        for k, p in files.items():
            if p:
                p.write_text(text[k], encoding="utf-8")
    for it, why in failed:
        print(f"[못 넣음] {it.get('번호')} · 장 {it.get('장')} · {it.get('종류')}: {why} — 원문 첫머리 「{it.get('원문', '')[:40]}」")
    print(f"{'(시험) ' if dry else ''}넣음 {done} / 못 넣음 {len(failed)} / 전체 {len(items)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
