"""회차 구성표(구성표.md)를 구성.json에서 만든다(대본.md S-115 · S-131). 손으로 고치지 않는다.

python 제작용/구성/구성표.py 제작용/구성/<과정>/<NN>회차/구성.json

- 낭독 추정은 실제 강사 복제 음성으로 맞춘 계수(제작용/촬영/시간계수.json)로 잰다(대본시간.py와 같은 계산).
- 학습 대기는 대본의 `> [대기 N초]`를 따로 센다. 실습 대본(kind practice)은 실습 큐로 재므로(시간계산.py estimate) 여기서 재지 않는다.
- 구성.json의 `rows`(실라버스 행: kind · title · minutes · slides)가 있으면 행별 배정과 낭독을 나란히 낸다.
- pptx_sha256은 지금 PPTX의 해시로 다시 적는다.
"""
import hashlib, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '제작용/촬영'))
from 시간계산 import load_coef, script_slides, slide_seconds  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    cfg_path = Path(sys.argv[1]).resolve()
    cfg = json.loads(cfg_path.read_text('utf8'))
    base = cfg_path.parent
    k = load_coef()
    pptx = (base / cfg['pptx']).resolve()
    cfg['pptx_sha256'] = hashlib.sha256(pptx.read_bytes()).hexdigest()
    sec = {}  # 장 번호 → 낭독 초
    unit_rows, wait_total = [], 0
    for u in cfg['units']:
        f = (base / u['file']).resolve()
        rel = Path(u['file']).as_posix()
        if u['kind'] != 'pptx':
            unit_rows.append(f"| [{f.name}]({rel}) | 실습 대본 · {u.get('status', '')} | 실습 큐로 잼 | — |")
            continue
        body = f.read_text('utf8')
        slides = script_slides(body)
        total = 0.0
        for n, (text, share, _) in slides.items():
            s = slide_seconds(text, k) / share if share > 1 else slide_seconds(text, k)
            sec[n] = s
            total += s
        wait = sum(int(x) for x in re.findall(r'^> \[대기 (\d+)초\]', body, re.M))
        wait_total += wait
        a, b = u['slides']
        if sorted(slides) != list(range(a, b + 1)):
            raise SystemExit(f'{f}: [SLIDE NN]이 구성.json의 {a}~{b}장과 다르다 — {sorted(slides)}')
        unit_rows.append(f"| [{f.name}]({rel}) | {a}~{b} | {total / 60:.1f}분 | {wait}초 |")
    if sorted(sec) != list(range(1, cfg['slide_count'] + 1)):
        raise SystemExit(f'{cfg_path}: 대본이 덮는 장이 1~{cfg["slide_count"]}장이 아니다')
    out = [f"# {cfg['title']} — 구성표", '',
           '`제작용/구성/구성표.py`가 구성.json에서 만든다. 손으로 고치지 않는다. 분할 대본이 수정 원본이고 제목 · 제작 표시는 낭독하지 않는다.', '',
           '| 단위 파일 | PPTX 장 / 상태 | 낭독 추정 | 학습 대기 |', '|---|---|---:|---:|', *unit_rows, '',
           f"진행 순서: {cfg['playback']}", '']
    if cfg.get('rows'):
        out += ['| 구분 | 실라버스 행 | 배정 | 장 | 낭독 추정 |', '|---|---|---:|---|---:|']
        for r in cfg['rows']:
            a, b = r['slides']
            s = sum(sec[n] for n in range(a, b + 1))
            out.append(f"| {r['kind']} | {r['title']} | {r['minutes']}분 | {a}~{b} | {s / 60:.1f}분 |" if r.get('minutes') is not None
                       else f"| {r['kind']} | {r['title']} | — | {a}~{b} | {s / 60:.1f}분 |")
        out.append('')
    lc = k['lecture']
    out += [f"PPTX {cfg['slide_count']}장. 이론 대본 낭독 추정 합 {sum(sec.values()) / 60:.1f}분, 학습 대기 {wait_total}초 별도. "
            f"계수는 강사 복제 음성 이론 영상 {lc['slides']}장으로 맞춘 값(장 시간 = {lc['scale']}×말 길이 + {lc['per_slide']}초)이고, "
            '낭독 추정이지 조작 · AI 대기 · 실습 진행 시간이 아니다. 실습 행의 장은 이론 대본 안의 간지 · 설명 장 낭독만 센다.', '']
    (base / '구성표.md').write_text('\n'.join(out), encoding='utf8', newline='\n')
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(f"{base / '구성표.md'}: 낭독 {sum(sec.values()) / 60:.1f}분, 대기 {wait_total}초")


if __name__ == '__main__':
    main()
