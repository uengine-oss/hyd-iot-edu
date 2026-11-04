"""강조 뒤 영상과 그 자막 · 시간표를 산출물 자리에 바꿔 끼우고 README 행을 찍는다. 저장소 루트에서: python3 작업/…/도구/입고.py <키 …>(예: 실전4_01)
- 영상: 영상출력/<키>/강조/<이름>.mp4 → workspace/강의제작/산출물/영상/<과정>/<이름>.mp4 (이전 판은 git 이력)
- 자막 · 시간표: 영상출력/<키>/_작업/영상_자막_기록/ → workspace/강의제작/산출물/영상/_작업/영상_자막_기록/
- 장 범위는 대본 파일의 `## [SLIDE` 첫 · 끝 번호, 길이는 ffprobe, 강조 수는 강조 설정. 100 MiB 넘으면 멈춘다.
"""
import json, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
W = Path(__file__).resolve().parents[1]
S = ROOT / "workspace/강의제작/산출물"
for key in sys.argv[1:]:
    course = {"통합": "통합반", "실전": "실전반"}[key[:2]]; nn = f"0{key[2]}"
    out = W / "영상출력" / key
    vid = next((out / "강조").glob(f"{course}_{nn}회차_*.mp4")); name = vid.stem
    if vid.stat().st_size >= 100 * 1024 ** 2: sys.exit(f"{vid}: 100 MiB 이상")
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(vid)], capture_output=True, text=True).stdout)
    script = S / course / "이론" / f"{nn}회차" / "대본" / (name.split(f"{nn}회차_", 1)[1] + ".md")
    nums = [int(x) for m in re.findall(r"^## \[SLIDE (\d+)(?:~(\d+))?\]", script.read_text(encoding="utf-8"), re.M) for x in m if x]
    marks = len(json.loads((ROOT / f"workspace/강의제작/제작도구/구성/{course}/{nn}회차/강조_{name}.json").read_text(encoding="utf-8"))["표시"])
    shutil.copy2(vid, S / "영상" / course / vid.name)
    rec = S / "영상/_작업/영상_자막_기록"
    for f in (out / "_작업/영상_자막_기록").glob(f"{name}*"): shutil.copy2(f, rec / f.name)
    print(f"| `{course}/{vid.name}` (SLIDE {min(nums)}~{max(nums)}) | {int(d // 60)}:{d % 60:04.1f} | 2026-11-03 제작 · 현행 덱 {min(nums)}~{max(nums)}장과 대본 반영 · 강조 {marks}개 · 영상 검토 1회 · 사용자 청취 판정 대기 |")
