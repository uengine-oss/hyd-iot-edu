# -*- coding: utf-8 -*-
"""코드 · 설정에서 「전체 목록」을 빌드 때마다 직접 뽑는다(hyd-iot-edu · ceco_demo 공용 사본).
사람이 옮겨 적지 않으므로 저장소가 바뀌면 문서도 그대로 따라간다. 환경변수는 이름만 싣고 값은 싣지 않는다.
  compose(path)            : 서비스 · 볼륨 · 망 표와 이름 목록
  sql_objects(paths, root) : CREATE TABLE(컬럼) · VIEW · FUNCTION · TRIGGER · ALTER ADD COLUMN
  routes(files, root, ...) : FastAPI 데코레이터 경로(앱에 등록된 것만 넘겨받음)
  table(head, rows)        : 표 HTML
"""
import html, pathlib, re

import yaml


def esc(t):
    return html.escape(str(t), quote=True)


def table(head, rows, cls="tbl small"):
    h = "".join(f"<th>{esc(x)}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tscroll"><table class="{cls}"><tr>{h}</tr>{b}</table></div>'


def code(x):
    return f"<code>{esc(x)}</code>"


def _env_names(env):
    if isinstance(env, dict):
        return list(env)
    return [str(e).split("=", 1)[0] for e in (env or [])]


def _list(v):
    if v is None:
        return []
    if isinstance(v, dict):
        return list(v)
    return [x if isinstance(x, str) else (x.get("source") or x.get("target") or str(x)) if isinstance(x, dict) else str(x) for x in v]


def compose(path):
    d = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
    svcs = d.get("services") or {}
    rows = []
    for name, s in svcs.items():
        img = s.get("image") or ""
        b = s.get("build")
        if b:
            ctx = b if isinstance(b, str) else (b.get("context", "") + ((" · " + b["dockerfile"]) if b.get("dockerfile") else ""))
            img = (img + " · " if img else "") + "build " + ctx
        prof = ", ".join(s.get("profiles") or []) or "기본"
        nets = ", ".join(_list(s.get("networks"))) or "default"
        ports = "<br>".join(esc(p if isinstance(p, str) else f'{p.get("published", "")}:{p.get("target", "")}') for p in (s.get("ports") or []))
        vols = "<br>".join(esc(v if isinstance(v, str) else f'{v.get("source", "")}:{v.get("target", "")}') for v in (s.get("volumes") or []))
        dep = s.get("depends_on") or []
        dep = ", ".join(f"{k}({v.get('condition', '')})" if isinstance(v, dict) else k for k, v in (dep.items() if isinstance(dep, dict) else [(x, None) for x in dep]))
        ef = s.get("env_file") or []
        ef = [x if isinstance(x, str) else f'{x.get("path", "")}{"" if x.get("required", True) else "(없어도 됨)"}' for x in (ef if isinstance(ef, list) else [ef])]
        envn = " ".join(_env_names(s.get("environment"))) + ((" · env_file " + ", ".join(ef)) if ef else "")
        rest = s.get("restart") or ""
        rows.append(f'<li class="hop"><p class="hophead"><span class="hopno">{esc(prof)}</span><b>{esc(name)}</b></p>'
                    f'<dl class="spec hopdl"><dt>이미지 · 빌드</dt><dd>{esc(img) or "—"}</dd><dt>망</dt><dd>{esc(nets)}</dd>'
                    f'<dt>포트(호스트:컨테이너)</dt><dd class="fld">{ports or "—"}</dd><dt>볼륨 · 바인드</dt><dd class="fld">{vols or "—"}</dd>'
                    f'<dt>의존(조건)</dt><dd>{esc(dep) or "—"}</dd><dt>환경변수 이름</dt><dd class="fld">{esc(envn) or "—"}</dd><dt>재시작</dt><dd>{esc(rest) or "—"}</dd></dl></li>')
    t1 = '<ol class="hops svcs">' + "".join(rows) + "</ol>"
    vols = d.get("volumes") or {}
    nets = d.get("networks") or {}
    used = {}
    for name, s in svcs.items():
        for v in s.get("volumes") or []:
            src = v.split(":", 1)[0] if isinstance(v, str) else v.get("source", "")
            used.setdefault(src, []).append(name)
    t2 = table(["볼륨", "쓰는 서비스"], [[code(v), esc(", ".join(used.get(v, [])) or "—")] for v in vols])
    nrows = []
    for n, nd in nets.items():
        nd = nd or {}
        sub = ""
        ipam = (nd.get("ipam") or {}).get("config") or []
        if ipam:
            sub = ", ".join(c.get("subnet", "") for c in ipam)
        members = [k for k, s in svcs.items() if n in _list(s.get("networks"))]
        nrows.append([code(n), esc("internal" if nd.get("internal") else "—"), esc(sub or "—"), esc(", ".join(members))])
    t3 = table(["망", "internal", "서브넷", "붙은 서비스"], nrows)
    return t1, t2, t3, dict(services=list(svcs), volumes=list(vols), networks=list(nets))


def _split_top(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


CONSTRAINT = re.compile(r"^(primary|unique|foreign|check|constraint|exclude|like)\b", re.I)


def sql_objects(paths, root):
    """CREATE TABLE 은 컬럼까지, 나머지는 이름만. 반환: [(파일, 종류, 이름, 내용)]"""
    out = []
    for p in paths:
        p = pathlib.Path(p)
        s = p.read_text(encoding="utf-8")
        s = re.sub(r"--[^\n]*", "", s)
        rel = p.relative_to(root).as_posix()
        n0 = len(out)
        for m in re.finditer(r"create\s+(?:unlogged\s+)?table\s+(?:if\s+not\s+exists\s+)?([\w.\"]+)\s*\(", s, re.I):
            i, depth = m.end(), 1
            while depth and i < len(s):
                depth += {"(": 1, ")": -1}.get(s[i], 0)
                i += 1
            body = s[m.end():i - 1]
            cols = []
            for part in _split_top(body):
                part = " ".join(part.split())
                if not part or CONSTRAINT.match(part):
                    continue
                toks = part.split(" ")
                cols.append(toks[0].strip('"') + (" " + toks[1] if len(toks) > 1 else ""))
            out.append((rel, "TABLE", m.group(1).strip('"'), ", ".join(cols)))
        assert len(out) - n0 == len(re.findall(r"create\s+(?:unlogged\s+)?table\s", s, re.I)), f"{rel} 의 CREATE TABLE 을 다 읽지 못함"
        for m in re.finditer(r"create\s+(?:or\s+replace\s+)?(materialized\s+view|view)\s+(?:if\s+not\s+exists\s+)?([\w.\"]+)", s, re.I):
            out.append((rel, m.group(1).upper(), m.group(2).strip('"'), ""))
        for m in re.finditer(r"create\s+(?:or\s+replace\s+)?function\s+([\w.\"]+)\s*\(", s, re.I):
            out.append((rel, "FUNCTION", m.group(1).strip('"'), ""))
        for m in re.finditer(r"create\s+(?:or\s+replace\s+)?(?:constraint\s+)?trigger\s+([\w\"]+)", s, re.I):
            out.append((rel, "TRIGGER", m.group(1).strip('"'), ""))
        for m in re.finditer(r"alter\s+table\s+(?:if\s+exists\s+)?(?:only\s+)?([\w.\"]+)\s+add\s+column\s+(?:if\s+not\s+exists\s+)?([\w\"]+)\s+([\w\[\]]+)", s, re.I):
            out.append((rel, "ADD COLUMN", m.group(1).strip('"'), f"{m.group(2)} {m.group(3)}"))
        for m in re.finditer(r"create\s+(?:type)\s+([\w.\"]+)\s+as\s+enum\s*\(([^)]*)\)", s, re.I):
            out.append((rel, "ENUM", m.group(1).strip('"'), " ".join(m.group(2).split())))
        for m in re.finditer(r"create\s+role\s+([\w\"]+)", s, re.I):
            out.append((rel, "ROLE", m.group(1).strip('"'), ""))
    return out


def sql_html(objs):
    out, files = [], []
    for f, *_r in objs:
        if f not in files:
            files.append(f)
    for f in files:
        rows = [[esc(k), code(n), f'<span class="fld">{esc(c) or "—"}</span>'] for ff, k, n, c in objs if ff == f]
        out.append(f'<p class="sqlfile"><code>{esc(f)}</code> · {len(rows)}개</p>' + table(["종류", "이름", "컬럼 · 값"], rows))
    return "".join(out)


ROUTE = re.compile(r"^\s*@(\w+)\.(get|post|put|delete|patch)\(\s*([\"'])(.*?)\3", re.M)


def routes(files, root, objs=("app",), prefixes=None):
    """files: [(서비스, 경로)] — objs 에 든 이름의 데코레이터만(=앱에 등록된 것). prefixes: {(파일, 변수): 접두사}"""
    rows = []
    for svc, f in files:
        f = pathlib.Path(f)
        s = f.read_text(encoding="utf-8")
        assert len(ROUTE.findall(s)) == len(re.findall(r"^\s*@\w+\.(?:get|post|put|delete|patch)\(", s, re.M)), f"{f} 의 경로 데코레이터를 다 읽지 못함"
        for m in ROUTE.finditer(s):
            var, meth, path = m.group(1), m.group(2).upper(), m.group(4)
            if var not in objs:
                continue
            pre = (prefixes or {}).get((f.name, var), "")
            line = s.count("\n", 0, m.start()) + 1
            rows.append((svc, meth, pre + path, f"{f.relative_to(root).as_posix()}:{line}"))
    return rows


def routes_html(rows):
    return table(["서비스", "메서드", "경로", "코드"], [[esc(a), esc(b), code(c), f'<span class="ref">{esc(d)}</span>'] for a, b, c, d in rows])
