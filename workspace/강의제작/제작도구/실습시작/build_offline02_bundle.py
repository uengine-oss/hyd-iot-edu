"""두 과정 오프라인 2회차 그래프 수업의 학생 파일과 가이드를 작업 폴더에 묶는다."""
import argparse
import hashlib
import json
import posixpath
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from build_guide_bundle import COURSES, HERE, ROOT, local_links


def build(course, destination):
    course_dir = ROOT / "workspace/강의제작/산출물" / course / "실습/02회차"
    source = HERE / "offline02" / course / "오프라인_그래프실습.html"
    files = {"가이드열기.html": source.read_bytes(), "launcher.py": (HERE / "launcher.py").read_bytes()}
    inputs = []
    entries = {1: ("관계조회열기.cmd", "open_neo4j"), 3: ("설계실습열기.cmd", "open_lab"),
               4: ("구현실습열기.cmd", "open_lab")}
    for number in range(1, 5):
        matches = list((course_dir / "랩").glob(f"02일차_실습{number}_*.zip"))
        if len(matches) != 1:
            raise ValueError(f"{course} 실습 {number} 시작본 {len(matches)}개")
        package = matches[0]
        if number in entries:
            # 온라인 시작 도구와 같은 열기 함수를 이미 압축 해제된 실습 폴더에 적용한다.
            filename, action = entries[number]
            command = (
                '@echo off\r\nchcp 65001 >nul\r\ncd /d "%~dp0"\r\n'
                f'python -X utf8 -c "from pathlib import Path; import sys; from launcher import {action}; '
                f'print({action}(Path(sys.argv[1]).resolve()) or \'\')" '
                f'"02회차\\랩\\{package.stem}"\r\nif errorlevel 1 pause\r\n'
            )
            files[filename] = command.encode("utf-8")
        inputs.append({"file": package.name, "sha256": hashlib.sha256(package.read_bytes()).hexdigest()})
        prefix = f"02회차/랩/{package.stem}/"
        with zipfile.ZipFile(package) as archive:
            for name in archive.namelist():
                if not name.startswith(prefix) or ".." in PurePosixPath(name).parts or "\\" in name or name in files:
                    raise ValueError(f"시작본 경로 오류: {name}")
                files[name] = archive.read(name)
    count = 0
    for name, data in files.items():
        if name.endswith(".html"):
            for url in local_links(data.decode("utf-8-sig")):
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), url))
                if target not in files:
                    raise ValueError(f"{name}에서 열 수 없는 파일: {url}")
                count += 1
    directory = destination / course
    directory.mkdir(parents=True, exist_ok=True)
    result = directory / "오프라인2_그래프실습_검수.zip"
    with tempfile.TemporaryDirectory(dir=directory) as temp:
        tmp = Path(temp) / result.name
        with zipfile.ZipFile(tmp, "w") as archive:
            for name, data in sorted(files.items()):
                archive.writestr(zipfile.ZipInfo(name), data, compress_type=zipfile.ZIP_DEFLATED)
        with zipfile.ZipFile(tmp) as archive:
            if len(archive.namelist()) != len(files) or any(archive.read(n) != v for n, v in files.items()):
                raise ValueError(f"{course} ZIP 검증 실패")
        tmp.replace(result)
    return dict(course=course, entries=len(files), local_links=count,
                zip_sha256=hashlib.sha256(result.read_bytes()).hexdigest(), input_archives=inputs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", type=Path, required=True)
    path = parser.parse_args().draft.resolve()
    if (ROOT / "작업").resolve() not in path.parents:
        parser.error("검수 출력은 작업 폴더 아래에 지정하세요.")
    rows = [build(c, path) for c in COURSES]
    (path / "그래프실습_묶음검사.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
