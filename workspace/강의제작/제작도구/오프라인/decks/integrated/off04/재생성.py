"""통합반 현장 4회차를 조립하고 온라인 원본의 재사용 화면 및 강사 노트를 검증한다."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

FOLDER = Path(__file__).resolve().parent
DECKS = FOLDER.parents[1]
ROOT = DECKS.parents[4]
W = ROOT / "workspace/강의제작"
BUILDER = ROOT / ".claude/skills/hyd-course-deck/scripts/deck2pptx.py"


def icons(slide):
    result = {}
    for sh in slide.shapes:
        if sh.shape_type != MSO_SHAPE_TYPE.PICTURE or not sh.name.startswith("아이콘:"):
            continue
        key = (sh.name, sh.left, sh.top, sh.width, sh.height, sh.rotation,
               sh.crop_left, sh.crop_top, sh.crop_right, sh.crop_bottom)
        if key in result:
            raise ValueError(f"이름과 배치가 같은 아이콘이 두 개임: {key}")
        result[key] = sh
    return result


def text_key(shape):
    return (shape.name, shape.text, shape.left, shape.top, shape.width, shape.height, shape.rotation)


def run(*args):
    subprocess.run([sys.executable, *map(str, args)], cwd=ROOT, check=True)


def main():
    spec = json.loads((FOLDER / "구성.json").read_text(encoding="utf-8"))
    md = FOLDER / spec["md"]
    output = W / "산출물/통합반/이론_오프라인/04회차/통합반_오프라인_04회차.pptx"
    online = Presentation(W / "산출물/통합반/이론/04회차/통합반_04일차.pptx")
    run(DECKS / "조립.py", FOLDER)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as scratch:
        candidate = Path(scratch) / output.name
        run(BUILDER, md, candidate)
        pres = Presentation(candidate)
        if len(pres.slides) != len(spec["slides"]):
            raise ValueError("구성 파일과 생성한 덱의 장 수가 다름")
        copied = 0
        frames = 0
        for n, entry in enumerate(spec["slides"]):
            if "src" not in entry:
                continue
            if entry["src"] != "integrated/day04":
                raise ValueError(f"현장 {n + 1}장 원본 경로 확인 필요: {entry['src']}")
            if not 1 <= entry["n"] <= len(online.slides):
                raise ValueError(f"현장 {n + 1}장 온라인 출처 장 번호가 범위를 벗어남")
            source_slide = online.slides[entry["n"] - 1]
            target_slide = pres.slides[n]
            # 온라인 코드 블록의 숫자·단위 사이 간격도 원판의 글꼴로 재생성한다.
            original_frames = {text_key(sh): sh for sh in source_slide.shapes
                               if sh.has_text_frame and sh.text.strip()}
            for sh in target_slide.shapes:
                if not sh.has_text_frame or not sh.text.strip():
                    continue
                matching = original_frames.get(text_key(sh))
                if matching is None or sh.text_frame._txBody.xml == matching.text_frame._txBody.xml:
                    continue
                body = matching.text_frame._txBody
                if any(qn("r:id") in node.attrib for node in body.iter()):
                    raise ValueError(f"현장 {n + 1}장 글상자의 외부 링크 확인 필요")
                sh._element.replace(sh.text_frame._txBody, deepcopy(body))
                frames += 1
            source = icons(source_slide)
            target = icons(target_slide)
            if source.keys() != target.keys():
                raise ValueError(f"현장 {n + 1}장 아이콘의 이름, 위치 또는 자르기가 원본과 다름")
            for key, original in source.items():
                icon = target[key]
                if icon.image.blob != original.image.blob:
                    _, rid = target_slide.part.get_or_add_image_part(BytesIO(original.image.blob))
                    blip = icon._element.blipFill.blip
                    previous = blip.get(qn("r:embed"))
                    blip.set(qn("r:embed"), rid)
                    if not any(node.get(qn("r:embed")) == previous for node in target_slide._element.iter()):
                        target_slide.part.drop_rel(previous)
                    copied += 1
        if copied or frames:
            sys.path.insert(0, str(BUILDER.parent))
            from deck2pptx import save_stable
            save_stable(pres, candidate)
        print(f"온라인 원본에서 복원한 아이콘 {copied}개 · 같은 글과 배치의 글상자 {frames}개", flush=True)
        run(DECKS / "대조.py", md, candidate, "--fix")
        run(DECKS / "대조.py", md, candidate)
        run(DECKS / "노트점검.py", md, candidate)
        candidate.replace(output)


if __name__ == "__main__":
    main()
