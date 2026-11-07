"""강조 뒤 영상을 Release 「영상」에, 그 자막 · 시간표를 산출물 자리에 바꿔 끼우고 영상 README에 붙일 행을 찍는다.
언제: 영상을 강조까지 굽고 검사 · 검토를 끝낸 뒤, 커밋 전. 이전 판은 git 이력에 있다.
명령: <py> workspace/강의제작/제작도구/기존제작/tools/video/입고.py <영상 출력 폴더 …> [--시험] [--날짜 YYYY-MM-DD] [--상태 "글"]

- 영상 출력 폴더 하나 = 영상 하나: <폴더>/강조/<과정>_<NN>회차_<대본 이름>.mp4, <폴더>/_작업/영상_자막_기록/(강의영상.py가 쓴 자막 · 시간표).
- 영상 → `영상올리기.py`(Release 「영상」, 내려받아 대조, 산출물/영상/<과정>/의 옛 판은 지움), 자막 · 시간표 → 산출물/영상/_작업/영상_자막_기록/(복사 뒤 해시 대조).
- 장 범위는 대본 파일의 `## [SLIDE` 첫 · 끝 번호, 길이는 ffprobe, 강조 수는 구성/<과정>/<NN>회차/강조_<이름>.json.
- --시험: 판정과 README 행만 찍고 올리거나 바꾸지 않는다.
"""
import argparse, datetime, hashlib, json, re, shutil, subprocess, sys
from pathlib import Path

G = Path(__file__).resolve().parents[4]   # workspace/강의제작
S = G / "산출물"
UP = Path(__file__).with_name("영상올리기.py")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def put(src, dst):
    tmp = dst.with_name(dst.name + ".입고중")
    shutil.copyfile(src, tmp)
    if sha(tmp) != sha(src):
        sys.exit(f"{dst}: 복사한 파일의 해시가 원본과 다르다")
    tmp.replace(dst)


def one(folder, a):
    folder = Path(folder)
    found = sorted((folder / "강조").glob("*.mp4"))
    if len(found) != 1:
        sys.exit(f"{folder / '강조'}: 영상이 하나가 아니다({[x.name for x in found]})")
    vid = found[0]; name = vid.stem
    m = re.fullmatch(r"(통합반|실전반)_(\d\d)회차_(.+)", name)
    if not m:
        sys.exit(f"{vid}: 이름이 <과정>_<NN>회차_<대본 이름> 꼴이 아니다")
    course, nn, stem = m.groups()
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(vid)], capture_output=True, text=True, check=True).stdout)
    script = S / course / "이론" / f"{nn}회차" / "대본" / f"{stem}.md"
    if not script.exists():
        sys.exit(f"{script}: 대본이 없다")
    nums = [int(x) for t in re.findall(r"^## \[SLIDE (\d+)(?:~(\d+))?\]", script.read_text(encoding="utf-8"), re.M) for x in t if x]
    cfg = G / "제작도구" / "구성" / course / f"{nn}회차" / f"강조_{name}.json"
    if not cfg.exists():
        sys.exit(f"{cfg}: 강조 설정이 없다")
    marks = len(json.loads(cfg.read_text(encoding="utf-8"))["표시"])
    side = sorted((folder / "_작업" / "영상_자막_기록").glob(f"{name}*"))
    if {x.suffix for x in side} != {".srt", ".md"}:
        sys.exit(f"{folder / '_작업' / '영상_자막_기록'}: {name}의 자막 · 시간표가 다 없다({[x.name for x in side]})")
    rec = S / "영상" / "_작업" / "영상_자막_기록"
    subprocess.run([sys.executable, str(UP), str(vid), *(["--시험"] if a.test else [])], check=True)
    if not a.test:
        for f in side:
            put(f, rec / f.name)
    print(f"| `{course}/{vid.name}` — Release 영상 (SLIDE {min(nums)}~{max(nums)}) | {int(d // 60)}:{d % 60:04.1f} | {a.date} 제작 · 현행 덱 {min(nums)}~{max(nums)}장과 대본 반영 · 강조 {marks}개 · {a.state} |")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--시험", dest="test", action="store_true")
    ap.add_argument("--날짜", dest="date", default=datetime.date.today().isoformat())
    ap.add_argument("--상태", dest="state", default="영상 검토 1회 · 사용자 청취 판정 대기")
    a = ap.parse_args()
    for f in a.folders:
        one(f, a)
