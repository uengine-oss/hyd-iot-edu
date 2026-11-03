"""오프라인1 검수 안내에서 실제로 연결한 제공물만 묶는다. 배포 정본 변경 없음.

python build_guide_bundle.py --draft 작업/<작업>/오프라인1_제공물검수
기존 ZIP의 산출물/ 루트 경로를 유지하고 다음 회차와 시작 도구는 넣지 않는다.
"""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import argparse
import hashlib
import json
import posixpath
import re
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREFIX = Path('workspace/강의제작')
COURSES = ('통합반', '실전반')
PRODUCTION_FILES = {'예상시간.md', '채울_화면.md', '행동목록.json'}

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
    def handle_starttag(self, tag, attrs):
        self.urls.extend(v for k, v in attrs if k in ('src', 'href') and v)

def local_links(content):
    parser = Links()
    parser.feed(content)
    return [unquote(urlsplit(u).path) for u in parser.urls if not urlsplit(u).scheme and urlsplit(u).path]

def student_html(content):
    """원본은 보존하고 학생 출력에서만 제작자료 링크를 제거한다."""
    removed = []
    def anchor(match):
        tag = match.group(0)
        href = re.search(r'href=["\']([^"\']+)["\']', tag)
        if href:
            url = urlsplit(href[1])
            if not url.scheme and Path(unquote(url.path)).name in PRODUCTION_FILES:
                removed.append(href[1])
                return ''
        return tag
    text = re.sub(r'<a\b[^>]*>.*?</a>', anchor, content, flags=re.S)
    # 링크 사이 구분자만 정리하고 본문과 정상 링크는 그대로 둔다.
    def navigation(match):
        body = re.sub(r'(?:\s*·\s*){2,}', ' · ', match[1])
        body = re.sub(r'^\s*·\s*|\s*·\s*$', '', body)
        return '<nav>' + body + '</nav>'
    text = re.sub(r'<nav>(.*?)</nav>', navigation, text, flags=re.S)
    return text, removed


def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft', required=True, type=Path)
    args = parser.parse_args()
    draft = args.draft.resolve()
    if not draft.is_relative_to((ROOT/'작업').resolve()):
        parser.error('검수 묶음은 저장소 작업 폴더에만 둡니다.')
    status = json.loads((draft/'검수상태.json').read_text(encoding='utf-8'))
    previous_path = draft/'묶음검사.json'
    previous = json.loads(previous_path.read_text(encoding='utf-8')) if previous_path.exists() else []
    old_owned = {PREFIX/e['path']: e['sha256'] for item in previous for e in item['entries'] if e['path'] != '가이드열기.html'}
    results = []
    for course in COURSES:
        base = PREFIX / f'산출물/{course}/실습/01회차'
        entry = base / '오프라인_가이드.html'
        queue, files, origins = [entry], {}, []
        while queue:
            relative = queue.pop()
            if relative in files:
                continue
            if not relative.is_relative_to(base) or relative.name.startswith('.env'):
                raise ValueError(f'1회차 연결 범위 밖: {relative}')
            staged = draft/relative
            # 회차 진입 HTML만 명시적 검수 원고이며 의존 파일은 매번 최신 정본을 읽는다.
            source = staged if relative == entry else ROOT/relative
            if not source.is_file():
                raise FileNotFoundError(f'가이드 연결 파일 없음: {relative}')
            if relative.name in PRODUCTION_FILES:
                raise ValueError(f'학생 묶음에 제작자료 참조가 남음: {relative}')
            original = source.read_bytes()
            content, removed = original, []
            if relative.suffix.lower() == '.html':
                filtered, removed = student_html(original.decode('utf-8-sig'))
                if removed:
                    content = filtered.encode('utf-8')
            origins.append({'path': relative.as_posix(), 'source': str(source.relative_to(ROOT)), 'source_sha256': digest(original), 'output_sha256': digest(content), 'removed_links': removed, 'source_role': 'draft_entry' if relative == entry else 'production_dependency'})
            files[relative] = content
            if relative.suffix.lower() == '.html':
                for link in local_links(content.decode('utf-8-sig')):
                    target = Path(posixpath.normpath(posixpath.join(relative.parent.as_posix(), link)))
                    queue.append(target)
            if source != staged:
                staged.parent.mkdir(parents=True, exist_ok=True)
                staged.write_bytes(content)
        removed_staged = []
        for relative, old_sha in old_owned.items():
            if relative.is_relative_to(base) and relative not in files:
                stale = (draft/relative).resolve()
                if not stale.is_relative_to(draft):
                    raise ValueError(f'검수 폴더 밖 경로: {relative}')
                if stale.is_file():
                    if digest(stale.read_bytes()) != old_sha:
                        raise ValueError(f'사용자가 바꾼 검수 파일은 보존합니다: {relative}')
                    stale.unlink()
                    removed_staged.append(relative.as_posix())
        target = draft/base/'오프라인1_가이드.zip'
        zip_entry = entry.relative_to(PREFIX).as_posix()
        opener = f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={zip_entry}"><a href="{zip_entry}">오프라인1 가이드 열기</a>'.encode('utf-8')
        expected = {path.relative_to(PREFIX).as_posix(): data for path, data in files.items()}
        expected['가이드열기.html'] = opener
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, data in sorted(expected.items()):
                item = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                item.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(item, data)
        with zipfile.ZipFile(target) as z:
            if set(z.namelist()) != set(expected):
                raise ValueError('ZIP 경로 집합 불일치')
            for name, data in expected.items():
                if z.read(name) != data:
                    raise ValueError(f'ZIP 바이트 불일치: {name}')
                if name.endswith('.html'):
                    for link in local_links(data.decode('utf-8-sig')):
                        destination = posixpath.normpath(posixpath.join(posixpath.dirname(name), link))
                        if destination not in expected:
                            raise ValueError(f'ZIP 내부 링크 없음: {name} -> {link}')
        results.append({'course': course, 'path': str(target.relative_to(ROOT)), 'sha256': digest(target.read_bytes()),
            'status': '검수용·배포 미적용', 'origins': origins, 'removed_staged_files': removed_staged, 'entries': [{'path': n, 'sha256': digest(d)} for n,d in sorted(expected.items())],
            'path_set_equal': True, 'bytes_equal': True, 'local_links_valid': True,
            'pending': status['pending'], 'note': 'Notion 가이드와 사진은 현재 정본에서 연결한다. 04/06 현행화·현장 대안·받기 시험은 검수상태의 보류 목록을 따르며 이 묶음은 배포하지 않는다.'})
    (draft/'묶음검사.json').write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('두 과정 검수 ZIP의 경로·바이트·내부 링크 일치. 미확인 실습이 있어 배포하지 않음.')

if __name__ == '__main__':
    main()
