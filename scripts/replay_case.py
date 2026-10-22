"""재생 모드 사례 만들기 · 검사. 계약: 문서/시스템/참조/재생모드.md

  build  <원녹화.json> <사례 id>   강사 녹화(포털 ?replay-record= 로 내려받은 것)를 안내서와 맞춰 재생 녹화로 만든다
                                   → it/portal/www/replay/cases/<id>.recording.json, 안내서의 recording 값을 새 녹화 id 로 고친다
  check  [<사례 id> ...]           저장소에 있는 사례를 검사한다(없으면 cases.json 의 전부). 문제가 있으면 좌표와 함께 실패한다

검사 항목: 안내서의 행동이 녹화의 쓰기와 같은 순서 · 같은 요청인지, 안내서가 허용하지 않은 쓰기가 녹화에 섞이지 않았는지,
녹화에 비밀값(이 셸의 키 환경 변수 값 · 키 모양 문자열) · 메일 주소 · 절대 경로가 없는지, 강의 자료(랩 · 대본)가 녹화 뒤 바뀌지 않았는지,
포털 파일이 녹화 당시와 같은지. 값을 출력하지 않고 위치만 출력한다.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WWW = ROOT / "it" / "portal" / "www"
REPLAY = WWW / "replay"
SECRET_ENV = ("OPENAI_API_KEY", "LLM_API_KEY", "ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY", "CODEX_MODEL_PROVIDER_API_KEY",
              "CLAUDE_CODE_OAUTH_TOKEN", "GITHUB_TOKEN", "SUPABASE_SERVICE_ROLE_KEY")
SECRET_SHAPES = [
    ("키 모양(sk-)", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")),
    ("키 모양(Bearer)", re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}")),
    ("JWT 모양", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    # 시드의 가상 사용자 주소(@hyd.local, it/supabase/seed.sql)는 저장소에 이미 있는 교육용 값이라 뺀다
    ("메일 주소", re.compile(r"[A-Za-z0-9._%+-]+@(?!hyd\.local\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("절대 경로(Windows)", re.compile(r"[A-Za-z]:\\\\(Users|work)\\\\", re.I)),
    ("절대 경로(홈)", re.compile(r"/(home|Users|root)/[A-Za-z0-9._-]+/")),
]


class CaseError(Exception):
    pass


def git_blob(path: Path) -> str:
    """git 이 그 파일 내용에 매기는 해시(커밋 여부와 상관없이 지금 내용 기준)."""
    data = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def portal_content_hash() -> str:
    """포털 화면 파일(replay* 제외)의 내용 해시. 녹화 당시와 다르면 화면이 녹화 응답과 어긋날 수 있다."""
    h = hashlib.sha256()
    for p in sorted(WWW.glob("*")):
        if p.is_file() and p.suffix in {".js", ".css", ".html", ".json"} and not p.name.startswith("replay"):
            h.update(p.name.encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()[:16]


def read_recording(path: Path) -> str:
    """녹화 파일은 gzip(.json.gz)으로 둔다 — 같은 응답이 시각마다 되풀이돼 원문은 수십 MB가 된다. 재생 화면은 브라우저 표준 DecompressionStream 으로 푼다."""
    data = path.read_bytes()
    return (gzip.decompress(data) if path.suffix == ".gz" else data).decode("utf-8")


def load_index() -> dict:
    return json.loads((REPLAY / "cases.json").read_text(encoding="utf-8"))


def entry_for(case_id: str) -> dict:
    for c in load_index()["cases"]:
        if c["id"] == case_id:
            return c
    raise CaseError(f"replay/cases.json 에 사례 {case_id} 가 없습니다")


def match_writes(guide: dict, writes: list[dict], where: str) -> list[dict]:
    """안내서의 행동 항목을 녹화된 쓰기에 순서대로 맞춘다. 맞지 않거나 허용되지 않은 쓰기가 있으면 실패."""
    acts = [i for i in guide["items"] if i["kind"] == "action"]
    allow = [(a["method"], re.compile("^" + a["key"] + "$")) for a in guide.get("allow", [])]
    out, n = [], 0
    for w in writes:
        if w.get("status", 0) >= 400 and any(is_mistake(m, w) for m in guide.get("mistakes", [])):
            continue   # 강사가 일부러 해 둔 흔한 실수(서버가 거절해 상태가 바뀌지 않은 쓰기). 재생도 이것을 먼저 본다
        if n < len(acts):
            m = acts[n]["match"]
            if w["method"] == m["method"] and re.fullmatch(m["key"], w["key"]):
                body = json.loads(w["request"]) if w["request"] else {}
                if not subset(m.get("body"), body):
                    raise CaseError(f"{where}: {n + 1}번째 행동 「{acts[n]['title']}」의 녹화 입력이 안내서의 정해진 입력과 다릅니다")
                out.append(w)
                n += 1
                continue
        if any(w["method"] == meth and rx.fullmatch(w["key"]) for meth, rx in allow):
            continue
        raise CaseError(f"{where}: 안내서에 없는 쓰기가 녹화에 있습니다 — {w['method']} {w['key']} (녹화 {w['t_req'] / 1000:.1f}초)")
    if n != len(acts):
        raise CaseError(f"{where}: 안내서 행동 {len(acts)}건 가운데 {n}건만 녹화에 있습니다(다음: 「{acts[n]['title']}」)")
    return out


def is_mistake(m: dict, w: dict) -> bool:
    if w["method"] != m["method"] or not re.fullmatch(m["key"], w["key"]):
        return False
    try:
        return subset(m.get("body"), json.loads(w["request"]) if w["request"] else {})
    except ValueError:
        return False


def subset(want, got) -> bool:
    if want is None:
        return True
    if not isinstance(want, dict):
        return want == got
    return isinstance(got, dict) and all(subset(v, got.get(k)) for k, v in want.items())


def scan_secrets(text: str, where: str) -> list[str]:
    found = []
    for name in SECRET_ENV:
        value = os.environ.get(name, "")
        if len(value) >= 8 and value in text:
            found.append(f"{where}: 환경 변수 {name} 의 값")
    for label, rx in SECRET_SHAPES:
        if rx.search(text):
            found.append(f"{where}: {label}")
    return found


def check_case(case_id: str) -> list[str]:
    problems: list[str] = []
    entry = entry_for(case_id)
    guide_path, rec_path = REPLAY / entry["guide"], REPLAY / entry["recording"]
    for p in (guide_path, rec_path):
        if not p.exists():
            return [f"{p.relative_to(ROOT)} 가 없습니다"]
    guide = json.loads(guide_path.read_text(encoding="utf-8"))
    rec_text = read_recording(rec_path)
    rec = json.loads(rec_text)
    where = str(rec_path.relative_to(ROOT))
    if guide.get("recording") != rec.get("id"):
        problems.append(f"{guide_path.relative_to(ROOT)}: recording {guide.get('recording')} ≠ 녹화 id {rec.get('id')}")
    try:
        actions = match_writes(guide, rec["writes"], where)
        if [a["t_req"] for a in actions] != [a["t_req"] for a in rec["actions"]]:
            problems.append(f"{where}: actions 가 writes 에서 안내서 순서로 고른 것과 다릅니다")
    except CaseError as e:
        problems.append(str(e))
    for m in guide.get("mistakes", []):
        if not any(w.get("status", 0) >= 400 and is_mistake(m, w) for w in rec["writes"]):
            problems.append(f"{guide_path.relative_to(ROOT)}: 실수 「{m.get('explain', '')[:40]}」의 녹화(서버가 거절한 응답)가 없습니다 — 녹화 때 그 실수를 한 번 해 둔다")
    for n, it in enumerate([i for i in guide["items"] if i["kind"] == "action"]):
        for f in it["match"].get("same", []) + it["match"].get("free", []):
            a = rec["actions"][n] if n < len(rec["actions"]) else None
            if a is not None and f not in (json.loads(a["request"] or "{}")):
                problems.append(f"{guide_path.relative_to(ROOT)}: {n + 1}번째 행동의 칸 {f} 가 녹화된 요청에 없습니다")
    missing = [h for fs in rec["frames"].values() for f in fs for h in [f[2]] if h is not None and h not in rec["bodies"]]
    missing += [w["response"] for w in rec["writes"] if w["response"] not in rec["bodies"]]
    if missing:
        problems.append(f"{where}: 본문이 없는 응답 {len(missing)}건")
    problems += scan_secrets(rec_text, where) + scan_secrets(guide_path.read_text(encoding="utf-8"), str(guide_path.relative_to(ROOT)))
    for rel, blob in guide.get("lecture", {}).get("sources", {}).items():
        p = ROOT / rel
        if not p.exists():
            problems.append(f"{guide_path.relative_to(ROOT)}: 강의 자료 {rel} 가 없습니다")
        elif git_blob(p) != blob:
            problems.append(f"{guide_path.relative_to(ROOT)}: 강의 자료 {rel} 가 안내서 작성 뒤 바뀌었습니다 — 안내 · 녹화가 아직 맞는지 확인하고 sources 해시를 고친다")
    if rec.get("portal_content") != portal_content_hash():
        problems.append(f"{where}: 포털 화면 파일이 녹화 당시와 다릅니다(녹화 {rec.get('portal_content')} ≠ 지금 {portal_content_hash()}) — 재생해 보고 다시 녹화하거나 확인 기록을 남긴다")
    return problems


def build(raw_path: Path, case_id: str) -> Path:
    entry = entry_for(case_id)
    guide_path = REPLAY / entry["guide"]
    guide = json.loads(guide_path.read_text(encoding="utf-8"))
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    if raw.get("format") != "hyd-replay-recording/1" or raw.get("case") != case_id:
        raise CaseError(f"{raw_path}: 이 사례({case_id})의 녹화 파일이 아닙니다")
    actions = match_writes(guide, raw["writes"], str(raw_path))
    started = datetime.fromtimestamp(raw["started_wall"] / 1000, tz=timezone.utc)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    used = {f[2] for fs in raw["frames"].values() for f in fs} | {w["response"] for w in raw["writes"]}
    rec = {
        "format": "hyd-replay/1",
        "id": f"{case_id}@{started.strftime('%Y%m%dT%H%M%SZ')}",
        "case": case_id,
        "recorded_at": started.strftime("%Y-%m-%d %H:%M UTC"),
        "started_wall": raw["started_wall"],
        "duration": raw["ended_wall"] - raw["started_wall"],
        "repo_commit": commit,
        "portal_fingerprint": raw["portal_fingerprint"],
        "portal_content": portal_content_hash(),
        "conditions": guide["conditions"],
        "actions": actions,
        "writes": raw["writes"],
        "frames": raw["frames"],
        "streams": raw["streams"],
        "bodies": {h: b for h, b in raw["bodies"].items() if h in used},
    }
    text = json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
    leaks = scan_secrets(text, "녹화")
    if leaks:
        raise CaseError("녹화에 비밀값으로 보이는 것이 있어 저장하지 않았습니다: " + " / ".join(leaks))
    out = REPLAY / entry["recording"]
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".gz":
        out.write_bytes(gzip.compress(text.encode("utf-8"), compresslevel=9, mtime=0))
    else:
        out.write_text(text, encoding="utf-8")
    guide["recording"] = rec["id"]
    guide_path.write_text(json.dumps(guide, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # 사례 고르기 화면이 큰 녹화 파일을 읽지 않도록 목록에 녹화 시각 · 조건 요약을 옮겨 둔다(이 도구만 쓴다)
    index = load_index()
    for c in index["cases"]:
        if c["id"] == case_id:
            c["recorded_at"], c["conditions"] = rec["recorded_at"], guide["conditions"]["summary"]
    (REPLAY / "cases.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[0] == "build":
        try:
            out = build(Path(argv[1]), argv[2])
        except CaseError as e:
            print("실패:", e)
            return 1
        print(f"저장: {out.relative_to(ROOT)} ({out.stat().st_size:,} 바이트)")
        argv = ["check", argv[2]]
    if argv and argv[0] == "check":
        ids = argv[1:] or [c["id"] for c in load_index()["cases"]]
        bad = 0
        for cid in ids:
            problems = check_case(cid)
            print(f"{cid}: {'통과' if not problems else '문제 ' + str(len(problems)) + '건'}")
            for p in problems:
                print("  -", p)
            bad += bool(problems)
        return 1 if bad else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
