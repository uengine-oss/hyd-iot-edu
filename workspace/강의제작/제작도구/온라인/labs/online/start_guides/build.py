"""4회차 이후 랩의 START.md로 학생 가이드(안내.html)와 학생 ZIP을 만들고 검사한다.

대상은 START.md가 있는 랩 폴더다. 가이드는 START.md 한 곳에서 만든다(같은 내용을 두 곳에 쓰지 않는다).
ZIP에는 랩 폴더만 넣는다. 강사 대본(../../대본)은 넣지 않는다.

    python workspace/강의제작/제작도구/온라인/labs/online/start_guides/build.py <랩 폴더> [<랩 폴더> ...]
    python workspace/강의제작/제작도구/온라인/labs/online/start_guides/build.py --check <랩 폴더> ...   # 생성 없이 검사만

검사(실패하면 좌표를 찍고 종료 코드 1):
- START.md와 생성한 안내.html의 상대 링크가 랩 폴더 안의 실제 파일을 가리키는가
- 학생 파일에 제작 지시 문구(「제작 참고용」「낭독하지 않음」「강사 대본」)가 없는가
- ZIP이 랩 폴더와 경로 · 내용이 같고, 풀었을 때 START.md·안내.html이 있고 그 링크가 ZIP 안에서 통하는가
ZIP 쓰기는 실습시작/lab_package.py, 검사는 실습시작/verify_packages.py(check_zip · forbidden_hits · link_errors) 한 곳을 부른다.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "실습시작"))
import lab_package  # noqa: E402
from verify_packages import check_zip, forbidden_hits, link_errors  # noqa: E402

CSS = (
    "*{box-sizing:border-box}body{margin:0;background:#f4f6f3;color:#20342f;"
    'font:17px/1.8 "Malgun Gothic",sans-serif}main{max-width:1000px;margin:auto;padding:52px 28px}'
    "h1{font-size:36px;line-height:1.35}h2{font-size:25px;line-height:1.45;margin:0 0 18px}"
    "h3{font-size:20px;margin:22px 0 8px}section{background:white;border:1px solid #dce5df;"
    "border-radius:16px;padding:30px;margin:24px 0}a{color:#176554;text-underline-offset:4px}"
    "nav{display:flex;gap:14px;flex-wrap:wrap}nav a{display:inline-block;background:#e2eee7;"
    "padding:8px 16px;border-radius:8px}p{margin:12px 0}li{margin:8px 0}pre{white-space:pre-wrap;"
    "overflow-wrap:anywhere;background:#edf2ef;padding:18px;border-radius:8px;font-size:15px}"
    "code{font-family:Consolas,monospace}table{border-collapse:collapse;width:100%}"
    "td,th{padding:12px;border-bottom:1px solid #dce5df;text-align:left;vertical-align:top}"
    "small{color:#607269}details{border-top:1px solid #dce5df;margin-top:18px;padding-top:12px}"
    "summary{cursor:pointer}"
)
KEEP_ALL = frozenset()  # .env 틀도 넣는다(실전반 04-2 코드/.env — verify_packages.TEMPLATES)


class BuildError(Exception):
    pass


def inline(text: str) -> str:
    parts = re.split(r"(`[^`]+`)", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append("<code>" + html.escape(part[1:-1]) + "</code>")
            continue
        s = html.escape(part, quote=False)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(
            r"\[([^\]]+)\]\(([^)\s]+)\)",
            lambda m: f'<a href="{html.escape(m.group(2))}">{m.group(1)}</a>',
            s,
        )
        out.append(s)
    return "".join(out)


def render(md: str) -> tuple[str, str, list[tuple[str, str]]]:
    """START.md → (제목, 본문 HTML, [(절 id, 절 제목)])."""
    lines = md.splitlines()
    title = ""
    body: list[str] = []
    nav: list[tuple[str, str]] = []
    in_section = False
    i = 0

    def close_section():
        nonlocal in_section
        if in_section:
            body.append("</section>")
            in_section = False

    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            block = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            if i >= len(lines):
                raise BuildError("START.md: 닫히지 않은 코드 블록")
            body.append("<pre><code>" + html.escape("\n".join(block)) + "</code></pre>")
            i += 1
            continue
        if line.startswith("# "):
            if title:
                raise BuildError(f"START.md:{i + 1}: 제목(#)이 둘 이상")
            title = line[2:].strip()
            i += 1
            continue
        if line.startswith("## "):
            close_section()
            sid = f"s{len(nav) + 1}"
            nav.append((sid, line[3:].strip()))
            body.append(f'<section id="{sid}"><h2>{inline(line[3:].strip())}</h2>')
            in_section = True
            i += 1
            continue
        if line.startswith("### "):
            body.append(f"<h3>{inline(line[4:].strip())}</h3>")
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
            if len(cells) < 2 or not all(re.fullmatch(r":?-{3,}:?", c) for c in cells[1]):
                raise BuildError(f"START.md:{i}: 표 머리 구분선이 없음")
            head = "".join(f"<th>{inline(c)}</th>" for c in cells[0])
            rest = "".join(
                "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in cells[2:]
            )
            body.append(f"<table><tr>{head}</tr>{rest}</table>")
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if m:
            ordered = m.group(2)[0].isdigit()
            tag = "ol" if ordered else "ul"
            items = []
            while i < len(lines):
                m2 = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if m2 and (m2.group(2)[0].isdigit()) == ordered and not m2.group(1):
                    items.append(m2.group(3))
                    i += 1
                elif m2 and m2.group(1):
                    items[-1] += "<br>· " + m2.group(3)
                    i += 1
                elif lines[i].startswith("   ") and lines[i].strip() and items:
                    items[-1] += " " + lines[i].strip()
                    i += 1
                else:
                    break
            body.append(
                f"<{tag}>"
                + "".join("<li>" + inline(it).replace("&lt;br&gt;", "<br>") + "</li>" for it in items)
                + f"</{tag}>"
            )
            continue
        if not line.strip():
            i += 1
            continue
        para = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||```|\s*([-*]|\d+\.)\s)", lines[i]):
            para.append(lines[i].strip())
            i += 1
        text = " ".join(para)
        if text.startswith("> "):
            body.append(f'<p class="check">{inline(text[2:])}</p>')
        else:
            body.append(f"<p>{inline(text)}</p>")
    close_section()
    if not title:
        raise BuildError("START.md: 제목(# …)이 없음")
    return title, "\n".join(body), nav


def student_files(lab: Path) -> list[Path]:
    return lab_package.student_files(lab, KEEP_ALL)


def tree(lab: Path) -> str:
    items = []
    for p in student_files(lab):
        rel = p.relative_to(lab).as_posix()
        if rel == "안내.html":
            continue
        items.append(f'<li><a href="{html.escape(rel)}">{html.escape(rel)}</a></li>')
    return "<details><summary>받은 폴더의 파일</summary><ul>" + "".join(items) + "</ul></details>"


def build_guide(lab: Path) -> str:
    start = lab / "START.md"
    if not start.exists():
        raise BuildError(f"{lab}: START.md 없음")
    title, body, nav = render(start.read_text(encoding="utf-8"))
    nav_html = "<nav>" + "".join(f'<a href="#{sid}">{html.escape(t)}</a>' for sid, t in nav) + "</nav>"
    return (
        '<!doctype html><html lang="ko"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{CSS}</style><main>"
        f"<small>HYD · 실습 가이드</small><h1>{inline(title)}</h1>"
        '<p>VS Code에서 이 폴더(이 안내 파일이 있는 폴더)를 열고 <a href="START.md">START.md</a>를 함께 읽으세요. '
        "이 안내는 START.md와 같은 내용입니다.</p>"
        f"{nav_html}\n{body}\n<section><h2>받은 폴더</h2>{tree(lab)}</section></main></html>\n"
    )


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    labs = [Path(a) for a in argv if a != "--check"]
    if not labs:
        print(__doc__)
        return 2
    errors: list[str] = []
    for lab in labs:
        if not lab.is_dir():
            errors.append(f"{lab}: 랩 폴더 없음")
            continue
        try:
            guide = build_guide(lab)
        except BuildError as exc:
            errors.append(f"{lab}: {exc}")
            continue
        if not check_only:
            (lab / "안내.html").write_text(guide, encoding="utf-8", newline="\n")
        elif (lab / "안내.html").read_text(encoding="utf-8") != guide:
            errors.append(f"{lab}/안내.html: START.md와 다름(다시 생성 필요)")
        files = {p.relative_to(lab).as_posix(): p.read_bytes() for p in student_files(lab)}
        files["안내.html"] = guide.encode("utf-8")
        errors += [f"{lab.name}/{e}" for e in link_errors(files, docs={"START.md", "안내.html"})]
        errors += forbidden_hits((f"{lab.name}/{name}", data) for name, data in files.items())
        zpath = lab.parent / f"{lab.name}.zip"
        if not check_only:
            try:
                zpath = lab_package.pack(lab, KEEP_ALL)
            except ValueError as exc:
                errors.append(str(exc))
        if zpath.exists():
            zip_errors, notes = check_zip(zpath, lab, need=("START.md", "안내.html"), exclude_names=KEEP_ALL)
            errors += zip_errors
            for note in notes:
                print("참고:", note)
        else:
            errors.append(f"{zpath}: ZIP 없음(다시 생성 필요)")
        print(f"{'검사' if check_only else '생성'}: {lab} ({len(student_files(lab))}개 파일)")
    for e in errors:
        print("오류:", e)
    print(f"결과: 랩 {len(labs)}개, 오류 {len(errors)}개")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
