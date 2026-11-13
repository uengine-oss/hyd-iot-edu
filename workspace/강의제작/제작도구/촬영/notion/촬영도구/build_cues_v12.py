"""v12 녹화 큐 만들기: 새 대본 「2. 새 대본 전문」을 ▸(조작 자리)와 ‖(쉬는 자리)에서 잘라 source-cues-v12.json을 쓴다.
사용: PYTHONUTF8=1 python build_cues_v12.py [새대본.md]   (기본값은 아래 SCRIPT)

- 큐 id는 「s<단계 2자리>-<그 단계 안 차례 2자리>」(예 s05-03)다. 대본 글을 고쳐도 ▸ · ‖의 차례가 같으면 id가 같다.
- ▸로 끝난 큐는 그 끝에서 할 조작 이름(op)을 OPS에서 차례대로 받는다. 단계마다 대본의 ▸ 수와 OPS의 조작 수가 다르면
  그 단계 · 줄 · ▸ 목록을 대고 멈춘다. 구간 모듈 segs/v12-NN.mjs가 같은 조작 이름으로 손잡이를 달므로, 동선이 바뀌면 두 곳을 함께 고친다
  (모듈 쪽 이름 대조는 node preflight12.mjs가 한다).
- 큐 사이 쉼(pause_before)은 영상 V-14의 2회차 값이다(사용자 2026-11-13 — 1회차 값은 빠르게 들렸다): ▸ 뒤에 말이 이어지면 잇기 0.6초,
  ‖ 뒤는 큐 사이 1.3초, ▸ ‖(조작 결과를 본 뒤)는 2.0초, 단계가 바뀌는 곳은 2.3초. 앞 큐가 묻는 말(「?」로 끝남)이면 0.3초를 더한다.
- text는 읽을 글이다. 대본의 「」는 지금 음성 캐시와 같게 ‘’로 바꾼다(소리 내지 않는 글자). script는 대본 원문 조각이다.
- point는 그 큐의 마지막 문장이 시작하는 글자 비율이다. 녹화 제어는 그 자리에서 커서를 출발시키고 큐 끝(▸) 약 250ms 전에 누른다."""
import json, re, sys
from pathlib import Path
from common import HERE

SCRIPT = HERE.parents[5] / '작업' / '2026-11-12_실습영상-화면대조' / '01-02' / '새대본.md'
OUT = HERE / 'source-cues-v12.json'
PAUSE = {'시작': 0, '잇기': 600, '큐': 1300, '결과': 2000, '단계': 2300}  # 영상 V-14 2회차 값(ms)
QUESTION_EXTRA = 300  # 앞 큐가 묻는 말이면 그 뒤 쉼에 더한다

# 단계마다 ▸ 하나에 조작 이름 하나, 대본 차례대로. 같은 단계 안에서 같은 이름을 두 번 쓰면 같은 손잡이가 두 번 불린다.
OPS = {
    1: ['노션열기'],
    2: ['새페이지', '페이지고르기', '제목입력', '제목위올리기', '아이콘공책', '아이콘짚기', '커버추가', '커버변경', '커버고르기',
        '제목끝엔터', '목록이름짚기', '목록접기'],
    3: ['소개입력', '엔터두번', '손잡이짚기'],
    4: ['슬래시', '콜아웃검색', '콜아웃고르기', '굵게켜기', '굵은줄', '굵게끄기', '상자엔터', '설명줄', '손잡이누르기', '색이름치기', '색고르기'],
    5: ['상자밖', '빈줄둘', '갤러리검색', '갤러리보기', '빈목록짚기', '새페이지자리짚기', '제목자리짚기', '이름입력엔터'],
    6: ['설정', '보기이름입력', '보기이름짚기', '목록이름짚기', '닫기'],
    7: ['새로만들기', '전체페이지', '제목입력', '이모지연필', '속성줄짚기', '소개입력', '엔터두번', '콜아웃슬래시', '콜아웃고르기', '굵은줄', '설명줄'],
    8: ['상자밖', '한줄띄움', '제목2단축', '제목2입력', '페이지슬래시', '페이지고르기', '하위제목', '이모지팔레트', '경로짚기', '경로부모짚기'],
    9: ['소개입력', '엔터두번', '제목2', '제목2엔터', '글머리단축', '항목1', '항목2', '항목3', '목록끝'],
    10: ['토글단축', '토글질문', '삼각형짚기', '안쪽누르기', '설명1', '설명2', '접기', '펴기', '다시접기', '질문끝엔터', '빈토글지우기'],
    11: ['구분선', '제목2', '할일단축', '네모짚기', '할일1', '할일2', '목록끝'],
    12: ['소개끝엔터', '한줄띄움', '목차', '목차항목1짚기', '목차항목2짚기', '목차누르기'],
    13: ['경로부모', '첫페이지줄짚기', '나의페이지끝엔터', '페이지만들기', '제목입력', '이모지사슬', '소개입력', '엔터두번', '제목2',
         '번호단축', '번호1', '번호2', '번호3', '번호4', '목록끝', '한줄띄움', '콜아웃만들기', '상자글'],
    14: ['상자밖한줄', '제목2', '도움말글', '가이드복사', '노션복귀', '글자고르기', '링크단축', '붙여넣기엔터', '링크짚기', '선택풀고엔터', '이유글'],
    15: ['경로부모', '두줄짚기', '나의페이지끝엔터', '콜아웃만들기', '굵은줄', '굵게끄고엔터', '설명1', '설명2', '손잡이색이름', '색고르기',
         '상자밖', '콜아웃만들기2', '회색짚기', '둘째상자글', '둘째설명2'],
    16: ['둘째손잡이끌기', '놓기', '첫페이지넣기', '둘째페이지넣기'],
    17: ['홈으로', '새로만들기', '전체페이지', '제목입력', '이모지전구', '소개입력', '콜아웃만들기', '상자글', '최근파랑'],
    18: ['상자밖한줄', '제목2', '글머리단축', '항목1', '항목2', '항목3', '목록끝', '토글단축', '질문', '안쪽설명', '접기'],
    19: ['홈으로', '설정', '속성편집', '이름짚기', '생성일짚기', '태그짚기', '새속성', '분야이름', '선택유형', '옵션추가', '옵션도구',
         '옵션학습방법', '옵션AI실습', '뒤로', '분야짚기', '새속성2', '이해도이름유형', '옵션설명못함', '옵션대충앎', '옵션설명가능뒤로',
         '새속성3', '이미지이름유형닫기'],
    20: ['카드열기', '분야짚기', '이해도짚기', '카드이미지짚기', '분야칸', '도구', '대충앎', '가이드복사1', '이미지칸', '링크탭',
         '붙여넣기', '링크버튼', '창닫기', '가이드복사2', '둘째카드열기', '학습방법', '이해도고르기', '링크탭2', '붙여넣고링크', '붙음짚기'],
    21: ['홈으로', '설정', '레이아웃', '미리보기값짚기', '미리보기누르기', '카드이미지', '카드크기작게', '닫기', '작은카드짚기'],
    22: ['보기추가짚기', '표고르기', '이름입력', '완료', '닫기', '주제카드탭', '전체주제탭', '줄짚기'],
    23: ['설정', '속성표시', '생성일태그숨김', '카드이미지숨김', '닫기', '주제카드탭', '그림짚기', '전체주제복귀', '검색지식',
         '검색지우기', '검색닫고카드탭'],
    24: ['화살표', '새템플릿', '안내짚기', '제목입력', '이모지종이', '소개입력', '엔터두번', '콜아웃만들기', '상자글', '상자밖한줄', '제목2',
         '글머리1', '글머리2', '목록끝', '토글질문', '안쪽설명', '접기', '템플릿닫기'],
    25: ['템플릿적용', '전체페이지', '소개짚기', '상자짚기', '기록짚기', '토글짚기', '이모지책', '제목바꾸기', '소개바꾸기', '기록끝엔터',
         '페이지만들기', '하위제목이모지', '본문입력', '홈으로', '카드세장짚기'],
    26: ['공유', '공유짚기', '게시탭', '닫기', '문장고르기', '댓글단축', '댓글닫기'],
    27: ['작업', '내보내기', '형식HTML', '보기칸짚기', '콘텐츠칸짚기', '하위포함', '내보내기누르기', '내려받기목록', '새탭열기', '카드누르기'],
    28: ['카드열기', '두상자짚기', '첫페이지열기', '둘째페이지열기', '홈으로'],
}


def fail(msg):
    raise SystemExit(f'build_cues_v12: {msg}')


def last_sentence_start(text):
    starts = [0] + [m.end() for m in re.finditer(r'[.?!]\s+', text)]
    starts = [s for s in starts if s < len(text)]
    return round(starts[-1] / len(text), 3)


def parse(path):
    lines = path.read_text(encoding='utf-8').split('\n')
    try:
        a = next(i for i, l in enumerate(lines) if l.startswith('## 2. '))
    except StopIteration:
        fail(f'{path}: 「## 2. 새 대본 전문」 제목 줄이 없음')
    steps, cur = {}, None
    for i in range(a + 1, len(lines)):
        l, ln = lines[i], i + 1
        if l.startswith('## '):
            break
        m = re.match(r'### (\d+)\. ', l)
        if m:
            cur = int(m.group(1))
            if cur in steps:
                fail(f'{path}:{ln}: 단계 {cur} 제목이 두 번 나옴')
            steps[cur] = {'cues': [], 'marks': []}
            continue
        if not l.strip() or l.strip() == '---':
            continue
        if cur is None:
            fail(f'{path}:{ln}: 단계 제목(### N.) 앞에 글이 있음')
        cues, buf = steps[cur]['cues'], ''
        for tok in re.split(r'(▸|‖)', l):
            if tok == '▸':
                if not buf.strip():
                    fail(f'{path}:{ln}: 단계 {cur}의 ▸ 앞에 읽을 글이 없음(▸ 두 개가 붙었거나 줄이 ▸로 시작)')
                cues.append({'script': buf.strip(), 'action': True, 'end': '잇기', 'line': ln})
                steps[cur]['marks'].append(ln)
                buf = ''
            elif tok == '‖':
                if buf.strip():
                    cues.append({'script': buf.strip(), 'action': False, 'end': '큐', 'line': ln})
                elif cues and cues[-1]['action'] and cues[-1]['end'] == '잇기':
                    cues[-1]['end'] = '결과'
                else:
                    fail(f'{path}:{ln}: 단계 {cur}의 ‖ 앞에 큐가 없음(‖ 두 개가 붙었거나 단계 첫머리가 ‖)')
                buf = ''
            else:
                buf += tok
        if buf.strip():
            fail(f'{path}:{ln}: 단계 {cur}의 문단이 ▸나 ‖로 끝나지 않음 — 끝 글 「{buf.strip()[-30:]}」(문단 끝은 쉼 자리다)')
    return steps


def build(path):
    steps = parse(path)
    if sorted(steps) != sorted(OPS):
        fail(f'단계 목록이 다름: 대본 {sorted(steps)} / OPS {sorted(OPS)}')
    out, prev_end, prev_q = [], None, False
    for st in sorted(steps):
        s, ops = steps[st], OPS[st]
        if len(s['marks']) != len(ops):
            fail(f"단계 {st}: 대본의 ▸ {len(s['marks'])}개(줄 {s['marks']}) / OPS {len(ops)}개 {ops} — "
                 f"대본 동선이 바뀌었으면 OPS와 segs/v12-*.mjs의 그 단계 손잡이를 함께 고친다")
        if s['cues'] and s['cues'][-1]['end'] == '잇기':
            fail(f"{path}:{s['cues'][-1]['line']}: 단계 {st}가 ▸로 끝남 — 단계 끝은 ‖(결과를 보는 쉼)여야 한다")
        k = 0
        for n, c in enumerate(s['cues'], 1):
            text = c['script'].replace('「', '‘').replace('」', '’')
            kind = '시작' if prev_end is None else '단계' if n == 1 else '잇기' if prev_end == '잇기' else '결과' if prev_end == '결과' else '큐'
            op = None
            if c['action']:
                op, k = ops[k], k + 1
            out.append({'id': f's{st:02}-{n:02}', 'step': st, 'n': n, 'line': c['line'], 'text': text, 'script': c['script'],
                        'op': op, 'end': c['end'], 'pause_kind': kind, 'pause_before': PAUSE[kind] + (QUESTION_EXTRA if prev_q else 0), 'point': last_sentence_start(text)})
            prev_end = c['end']
            prev_q = text.rstrip(' ’"').endswith('?')
    return out


if __name__ == '__main__':
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else SCRIPT
    if not src.is_file():
        fail(f'대본 파일 없음: {src}')
    cues = build(src)
    OUT.write_text(json.dumps({'source': src.name, 'cues': cues}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    per = {}
    for c in cues:
        v = per.setdefault(c['step'], [0, 0])
        v[0] += 1
        v[1] += c['op'] is not None
    print(json.dumps({'out': OUT.name, 'cues': len(cues), 'ops': sum(v[1] for v in per.values()), 'chars': sum(len(c['text']) for c in cues),
                      'per_step': {k: f'{v[0]}큐 {v[1]}조작' for k, v in per.items()}}, ensure_ascii=False))
