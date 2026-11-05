"""현장 8회차 원고를 조립하고 온라인 9회차 원본 화면과 현장 발표자 노트를 보존한다.

사용법: python 재생성.py <새 PPTX 경로>
환경과 글꼴은 프로젝트 CLAUDE.md의 덱 제작 환경을 따른다.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import posixpath
from shutil import copyfile, copyfileobj
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from lxml import etree as ET

FOLDER = Path(__file__).resolve().parent
DECKS = FOLDER.parents[1]
ROOT = DECKS.parents[4]
BUILDER = ROOT / ".claude/skills/hyd-course-deck/scripts/deck2pptx.py"
ONLINE = ROOT / "workspace/강의제작/산출물/통합반/이론/09회차/통합반_09일차.pptx"
# 원본 경로의 마지막 커밋 9d5fa180. 원본 개정 시 화면·장 대응을 재검토한다.
SOURCE_SHA256 = "fa687ee9c9df4c52f210e6623552fc41e11ea90cdf3e0e49f1dd9ee558a93c66"
NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def relationships(part):
    return posixpath.join(posixpath.dirname(part), "_rels", posixpath.basename(part) + ".rels")


def read_xml(package, part):
    return ET.fromstring(package.read(part))


def encode_xml(element):
    return ET.tostring(element, encoding="UTF-8", xml_declaration=True, standalone=True)


def target_part(part, target):
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(part), target))


def slide_parts(package):
    presentation = "ppt/presentation.xml"
    by_id = {r.get("Id"): target_part(presentation, r.get("Target"))
             for r in read_xml(package, relationships(presentation))}
    items = read_xml(package, presentation).find("p:sldIdLst", NS)
    return [by_id[item.get(f"{{{NS['r']}}}id")] for item in items]


def restore_screens(draft, entries, result):
    with ZipFile(ONLINE) as source, ZipFile(draft) as destination, ZipFile(result, "w") as output:
        originals, targets = slide_parts(source), slide_parts(destination)
        if len(targets) != len(entries):
            raise ValueError("조립된 장 수와 구성.json의 장 수가 다릅니다.")
        existing_images = {sha256(destination.read(name)).hexdigest(): name
                           for name in destination.namelist() if name.startswith("ppt/media/")}
        replacements = {}
        for page, (entry, target) in enumerate(zip(entries, targets), 1):
            if "new" in entry:
                continue
            number = entry["n"]
            if entry["src"] != "integrated/day09" or not 1 <= number <= len(originals):
                raise ValueError(f"현장 {page}장의 온라인 출처를 확인하세요.")
            origin = originals[number - 1]
            screen = read_xml(source, origin)
            # 하단 번호만 현장 순서로 바꾼다. 표와 그림 안의 수치는 그대로 둔다.
            for shape in screen.findall(".//p:sp", NS):
                runs = shape.findall(".//a:t", NS)
                offset = shape.find("p:spPr/a:xfrm/a:off", NS)
                if (len(runs) == 1 and runs[0].text == str(number) and offset is not None
                        and int(offset.get("y")) > 6000000):
                    runs[0].text = str(page)
            links = read_xml(source, relationships(origin))
            local_links = {r.get("Type").rsplit("/", 1)[1]: r.get("Target")
                           for r in read_xml(destination, relationships(target))}
            for link in links:
                kind = link.get("Type").rsplit("/", 1)[1]
                if kind in ("slideLayout", "notesSlide"):
                    link.set("Target", local_links[kind])
                elif kind == "image" and not link.get("TargetMode"):
                    part = target_part(origin, link.get("Target"))
                    data = source.read(part)
                    digest = sha256(data).hexdigest()
                    if digest not in existing_images:
                        image = f"ppt/media/off08_{digest}{Path(part).suffix}"
                        existing_images[digest] = image
                        replacements[image] = data
                    link.set("Target", posixpath.relpath(existing_images[digest], posixpath.dirname(target)))
                else:
                    raise ValueError(f"현장 {page}장의 지원하지 않는 화면 관계: {kind}")
            replacements[target] = encode_xml(screen)
            replacements[relationships(target)] = encode_xml(links)
        for member in destination.infolist():
            data = replacements.pop(member.filename, None)
            output.writestr(member, destination.read(member) if data is None else data)
        for part, data in replacements.items():
            output.writestr(ZipInfo(part), data, compress_type=ZIP_DEFLATED)


def run(script, *args):
    subprocess.run([sys.executable, str(script), *map(str, args)], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path, help="기존 파일이 없는 .pptx 경로")
    target = parser.parse_args().output.resolve()
    if target.exists() or target.suffix.lower() != ".pptx":
        parser.error("새 .pptx 파일 경로를 지정하세요.")
    if sha256(ONLINE.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError(f"온라인 9회차 원본 판이 달라졌습니다: {ONLINE}")
    spec = json.loads((FOLDER / "구성.json").read_text("utf-8"))
    # 조립기는 입력 폴더에 MD를 쓰므로, 그림 상대경로가 같은 깊이의 임시 폴더에서 실행한다.
    with TemporaryDirectory(dir=FOLDER.parent, prefix=".off08-") as work:
        work = Path(work)
        for name in ("구성.json", "새장.md"):
            copyfile(FOLDER / name, work / name)
        run(DECKS / "조립.py", work)
        md, draft, result = work / spec["md"], work / "draft.pptx", work / "result.pptx"
        run(BUILDER, md, draft)
        restore_screens(draft, spec["slides"], result)
        run(DECKS / "대조.py", md, result)
        run(DECKS / "노트점검.py", md, result)
        target.parent.mkdir(parents=True, exist_ok=True)
        with result.open("rb") as src, target.open("xb") as dst:
            copyfileobj(src, dst)
    print(target)


if __name__ == "__main__":
    main()
