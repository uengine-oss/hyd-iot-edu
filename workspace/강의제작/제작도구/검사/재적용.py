"""이미 고친 대본 · 원고를 기준 커밋으로 되돌린 뒤, 사용자가 고른 항목만 점검적용.py로 다시 얹는다. 첫 판정은 판정_전체/에 보관한다.
언제: 점검 항목을 다 고친 뒤 사용자가 「이것만」으로 범위를 줄였을 때(공통 C-5 승인) — 사람이 파일을 하나씩 되돌리지 않으려고 쓴다.
명령: <py> workspace/강의제작/제작도구/검사/재적용.py <작업 폴더> --기준 <커밋> --덱 통합반:01 실전반:02 … [--오프라인 통합반:01 …] --고른것 <파일> [--공통 실전반:01=통합반:01] [--루트 폴더]

- 되돌리는 것: 덱마다 대본 · 덱 원고 · PPTX · 구성.json · 구성표.md, --오프라인 덱의 원고 · PPTX(기준 커밋에 있는 판 그대로). 다른 세션의 미커밋을 덮을 수 있으니 먼저 `동기화.py status`로 본다.
- 남길 항목: --고른것 파일({"<과정>_<NN>": {"<항목 번호>": "까닭"}}, 꼭 준다 — 사용자가 고른 것만). 나머지는 판정을 「보류」로 바꾼다. 노트추가는 남은 항목의 장만 둔다.
- --공통 실전반:01=통합반:01: 같은 판정을 그 대본에 대본만 적용하고, 그 덱 폴더에 조립.py가 있으면 돌린다(1회차처럼 두 과정이 함께 쓰는 덱).
- --루트: 저장소 루트 대신 빈 폴더를 주면 그 안에 커밋본을 풀어 시험한다(작업 트리를 건드리지 않는다).
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DK = {"통합반": "integrated", "실전반": "practical"}
env = dict(os.environ, PYTHONUTF8="1")


def git(*a):
    return subprocess.run(["git", "-c", "core.quotepath=false", *a], capture_output=True, cwd=REPO)


def tracked(base, path):
    r = git("ls-tree", "-r", "--name-only", base, path)
    if r.returncode:
        sys.exit(f"기준 {base}를 읽지 못했다: {r.stderr.decode('utf8', 'replace')}")
    return r.stdout.decode("utf8").splitlines()


def restore(base, root, rel):
    r = git("show", f"{base}:{rel}")
    if r.returncode:
        sys.exit(f"기준 {base}에 없다: {rel}")
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists() or p.read_bytes() != r.stdout:
        p.write_bytes(r.stdout)
        return 1
    return 0


def deck_files(base, course, nn):
    G = "workspace/강의제작"
    out = tracked(base, f"{G}/산출물/{course}/이론/{nn}회차/대본")
    out += [f"{G}/제작도구/온라인/decks/{DK[course]}/day{nn}/{course}_{nn}일차.md",
            f"{G}/산출물/{course}/이론/{nn}회차/{course}_{nn}일차.pptx",
            f"{G}/제작도구/구성/{course}/{nn}회차/구성.json",
            f"{G}/제작도구/구성/{course}/{nn}회차/구성표.md"]
    return out


def apply(W, root, *args, verb="실행"):
    r = subprocess.run([sys.executable, str(HERE / "점검적용.py"), verb, str(W), *args, "--루트", str(root)], capture_output=True, env=env)
    out = (r.stdout + r.stderr).decode("utf8", "replace")
    print(out.strip().split("\n")[0][:160])
    if r.returncode:
        sys.exit(f"{args} 적용 실패:\n{out[:1500]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work")
    ap.add_argument("--기준", dest="base", required=True)
    ap.add_argument("--덱", dest="decks", nargs="+", required=True)
    ap.add_argument("--오프라인", dest="offs", nargs="*", default=[])
    ap.add_argument("--고른것", dest="chosen", required=True)
    ap.add_argument("--공통", dest="shared", nargs="*", default=[])
    ap.add_argument("--루트", dest="root", default=str(REPO))
    a = ap.parse_args()
    W, root = Path(a.work).resolve(), Path(a.root).resolve()
    chosen = json.loads(Path(a.chosen).read_text("utf8"))
    decks = [d.split(":") for d in a.decks]
    shared = [tuple(x.split(":") for x in s.split("=")) for s in a.shared]
    ct = 0
    for c, n in decks + [t for t, _ in shared]:
        for rel in deck_files(a.base, c, n):
            ct += restore(a.base, root, rel)
    for o in a.offs:
        c, n = o.split(":")
        for rel in (f"workspace/강의제작/제작도구/오프라인/decks/{DK[c]}/off{n}/{c}_오프라인_{n}회차.md", f"workspace/강의제작/산출물/{c}/이론_오프라인/{n}회차/{c}_오프라인_{n}회차.pptx"):
            ct += restore(a.base, root, rel)
    print("기준 커밋으로 되돌린 파일", ct)
    (W / "판정_전체").mkdir(exist_ok=True)
    kept = removed = 0
    for c, n in decks:
        name = f"{c}_{n}"
        keep = W / "판정_전체" / f"{name}.json"
        if not keep.exists():
            shutil.copy(W / "판정" / f"{name}.json", keep)
        jd = json.loads(keep.read_text("utf8"))
        items = {x["번호"]: x for x in json.loads((W / "점검" / f"{name}.json").read_text("utf8"))["고칠것"]}
        pick = set(chosen.get(name, {}))
        unknown = pick - set(items)
        if unknown:
            sys.exit(f"{name}: 고른 항목 {sorted(unknown)}이 점검 목록에 없다")
        for k in jd["판정"]:
            if k not in pick:
                jd["판정"][k] = {"처리": "보류", "까닭": "사용자가 고른 항목이 아니라 남김"}; removed += 1
            else:
                kept += 1
        slides = {items[k]["장"] for k in pick}
        jd["노트추가"] = [x for x in jd.get("노트추가", []) if x["장"] in slides]
        (W / "판정" / f"{name}.json").write_text(json.dumps(jd, ensure_ascii=False, indent=1), "utf8", newline="\n")
        apply(W, root, c, n)
    for (c, n), (sc, sn) in shared:
        apply(W, root, c, n, "--목록", f"{sc}_{sn}", "--대본만")
        builder = root / f"workspace/강의제작/제작도구/온라인/decks/{DK[c]}/day{n}/조립.py"
        if builder.exists():
            r = subprocess.run([sys.executable, str(builder)], capture_output=True, env=env, cwd=root)
            print("조립", c, n, r.returncode, (r.stdout + r.stderr).decode("utf8", "replace").strip()[:160])
            if r.returncode:
                sys.exit(f"{builder} 실패")
    for c, n in decks + [t for t, _ in shared]:
        apply(W, root, c, n, "--기준", a.base, verb="정리")
    print(f"남긴 항목 {kept} · 보류로 바꾼 항목 {removed}")


if __name__ == "__main__":
    main()
