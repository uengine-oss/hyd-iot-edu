"""언제: 확정 PPTX에서 장 수를 줄일 때(덱 길 5) — 그 번호의 장만 빼고 다른 장은 그대로 둔다. 그 뒤 장교체.py로 바뀐 장을 끼우고 쪽번호맞춤.py를 돌린다.
명령: <py> workspace/강의제작/제작도구/검사/장빼기.py <덱.pptx> <번호 …>
"""
import sys
from pptx import Presentation
p, nums = sys.argv[1], sorted({int(x) for x in sys.argv[2:]}, reverse=True)
prs = Presentation(p); lst = prs.slides._sldIdLst; ids = list(lst)
for n in nums:
    sid = ids[n - 1]; prs.part.drop_rel(sid.rId); lst.remove(sid)
prs.save(p); print(f"뺌: {sorted(nums)} → {len(prs.slides)}장")
