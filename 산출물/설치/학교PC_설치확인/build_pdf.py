"""학교PC_설치확인.md → 학교PC_설치확인.pdf (pandoc으로 HTML을 만들고 Chromium으로 인쇄한다).

    python build_pdf.py

필요한 것: pandoc, playwright(Chromium). 그림은 img/ 를 상대 경로로 읽는다.
"""
import os
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
SRC, HTML, PDF = HERE / "학교PC_설치확인.md", HERE / "_build.html", HERE / "학교PC_설치확인.pdf"
CSS = """
@page { size: A4; margin: 16mm 15mm 16mm; }
body { font-family: "Malgun Gothic","맑은 고딕","Noto Sans KR","WenQuanYi Zen Hei",sans-serif; font-size: 10.5pt;
       line-height: 1.75; color: #1f2429; word-break: keep-all; overflow-wrap: break-word; }
header#title-block-header { display: none; }
h1 { font-size: 20pt; color: #14335e; border-bottom: 3px solid #1b4b8f; padding-bottom: 8px; margin: 0 0 18px; }
h2 { font-size: 15pt; color: #14335e; border-top: 2.5px solid #1b4b8f; padding-top: 12px; margin: 30px 0 12px; }
h3 { font-size: 12.5pt; color: #24405f; margin: 24px 0 8px; }
h4 { font-size: 11pt; color: #24405f; margin: 20px 0 6px; }
table { border-collapse: collapse; width: 100%; margin: 10px 0 14px; font-size: 9.5pt; page-break-inside: avoid; }
th, td { border: 1px solid #c9d2dc; padding: 5px 8px; vertical-align: top; }
th { background: #eef3f8; }
code { font-family: Consolas,"D2Coding","WenQuanYi Zen Hei Mono",monospace; background: #f1f3f5; padding: 0 3px; border-radius: 3px; }
pre { background: #1e2329; color: #e6e6e6; padding: 10px 12px; border-radius: 6px; }
pre code { background: none; color: inherit; }
blockquote { margin: 12px 0; padding: 8px 14px; border-left: 4px solid #e0a43a; background: #fff8ec; }
figure { margin: 10px 0 16px; page-break-inside: avoid; }
img { max-width: 100%; border: 1px solid #d5dbe1; border-radius: 4px; }
figcaption { font-size: 9pt; color: #5a6470; margin-top: 4px; }
"""


def main():
    css = HERE / "_build.css"
    css.write_text(CSS, encoding="utf-8")
    subprocess.run(["pandoc", str(SRC), "-s", "-o", str(HTML), "--css", css.name, "--metadata", "lang=ko"],
                   cwd=HERE, check=True)
    exe = os.environ.get("CHROMIUM_PATH") or None
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exe)
        page = browser.new_page()
        page.goto(HTML.as_uri(), wait_until="networkidle")
        page.pdf(path=str(PDF), format="A4", print_background=True,
                 display_header_footer=True, header_template="<span></span>",
                 footer_template='<div style="font-size:8pt;width:100%;text-align:center;color:#888">'
                                 '<span class="pageNumber"></span> / <span class="totalPages"></span></div>',
                 margin={"top": "16mm", "bottom": "16mm", "left": "15mm", "right": "15mm"})
        browser.close()
    HTML.unlink()
    css.unlink()
    print(f"{PDF.name} {PDF.stat().st_size // 1024} KB")


if __name__ == "__main__":
    sys.exit(main())
