"""기존 ARROWS 영상/JSON 보존, 변경된 단계 가이드와 실제 캡처를 ZIP에 동기화."""
from pathlib import Path
from tempfile import NamedTemporaryFile
import zipfile
ROOT=Path(__file__).resolve().parents[4]
for course in ['통합반','실전반']:
    folder=ROOT/'workspace/강의제작/산출물'/course/'실습/01회차/랩/01일차_실습4_관계그림'
    files = {('01회차/랩/' + folder.name + '/' + f.relative_to(folder).as_posix()): f
             for f in sorted(folder.rglob('*')) if f.is_file()}
    if not (folder / '가이드.html').is_file() or any(
        f.name in {'채울_화면.md', '예상시간.md'} for f in files.values()
    ):
        raise ValueError(f'{course} ARROWS 학생 폴더의 가이드와 제작 파일을 확인하세요.')
    with NamedTemporaryFile(dir=folder.parent, suffix='.tmp', delete=False) as tmp:
        candidate = Path(tmp.name)
    try:
        with zipfile.ZipFile(candidate, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, file in files.items():
                archive.write(file, name)
        with zipfile.ZipFile(candidate) as archive:
            if archive.namelist() != list(files) or any(
                archive.read(name) != file.read_bytes() for name, file in files.items()
            ):
                raise ValueError(f'{course} ARROWS ZIP 검증에 실패했습니다.')
        candidate.replace(folder.with_suffix('.zip'))
    finally:
        candidate.unlink(missing_ok=True)
print('ARROWS 가이드·실제 단계 캡처 ZIP 2개 동기화')
