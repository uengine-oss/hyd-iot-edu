"""이론 영상의 자막(.srt)이 대본의 낭독 문장과 같은지, 쉼_저장에 크게(3)가 셋 이상인 구획이 있는지 잰다. 읽기만 한다.
언제: 영상을 구운 뒤 검토자가 볼 때 · 입고 전. 검토자마다 대조 스크립트를 다시 짜지 않으려고 쓴다.
명령: <py> workspace/강의제작/제작도구/검사/자막대조.py <자막 폴더> <대본 …>   # 어긋남 0이면 종료 0

자막 폴더 = <과정>_<NN>회차_<대본 이름>.srt가 든 폴더(영상 출력의 _작업/영상_자막_기록/ 또는 산출물/영상/_작업/영상_자막_기록/). 문장은 공백을 빼고 순서대로 견준다.
"""
import difflib, re, sys
from pathlib import Path

sys.dont_write_bytecode = True
VIDEO = Path(__file__).resolve().parents[1] / "기존제작/tools/video"
sys.path.insert(0, str(VIDEO))
_argv, sys.argv = sys.argv, sys.argv[:1]
import 쉼옮기기 as breath  # noqa: E402
sys.argv = _argv
tool = breath.tool


def srt_lines(p):
    out = []
    for block in re.split(r"\n\s*\n", p.read_text(encoding="utf-8").strip()):
        lines = block.splitlines()
        if len(lines) >= 3:
            out.append(" ".join(lines[2:]).strip())
    return out


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    folder, bad = Path(sys.argv[1]), 0
    for sc in map(Path, sys.argv[2:]):
        r = sc.resolve()
        name = f"{r.parents[3].name}_{r.parents[1].name}_{r.stem}"
        srt = folder / f"{name}.srt"
        if not srt.exists():
            print(f"{name}: 자막이 없다 — {srt}"); bad += 1; continue
        blocks = tool.slides_text(r)
        want = [s for _, _, t in blocks for s in breath.sentences(t)]
        got = srt_lines(srt)
        a, b = ["".join(x.split()) for x in want], ["".join(x.split()) for x in got]
        ops = [o for o in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if o[0] != "equal"]
        big = []
        for first, _, t in blocks:
            ss = breath.sentences(t)
            f = breath.tool.HERE / "쉼_저장" / f"{tool.breath_key(ss)}.json"
            if len(ss) >= 2 and f.exists() and breath.valid(breath.load(f)) and breath.load(f)["쉼"].count(3) > 2:
                big.append(first)
        print(f"{name}: 대본 문장 {len(a)} · 자막 {len(b)} · 어긋남 {len(ops)} · 크게 셋 이상 구획 {big}")
        for tag, i1, i2, j1, j2 in ops[:10]:
            print(f"  대본 {i1 + 1}번째: {' / '.join(want[i1:i2])[:70]!r} ↔ 자막 {j1 + 1}번째: {' / '.join(got[j1:j2])[:70]!r}")
        bad += len(ops) + len(big)
    print("어긋남 0" if not bad else f"어긋남 {bad}")
    sys.exit(0 if not bad else 1)


if __name__ == "__main__":
    main()
