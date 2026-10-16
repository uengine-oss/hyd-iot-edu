"""낭독본 MD → 대본 PDF(대본만: 장 제목과 읽을 문장).

    python3 만들기/tools/deck/대본PDF.py <낭독본.md> <출력.pdf>

- 글꼴은 Pretendard(npm 패키지 pretendard@1.3.9)를 처음 한 번 `~/.cache/대본PDF/`에 받아 쓴다.
- 변환은 pandoc(MD → HTML)과 Chromium 계열 브라우저의 PDF 인쇄로 한다. 브라우저는 환경변수 CHROME,
  Playwright의 chromium, chromium · google-chrome 순으로 찾고, 없으면 좌표와 함께 실패한다.
"""
import glob, os, pathlib, shutil, subprocess, sys, tempfile

src, out = map(pathlib.Path, sys.argv[1:3])
cache = pathlib.Path.home() / ".cache/대본PDF"
fonts = cache / "package/dist/web/static/woff2"
if not (fonts / "Pretendard-Regular.woff2").exists():
    cache.mkdir(parents=True, exist_ok=True)
    subprocess.run(["npm", "pack", "pretendard@1.3.9"], cwd=cache, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["tar", "xzf", "pretendard-1.3.9.tgz"], cwd=cache, check=True)

def find_chrome():
    cands = [os.environ.get("CHROME")]
    cands += sorted(glob.glob(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers") + "/chromium-*/chrome-linux/chrome"))
    cands += [shutil.which(n) for n in ("chromium", "chromium-browser", "google-chrome", "chrome")]
    for c in cands:
        if c and pathlib.Path(c).exists():
            return c
    sys.exit("대본PDF.py: Chromium 계열 브라우저를 찾지 못했다(CHROME 환경변수로 경로를 준다)")

css = f"""
@font-face {{ font-family: P; src: url('file://{fonts}/Pretendard-Regular.woff2'); font-weight: 400; }}
@font-face {{ font-family: P; src: url('file://{fonts}/Pretendard-SemiBold.woff2'); font-weight: 600; }}
@font-face {{ font-family: P; src: url('file://{fonts}/Pretendard-Bold.woff2'); font-weight: 700; }}
@page {{ size: A4; margin: 20mm 18mm 18mm; }}
body {{ font-family: P, sans-serif; font-size: 11pt; line-height: 1.75; color: #1a1a1a; word-break: keep-all; }}
h1 {{ font-size: 18pt; font-weight: 700; margin: 0 0 10mm; border-bottom: 2px solid #1a1a1a; padding-bottom: 3mm; }}
h2 {{ font-size: 12pt; font-weight: 600; color: #1f4e79; margin: 8mm 0 2mm; break-after: avoid; }}
p {{ margin: 0 0 3mm; orphans: 2; widows: 2; }}
"""
with tempfile.TemporaryDirectory() as t:
    html = pathlib.Path(t) / "a.html"
    (pathlib.Path(t) / "a.css").write_text(css)
    subprocess.run(["pandoc", str(src), "-s", "-o", str(html), "--css", "a.css",
                    "--metadata", f"pagetitle={src.stem}", "-f", "markdown-smart"], check=True)
    subprocess.run([find_chrome(), "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                    "--allow-file-access-from-files", f"--print-to-pdf={out.resolve()}", html.as_uri()],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
if not out.exists() or out.stat().st_size == 0:
    sys.exit(f"대본PDF.py: PDF가 만들어지지 않았다: {out}")
print(out)
