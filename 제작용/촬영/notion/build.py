"""Notion 촬영 준비 원고를 두 과정 정본·HTML·ZIP에 반영한다. 앱/학생 코드는 실행하지 않는다."""
from pathlib import Path
import html
import json
import re
import zipfile
import hashlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = HERE / '수업원고.md'

def render(text):
    out = []
    for block in text.strip().split('\n\n'):
        if block.startswith('# '):
            out.append('<h1>' + html.escape(block[2:]) + '</h1>')
        elif block.startswith('## '):
            out.append('<h2>' + html.escape(block[3:]) + '</h2>')
        elif block.startswith('> '):
            out.append('<aside>' + html.escape(block[2:]) + '</aside>')
        else:
            out.append('<p>' + html.escape(block) + '</p>')
    return '\n'.join(out)

def main():
    source = SOURCE.read_text(encoding='utf-8')
    scenes = re.findall(r'^## (N\d+) · (.+)$', source, re.M)
    assert len(scenes) >= 25
    manifest = {'source': str(SOURCE.relative_to(ROOT)), 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(), 'scenes': len(scenes), 'courses': []}
    for course in ['통합반', '실전반']:
        base = ROOT / '산출물' / course / '실습/01회차'
        script = base / '대본/02_실습_학습노트.md'
        lab = base / '랩/01일차_실습1_학습노트'
        archive = lab.with_suffix('.zip')
        old_names = zipfile.ZipFile(archive).namelist()
        file_names = [n for n in old_names if not n.endswith('/')]
        prefix = '01회차/랩/' + lab.name + '/'
        script_entry = '01회차/대본/' + script.name
        assert set(file_names) == {prefix + f.name for f in lab.iterdir() if f.is_file()} | {script_entry}, '기존 ZIP 구조가 예상과 다릅니다'
        text = source.replace('{{과정}}', course)
        script.write_text(text, encoding='utf-8')
        (lab / '학습노트_입력틀.md').write_text(INPUTS, encoding='utf-8')
        capture = '# 학습노트 — 화면별 촬영 자리\n\n현재 촬영 준비판의 전체 장면 사진은 미촬영이다. 기존 2:48 샘플을 전체 장면 사진으로 대체하지 않는다. 아래 각 단계에서 메뉴 선택 전·입력 중·확인 후를 같은 판본으로 추출하고 작업 대상에 하이라이트를 붙인다.\n\n'
        for sid, title in scenes:
            capture += f'## {sid} · {title}\n\n- 상태: 미촬영\n- 예정 파일: `화면/{sid}-01.png` (필요한 중간 장면은 02, 03 추가)\n- 대상·확인 기준: 가이드의 {sid} 조작·확인 문단. 포인터/하이라이트는 메뉴명·입력값을 가리지 않는다.\n\n'
        (lab / '채울_화면.md').write_text(capture.rstrip()+'\n', encoding='utf-8')
        links = '<nav><a href="학습노트_입력틀.md">입력 문구</a> · <a href="참고_교재_발췌.md">교재 발췌</a> · <a href="채울_화면.md">사진 자리</a></nav>'
        guide = '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>학습노트 촬영 준비</title><style>body{font:18px/1.8 "Malgun Gothic",sans-serif;max-width:1000px;margin:40px auto;padding:0 24px;color:#23303e}h1{font-size:30px}h2{font-size:25px;margin-top:42px}aside{background:#eef2f6;border-left:4px solid #52748a;padding:15px;white-space:pre-wrap}p{white-space:pre-wrap}nav{padding:16px;background:#edf6f3}a{color:#245a86}</style></head><body><p>온라인 제작 참고 · 촬영 준비판 · 전체 실행·사진 미촬영</p>' + links + render(text) + '</body></html>\n'
        (lab / '가이드.html').write_text(guide, encoding='utf-8')
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in sorted(lab.rglob('*')):
                if f.is_file():
                    info = zipfile.ZipInfo(prefix + f.relative_to(lab).as_posix(), (2026, 10, 22, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    z.writestr(info, f.read_bytes())
            info = zipfile.ZipInfo(script_entry, (2026, 10, 22, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, script.read_bytes())
        with zipfile.ZipFile(archive) as z:
            expected = {prefix + f.relative_to(lab).as_posix(): f.read_bytes() for f in lab.rglob('*') if f.is_file()}
            expected[script_entry] = script.read_bytes()
            assert set(z.namelist()) == set(expected)
            assert all(z.read(n) == b for n, b in expected.items())
        for target in re.findall(r'href="([^"]+)"', guide):
            assert (lab / target).is_file(), target
        assert guide.count('<h2>') == len(scenes)
        cfg_path = ROOT / '제작용/구성' / course / '01회차/구성.json'
        cfg = json.loads(cfg_path.read_text(encoding='utf-8-sig'))
        for unit in cfg['units']:
            if unit['file'].endswith('02_실습_학습노트.md'):
                unit['status'] = '2026-10-22 기존 완성본 보강·주제 갤러리 촬영 준비판 동기화 · 전체 리허설·촬영 미수행'
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        manifest['courses'].append({'course': course, 'zip_prefix': prefix, 'zip_files': len(expected), 'script_sha256': hashlib.sha256(script.read_bytes()).hexdigest(), 'zip_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'zip_bytes_match': True, 'local_links_exist': True})
    (HERE / '정적검사.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))

INPUTS = '''# 주제 갤러리 입력 자료

두 과정 공통. 주제별 자유 구성 예시이며 필수 작성 양식이 아니다.

- 홈: 내 학습 노트 / 주제 모음.
- 안내: 관심 있는 주제를 모으고, 배운 내용을 나만의 방식으로 쌓아 갑니다.
- 주제 카드: Notion 익히기 / 지식 자산화. 기존 이상 감지·에이전트 기초는 보존하며 이번 수업에서 배운 척하지 않는다.
- Notion 익히기 하위 페이지: 첫 페이지 꾸미기 / 페이지 연결하기. 좌우 단·설명·페이지 멘션으로 연결한다.
- 첫 페이지 꾸미기: 오늘 써 본 방법, 제목/목록/토글, 다음에 해 볼 것 체크리스트, 목차.
- 페이지 연결하기: 하위 페이지 만드는 번호 목록, Notion 글쓰기 도움말 링크.
- 지식 자산화 하위 페이지: 1회차 교재 · 지식 자산화. 기존 참고_교재_발췌.md 첨부.
- 기본 보기: 주제 카드(페이지 커버 미리보기), 전체 주제(표). 별도 자료함·실수노트·복습달력은 만들지 않는다.
- 주제 시작 템플릿: 새 주제. 같은 분위기의 표지·아이콘·짧은 안내·자유 메모/페이지자리. 항목 이름은 바꾸거나 지워도 된다.
- https://www.notion.com/help/writing-and-editing-basics
- 긴 URL은 붙여넣고 짧은 문장은 직접 입력한다. 표지/아이콘 선택도 원고의 해당 동작과 함께 설명한다.
'''

if __name__ == '__main__':
    main()
