"""언제: 확정 PPTX에서 장을 빼거나 넣은 뒤 — 장마다 오른쪽 아래 장 번호 글자(숫자만 든 글상자)를 실제 순서로 맞춘다(옛 장이 옛 번호를 달고 남는다).
명령: <py> workspace/강의제작/제작도구/검사/쪽번호맞춤.py <덱.pptx>
"""
import sys
from pptx import Presentation
p = sys.argv[1]; prs = Presentation(p); W, H = prs.slide_width, prs.slide_height; fixed = []
for i, s in enumerate(prs.slides, 1):
    cand = [sh for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip().isdigit() and sh.left > W * 0.8 and sh.top > H * 0.85]
    if len(cand) > 1: sys.exit(f"{i}장: 번호 후보 {len(cand)}개")
    if not cand: continue
    tf = cand[0].text_frame; runs = [r for para in tf.paragraphs for r in para.runs]
    if runs[0].text.strip() != str(i):
        fixed.append((i, runs[0].text.strip())); runs[0].text = str(i)
        for r in runs[1:]: r.text = ""
prs.save(p); print("고침:", fixed if fixed else "없음")
