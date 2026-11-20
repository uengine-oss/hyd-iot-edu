"""2회차 실습 04 관계 조회(Neo4j Browser) 가이드 사진(두 과정 공통 — 통합반 04 · 실전반 05가 같은 영상)을 그 영상의 녹화 프레임에서 뽑고 빨간 표시를 그린다.
사진의 녹화 시각 · 표시 좌표는 이 파일 한 곳이다.

python3 workspace/강의제작/제작도구/촬영/neo4j/사진_만들기.py
    → `촬영/neo4j/가이드사진/images/<이름>.jpg`(가이드 생성기가 두 과정 guide.html 안에 넣는다)와 `실습시작/capture-provenance.json`의 그 사진 항목.
- 원본은 영상 「관계조회-04」를 만든 녹화 take(TAKE — 설명 창을 덮고 강조를 고친 사본, 근거 폴더 `고침/손본_take.py`)의 프레임이다. 영상에 그려 넣은 화살표 · 강조가 없는 화면이고,
  그 밖은 영상 화면과 같다. 시각은 take 시계(ms)이고, 그 시각까지 받은 마지막 프레임을 쓴다. 표시는 늘 그 원본에 다시 그린다.
- 표시 자리는 영상에서 말이 짚은 대상의 상자(timing.json highlights)와 Neo4j Browser에서 잰 단추 상자(Connect · Dismiss · 원통 단추 · 패널 접기)에서 왔고,
  글 한 줄 결과(Created … · Deleted …)는 그 줄의 글자 상자, 표는 머리 아래 행들이다.
- 영상 밖 화면(첫 절의 파일 탐색기 · PowerShell)은 `SCREENS`이고, 원본 PNG는 `사진원본/`에 둔다. 옛 판(2026-11-06 · 11판) 사진의 원본도 `사진원본/`에 남아 있다.
- 사진의 설명 글은 가이드 생성기(`실습시작/graph_guide.py` integrated_relations)가 가진다.
"""
from pathlib import Path
import bisect
import hashlib
import json

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
TAKE = '작업/촬영/neo4j/rec-04-01q'      # 영상 관계조회-04(합본4 → 최종)를 만든 take. 녹화 원본이라 커밋하지 않고, 근거에는 프레임 해시가 남는다
LABS = ['workspace/강의제작/제작도구/촬영/neo4j/가이드사진/images']   # 가이드 생성기(build_common.py)가 이 사진을 guide.html 안에 넣는다 — 두 과정이 같은 사진
OLD_LABS = [f'workspace/강의제작/산출물/{c}/실습/02회차/랩/02일차_실습1_관계조회/images' for c in ('통합반', '실전반')]   # 옛 사진 자리(근거 기록을 지울 때만 본다)
PROVENANCE = HERE.parent.parent/'실습시작/capture-provenance.json'
ORIGINALS = HERE/'사진원본'
RED, WIDTH = '#d32f2f', 4

# 이름, take 시각(ms), 가이드 절, 빨간 표시들(프레임 px [x0, y0, x1, y1])
# 표시 규칙(P-8): 선 굵기 WIDTH, 선의 안팎 GAP px 안에 글자 · 단추 같은 어두운 화소(밝기 DARK 미만)가 없고, 한 사진의 상자끼리는 GAP px 넘게 떨어진다.
PHOTOS = [
    ('q01-connect', 100173, '예제 준비하고 연결하기', [[902, 469, 1224, 523], [696, 624, 1224, 678], [696, 724, 1224, 778], [800, 933, 1120, 1003]]),
    ('q01-dismiss', 106000, '예제 준비하고 연결하기', [[849, 286, 960, 342]]),
    ('q01-address', 139819, '예제 준비하고 연결하기', [[22, 3, 300, 37]]),
    ('q01-overview', 215114, '예제 준비하고 연결하기', [[5, 40, 55, 95], [8, 144, 122, 193], [8, 276, 178, 325]]),
    ('q01-collapse', 242800, '예제 준비하고 연결하기', [[494, 34, 552, 91]]),
    ('q02-paste', 262000, '노드 만들기: CREATE', [[36, 93, 752, 156], [1851, 90, 1916, 137]]),
    ('q02-created', 379592, '노드 만들기: CREATE', [[57, 221, 405, 246]]),
    ('q03-graph', 469742, '찾아서 돌려받기: MATCH · RETURN', [[657, 674, 763, 780], [657, 375, 763, 481]]),
    ('q03-details', 493003, '찾아서 돌려받기: MATCH · RETURN', [[1419, 329, 1576, 371], [1419, 485, 1890, 631]]),
    ('q03-table', 512207, '찾아서 돌려받기: MATCH · RETURN', [[101, 214, 176, 274], [4, 304, 1416, 447]]),
    ('q03-values', 604748, '찾아서 돌려받기: MATCH · RETURN', [[12, 312, 1908, 422]]),
    ('q04-where', 651031, '조건 더하기: WHERE', [[619, 487, 801, 668]]),
    ('q05-merge-new', 780976, '있으면 찾고 없으면 만들기: MERGE · SET, 관계 잇기', [[57, 897, 384, 921], [619, 487, 801, 668]]),
    ('q05-merge-again', 819327, '있으면 찾고 없으면 만들기: MERGE · SET, 관계 잇기', [[57, 897, 176, 922], [619, 487, 801, 668]]),
    ('q05-linked', 945023, '있으면 찾고 없으면 만들기: MERGE · SET, 관계 잇기', [[682, 487, 738, 668], [1488, 448, 1670, 489]]),
    ('q06-set', 1013836, '속성 고치기: SET', [[656, 391, 764, 499], [1419, 485, 1890, 631]]),
    ('q07-detach', 1086954, '지우고 다시 찾기: DETACH DELETE · DELETE', [[57, 221, 322, 246]]),
    ('q07-left', 1125069, '지우고 다시 찾기: DETACH DELETE · DELETE', [[657, 674, 763, 780], [657, 375, 763, 481]]),
    ('q07-zero', 1193498, '지우고 다시 찾기: DETACH DELETE · DELETE', [[12, 312, 1908, 371]]),
    ('q08-labels', 1287309, '설비 데이터를 레이블마다 세기', [[12, 312, 1908, 575]]),
    ('q09-one-hop', 1375241, '관계를 한 번 건너기: 한 단계', [[12, 312, 1908, 626]]),
    ('q10-path', 1466861, '관계를 두 번 건너기: 경로', [[390, 246, 1006, 771], [1482, 372, 1828, 407]]),
    ('q10-part', 1554183, '관계를 두 번 건너기: 경로', [[654, 318, 1422, 364]]),
    ('q11-rows', 1635295, '답이 맞는지 맞춰 보기: 원래 행 · 조건 · 집계', [[10, 310, 1910, 577]]),
    ('q11-where', 1686146, '답이 맞는지 맞춰 보기: 원래 행 · 조건 · 집계', [[10, 310, 1910, 526]]),
    ('q11-aggregate', 1752975, '답이 맞는지 맞춰 보기: 원래 행 · 조건 · 집계', [[639, 259, 1908, 475]]),
]
DARK, GAP = 140, 6
# 상자를 띄울 자리가 없어 표시 검사를 하지 않는 사진과 그 까닭(그 사진은 키워 눈으로 보아, 선이 글자를 가로지르지 않음을 확인했다)
LINE = '한 줄짜리 결과 글을 감싼 상자라 줄 높이 안에 6px 여백과 선을 둘 자리가 없다(선이 글자에 닿지 않는 것은 키워 보았다)'
UNCHECKED = {
    'q01-connect': '입력칸 둘레(Password 칸은 커서가 든 짙은 테두리)와 칸 이름 글이 6px 안에 있어, 칸을 감싼 상자가 그 테두리에 붙는다(칸 안 글자는 가리지 않는다)',
    'q01-dismiss': '안내 창이 짙은 보라색이라 Dismiss 둘레 어디에 선을 그어도 어두운 화소에 닿는다',
    'q01-address': '맨 위 막대의 Instance 칸(초록 점과 주소가 든 회색 둥근 칸)이 막대 높이에 꽉 차서 6px 여백을 둘 자리가 없다(그 칸 둘레에 선을 두어 글자는 가리지 않는다)',
    'q10-path': '오른쪽 목록의 레이블 단추(Asset · Component · Part)가 짙은 색이라 단추 줄을 두른 선이 6px 안에 닿는다(단추 글자는 가리지 않는다)',
    'q02-paste': '입력칸이 쿼리 두 줄 높이뿐이고 Run 단추는 짙은 파랑이라, 상자가 쿼리 글 · 단추에 6px 안으로 붙는다(줄 번호와 글자는 가리지 않는다)',
    'q02-created': LINE, 'q05-merge-new': LINE, 'q05-merge-again': LINE, 'q07-detach': LINE,
    'q06-set': '속성 표의 <id> 값이 두 줄로 접혀 그 아래 id 행 위로 6px을 비울 자리가 없다',
}

# 영상 밖 화면(영상이 연결 창부터 시작해 찍히지 않은 준비 단계): 이 PC에서 학생 경로대로 ZIP을 풀고 파일 탐색기 → PowerShell로 실행하며
# 창을 그대로 찍은 원본(사진원본/<이름>.png). 이름, 원본, 가이드 절, 빨간 표시들, 자르기(없으면 전체)
# 어두운 터미널에서는 밝기 검사(DARK)가 글자와 배경을 가르지 못해 검사하지 않고, 상자 둘레를 4배로 키워 눈으로 본다.
SCREENS = [
    ('00-explorer', ORIGINALS/'00-explorer.png', '예제 준비하고 연결하기', [[208, 47, 743, 80]], [0, 0, 983, 130]),   # 아래 파일 목록은 옛 판(안내.html이 있던 때)이라 주소 표시줄 줄만 싣는다
    ('00-powershell', ORIGINALS/'00-powershell.png', '예제 준비하고 연결하기', [[10, 119, 1205, 415]], [0, 0, 1499, 440]),
]


def mark_problems(gray, rects, cursor):
    """표시 규칙 위반 목록. gray는 표시 전 프레임(흑백 배열 — 리스트의 리스트가 아닌 numpy)."""
    import numpy as np
    dark = gray < DARK
    if cursor:
        x, y = cursor
        dark[max(0, y-4):y+40, max(0, x-4):x+28] = False
    h, w = dark.shape
    def count(x0, y0, x1, y1):
        return int(dark[max(0, y0):min(h, y1), max(0, x0):min(w, x1)].sum())
    problems = []
    for r in rects:
        x0, y0, x1, y1 = r
        sides = {'위': count(x0-GAP, y0-GAP, x1+GAP, y0+WIDTH+GAP), '아래': count(x0-GAP, y1-WIDTH-GAP, x1+GAP, y1+GAP),
                 '왼쪽': count(x0-GAP, y0-GAP, x0+WIDTH+GAP, y1+GAP), '오른쪽': count(x1-WIDTH-GAP, y0-GAP, x1+GAP, y1+GAP)}
        problems += [f'{r} {side} 선 {GAP}px 안 어두운 화소 {n}' for side, n in sides.items() if n]
    for i, a in enumerate(rects):
        for b in rects[i+1:]:
            if a[0]-GAP < b[2] and b[0]-GAP < a[2] and a[1]-GAP < b[3] and b[1]-GAP < a[3]:
                problems.append(f'{a}와 {b}가 {GAP}px 안으로 붙거나 겹침')
    return problems


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


VIDEO = '작업/촬영/neo4j/관계조회-04-합본4/관계조회-04-최종_1080p.mp4'   # 이 take로 만든 최종 영상(근거에 해시를 남겨 어느 영상의 화면인지 잇는다)


def main():
    import numpy as np
    take = ROOT/TAKE
    timing = json.loads((take/'timing.json').read_text(encoding='utf-8'))
    frames, times = timing['frames'], [f['time'] for f in timing['frames']]
    video_sha = sha(ROOT/VIDEO) if (ROOT/VIDEO).exists() else None
    picked, failures = {}, []
    for name, ms, section, rects in PHOTOS:   # 먼저 모든 표시를 검사하고, 하나라도 어기면 아무것도 쓰지 않는다
        frame = take/frames[max(bisect.bisect_right(times, ms) - 1, 0)]['file']
        picked[name] = frame
        if name in UNCHECKED:
            continue
        failures += [f'{name}: {p}' for p in mark_problems(np.asarray(Image.open(frame).convert('L')).astype(int), rects, None)]
    if failures:
        raise SystemExit('표시 규칙 위반 — 사진을 쓰지 않았다:\n' + '\n'.join(failures))
    records = []
    for name, ms, section, rects in PHOTOS:
        frame = picked[name]
        image = Image.open(frame).convert('RGB')
        draw = ImageDraw.Draw(image)
        for rect in rects:
            draw.rectangle(rect, outline=RED, width=WIDTH)
        for lab in LABS:
            target = ROOT/lab/f'{name}.jpg'
            target.parent.mkdir(parents=True, exist_ok=True)
            image.save(target, quality=92)
            records.append({'target': f'{lab}/{name}.jpg', 'kind': '학생 실습 화면', 'section': section,
                            'source': f'{TAKE}/{frame.relative_to(take).as_posix()}', 'source_sha256': sha(frame), 'take_ms': ms,
                            'video': VIDEO, 'video_sha256': video_sha, 'rectangles': rects,
                            **({'unchecked': UNCHECKED[name]} if name in UNCHECKED else {}), 'sha256': sha(target)})
    for name, source, section, rects, crop in SCREENS:
        image = Image.open(source).convert('RGB')
        draw = ImageDraw.Draw(image)
        for rect in rects:
            draw.rectangle(rect, outline=RED, width=WIDTH)
        if crop:
            image = image.crop(crop)
        for lab in LABS:
            target = ROOT/lab/f'{name}.jpg'
            image.save(target, quality=92)
            records.append({'target': f'{lab}/{name}.jpg', 'kind': '학생 실습 화면', 'section': section, 'source_type': 'image',
                            'source': source.relative_to(ROOT).as_posix(), 'source_sha256': sha(source),
                            'source_note': '2026-11-06 이 PC에서 ZIP을 D:/HYD-Practice에 풀고 파일 탐색기 주소 표시줄 → PowerShell(Windows Terminal)로 두 명령을 실행하며 창을 찍음',
                            'crop_box': crop, 'rectangles': rects, 'pointer': None, 'sha256': sha(target)})
    for lab in LABS:   # 옛 판 사진(그 원본은 사진원본/에 있다)은 가이드가 쓰지 않으므로 지운다
        for old in (ROOT/lab).glob('*.jpg'):
            if old.stem not in {n for n, *_ in PHOTOS + SCREENS}:
                old.unlink()
    old = json.loads(PROVENANCE.read_text(encoding='utf-8'))
    keep = [x for x in old if not any(x['target'].removeprefix('workspace/').startswith(lab.removeprefix('workspace/') + '/') for lab in LABS + OLD_LABS)]
    PROVENANCE.write_text(json.dumps(keep + records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(len(PHOTOS) + len(SCREENS), '사진. 눈으로 본 뒤 가이드를 만든다.')


if __name__ == '__main__':
    main()
