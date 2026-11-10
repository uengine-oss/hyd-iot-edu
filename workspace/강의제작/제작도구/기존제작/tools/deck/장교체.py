"""언제: 확정 PPTX에서 사용자가 승인한 장의 화면(문구 · 배치 · 아이콘)을 새로 짰을 때(덱 길 5 「확정 덱의 화면」).
그 장만 덱 MD로 새로 빌드한 PPTX에서 장의 도형 트리와 그림을 가져와 확정 PPTX의 같은 번호 장에 바꿔 끼운다.
다른 장, 장 순서, 노트는 건드리지 않는다(노트는 이 뒤에 노트주입.py로 넣는다).

    <py> 장교체.py <확정.pptx> <새 빌드.pptx> --장 2,5,6 [--검사]

- 두 PPTX의 장 수가 같아야 하고, 그 장의 레이아웃 이름이 같아야 한다. 다르면 장 번호와 까닭을 대며 멈춘다.
- 그림은 새 빌드의 바이트를 확정 PPTX에 넣고 관계를 새로 건다. 그 장에서 더는 쓰지 않는 그림 관계는 지운다.
- --검사: 바꾼 뒤 그 장의 글이 새 빌드와 같은지 견주고, 다른 장의 글이 바뀌지 않았는지 본다. 하나라도 어긋나면 종료 코드 1.
"""
import argparse
import copy
import io
import sys

from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT

R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def texts(slide):
    return [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]


def swap(dst_slide, src_slide):
    if dst_slide.slide_layout.name != src_slide.slide_layout.name:
        raise SystemExit(f"레이아웃이 다르다: {dst_slide.slide_layout.name} ≠ {src_slide.slide_layout.name}")
    dtree, stree = dst_slide.shapes._spTree, src_slide.shapes._spTree
    keep = {"nvGrpSpPr", "grpSpPr"}
    for el in list(dtree):
        if el.tag.split("}")[1] not in keep:
            dtree.remove(el)
    for el in stree:
        if el.tag.split("}")[1] in keep:
            continue
        new = copy.deepcopy(el)
        for node in new.iter():
            for attr in (f"{{{R}}}embed", f"{{{R}}}link"):
                rid = node.get(attr)
                if not rid:
                    continue
                part = src_slide.part.related_part(rid)
                _, new_rid = dst_slide.part.get_or_add_image_part(io.BytesIO(part.blob))
                node.set(attr, new_rid)
        dtree.append(new)
    used = set()
    for node in dtree.iter():
        for attr in (f"{{{R}}}embed", f"{{{R}}}link"):
            if node.get(attr):
                used.add(node.get(attr))
    for rid, rel in list(dst_slide.part.rels.items()):
        if rel.reltype == RT.IMAGE and rid not in used:
            dst_slide.part.drop_rel(rid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dst")
    ap.add_argument("src")
    ap.add_argument("--장", required=True)
    ap.add_argument("--검사", action="store_true")
    a = ap.parse_args()
    nums = [int(x) for x in a.장.split(",")]
    dst, src = Presentation(a.dst), Presentation(a.src)
    if len(dst.slides) != len(src.slides):
        sys.exit(f"장 수가 다르다: 확정 {len(dst.slides)} · 새 빌드 {len(src.slides)}")
    before = [texts(s) for s in dst.slides]
    for n in nums:
        swap(dst.slides[n - 1], src.slides[n - 1])
    dst.save(a.dst)
    print(f"바꿈: {', '.join(map(str, nums))}장")
    if a.검사:
        after = Presentation(a.dst)
        bad = []
        for i, s in enumerate(after.slides, 1):
            want = texts(src.slides[i - 1]) if i in nums else before[i - 1]
            if texts(s) != want:
                bad.append(i)
        if bad:
            sys.exit(f"[실패] 글이 기대와 다른 장: {bad}")
        print(f"[통과] 바꾼 장 {len(nums)}개는 새 빌드와 같고, 나머지 {len(after.slides) - len(nums)}장은 그대로다")


if __name__ == "__main__":
    main()
