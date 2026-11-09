"""학생 배포용 드라이브 정리판을 만든다: 반/회차마다 0 전체(묶음 ZIP) · 1 이론 교재 · 2 실습 자료 · 3 오프라인 수업 자료.
언제: 회차의 교재 PPTX와 실습 ZIP을 클래스룸에 처음 올리거나 바꿀 때(배포 B-4). 만든 폴더를 사용자가 드라이브 「피지컬 AI 사관학교」에 통째로 올린다.
명령: <py> workspace/강의제작/제작도구/배포/드라이브정리.py <원본 폴더> <출력 폴더> [--회차 01 02 …]
  원본 폴더 꼴: <원본>/<실전반|통합반>/<NN회차>/<파일> (파일 이름은 아래 분류표를 따른다)
분류: 「이론 교재 (온라인|오프라인)」이 든 PPTX → 1 이론 교재(1 온라인 수업용, 2 오프라인 수업용)
      「오프라인 」으로 시작 → 3 오프라인 수업 자료 / 「완성본」이 든 ZIP → 2 실습 자료의 「완성본 · …」 / 「실습」으로 시작 → 2 실습 자료
      앞에 붙은 「NN 」 번호는 뗀다. 분류되지 않는 파일이 하나라도 있으면 아무것도 만들지 않고 멈춘다.
"""
import re
import shutil
import sys
import zipfile
from pathlib import Path

GROUPS = ("1 이론 교재", "2 실습 자료", "3 오프라인 수업 자료")


def classify(name):
    n = re.sub(r"^\d\d ", "", name)
    if "이론 교재" in n and n.endswith(".pptx"):
        n = n.replace("이론 교재 (온라인)", "이론 교재 · 온라인 수업용").replace("이론 교재 (오프라인)", "이론 교재 · 오프라인 수업용")
        if "온라인 수업용" in n:
            return GROUPS[0], "1 " + n
        if "오프라인 수업용" in n:
            return GROUPS[0], "2 " + n
        return None
    if n.startswith("오프라인 "):
        return GROUPS[2], n
    if "완성본" in n and n.endswith(".zip"):
        return GROUPS[1], "완성본 · " + n.replace(" 완성본", "")
    if n.startswith("실습") and n.endswith(".zip"):
        return GROUPS[1], n
    return None


def plan(src, sessions):
    out, bad = [], []
    for d in sorted(src.glob("*/*회차")):
        if sessions and d.name[:2] not in sessions:
            continue
        items = {g: [] for g in GROUPS}
        for p in sorted(x for x in d.iterdir() if x.is_file()):
            c = classify(p.name)
            if c is None:
                bad.append(p)
            else:
                items[c[0]].append((p, c[1]))
        out.append((d.parent.name, d.name, items))
    return out, bad


def build(src, dst, sessions):
    todo, bad = plan(src, sessions)
    if bad:
        sys.exit("분류 못 한 파일(이름을 고치거나 분류표를 늘린다):\n" + "\n".join(f"  {p}" for p in bad))
    if not todo:
        sys.exit(f"{src}에 <반>/<NN회차>/ 폴더가 없다")
    for course, sess, items in todo:
        names = [n for files in items.values() for _, n in files]
        dup = sorted({n for n in names if names.count(n) > 1})
        if dup:
            sys.exit(f"{course} {sess}: 정리판에서 이름이 겹친다(원본 이름을 고친다) — {dup}")
    for course, sess, items in todo:
        base = dst / course / sess
        if base.exists():
            shutil.rmtree(base)
        for g, files in items.items():
            if files:
                (base / g).mkdir(parents=True)
                for p, n in files:
                    shutil.copy2(p, base / g / n)
        (base / "0 전체").mkdir(parents=True)
        z = base / "0 전체" / f"{course} {sess} 전체 자료 한 번에 받기.zip"
        with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as zf:
            for g, files in items.items():
                for p, n in files:
                    zf.write(p, f"{g[2:]}/{n}")
        with zipfile.ZipFile(z) as zf:
            names, broken = zf.namelist(), zf.testzip()
        want = sum(len(f) for f in items.values())
        if broken or len(names) != want:
            sys.exit(f"{z}: 묶음 검사 실패 — 들어간 {len(names)}개 / 원본 {want}개, 깨진 항목 {broken}")
        print(f"== {course} {sess}  묶음 {len(names)}개 · {z.stat().st_size / 1e6:.1f}MB")
        for g, files in items.items():
            for _, n in files:
                print(f"   {g} | {n}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    sess = a[a.index("--회차") + 1:] if "--회차" in a else []
    build(Path(a[0]), Path(a[1]), sess)
