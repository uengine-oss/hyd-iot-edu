# -*- coding: utf-8 -*-
"""docs/마스터_가이드.html · .pdf 생성기 — 시스템 아키텍처 그림 한 장 + 시나리오 이야기 하나(사용자 2026-10-07 "2가지만").
  python master_build.py            → HTML + PDF
  python master_build.py --html     → HTML 만
그림: arch_layers.py(렌더러) + arch_layers_hyd.py(카드 · 화살표). 이야기: guide_story.py. 틀: guide_tpl.html.
빌드 검사: ① compose 서비스 · 볼륨 · 망 · Kafka 토픽이 모두 그림에 이름으로 있다(arch_appendix_hyd 가 저장소에서 직접 뽑음)
           ② 그림의 화살표 1~N 이 모두 이야기에 나온다 ③ 치환 잔여 · 없는 앵커 · 중복 id 가 없다.
이전 판(1부 이야기 + 2부 300쪽 상세)은 .evidence/docs-1007/이전판/(git 제외) 에 있다.
"""
import collections, html, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
DOCS = HERE.parent
OUT_HTML = DOCS / "마스터_가이드.html"
OUT_PDF = DOCS / "마스터_가이드.pdf"
sys.path.insert(0, str(HERE))


def build_html():
    import arch_layers as AL, arch_layers_hyd as LH, arch_appendix_hyd as APX, guide_story as GS
    lsvg, (lw, lh) = AL.svg(LH.LAYERS, LH.CARDS, LH.ARROWS, LH.NCOL)
    # ① 그림이 저장소의 모든 요소를 이름으로 담는가
    _apx, names = APX.build()
    figtxt = " ".join(" ".join([c["title"], c.get("tech", ""), c.get("box", "")] + c.get("lines", [])) for c in LH.CARDS.values()) + " " + " ".join(a[3] + " " + a[4] for a in LH.ARROWS)
    miss = {k: [x for x in names[k] if x not in figtxt] for k in ("services", "volumes", "networks", "kafka")}
    assert not any(miss.values()), f"그림에 없는 요소: { {k: v for k, v in miss.items() if v} }"
    # ② 이야기가 그림의 화살표를 모두 지나가는가
    alltxt = " ".join(GS.INTRO) + " ".join(" ".join(p) for _n, _t, p in GS.CHAPTERS)
    said = {int(x) for x in re.findall(r"\{a:(\d+)\}", alltxt)}
    allno = set(range(1, len(LH.ARROWS) + 1))
    assert said == allno, f"이야기에 없는 화살표: {sorted(allno - said)} · 없는 번호: {sorted(said - allno)}"
    ab = lambda t: re.sub(r'href="#la\d+"', 'href="#arch"', AL.abadges(t, LH.ARROWS))   # 동그라미를 누르면 그림으로
    story, toc = [], []
    for i, (no, title, paras) in enumerate(GS.CHAPTERS, 1):
        toc.append(f'<li><a href="#ch{i}">{html.escape(no)} · {html.escape(title)}</a></li>')
        story.append(f'<section class="chap"><h2 id="ch{i}"><span class="chapno">{html.escape(no)}</span>{html.escape(title)}</h2>'
                     + "".join(f"<p>{ab(p)}</p>" for p in paras) + "</section>")
    lpw = 560
    lfig = round((lpw - 16) * lh / lw)
    s = (HERE / "guide_tpl.html").read_text(encoding="utf-8")
    rep = {"<!--TITLE-->": html.escape(GS.TITLE), "<!--SUBTITLE-->": html.escape(GS.SUBTITLE),
           "<!--INTRO-->": "".join(f"<p>{ab(p)}</p>" for p in GS.INTRO), "<!--TOC-->": "\n".join(toc) + '\n<li><a href="#sources">저장소 밖 사실의 출처</a></li>',
           "<!--LEGEND_L-->": AL.legend_html(), "<!--SVG_LAYERS-->": lsvg, "<!--STORY-->": "\n".join(story),
           "<!--SOURCES-->": "".join(f'<li>{html.escape(t)} — <a href="{html.escape(u)}">{html.escape(u)}</a></li>' for t, u in GS.SOURCES),
           "{{NLA}}": str(len(LH.ARROWS)), "{{NLC}}": str(len(LH.CARDS)), "{{NSVC}}": str(len(names["services"])), "{{NVOL}}": str(len(names["volumes"])),
           "{{NNET}}": str(len(names["networks"])), "{{NTOP}}": str(len(names["kafka"])),
           "{{LPOSTER_W}}": str(lpw), "{{LPOSTER_H}}": str(lfig + 70), "{{LFIG_H}}": str(lfig - 2),
           # 이 문서에 없는 그림 쪽(틀의 CSS 에 남은 이름) — 값만 채운다
           "{{POSTER_W}}": "420", "{{POSTER_H}}": "594", "{{FIG_H}}": "560", "{{SPOSTER_W}}": "420", "{{SPOSTER_H}}": "594", "{{SFIG_H}}": "560"}
    for k, v in rep.items():
        assert k in s, k
        s = s.replace(k, v)
    left = re.findall(r"\{a:\d+\}|\{\{\w+\}\}|<!--[A-Z_]+-->", s)
    assert not left, left
    ids = collections.Counter(re.findall(r'\bid="([^"]+)"', s))
    dup = [k for k, v in ids.items() if v > 1]
    assert not dup, f"중복 id: {dup[:10]}"
    miss = sorted({h for h in re.findall(r'href="#([^"]+)"', s)} - set(ids))
    assert not miss, f"없는 앵커: {miss[:10]}"
    OUT_HTML.write_text(s, encoding="utf-8")
    plain = re.sub(r"<[^>]+>|\{a:\d+\}", "", alltxt)
    print(f"HTML {OUT_HTML.name} {len(s.encode())} bytes · 그림 카드 {len(LH.CARDS)} · 화살표 {len(LH.ARROWS)}(이야기에 전부) · 장 {len(GS.CHAPTERS)} · 이야기 {len(plain)}자")


def build_pdf():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(OUT_HTML.as_uri(), wait_until="networkidle")
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(1500)
        pg.pdf(path=str(OUT_PDF), prefer_css_page_size=True, print_background=True,
               display_header_footer=True, header_template="<span></span>",
               footer_template='<div style="font-size:8px;color:#8a949b;width:100%;text-align:center;font-family:sans-serif"><span class="pageNumber"></span> / <span class="totalPages"></span></div>')
        b.close()
    print("PDF", OUT_PDF.name, OUT_PDF.stat().st_size, "bytes")


if __name__ == "__main__":
    build_html()
    if "--html" not in sys.argv:
        build_pdf()
