"""Notion 실습을 실제 촬영판(사용자 확정 영상)의 발화 · 조작 시각으로 두 과정 대본 · 가이드 · 시간 · ZIP에 반영한다.
장면 제목 · 준비 문단 · 입력값은 준비 원고(수업원고.md · 행동목록.json)에서, 말한 문장과 시각은 영상 verification.json과 음성 캐시에서 온다.
앱/학생 코드는 실행하지 않는다. 학생 가이드는 build_student_guide.py의 검수 출력으로만 반영한다.
사용: python build.py --student-draft <검수출력> --student-backup <작업폴더/새백업>"""
from pathlib import Path
import html
import json
import re
import sys
import zipfile
import hashlib
import shutil
import argparse
from apply_student_guide import preflight, preflight_targets, apply_course

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--student-draft", type=Path, required=True)
    parser.add_argument("--student-backup", type=Path, required=True)
    args = parser.parse_args()
    preflight(args.student_draft)
    assert args.student_backup.resolve().is_relative_to((ROOT / "작업").resolve())
    assert all(not (args.student_backup / course).exists() for course in ["통합반", "실전반"]), "기존 학생가이드 백업을 덮지 않습니다"
    preflight_targets(args.student_backup)
    for course in ("통합반", "실전반"):
        cfg = json.loads((ROOT / "workspace/강의제작/제작도구/구성" / course / "01회차/구성.json").read_text(encoding="utf-8-sig"))
        assert any(u["file"].endswith("02_실습_학습노트.md") for u in cfg["units"]), "실습 구성 단위 누락"
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
              f'> 시간: 실측 {mmss(total)}(말 {mmss(spoken)}, 큐 {len(rows)}개). 구간별 길이는 [예상시간](../../../../../제작도구/촬영/notion/예상시간.md).', '']
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

    manifest = {'source_video': VIDEO.relative_to(ROOT).as_posix(), 'video_seconds': total, 'cues': len(rows), 'sections': len(order),
                'titles_from': str(SOURCE.relative_to(ROOT).as_posix()), 'courses': []}
    for course in ['통합반', '실전반']:
        base = ROOT / 'workspace/강의제작/산출물' / course / '실습/01회차'
        script_path = base / '대본/02_실습_학습노트.md'
        lab = base / '랩/01일차_실습1_학습노트'
        archive = lab.with_suffix('.zip')
        text = script.replace('{{과정}}', course)
        script_path.write_text(text, encoding='utf-8', newline='\n')
        course_result = apply_course(args.student_draft, args.student_backup, course)
        cfg_path = ROOT / 'workspace/강의제작/제작도구/구성' / course / '01회차/구성.json'
        cfg = json.loads(cfg_path.read_text(encoding='utf-8-sig'))
        for unit in cfg['units']:
            if unit['file'].endswith('02_실습_학습노트.md'):
                unit['status'] = f'{CONFIRMED} 촬영판 실제 발화 동기화 · 영상 {mmss(total)} · 큐 {len(rows)}개 · 사용자 재생 확정'
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
        manifest['courses'].append({**course_result, 'script_sha256': hashlib.sha256(script_path.read_bytes()).hexdigest()})
    (HERE / '정적검사.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
