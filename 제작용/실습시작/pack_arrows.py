"""기존 ARROWS 영상/JSON 보존, 변경된 단계 가이드와 실제 캡처를 ZIP에 동기화."""
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[2]
for course in ['통합반','실전반']:
    folder=ROOT/'산출물'/course/'실습/01회차/랩/01일차_실습4_관계그림'
    with zipfile.ZipFile(folder.with_suffix('.zip'),'w',zipfile.ZIP_DEFLATED) as z:
        for file in sorted(folder.rglob('*')):
            if file.is_file():z.write(file,Path('01회차/랩')/folder.name/file.relative_to(folder))
print('ARROWS 가이드·실제 단계 캡처 ZIP 2개 동기화')
