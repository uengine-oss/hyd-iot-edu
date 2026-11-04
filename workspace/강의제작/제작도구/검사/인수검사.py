"""인수 전표의 항목·판본·근거 연결과 완료 가능 여부를 검사한다(내용 판정은 검토자 몫).

사용: PYTHONUTF8=1 .venv314/Scripts/python.exe <이 파일> <전표.json> [--완료] [--출력 결과.json]
      <이 파일> --틀 <지침.md> [--종류 <이름> ...]   # criteria 틀(JSON 배열, 행 SHA256 포함) — 새 전표는 여기서 시작한다
      <이 파일> --자가시험                            # 일부러 깨뜨린 사본으로 각 판정이 잡는지 확인
전표는 작업 폴더에 둔다. 경로는 저장소 루트 기준이고(Windows 역슬래시도 같게 읽는다), 파일 SHA256은 파일의 전체 해시다.

판정 대상 행 = 그 지침의 행 + 같은 폴더 공통.md에서 그 지침에 해당하는 행(C-n). 공통.md의 `### 이름 (대상: 코딩랩 · 가이드)` 절은 적힌 지침의 일에만 들고, 표시가 없는 절은 모든 일에 든다.
공통.md를 지침으로 주면 공통.md 전 행이다. 대상 이름이 문서 이름(실라버스 · 덱 · 대본 · 영상 · 코딩랩 · 가이드)이 아니면 실패한다.
지침이 일 종류로 갈리면 인수 조건 절이 `### <종류>` 표로 나뉜다(`### 공통 — 주제`처럼 「 — 」 뒤는 주제이고 종류는 그 앞이다).
--종류(전표에서는 산출물의 "kind": 이름 또는 이름 배열)를 주면 그 종류 표 · `### 공통` · 공통.md 행만 판정 대상이고 해당 없는 행은 틀에 나오지 않는다.
없는 종류 이름, `### 공통`이 없는 지침에 종류를 준 것은 실패한다. 종류를 안 적으면 그 지침의 전 행이 필수다.

지침은 인수 조건 행마다 판본을 본다 — 행 SHA256은 그 행의 칸(번호 · 통과 기준 · 확인 방법)을 「 | 」로 이은 글자의 해시라,
지침의 다른 곳이 바뀌어도 근거는 그대로 이어지고 바뀐 행만 다시 판정한다. 판본이 바뀐 근거 파일은 파일 하나에 한 줄로 알린다.
기본 모드는 불통과/미확인 수를 보고하며, --완료는 둘 중 하나라도 있으면 실패한다.
누락·잘못된 상태·빈 이유·없는 근거·판본 불일치·작성자의 자체 검토는 모드와 관계없이 실패한다.

옛 전표(지침을 재편하기 전에 쓴 것)의 처리 — 결과의 산출물마다 「행 잇기」가 수를 적는다:
- 안 바뀐 행은 그대로 이어진다(「이어짐」). 글자가 바뀐 행은 위와 같이 실패하고 그 행만 다시 판정한다(「바뀜」).
- 지침에서 없어진 행은 「옛 행」이다: 판정 수에 세지 않고 「notices」로 알린다. 기본 모드는 실패가 아니지만 completion_ready가 false이고 --완료는 실패한다.
- schema_version 1 · 2에 없는 공통.md 행은 「공통 미판정」이다: 옛 행과 같게 알리고 --완료는 실패한다. schema_version 3은 공통.md 행도 빠지면 누락으로 실패한다.
기존 근거는 현재 파일/지침과 적용 범위가 같다고 검토자가 확인한 경우만 연결한다.
이 도구의 성공은 문장·화면·사실·실측 품질이나 근거 내용의 타당성을 증명하지 않는다.

전표 형식(schema_version=3):
{
  "schema_version": 3,
  "required_artifacts": ["통합반-온라인-3-영상"],
  "artifacts": [{
    "id": "통합반-온라인-3-영상",
    "guideline": {"path": "workspace/강의제작/지침/영상.md"},
    "kind": "이론 영상",
    "files": [{"path": "정본 경로", "sha256": "전체 SHA256"}],
    "authors": ["작성 에이전트 ID"],
    "reviewer": "직접 수정하지 않은 감독 또는 검토 에이전트 ID",
    "criteria": [{
      "id": "V-1", "row_sha256": "--틀이 낸 그 행의 SHA256", "status": "통과", "reason": "판정 이유",
      "evidence": [{"path": "근거 파일 경로", "sha256": "전체 SHA256", "locator": "장·행·JSON 키 등"}]
    }]
  }]
}
criteria에는 판정 대상 행 전체를 넣는다(같은 조건으로 낸 --틀이 그 목록이다). 해당 없음에는 이유가 필수이고,
통과에는 파일·판본·위치가 있는 근거가 필수다. 불통과/미확인에는 문제 또는 남은 확인을 reason에 쓴다.
옛 형식 schema_version=2(공통.md 없음), 1(guideline에 지침 전체 sha256, criteria에 row_sha256 없음 — 지침이 한 글자만 바뀌어도 전 항목이 끊김)도 받는다. 새 전표는 3으로 쓴다.
전표/근거는 신뢰된 명령이 아니며 이 도구는 연결된 파일을 실행하지 않는다. .env는 읽지 않는다.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
STATES = ("통과", "불통과", "해당 없음", "미확인")
HASH = re.compile(r"[0-9a-f]{64}")
ROW_ID = re.compile(r"[A-Z]-\d+")
TABLE_SEP = re.compile(r"^\|\s*:?-{3,}")
COMMON_NAME = "공통.md"
COMMON_KIND = "공통"
WORKS = ("실라버스", "덱", "대본", "영상", "코딩랩", "가이드")
TARGET = re.compile(r"\s*\(대상:\s*([^()]*)\)\s*$")


def text(value):
    return isinstance(value, str) and bool(value.strip())


def table_rows(p):
    """인수 조건 절 안 표의 행: (줄, 위의 `### ` 제목, [칸...]). 인수 조건 표를 읽는 곳은 여기 하나다(재편검사도 이것을 쓴다)."""
    rows, inside, intable, heading = [], False, False, ""
    for i, l in enumerate(p.read_text(encoding="utf-8-sig").splitlines(), 1):
        if l.startswith("## "):
            inside = l[3:].strip() == "인수 조건"
            continue
        if not inside:
            continue
        if l.startswith("### "):
            heading = l[4:].strip()
        if l.startswith("|"):
            if TABLE_SEP.match(l):
                intable = True
                continue
            if intable:
                rows.append((i, heading, [c.strip() for c in l.strip().strip("|").split("|")]))
        else:
            intable = False
    return rows


def acceptance_rows(p):
    """인수 조건 표의 행: (줄, [칸...])."""
    return [(line, cells) for line, _, cells in table_rows(p)]


def kind_of(heading):
    """`### 이론 영상` · `### 공통 — 범위와 시간`의 종류 이름. 제목 없는 표(절 첫머리)는 모든 종류에 든다."""
    return heading.split(" — ")[0].strip() or COMMON_KIND


def heading_target(heading):
    """`이름 (대상: 코딩랩 · 가이드)`의 (이름, [대상...]). 표시가 없으면 대상은 None — 모든 일이다."""
    found = TARGET.search(heading)
    if not found:
        return heading.strip(), None
    return heading[:found.start()].strip(), [name.strip() for name in found[1].split("·")]


def common_blocks(p):
    """공통.md를 `## ` · `### ` 제목으로 나눈 덩이: (시작 줄, 끝 줄, 제목, 대상). 제목 앞 머리도 대상 None 덩이다. 줄 번호는 Read 도구와 같게 줄바꿈으로 센다."""
    lines = p.read_bytes().decode("utf-8-sig").split("\n")
    lines = lines[:-1] if lines[-1] == "" else lines
    blocks, start, title, targets = [], 1, "", None
    for i, line in enumerate(lines, 1):
        if line.startswith(("## ", "### ")):
            if i > start:
                blocks.append((start, i - 1, title, targets))
            title, targets = heading_target(line.lstrip("#"))
            start = i
    blocks.append((start, len(lines), title, targets))
    return blocks


def common_ranges(p, works):
    """그 일들이 읽을 공통.md 줄 범위 [(시작, 끝)](이어진 덩이는 합친다). works가 비면 일을 정할 수 없는 것이라 전체다."""
    ranges = []
    for start, end, _, targets in common_blocks(p):
        if not works or targets is None or set(works) & set(targets):
            if ranges and ranges[-1][1] == start - 1:
                ranges[-1] = (ranges[-1][0], end)
            else:
                ranges.append((start, end))
    return ranges


def target_rows(shared, work):
    """공통.md 표의 행을 그 일에 드는 것과 안 드는 것으로 가른다: (든 행 [(줄, 칸)], 안 든 ID, 문제 목록). work가 여섯 문서가 아니면 다 든다."""
    inside, outside, problems = [], set(), []
    for line, heading, cells in table_rows(shared):
        targets = heading_target(heading)[1]
        for name in targets or []:
            if name not in WORKS:
                problems.append(f"{shared.name}:{line}: 절 「{heading}」의 대상 「{name}」이 문서 이름이 아님 — {' · '.join(WORKS)}")
        if targets is None or work in targets or work not in WORKS:
            inside.append((line, cells))
        else:
            outside.add(cells[0])
    return inside, outside, problems


def row_parts(guide, root=ROOT, kinds=None):
    """(그 지침의 행 {ID: 행 SHA256}, 공통.md에서 그 지침에 드는 행, 문제 목록). 문서 순서다. 첫 칸이 ID 꼴이 아닌 행(표 안 소제목 등)은 항목에 넣지 않는다."""
    problems, dup, own, common = [], False, {}, {}
    rel = guide.relative_to(root.resolve()).as_posix()
    table = table_rows(guide)
    names = {kind_of(h) for _, h, _ in table}
    for kind in kinds or []:
        if kind not in names:
            problems.append(f"{rel}: 종류 「{kind}」 표가 없음 — 있는 제목: {sorted(names)}")
    if kinds and COMMON_KIND not in names:
        problems.append(f"{rel}: 종류로 나뉜 지침이 아님(`### {COMMON_KIND}` 표 없음) — 종류를 적지 않고 전 행을 판정한다")
    for line, heading, cells in table:
        if kinds and kind_of(heading) not in (*kinds, COMMON_KIND):
            continue
        if not ROW_ID.fullmatch(cells[0]):
            problems.append(f"{rel}:{line}: 인수 조건 행의 번호가 ID 꼴이 아님")
        elif cells[0] in own:
            dup = True
        else:
            own[cells[0]] = hashlib.sha256(" | ".join(cells).encode("utf-8")).hexdigest()
    shared = guide.with_name(COMMON_NAME)
    if guide.name != COMMON_NAME and guide.parent.name == "지침" and not shared.is_file():
        problems.append(f"{rel}: 같은 폴더에 {COMMON_NAME}이 없음")
    elif guide.name != COMMON_NAME and shared.is_file():
        inside, _, target_problems = target_rows(shared, guide.stem)
        problems += target_problems
        for line, cells in inside:
            if not ROW_ID.fullmatch(cells[0]):
                problems.append(f"{shared.relative_to(root.resolve()).as_posix()}:{line}: 인수 조건 행의 번호가 ID 꼴이 아님")
            elif cells[0] in own or cells[0] in common:
                dup = True
            else:
                common[cells[0]] = hashlib.sha256(" | ".join(cells).encode("utf-8")).hexdigest()
    if not own or dup:
        problems.append("지침 항목 없음 또는 중복")
    return own, common, problems


def criteria_of(guide, root=ROOT, kinds=None):
    """판정 대상 행 {ID: 행 SHA256}(그 지침 다음 공통.md)과 문제 목록."""
    own, common, problems = row_parts(guide, root, kinds)
    return {**own, **common}, problems


def resolve_path(value, root=ROOT):
    if not text(value):
        raise ValueError("경로 빈칸")
    path = Path(value.replace("\\", "/"))       # Windows에서 쓴 전표도 리눅스 · 클라우드에서 같은 판정
    if any(part.lower().startswith(".env") for part in path.parts):
        raise ValueError(".env 참조 금지")
    path = (root / path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("저장소 밖 경로")
    if any(part.lower().startswith(".env") for part in path.parts):
        raise ValueError(".env 참조 금지")
    return path


def validate(data, *, root=ROOT, complete=False):
    issues, notices, results, cache, guides, stale = [], [], [], {}, {}, {}

    def error(label, message):
        issues.append(f"{label}: {message}")

    def file_ref(ref, label, whole=True, group=None):
        """whole=False면 판본은 보지 않는다(v2 지침 — 행마다 본다). group을 주면 문제를 (근거 경로, 문제)마다 모은다."""
        if not isinstance(ref, dict):
            error(label, "파일 참조 형식")
            return None
        try:
            path = resolve_path(ref.get("path"), root)
            expected = ref.get("sha256")
            if whole and (not isinstance(expected, str) or not HASH.fullmatch(expected)):
                raise ValueError("SHA256 형식")
            if not path.is_file():
                raise ValueError("파일 없음")
            if whole and path not in cache:
                cache[path] = hashlib.sha256(path.read_bytes()).hexdigest()
            if whole and cache[path] != expected:
                raise ValueError("현재 판본과 SHA256 불일치")
            return path
        except (ValueError, OSError) as exc:
            if group is None:
                error(label, str(exc))
            else:
                group.setdefault((str(ref.get("path")).replace("\\", "/"), str(exc)), []).append(label)
            return None

    version = data.get("schema_version") if isinstance(data, dict) else None
    if version not in (1, 2, 3):
        return {"issues": ["전표 schema_version=3(옛 전표는 1 · 2) 필요"], "completion_ready": False}
    required, artifacts = data.get("required_artifacts"), data.get("artifacts")
    if not isinstance(required, list) or not required or not all(text(x) for x in required):
        return {"issues": ["required_artifacts 비어 있거나 잘못된 형식"], "completion_ready": False}
    if len(set(required)) != len(required):
        error("required_artifacts", "중복 ID")
    if not isinstance(artifacts, list):
        return {"issues": ["artifacts 배열 필요"], "completion_ready": False}
    found = []
    for index, artifact in enumerate(artifacts):
        label = f"artifacts[{index}]"
        if not isinstance(artifact, dict):
            error(label, "산출물 객체 필요")
            continue
        identity = artifact.get("id")
        if not text(identity):
            error(label, "ID 없음")
        else:
            found.append(identity)
            label = identity
        guide = file_ref(artifact.get("guideline"), label + " 지침", whole=version == 1)
        kinds = artifact.get("kind")
        kinds = [kinds] if isinstance(kinds, str) else kinds
        if kinds is not None and (not isinstance(kinds, list) or not kinds or not all(text(x) for x in kinds)):
            error(label, "kind는 종류 이름 또는 그 배열")
            kinds = None
        own, common, known = {}, {}, {}
        if guide:
            try:
                key = (guide, tuple(kinds or ()))
                if key not in guides:
                    guides[key] = row_parts(guide, root, kinds)
                own, common, problems = guides[key]
                for problem in problems:
                    error(label + " 지침", problem)
                everything = (guide, ())                  # 종류 밖 · 공통 대상 밖의 행과 지침에서 없어진 행을 가른다
                if everything not in guides:
                    guides[everything] = row_parts(guide, root)
                known = {**guides[everything][0], **guides[everything][1]}
                shared = guide.with_name(COMMON_NAME)
                if guide.name != COMMON_NAME and shared.is_file():
                    known.update(dict.fromkeys(target_rows(shared, guide.stem)[1], ""))
            except (OSError, UnicodeError) as exc:
                error(label + " 지침", str(exc))
        expected = {**own, **common}
        files = artifact.get("files")
        if not isinstance(files, list) or not files:
            error(label, "정본 files 없음")
        else:
            paths = []
            for f in files:
                path = file_ref(f, label + " 정본")
                if path:
                    paths.append(path)
            if len(paths) != len(set(paths)):
                error(label, "정본 files 중복")
        authors, reviewer = artifact.get("authors"), artifact.get("reviewer")
        if not isinstance(authors, list) or not authors or not all(text(x) for x in authors):
            error(label, "작성자 ID 없음")
        elif not text(reviewer) or reviewer.strip() in {x.strip() for x in authors}:
            error(label, "독립 검토자 없음 또는 작성자와 같음")
        rows = artifact.get("criteria")
        if not isinstance(rows, list):
            error(label, "criteria 배열 없음")
            continue
        ids, counts, old_rows, changed, carried = [], Counter(), [], [], 0
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                error(label, f"criteria[{index}] 객체 필요")
                continue
            row_id, state = row.get("id"), row.get("status")
            if known and text(row_id) and row_id not in known:
                old_rows.append(row_id)       # 판정 수에 세지 않고 아래에서 알린다
                continue
            if not text(row_id):
                error(label, f"criteria[{index}] ID 없음")
            else:
                ids.append(row_id)
            item = f"{label} {row_id}"
            if state not in STATES:
                error(item, "잘못된 상태")
            else:
                counts[state] += 1
            if not text(row.get("reason")):
                error(item, "판정 이유/남은 확인 없음")
            if version >= 2 and row_id in expected:
                row_hash = row.get("row_sha256")
                if not isinstance(row_hash, str) or not HASH.fullmatch(row_hash):
                    error(item, "지침 행 SHA256(row_sha256) 형식")
                elif row_hash != expected[row_id]:
                    changed.append(row_id)
                    error(item, "지침 행이 바뀜 — 이 항목만 다시 판정하고 row_sha256을 --틀의 값으로 바꾼다")
                else:
                    carried += 1
            evidence = row.get("evidence", [])
            if not isinstance(evidence, list):
                error(item, "evidence 배열 필요")
                continue
            if state == "통과" and not evidence:
                error(item, "통과 근거 없음")
            for ref in evidence:
                file_ref(ref, item, group=stale)
                if not isinstance(ref, dict) or not text(ref.get("locator")):
                    error(item, "근거 위치 없음")
        if len(ids) != len(set(ids)):
            error(label, "중복 인수 항목")
        must = set(own) | (set(common) if version >= 3 else set())
        lacking, extra = must - set(ids), set(ids) - set(expected)
        if guide and (lacking or extra):
            hint = "" if kinds else " — 일부 종류만 판정하면 산출물에 kind를 적는다"
            error(label, f"인수 항목 누락 {sorted(lacking)}, 초과(종류 · 공통 대상 밖 포함) {sorted(extra)}{hint}")
        unjudged = [] if version >= 3 else [c for c in common if c not in ids]
        if old_rows:
            notices.append(f"{label}: 옛 행 {len(old_rows)}개는 지침에서 없어져 판정에 세지 않음 — 빼고 간 곳의 행을 판정한다: {sorted(old_rows)}")
        if unjudged:
            notices.append(f"{label}: 공통 미판정 {len(unjudged)}개(공통.md 행이 없는 옛 전표) — schema_version 3으로 판정한다")
        if complete and (counts["불통과"] or counts["미확인"]):
            error(label, "불통과/미확인이 남아 완료 불가")
        if complete and (old_rows or unjudged):
            error(label, f"옛 행 {len(old_rows)} · 공통 미판정 {len(unjudged)}이 남아 완료 불가")
        results.append({"id": identity, "counts": {s: counts[s] for s in STATES},
                        "행 잇기": {"이어짐": carried, "바뀜": sorted(changed), "옛 행": sorted(old_rows), "공통 미판정": len(unjudged)}})
    for (ref_path, message), items in stale.items():          # 근거 파일 하나 = 한 줄(그 파일을 근거로 쓴 항목을 함께)
        shown = ", ".join(items[:5]) + (f" 외 {len(items) - 5}곳" if len(items) > 5 else "")
        issues.append(f"근거 {ref_path}: {message} — 이 파일을 근거로 쓴 {len(items)}곳: {shown}")
    if len(found) != len(set(found)):
        error("artifacts", "중복 산출물 ID")
    if set(required) != set(found):
        error("artifacts", f"필수 산출물 누락 {sorted(set(required)-set(found))}, 초과 {sorted(set(found)-set(required))}")
    totals = {s: sum(r["counts"][s] for r in results) for s in STATES}
    return {"artifacts": results, "totals": totals, "issues": issues, "notices": notices,
            "completion_ready": not issues and not notices and not totals["불통과"] and not totals["미확인"],
            "meaning": "항목·판본·근거 연결 검사이며 내용 품질의 자동 판정이 아님"}


def selftest():
    """임시 저장소에 지침 · 공통.md · 정본을 두고 바른 전표가 통과하는지, 하나씩 깨뜨리면 그 판정으로 잡히는지 본다."""
    tmp = Path(tempfile.mkdtemp()).resolve()
    guides = tmp / "지침"
    guides.mkdir()
    head = "| 번호 | 통과 기준 | 확인 방법 |\n|---|---|---|\n"

    def write_docs():
        (guides / "공통.md").write_text(f"# 공통\n\n## 인수 조건\n\n### 원리\n\n{head}| C-1 | 공통 기준 하나 | 본다 |\n\n### 말 (대상: 덱 · 영상)\n\n{head}| C-3 | 덱 · 영상만의 기준 | 본다 |\n\n### 패키지 (대상: 코딩랩 · 가이드)\n\n{head}| C-4 | 코딩랩 · 가이드만의 기준 | 본다 |\n\n### 저장소\n\n{head}| C-2 | 공통 기준 둘 | 본다 |\n", encoding="utf-8")
        (guides / "코딩랩.md").write_text(f"# 코딩랩\n\n## 인수 조건\n\n### 범위\n\n{head}| K-1 | 코딩랩 기준 하나 | 본다 |\n", encoding="utf-8")
        (guides / "덱.md").write_text(f"# 덱\n\n## 인수 조건\n\n### 범위\n\n{head}| D-1 | 덱 기준 하나 | 본다 |\n| D-2 | 덱 기준 둘 | 본다 |\n\n### 그림\n\n{head}| D-3 | 덱 기준 셋 | 본다 |\n", encoding="utf-8")
        (guides / "영상.md").write_text(f"# 영상\n\n## 인수 조건\n\n### 공통 — 시간\n\n{head}| V-1 | 영상 공통 시간 | 본다 |\n\n### 공통 — 말\n\n{head}| V-2 | 영상 공통 말 | 본다 |\n\n### 이론 영상\n\n{head}| V-3 | 이론 영상 기준 | 본다 |\n\n### 실습 영상\n\n{head}| V-4 | 실습 영상 기준 | 본다 |\n", encoding="utf-8")
    write_docs()
    (tmp / "정본.txt").write_text("정본", encoding="utf-8")
    file_hash = hashlib.sha256(b"\xec\xa0\x95\xeb\xb3\xb8").hexdigest()

    def row_hash(*cells):       # 도구 밖에서 따로 계산한 해시: 옛 전표의 값이 바뀌지 않았는지를 잰다
        return hashlib.sha256(" | ".join(cells).encode("utf-8")).hexdigest()

    def artifact(guide, rows, **more):
        return dict({"id": "산출물", "guideline": {"path": f"지침/{guide}"}, "files": [{"path": "정본.txt", "sha256": file_hash}],
                     "authors": ["작성"], "reviewer": "검토",
                     "criteria": [{"id": i, "row_sha256": h, "status": "해당 없음", "reason": "이유"} for i, h in rows.items()]}, **more)

    def sheet(version, art):
        return {"schema_version": version, "required_artifacts": ["산출물"], "artifacts": [art]}

    def rows_of(guide, kinds=None):
        return criteria_of(guides / guide, tmp, kinds)[0]

    cases = []

    def case(name, ok, detail=""):
        cases.append((name, bool(ok), detail))

    def caught(name, version, art, expect, complete=False):
        result = validate(sheet(version, art), root=tmp, complete=complete)
        case(name, any(expect in x for x in result["issues"]), result["issues"][:2])

    # 틀: 공통.md에서 그 지침에 드는 행이 함께 나오고 해시는 그 행의 칸을 이은 글자의 해시 그대로다
    deck = rows_of("덱.md")
    case("--틀이 지침 행과 그 지침에 드는 공통.md 행을 낸다", list(deck) == ["D-1", "D-2", "D-3", "C-1", "C-3", "C-2"], list(deck))
    case("행 해시가 옛 전표와 같은 식이다", deck["D-1"] == row_hash("D-1", "덱 기준 하나", "본다") and deck["C-2"] == row_hash("C-2", "공통 기준 둘", "본다"))
    case("공통.md를 지침으로 주면 공통 전 행", list(rows_of("공통.md")) == ["C-1", "C-3", "C-4", "C-2"], list(rows_of("공통.md")))
    case("다른 일은 다른 공통 절의 행을 낸다", list(rows_of("코딩랩.md")) == ["K-1", "C-1", "C-4", "C-2"], list(rows_of("코딩랩.md")))
    common_path = guides / "공통.md"
    deck_lines = common_ranges(common_path, ["덱"])
    package = next(b for b in common_blocks(common_path) if b[2] == "패키지")
    case("덱이 읽을 줄에 대상 밖 절이 없다", not any(a <= package[0] <= b for a, b in deck_lines), deck_lines)
    case("코딩랩이 읽을 줄에 그 절이 있다", any(a <= package[0] and package[1] <= b for a, b in common_ranges(common_path, ["코딩랩"])), common_ranges(common_path, ["코딩랩"]))
    case("일을 정할 수 없으면 전체", common_ranges(common_path, []) == [(1, len(common_path.read_text(encoding="utf-8").splitlines()))], common_ranges(common_path, []))
    # 종류: 해당 없는 행이 틀에 안 나온다
    theory = rows_of("영상.md", ["이론 영상"])
    case("--종류는 그 종류 · 공통 · 공통.md에서 그 지침에 드는 행만", list(theory) == ["V-1", "V-2", "V-3", "C-1", "C-3", "C-2"], list(theory))
    case("없는 종류는 실패", any("종류 「없는 종류」" in p for p in criteria_of(guides / "영상.md", tmp, ["없는 종류"])[1]))
    case("`### 공통` 없는 지침에 종류는 실패", any("종류로 나뉜 지침이 아님" in p for p in criteria_of(guides / "덱.md", tmp, ["범위"])[1]))
    # 새 전표
    good = validate(sheet(3, artifact("덱.md", deck)), root=tmp, complete=True)
    case("바른 새 전표 통과", good["completion_ready"] and not good["issues"], good["issues"])
    good = validate(sheet(3, artifact("영상.md", theory, kind="이론 영상")), root=tmp, complete=True)
    case("kind를 적은 일부 행 전표 통과", good["completion_ready"] and not good["issues"], good["issues"])
    caught("새 전표에 공통 행이 빠짐", 3, artifact("덱.md", {k: v for k, v in deck.items() if k != "C-2"}), "누락 ['C-2']")
    caught("새 전표에 그 일 대상 공통 행이 빠짐", 3, artifact("덱.md", {k: v for k, v in deck.items() if k != "C-3"}), "누락 ['C-3']")
    package_row = row_hash("C-4", "코딩랩 · 가이드만의 기준", "본다")
    caught("대상 밖 공통 행을 넣음", 3, artifact("덱.md", {**deck, "C-4": package_row}), "공통 대상 밖 포함) ['C-4']")
    result = validate(sheet(3, artifact("덱.md", {**deck, "C-4": package_row})), root=tmp)
    case("대상 밖 공통 행은 옛 행으로 부르지 않는다", not result["notices"] and result["artifacts"][0]["행 잇기"]["옛 행"] == [], result["notices"])
    caught("kind 없이 일부 행만 넣음", 3, artifact("영상.md", theory), "누락 ['V-4']")
    caught("kind 밖의 행을 넣음", 3, artifact("영상.md", rows_of("영상.md"), kind="이론 영상"), "공통 대상 밖 포함) ['V-4']")
    caught("kind 이름이 없는 표", 3, artifact("영상.md", theory, kind="없는 종류"), "종류 「없는 종류」")
    caught("kind 형식이 틀림", 3, artifact("영상.md", theory, kind=[]), "kind는")
    caught("작성자가 검토", 3, artifact("덱.md", deck, reviewer="작성"), "독립 검토자")
    bad = artifact("덱.md", deck)
    bad["files"][0]["sha256"] = "0" * 64
    caught("정본 판본 불일치", 3, bad, "SHA256 불일치")
    # 옛 전표: 재편 전 지침으로 만든 v2 전표(D-1 · D-2 · D-3 · D-9). D-9는 지침에서 없어졌고 D-2는 글자가 바뀐다
    old = artifact("덱.md", {"D-1": deck["D-1"], "D-2": deck["D-2"], "D-3": deck["D-3"], "D-9": row_hash("D-9", "없어진 기준", "본다")})
    result = validate(sheet(2, old), root=tmp)
    links = result["artifacts"][0]["행 잇기"]
    case("옛 전표: 안 바뀐 행이 이어진다", links["이어짐"] == 3 and not links["바뀜"], links)
    case("옛 전표: 없어진 행을 옛 행으로 알린다", links["옛 행"] == ["D-9"] and any("옛 행 1개" in n for n in result["notices"]), result["notices"])
    case("옛 전표: 없어진 행은 판정 수에 세지 않는다", result["totals"]["해당 없음"] == 3, result["totals"])
    case("옛 전표: 그 일에 드는 공통 미판정만 알린다", links["공통 미판정"] == 3 and any("공통 미판정 3개" in n for n in result["notices"]), result["notices"])
    case("옛 전표: 조용히 완료되지 않는다", not result["completion_ready"] and not result["issues"], result["issues"])
    caught("--완료는 공통 행을 다 넣어도 옛 행 하나로 실패", 3, artifact("덱.md", {**deck, "D-9": row_hash("D-9", "없어진 기준", "본다")}), "옛 행 1 · 공통 미판정 0", complete=True)
    clean =artifact("덱.md", {k: deck[k] for k in ("D-1", "D-2", "D-3")})
    caught("옛 전표 --완료는 공통 미판정으로 실패", 2, clean, "공통 미판정 3", complete=True)
    (guides / "덱.md").write_text((guides / "덱.md").read_text(encoding="utf-8").replace("덱 기준 둘", "덱 기준 둘 고침"), encoding="utf-8")
    result = validate(sheet(2, clean), root=tmp)
    links = result["artifacts"][0]["행 잇기"]
    case("옛 전표: 바뀐 행만 실패하고 나머지는 이어진다", links["바뀜"] == ["D-2"] and links["이어짐"] == 2 and any("D-2: 지침 행이 바뀜" in x for x in result["issues"]) and len(result["issues"]) == 1, result["issues"])
    write_docs()
    common_path.write_text(common_path.read_text(encoding="utf-8").replace("(대상: 코딩랩 · 가이드)", "(대상: 코딩 랩 · 가이드)"), encoding="utf-8")
    case("대상 이름 오타는 --틀 · 판정이 실패", any("「코딩 랩」이 문서 이름이 아님" in p for p in criteria_of(guides / "덱.md", tmp)[1]), criteria_of(guides / "덱.md", tmp)[1])
    write_docs()
    (guides / "공통.md").unlink()
    case("지침 폴더에 공통.md가 없으면 실패", any("공통.md이 없음" in p for p in criteria_of(guides / "덱.md", tmp)[1]))
    shutil.rmtree(tmp)
    ok = True
    for name, hit, detail in cases:
        print(f"{'통과' if hit else '실패'}: {name}" + (f" — {detail}" if not hit else ""))
        ok &= hit
    print(f"자가시험 {len(cases)}건 · 실패 {sum(not c[1] for c in cases)}")
    return ok


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest", nargs="?")
    parser.add_argument("--완료", dest="complete", action="store_true")
    parser.add_argument("--출력", dest="output")
    parser.add_argument("--틀", dest="template", metavar="지침")
    parser.add_argument("--종류", dest="kinds", action="append", metavar="이름", help="--틀과 함께: 그 종류 표 · `### 공통` · 공통.md 행만 낸다(여럿이면 되풀이)")
    parser.add_argument("--자가시험", dest="selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return 0 if selftest() else 1
    if not args.manifest and not args.template:
        parser.error("전표 경로 또는 --틀 <지침.md>가 필요하다")
    if args.kinds and not args.template:
        parser.error("--종류는 --틀과 함께 쓴다(전표에서는 산출물의 kind)")
    try:
        if args.template:
            rows, problems = criteria_of(resolve_path(args.template), kinds=args.kinds)
            if problems:
                raise ValueError("; ".join(problems))
            print(json.dumps([{"id": i, "row_sha256": h, "status": "미확인", "reason": "", "evidence": []} for i, h in rows.items()],
                             ensure_ascii=False, indent=2))
            return 0
        path = resolve_path(args.manifest)
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        result = validate(data, complete=args.complete)
        payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            output = resolve_path(args.output)
            protected = {path}
            if isinstance(data, dict):
                for artifact in data.get("artifacts", []):
                    if not isinstance(artifact, dict):
                        continue
                    refs = [artifact.get("guideline")] + artifact.get("files", [])
                    for row in artifact.get("criteria", []):
                        if isinstance(row, dict) and isinstance(row.get("evidence", []), list):
                            refs.extend(row.get("evidence", []))
                    for ref in refs:
                        if isinstance(ref, dict) and text(ref.get("path")):
                            protected.add(resolve_path(ref["path"]))
            if output in protected or not output.is_relative_to(ROOT / "작업"):
                raise ValueError("검사 출력은 입력·정본·지침·근거와 다른 작업 폴더 파일이어야 함")
            output.write_text(payload, encoding="utf-8")
        print(payload, end="")
        return bool(result["issues"])
    except (ValueError, TypeError, KeyError, OSError, UnicodeError) as exc:
        print(json.dumps({"issues": [str(exc)], "completion_ready": False}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
