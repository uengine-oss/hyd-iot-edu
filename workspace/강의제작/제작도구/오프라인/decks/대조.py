"""오프라인 덱의 온라인 출처 장이 원 PPTX 화면과 같은 글자인지 대조한다.

python3 workspace/강의제작/제작도구/오프라인/decks/대조.py <오프라인 덱 MD> <오프라인 PPTX> [--fix]

MD의 제작 기준 「[출처] 온라인 <과정> <회차>회차 <장>장」을 읽어, 원 PPTX(workspace/강의제작/산출물/<과정>/이론/NN회차)의
그 장과 새 PPTX의 같은 장에서 도형 글자와 위치 · 크기(노트 · 장 번호 제외)를 모아 비교한다. 다르면 장 번호와 차이를 찍고 실패한다.
확정 PPTX는 원고 밖에서 손본 장이 있다(통합반 1회차 47장의 글상자 위치, 통합반 2회차 24 · 55장의 강제 줄바꿈 등).
--fix는 공백 · 줄바꿈을 뺀 글자가 모두 같은 장에 한해, 원 PPTX 도형의 위치 · 크기와 글자 틀(줄바꿈 포함)을
새 PPTX의 같은 글자 도형에 옮겨 저장한다. 글 없는 도형과 번호 배지(장 번호 아닌 숫자)도 위치 · 크기를 비교하고 옮긴다. 공백을 빼고도 글자가 다르면 고치지 않고 실패한다.
"""
from pathlib import Path
import copy, hashlib, io, re, sys
from PIL import Image
from pptx import Presentation

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / '.claude/skills/hyd-course-deck/scripts'))
from deck2pptx import save_stable  # noqa: E402  같은 원고면 같은 바이트로 저장(빌더와 같은 저장)


def look(blob):
    # 같은 그림을 다시 래스터화하면 가장자리 몇 화소가 달라진다. 32×32 회색조를 64단계로 줄여 모양만 비교한다.
    im = Image.open(io.BytesIO(blob)).convert('LA').resize((32, 32))
    return hashlib.sha1(bytes(v // 64 for v in im.tobytes())).hexdigest()[:12]


def key(t):
    return re.sub(r'\s', '', t)


FOOTER_TOP = 6000000  # 이 아래의 숫자 하나는 장 번호다(EMU). 장 번호는 덱마다 달라 비교하지 않는다.


def is_page_number(sh, t):
    return t.isdigit() and sh.top is not None and sh.top > FOOTER_TOP


def kind(sh):
    return str(sh.shape_type) + ' ' + sh.element.tag.rsplit('}', 1)[-1]


def texts(slide):
    out = []
    for sh in slide.shapes:
        if sh.has_text_frame:
            t = chr(10).join(p.text for p in sh.text_frame.paragraphs).strip()  # 문단 나눔도 비교한다
            if t and not is_page_number(sh, t):
                out.append((t, sh.left, sh.top, sh.width, sh.height))
            elif not t:
                out.append(('도형 ' + kind(sh), sh.left, sh.top, sh.width, sh.height))  # 글 없는 칸 · 띠
        elif sh.shape_type != 13 and not getattr(sh, 'has_table', False):
            out.append(('도형 ' + kind(sh), sh.left, sh.top, sh.width, sh.height))  # 선 · 연결선
        if sh.shape_type == 13:  # 그림
            out.append(('그림 ' + look(sh.image.blob), sh.left, sh.top, sh.width, sh.height))
        if getattr(sh, 'has_table', False) and sh.has_table:
            for row in sh.table.rows:
                out.append((' | '.join(c.text for c in row.cells), 0, 0, 0, 0))
    return sorted(out)


def main():
    md, pptx = Path(sys.argv[1]), Path(sys.argv[2])
    fix = '--fix' in sys.argv
    prs = Presentation(pptx)
    new = prs.slides
    fixed = 0
    cache, bad = {}, 0
    for b in re.split(r'(?=^## SLIDE )', md.read_text('utf8'), flags=re.M)[1:]:
        n = int(re.match(r'## SLIDE (\d+)', b).group(1))
        m = re.search(r'\[출처\] 온라인 (\S+) (\d+)회차 (\d+)장', b)
        if not m:
            continue
        course, day, sn = m.group(1), int(m.group(2)), int(m.group(3))
        src = ROOT / f'workspace/강의제작/산출물/{course}/이론/{day:02d}회차/{course}_{day:02d}일차.pptx'
        if src not in cache:
            cache[src] = Presentation(src).slides
        a, c = texts(cache[src][sn - 1]), texts(new[n - 1])
        ka, kc = sorted(key(x[0]) for x in a), sorted(key(x[0]) for x in c)
        if a != c and fix and ka == kc:
            # 같은 도형끼리(글 · 종류가 같은 것) 나오는 차례대로 짝짓는다. 도형 구성이 다르면 옮기지 않고 아래에서 차이로 실패한다.
            def sign(sh):
                if sh.has_text_frame and sh.text_frame.text.strip():
                    t = sh.text_frame.text.strip()
                    return '장 번호' if is_page_number(sh, t) else key(t)
                return kind(sh)
            os_, ns_ = list(cache[src][sn - 1].shapes), list(new[n - 1].shapes)
            pairs = None
            if sorted(sign(s) for s in os_) == sorted(sign(s) for s in ns_):
                pool = {}
                for o in os_:
                    pool.setdefault(sign(o), []).append(o)
                pairs = [(s, pool[sign(s)].pop(0)) for s in ns_]
            if pairs is not None:
                for sh, o in pairs:
                    if sign(sh) == '장 번호':
                        continue
                    sh.left, sh.top, sh.width, sh.height = o.left, o.top, o.width, o.height
                    if sh.has_text_frame and sh.text_frame.text != o.text_frame.text:
                        old = sh.text_frame._txBody
                        old.getparent().replace(old, copy.deepcopy(o.text_frame._txBody))
                if texts(new[n - 1]) == a:
                    fixed += 1
                    print(f'{n}장 ← {course} {day}회차 {sn}장: 원 PPTX의 위치 · 크기 · 글자 틀을 옮김')
                    continue
                c = texts(new[n - 1])
        if a != c:
            bad += 1
            print(f'{n}장 ← {course} {day}회차 {sn}장: 화면 글자 다름')
            for x in sorted(set(a) - set(c)):
                print('   원:', x[0][:120], x[1:])
            for x in sorted(set(c) - set(a)):
                print('   새:', x[0][:120], x[1:])
    if fixed:
        save_stable(prs, pptx)
    print('대조 결과: 다른 장', bad, '· 위치를 옮긴 장', fixed)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
