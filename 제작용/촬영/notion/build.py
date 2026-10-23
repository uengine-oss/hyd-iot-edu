"""Notion 실습을 실제 촬영판(사용자 확정 영상)의 발화 · 조작 시각으로 두 과정 대본 · 가이드 · 시간 · ZIP에 반영한다.
장면 제목 · 준비 문단 · 입력값은 준비 원고(수업원고.md · 행동목록.json)에서, 말한 문장과 시각은 영상 verification.json과 음성 캐시에서 온다.
앱/학생 코드는 실행하지 않는다. 사용: python build.py"""
from pathlib import Path
import html
import json
import re
import sys
import zipfile
import hashlib
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = HERE / '수업원고.md'
sys.path.insert(0, str(HERE / '촬영도구'))
from common import WORK, AUDIO
VIDEO = WORK / 'Notion_학습노트_v11'  # 2026-10-23 사용자 재생 확정
CONFIRMED = '2026-10-23'


def stamp(s):
    m, sec = s.split(':')
    return int(m) * 60 + float(sec)


# 확정 영상의 촬영 구간(기능 단위)이 대본 · 가이드의 절이다. 준비 원고의 장면 번호는 촬영 중 문장을 바꾸거나 옮겨 일부(N01 · N12 · N19 · N23 · N25)가
# 영상에 남지 않으므로 절 기준으로 쓰지 않는다. 제목은 각 구간에서 실제로 한 일이다.
SEGMENTS = {
    '25': '작업 화면 · 새 페이지 · 제목과 소개 · 안내 상자',
    '26': '주제 갤러리 만들기와 첫 주제 열기',
    '27': '주제 소개와 하위 페이지',
    '28': '긴 설명 토글 · 다음에 할 일 · 목차',
    '29': '번호 목록과 도움말 링크',
    '30': '두 하위 페이지를 안내 상자로 묶기',
    '31': '두 상자를 나란히 놓기',
    '32': '다른 주제에 메모와 자료 담기',
    '33': '표 보기 「전체 주제」 추가',
    '34': '분야 · 이해도 속성 만들기',
    '35': '카드 그림과 크기 맞추기',
    '36': '다음 주제를 위한 템플릿',
    '37': '템플릿으로 새 주제 시작하기',
    '38': '공유 · 게시 · 댓글 · 내보내기 설정',
    '39': '내보내기 · 완성한 노트 둘러보기 · 마무리',
}


def shot_rows():
    """확정 영상의 큐를 말한 시각으로 촬영 구간에 넣는다. 문장은 음성 캐시, 입력값은 준비 원고의 행동 목록에서 가져온다."""
    ver = json.loads((VIDEO / 'verification.json').read_text(encoding='utf-8'))
    bounds, off = [], 0
    for s in ver['segments']:
        bounds.append((off / 1000, re.match(r'take-n(\d+)', s['segment']).group(1)))
        off += s['used_ms']
    sources = {c['id']: c for c in json.loads((HERE / '촬영도구/source-cues.json').read_text(encoding='utf-8'))}
    actions = {a['id']: a for a in json.loads((HERE / '행동목록.json').read_text(encoding='utf-8'))}
    rows = []
    for c in ver['cue_timeline']:
        f = AUDIO / (c['id'] + '.json')
        if not f.is_file():
            raise FileNotFoundError(f'{VIDEO.name}: 큐 {c["id"]}의 음성 문장 파일 없음 {f}')
        text = json.loads(f.read_text(encoding='utf-8'))['text']
        at = stamp(c['speech'][0])
        seg = [k for b, k in bounds if at >= b][-1]
        src = sources.get(c['id'], {}).get('source_action')
        rows.append({'id': c['id'], 'scene': seg, 'text': text, 'speech': c['speech'],
                     'action': c.get('action'), 'inputs': actions.get(src, {}).get('inputs') or []})
    starts = {}
    for b, k in bounds:
        starts.setdefault(k, b)
    unknown = set(starts) - set(SEGMENTS)
    if unknown or set(starts) != {r['scene'] for r in rows}:
        raise RuntimeError(f'{VIDEO.name}: 제목 없는 구간 {sorted(unknown)} 또는 큐 없는 구간 — SEGMENTS와 영상이 어긋남')
    return ver, rows, starts

def main():
    source = SOURCE.read_text(encoding='utf-8')
    prepare = re.search(r'^> 준비: .+$', source, re.M).group(0)
    titles = SEGMENTS
    ver, rows, starts = shot_rows()
    total = ver['duration_s']
    order = list(starts)
    span = {s: (starts[s], starts[order[i + 1]] if i + 1 < len(order) else total) for i, s in enumerate(order)}
    number = {s: i + 1 for i, s in enumerate(order)}
    mmss = lambda x: f'{int(x // 60)}:{x % 60:04.1f}'
    spoken = sum(stamp(r['speech'][1]) - stamp(r['speech'][0]) for r in rows)

    # 대본: 영상에서 실제로 말한 문장. 조작 표시는 그 문장을 말하는 동안 한 조작의 영상 시각(낭독하지 않음).
    script = ['# {{과정}} 1회차 실습 1 — Notion 주제 갤러리 만들기', '',
              f'> 제작용·비낭독: {CONFIRMED} 촬영판(영상 {mmss(total)}, 사용자 재생 확정)에서 실제로 말한 문장이다. 「조작」 표시는 그 문장을 말하는 동안 화면에서 한 조작과 영상 시각이며 읽지 않는다. 다시 찍을 때도 대상을 먼저 짚고 설명하며 조작하고, 결과는 나타난 뒤 말한다.', '',
              prepare, '',
              f'> 시간: 실측 {mmss(total)}(말 {mmss(spoken)}, 큐 {len(rows)}개). 구간별 길이는 [예상시간](../랩/01일차_실습1_학습노트/예상시간.md).', '']
    for s in order:
        script += [f'## {number[s]}. {titles[s]}', '']
        for r in rows:
            if r['scene'] != s:
                continue
            script += [r['text'], '']
            if r['action']:
                note = f'> 조작 {r["action"][0][:-2]}'
                if r['inputs']:
                    note += ' · 입력: ' + ' / '.join(str(x) for x in r['inputs'])
                script += [note, '']
    script = '\n'.join(script).rstrip() + '\n'

    timing = [f'# Notion 학습노트 실습 시간 — 실측', '',
              f'대상: {CONFIRMED} 촬영판(사용자 재생 확정). **실측 영상 길이 {mmss(total)}({total:.0f}초)**, 음성 {len(rows)}큐(말만 합하면 {mmss(spoken)}). 설명하면서 조작한 실제 타임라인이며 배속 · 중간 컷이 없다.', '',
              '| 구간 | 영상 시각 | 길이 |', '|---|---|---|']
    timing += [f'| {number[s]}. {titles[s]} | {mmss(span[s][0])} | {mmss(span[s][1] - span[s][0])} |' for s in order]
    ms = ver['motion_summary']
    timing += ['', f'측정: 이동 {ms["count"]}회 중 최대 프레임 공백 {ms["max_gap_ms_max"]}ms, 100ms 이상 {len(ms["over_100ms"])}회. 영상 위쪽에 Notion의 「최신 버전으로 업데이트」 막대가 1:59.8부터 보이며 그대로 두었다.']
    timing = '\n'.join(timing) + '\n'
    (HERE / '예상시간.md').write_text(timing, encoding='utf-8', newline='\n')

    capture = ['# 학습노트 — 화면', '',
               f'상태: 영상 촬영 완료({CONFIRMED}, {mmss(total)}). 구간별 정지 사진은 아직 뽑지 않았다. 사진이 필요하면 아래 영상 시각에서 같은 판본으로 뽑는다.', '',
               '| 구간 | 영상 시각 | 보여 준 것 |', '|---|---|---|']
    capture += [f'| {number[s]} | {mmss(span[s][0])} ~ {mmss(span[s][1])} | {titles[s]} |' for s in order]
    capture = '\n'.join(capture) + '\n'

    manifest = {'source_video': VIDEO.relative_to(ROOT).as_posix(), 'video_seconds': total, 'cues': len(rows), 'sections': len(order),
                'titles_from': str(SOURCE.relative_to(ROOT).as_posix()), 'courses': []}
    for course in ['통합반', '실전반']:
        base = ROOT / '산출물' / course / '실습/01회차'
        script_path = base / '대본/02_실습_학습노트.md'
        lab = base / '랩/01일차_실습1_학습노트'
        archive = lab.with_suffix('.zip')
        file_names = [n for n in zipfile.ZipFile(archive).namelist() if not n.endswith('/')]
        prefix = '01회차/랩/' + lab.name + '/'
        script_entry = '01회차/대본/' + script_path.name
        assert set(file_names) == {prefix + f.relative_to(lab).as_posix() for f in lab.rglob('*') if f.is_file()} | {script_entry}, '기존 ZIP 구조가 예상과 다릅니다'
        text = script.replace('{{과정}}', course)
        script_path.write_text(text, encoding='utf-8', newline='\n')
        (lab / '학습노트_입력틀.md').write_text((HERE / '입력자료.md').read_text(encoding='utf-8'), encoding='utf-8', newline='\n')
        (lab / '예상시간.md').write_text(timing, encoding='utf-8', newline='\n')
        shutil.copyfile(HERE / '행동목록.json', lab / '행동목록.json')
        (lab / '이미지').mkdir(exist_ok=True)
        (lab / '예시').mkdir(exist_ok=True)
        for asset in (HERE / 'design').glob('*.png'):
            shutil.copyfile(asset, lab / '이미지' / asset.name)
        for example in (HERE / '카드본문').glob('*.md'):
            body = example.read_text(encoding='utf-8')
            # 개인 원래 기록은 Notion과 제작 원본에 보존하되 수업 예시에 중복 배포하지 않는다.
            body = re.sub(r'<toggle>\s*기존 작성 내용[\s\S]*?</toggle>', '', body)
            (lab / '예시' / example.name).write_text(body.rstrip()+'\n', encoding='utf-8', newline='\n')
        (lab / '채울_화면.md').write_text(capture, encoding='utf-8', newline='\n')
        links = '<nav><a href="학습노트_입력틀.md">입력 문구</a> · <a href="참고_교재_발췌.md">교재 발췌</a> · <a href="채울_화면.md">구간별 영상 시각</a> · <a href="예상시간.md">실측 시간</a> · <a href="행동목록.json">준비 원고의 안내·행동 목록</a></nav>'
        links += '<nav>카드 그림: ' + ' · '.join('<a href="이미지/' + f.name + '">' + f.stem + '</a>' for f in sorted((lab / '이미지').glob('*.png'))) + '</nav>'
        links += '<nav>본문 예시: ' + ' · '.join('<a href="예시/' + f.name + '">' + f.stem.replace('_', ' ') + '</a>' for f in sorted((lab / '예시').glob('*.md'))) + '</nav>'
        steps = ''
        for s in order:
            steps += f'<h2>{number[s]}. {html.escape(titles[s])} <small>{mmss(span[s][0])}</small></h2><table><tbody>'
            for r in rows:
                if r['scene'] != s:
                    continue
                act = ''
                if r['action']:
                    act = r['action'][0][:-2] + (' · 입력: ' + ' / '.join(html.escape(str(x)) for x in r['inputs']) if r['inputs'] else '')
                steps += f'<tr><td>{html.escape(r["text"])}</td><td>{act or "—"}</td></tr>'
            steps += '</tbody></table>'
        guide = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>학습노트 — Notion 주제 갤러리</title>'
                 '<style>body{font:17px/1.8 "Malgun Gothic",sans-serif;max-width:1120px;margin:36px auto;padding:0 24px;color:#22303e}h1{font-size:30px}h2{font-size:23px;margin-top:36px}h2 small{color:#64748b;font-size:15px;font-weight:normal}'
                 'table{width:100%;border-collapse:collapse;table-layout:fixed;margin:12px 0}td{border:1px solid #cbd5e1;padding:9px;vertical-align:top;overflow-wrap:anywhere}td:last-child{width:26%;color:#475569;font-size:15px}nav{padding:14px;background:#edf6f3;margin:6px 0}a{color:#245a86}</style></head><body>'
                 f'<h1>{course} 1회차 실습 1 — Notion 주제 갤러리 만들기</h1><p>배운 내용을 주제 카드로 쌓아 두는 학습노트를 Notion에서 직접 만듭니다. 글 정리 · 하위 페이지 · 링크 · 갤러리 · 템플릿을 거쳐 공유 · 게시 · 내보내기 위치까지 봅니다. 왼쪽은 영상에서 강사가 하는 말, 오른쪽은 그때 하는 조작의 영상 시각과 입력값입니다(영상 {mmss(total)}).</p>'
                 + links + steps + '</body></html>\n')
        (lab / '가이드.html').write_text(guide, encoding='utf-8', newline='\n')
        when = (2026, 10, 23, 0, 0, 0)
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in sorted(lab.rglob('*')):
                if f.is_file():
                    info = zipfile.ZipInfo(prefix + f.relative_to(lab).as_posix(), when)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    z.writestr(info, f.read_bytes())
            info = zipfile.ZipInfo(script_entry, when)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, script_path.read_bytes())
        with zipfile.ZipFile(archive) as z:
            expected = {prefix + f.relative_to(lab).as_posix(): f.read_bytes() for f in lab.rglob('*') if f.is_file()}
            expected[script_entry] = script_path.read_bytes()
            assert set(z.namelist()) == set(expected)
            assert all(z.read(n) == b for n, b in expected.items())
        for target in re.findall(r'href="([^"]+)"', guide):
            assert (lab / target).is_file(), target
        assert guide.count('<h2>') == len(order)
        cfg_path = ROOT / '제작용/구성' / course / '01회차/구성.json'
        cfg = json.loads(cfg_path.read_text(encoding='utf-8-sig'))
        for unit in cfg['units']:
            if unit['file'].endswith('02_실습_학습노트.md'):
                unit['status'] = f'{CONFIRMED} 촬영판 실제 발화 동기화 · 영상 {mmss(total)} · 큐 {len(rows)}개 · 사용자 재생 확정'
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
        manifest['courses'].append({'course': course, 'zip_prefix': prefix, 'zip_files': len(expected), 'script_sha256': hashlib.sha256(script_path.read_bytes()).hexdigest(), 'zip_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'zip_bytes_match': True, 'local_links_exist': True})
    (HERE / '정적검사.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
