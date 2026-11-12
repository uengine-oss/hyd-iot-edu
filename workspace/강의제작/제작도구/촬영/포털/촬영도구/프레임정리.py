"""take의 frames/ 가운데 encode.py가 쓰지 않는 프레임만 지운다 — 디스크가 빠듯한 클라우드 VM에서 구간마다 검사(measure · 이음새검수)를 마친 뒤 돌린다.
  python3 프레임정리.py <take>            지울 수와 크기만 낸다
  python3 프레임정리.py <take> --실행     지우고, 지운 뒤 조각 키가 그대로인지 다시 계산해 확인한다(다르면 멈춘다)
녹화는 화면이 바뀔 때마다 프레임을 받아(초당 20~40장) 30fps로 합성하는 encode.py가 쓰지 않는 프레임이 생긴다(약 35 %). encode.py는 출력 시각마다
그 시각까지 받은 마지막 프레임을 고르고, 조각 키에는 고른 프레임의 이름 · 횟수 · 크기만 넣는다. 그래서 take 전체를 한 덩이로 합성할 때(`encode.py <출력> <take> …`)
고르지 않는 프레임을 지워도 조각 키와 출력 영상이 같다. 첫 · 끝 프레임은 이음새검수 · 앞뒤보기가 쓰므로 남긴다.
`<take>:<ms>`처럼 잘라 쓸 take에는 돌리지 않는다 — 자르는 자리가 바뀌면 고르는 프레임이 달라진다."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.chdir(HERE)
sys.path.insert(0, str(HERE))
import encode  # noqa: E402


def plan(take):
    T = encode._out_tool(None, None, None, encode.TOOLS, None)
    ffv = encode.out_of([encode.ff(), '-version']).decode().splitlines()[0]
    return T, ffv, encode.plan_spec(take, T, encode.TOOLS, 18, ffv)


def main():
    take, do = sys.argv[1], '--실행' in sys.argv
    T, ffv, chunks = plan(take)
    d = chunks[0].dir
    used = {f for c in chunks for f, _ in c.runs}
    allf = [f['file'] for f in json.loads((d / 'timing.json').read_text(encoding='utf-8'))['frames']]
    keep = used | {allf[0], allf[-1]}
    drop = [f for f in sorted(os.listdir(d / 'frames')) if 'frames/' + f not in keep]
    size = sum((d / 'frames' / f).stat().st_size for f in drop)
    print(f'{take}: 프레임 {len(allf)} · 쓰는 것 {len(used)} · 지울 것 {len(drop)} ({size / 1e6:.0f} MB)')
    if not do:
        return
    keys = [c.key for c in chunks]
    for f in drop:
        (d / 'frames' / f).unlink()
    again = [c.key for c in encode.plan_spec(take, T, encode.TOOLS, 18, ffv)]
    if again != keys:
        sys.exit(f'{take}: 지운 뒤 조각 키가 바뀌었다 {keys} → {again}')
    print('지움 · 조각 키 같음', keys)


if __name__ == '__main__':
    main()
