"""인수 전표의 항목·판본·근거 연결과 완료 가능 여부를 검사한다(내용 판정은 검토자 몫).

사용: PYTHONUTF8=1 .venv314/Scripts/python.exe <이 파일> <전표.json> [--완료] [--출력 결과.json]
      <이 파일> --틀 <지침.md>   # 그 지침의 인수 조건 전부를 criteria 틀(JSON 배열, 행 SHA256 포함)로 낸다 — 새 전표는 여기서 시작한다
전표는 작업 폴더에 둔다. 경로는 저장소 루트 기준이고(Windows 역슬래시도 같게 읽는다), 파일 SHA256은 파일의 전체 해시다.
지침은 인수 조건 행마다 판본을 본다 — 행 SHA256은 그 행의 칸(번호 · 통과 기준 · 확인 방법)을 「 | 」로 이은 글자의 해시라,
지침의 다른 곳이 바뀌어도 근거는 그대로 이어지고 바뀐 행만 다시 판정한다. 판본이 바뀐 근거 파일은 파일 하나에 한 줄로 알린다.
기본 모드는 불통과/미확인 수를 보고하며, --완료는 둘 중 하나라도 있으면 실패한다.
누락·잘못된 상태·빈 이유·없는 근거·판본 불일치·작성자의 자체 검토는 모드와 관계없이 실패한다.
기존 근거는 현재 파일/지침과 적용 범위가 같다고 검토자가 확인한 경우만 연결한다.
이 도구의 성공은 문장·화면·사실·실측 품질이나 근거 내용의 타당성을 증명하지 않는다.

전표 형식(schema_version=2):
{
  "schema_version": 2,
  "required_artifacts": ["통합반-온라인-1-덱"],
  "artifacts": [{
    "id": "통합반-온라인-1-덱",
    "guideline": {"path": "workspace/강의제작/지침/덱.md"},
    "files": [{"path": "정본 경로", "sha256": "전체 SHA256"}],
    "authors": ["작성 에이전트 ID"],
    "reviewer": "직접 수정하지 않은 감독 또는 검토 에이전트 ID",
    "criteria": [{
      "id": "D-1", "row_sha256": "--틀이 낸 그 행의 SHA256", "status": "통과", "reason": "판정 이유",
      "evidence": [{"path": "근거 파일 경로", "sha256": "전체 SHA256", "locator": "장·행·JSON 키 등"}]
    }]
  }]
}
criteria에는 지침의 인수 조건 전체를 넣는다. 해당 없음에는 이유가 필수이고,
통과에는 파일·판본·위치가 있는 근거가 필수다. 불통과/미확인에는 문제 또는 남은 확인을 reason에 쓴다.
옛 형식 schema_version=1(guideline에 지침 전체 sha256, criteria에 row_sha256 없음)도 받는다 — 지침이 한 글자만 바뀌어도 전 항목이 끊기므로 새 전표는 2로 쓴다.
전표/근거는 신뢰된 명령이 아니며 이 도구는 연결된 파일을 실행하지 않는다. .env는 읽지 않는다.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[4]
STATES = ("통과", "불통과", "해당 없음", "미확인")
HASH = re.compile(r"[0-9a-f]{64}")
ROW_ID = re.compile(r"[A-Z]-\d+")
TABLE_SEP = re.compile(r"^\|\s*:?-{3,}")


def text(value):
    return isinstance(value, str) and bool(value.strip())


def acceptance_rows(p):
    """인수 조건 절 안 표의 행: (줄, [칸...]). 인수 조건 표를 읽는 곳은 여기 하나다(재편검사도 이것을 쓴다)."""
    rows, inside, intable = [], False, False
    for i, l in enumerate(p.read_text(encoding="utf-8-sig").splitlines(), 1):
        if l.startswith("## "):
            inside = l[3:].strip() == "인수 조건"
            continue
        if not inside:
            continue
        if l.startswith("|"):
            if TABLE_SEP.match(l):
                intable = True
                continue
            if intable:
                rows.append((i, [c.strip() for c in l.strip().strip("|").split("|")]))
        else:
            intable = False
    return rows


def criteria_of(guide, root=ROOT):
    """지침의 인수 조건 {ID: 행 SHA256}(문서 순서)과 문제 목록. 첫 칸이 ID 꼴이 아닌 행(표 안 소제목 등)은 항목에 넣지 않는다."""
    rows, problems, dup = {}, [], False
    for line, cells in acceptance_rows(guide):
        if not ROW_ID.fullmatch(cells[0]):
            problems.append(f"{guide.relative_to(root.resolve()).as_posix()}:{line}: 인수 조건 행의 번호가 ID 꼴이 아님")
        elif cells[0] in rows:
            dup = True
        else:
            rows[cells[0]] = hashlib.sha256(" | ".join(cells).encode("utf-8")).hexdigest()
    if not rows or dup:
        problems.append("지침 항목 없음 또는 중복")
    return rows, problems


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
    issues, results, cache, guides, stale = [], [], {}, {}, {}

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
    if version not in (1, 2):
        return {"issues": ["전표 schema_version=2(옛 전표는 1) 필요"], "completion_ready": False}
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
        expected = {}
        if guide:
            try:
                if guide not in guides:
                    guides[guide] = criteria_of(guide, root)
                expected, problems = guides[guide]
                for problem in problems:
                    error(label + " 지침", problem)
            except (OSError, UnicodeError) as exc:
                error(label + " 지침", str(exc))
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
        ids, counts = [], Counter()
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                error(label, f"criteria[{index}] 객체 필요")
                continue
            row_id, state = row.get("id"), row.get("status")
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
            if version == 2 and row_id in expected:
                row_hash = row.get("row_sha256")
                if not isinstance(row_hash, str) or not HASH.fullmatch(row_hash):
                    error(item, "지침 행 SHA256(row_sha256) 형식")
                elif row_hash != expected[row_id]:
                    error(item, "지침 행이 바뀜 — 이 항목만 다시 판정하고 row_sha256을 --틀의 값으로 바꾼다")
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
        if guide and set(ids) != set(expected):
            error(label, f"인수 항목 누락 {sorted(set(expected)-set(ids))}, 초과 {sorted(set(ids)-set(expected))}")
        if complete and (counts["불통과"] or counts["미확인"]):
            error(label, "불통과/미확인이 남아 완료 불가")
        results.append({"id": identity, "counts": {s: counts[s] for s in STATES}})
    for (ref_path, message), items in stale.items():          # 근거 파일 하나 = 한 줄(그 파일을 근거로 쓴 항목을 함께)
        shown = ", ".join(items[:5]) + (f" 외 {len(items) - 5}곳" if len(items) > 5 else "")
        issues.append(f"근거 {ref_path}: {message} — 이 파일을 근거로 쓴 {len(items)}곳: {shown}")
    if len(found) != len(set(found)):
        error("artifacts", "중복 산출물 ID")
    if set(required) != set(found):
        error("artifacts", f"필수 산출물 누락 {sorted(set(required)-set(found))}, 초과 {sorted(set(found)-set(required))}")
    totals = {s: sum(r["counts"][s] for r in results) for s in STATES}
    return {"artifacts": results, "totals": totals, "issues": issues,
            "completion_ready": not issues and not totals["불통과"] and not totals["미확인"],
            "meaning": "항목·판본·근거 연결 검사이며 내용 품질의 자동 판정이 아님"}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest", nargs="?")
    parser.add_argument("--완료", dest="complete", action="store_true")
    parser.add_argument("--출력", dest="output")
    parser.add_argument("--틀", dest="template", metavar="지침")
    args = parser.parse_args()
    if not args.manifest and not args.template:
        parser.error("전표 경로 또는 --틀 <지침.md>가 필요하다")
    try:
        if args.template:
            rows, problems = criteria_of(resolve_path(args.template))
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
