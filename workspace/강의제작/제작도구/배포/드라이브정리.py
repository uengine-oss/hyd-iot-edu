"""학생 배포용 드라이브 정리판을 만든다: 반/회차마다 1 이론 교재 · 2 실습 자료 · 3 오프라인 수업 자료(배포 B-4).
언제: 회차의 교재 PPTX와 실습 ZIP을 클래스룸에 처음 올리거나 바꿀 때(배포 B-4). 만든 폴더를 사용자가 드라이브 「피지컬 AI 사관학교」에 통째로 올린다.
명령: <py> workspace/강의제작/제작도구/배포/드라이브정리.py <원본 폴더> <출력 폴더> [--회차 01 02 …]
  원본 폴더 꼴: <원본>/<실전반|통합반>/<NN회차>/<파일> (파일 이름은 아래 분류표를 따른다)
분류: 「이론 교재 (온라인|오프라인)」이 든 PPTX → 1 이론 교재(1 온라인 수업용, 2 오프라인 수업용)
      「오프라인 」으로 시작 → 3 오프라인 수업 자료 / 「완성본」이 든 ZIP → 2 실습 자료의 「완성본 · …」
      「실습」으로 시작하는 ZIP(코딩 랩) · HTML(도구 실습의 한 파일 가이드) → 2 실습 자료
      2 실습 자료에 실습 파일이 둘 이상이면 그 파일을 같은 이름으로 담은 「실습 자료 한꺼번에 받기 · <반> NN회차.zip」(압축 없음)을 끝에 더한다.
      앞에 붙은 「NN 」 번호는 뗀다. 분류되지 않는 파일이 하나라도 있으면 아무것도 만들지 않고 멈춘다.
"""
import re
import shutil
import sys
import zipfile
from pathlib import Path

GROUPS = ("1 이론 교재", "2 실습 자료", "3 오프라인 수업 자료")
BUNDLE = "실습 자료 한꺼번에 받기"


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
    if n.startswith("실습") and n.endswith((".zip", ".html")):
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
        labs = [(p, n) for p, n in items[GROUPS[1]] if not n.startswith("완성본")]
        if len(labs) >= 2:   # 실습 자료를 한꺼번에 받는 묶음 — 따로 받는 파일과 같은 이름 · 같은 바이트, 압축 없이(배포 B-4)
            z = base / GROUPS[1] / f"{BUNDLE} · {course} {sess}.zip"
            with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as zf:
                for p, n in labs:
                    zf.write(p, n)
            with zipfile.ZipFile(z) as zf:
                if zf.testzip() or zf.namelist() != [n for _, n in labs] or any(zf.read(n) != p.read_bytes() for p, n in labs):
                    sys.exit(f"{z}: 묶음 검사 실패")
            items[GROUPS[1]].append((z, z.name))
        print(f"== {course} {sess}  파일 {sum(len(f) for f in items.values())}개")
        for g, files in items.items():
            for p, n in files:
                print(f"   {g} | {n} · {p.stat().st_size / 1e6:.1f}MB")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    sess = a[a.index("--회차") + 1:] if "--회차" in a else []
    build(Path(a[0]), Path(a[1]), sess)
