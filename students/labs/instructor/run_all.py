"""정답 예로 랩 21개를 처음부터 끝까지 차례로 수행하고, 랩마다 자동 확인이 통과하는지 본다.

    python instructor/run_all.py                 # 임시 폴더에서 수행하고 지운다
    python instructor/run_all.py --project DIR   # DIR 에 학생 폴더 모양으로 남긴다(빈 폴더여야 한다)

연습용 그래프를 비우고 시작한다. 랩용 실행 환경(kit/compose.yaml)이 켜져 있어야 한다.
5일차 답 파일은 AI 를 부르지 않고 도구의 실제 반환값으로 조립한 기대 출력 예다(tools/expected_answers.py).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

import labpaths  # noqa: E402
import expected_answers  # noqa: E402
import mcp_records  # noqa: E402
from labcheck import graphstate  # noqa: E402
from labkit import prepared_graph, reset_graph  # noqa: E402
from labkit.graph import graph_session  # noqa: E402

KIT = labpaths.KIT
ANSWERS = labpaths.ANSWERS
WHAT_IF_MINUTES = "30"


class LabRun:
    """학생 폴더 하나(project)에서 정답 예를 놓고, 실행하고, 확인한다."""

    def __init__(self, project: Path):
        self.project = project
        self.work = project / "work"
        self.env = {**os.environ, "LAB_PROJECT_DIR": str(project), "PYTHONPATH": f"{KIT}{os.pathsep}{self.work}", "PYTHONIOENCODING": "utf-8"}

    def put(self, *relatives: str, source: Path = ANSWERS) -> None:
        for relative in relatives:
            origin, target = source / relative, self.project / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if origin.is_dir():
                shutil.copytree(origin, target, dirs_exist_ok=True)
            else:
                shutil.copy2(origin, target)

    def run(self, *command: str) -> str:
        done = subprocess.run([sys.executable, *command], cwd=KIT, env=self.env, capture_output=True, text=True)
        if done.returncode != 0:
            raise RuntimeError(f"실행 실패: {' '.join(command)}\n{done.stdout}\n{done.stderr}")
        return done.stdout

    def script(self, name: str, *args: str) -> str:
        return self.run(str(self.work / name), *args)

    def check(self, lab: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", "labcheck", lab], cwd=KIT, env=self.env, capture_output=True, text=True)

    def call_tool(self, name: str, arguments: dict) -> dict:
        return json.loads(self.run("-m", "labcheck.tool_driver", str(self.work / "agent"), "call", name, json.dumps(arguments, ensure_ascii=False)))

    def write_json(self, relative: str, value) -> None:
        target = self.work / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def agent_answers(self, *question_ids: str) -> None:
        questions = {q["id"]: q for q in json.loads((KIT / "day5" / "questions.json").read_text(encoding="utf-8"))["questions"]}
        for question_id in question_ids:
            self.write_json(f"agent/answers/{question_id}.json", expected_answers.build(questions, self.call_tool, question_id))

    # ── 랩별 수행 ─────────────────────────────────────────────
    def lab2_1(self) -> None:
        self.put("work/schema.json", "work/apply_schema.py")
        self.script("apply_schema.py")

    def lab2_2(self) -> None:
        self.put("work/load_csv.py")
        self.script("load_csv.py")

    def lab2_3(self) -> None:
        self.put("work/find_related.py")

    def lab3_1(self) -> None:
        self.put("work/decision_table.json", "work/evaluate.py")

    def lab3_2(self) -> None:
        """새로 만드는 파일 없음: 3-1 에서 만든 평가 프로그램에 준비된 입력을 넣어 본다."""

    def lab3_3(self) -> None:
        self.put("work/load_effects.py", "work/action_effects.py")
        self.script("load_effects.py")

    def lab4_1(self) -> None:
        self.put("work/split_manual.py", "work/candidates.json")
        self.script("split_manual.py")

    def lab4_2(self) -> None:
        self.put("work/review.json", "work/register_candidates.py")
        self.script("register_candidates.py")

    def lab4_3(self) -> None:
        self.put("work/lookup.py")

    def lab4_4(self) -> None:
        """새로 만드는 파일 없음: 4-3 의 조회 기능에 질문을 바꿔 넣는다."""

    def lab5_1(self) -> None:
        self.put("work/agent/system_prompt.md", "work/agent/agent.py")
        questions = {q["id"]: q for q in json.loads((KIT / "day5" / "questions.json").read_text(encoding="utf-8"))["questions"]}
        self.write_json("agent/answers/draft_q1.json", expected_answers.draft(questions["q1"]))

    def lab5_2(self) -> None:
        self.put("work/agent/tools.py")
        self.agent_answers("q1", "q2")

    def lab5_3(self) -> None:
        self.agent_answers("q3", "q4", "q5")

    def lab6_1(self) -> None:
        self.put(".claude", "work/meeting", source=ANSWERS / "lab6_1")

    def lab6_2(self) -> None:
        with graph_session() as session:
            before = graphstate.counts(session)
        prepared_graph.load()
        with graph_session() as session:
            after = graphstate.counts(session)
        if before != after:
            raise RuntimeError(f"준비된 그래프가 2~4일차 정답 예의 그래프와 다릅니다: 넣기 전 {before}, 넣은 뒤 {after}")
        shutil.copy2(KIT / "day6" / "mcp" / "lab.mcp.json", self.project / ".mcp.json")
        self.write_json("mcp/q_relations.json", mcp_records.relations_record(self.project))

    def lab6_3(self) -> None:
        self.write_json("mcp/chain.json", mcp_records.chain_record(self.project))

    def lab6_4(self) -> None:
        self.put(".claude", "work/meeting")

    def lab6_5(self) -> None:
        config_file = self.project / ".mcp.json"
        config = json.loads(config_file.read_text(encoding="utf-8"))
        notion = json.loads((KIT / "day6" / "notion" / "notion.mcp.example.json").read_text(encoding="utf-8"))
        config["mcpServers"].update(notion["mcpServers"])
        config_file.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def lab7_1(self) -> None:
        self.put("work/recommend.py")
        case = str(KIT / "day7" / "inputs" / "case_base.json")
        self.script("recommend.py", "--case", case, "--out", str(self.work / "day7" / "proposal_base.json"))
        self.script("recommend.py", "--case", case, "--available-minutes", WHAT_IF_MINUTES, "--out", str(self.work / "day7" / "proposal_whatif.json"))

    def lab7_2(self) -> None:
        self.put("work/review.py")
        case = str(KIT / "day7" / "inputs" / "case_base.json")
        for name in ("ok", "missing_evidence"):
            proposal = str(KIT / "day7" / "inputs" / f"proposal_{name}.json")
            (self.work / "day7" / f"review_{name}.json").write_text(self.script("review.py", "--case", case, "--proposal", proposal), encoding="utf-8")

    def lab7_3(self) -> None:
        self.put("work/hitl.py")


LAB_ORDER = ["2-1", "2-2", "2-3", "3-1", "3-2", "3-3", "4-1", "4-2", "4-3", "4-4", "5-1", "5-2", "5-3", "6-1", "6-2", "6-3", "6-4", "6-5", "7-1", "7-2", "7-3"]


def run_all(project: Path, log: Callable[[str], None] = print) -> dict[str, bool]:
    """그래프를 비우고 랩을 순서대로 수행한다. 랩 번호 → 자동 확인 통과 여부."""
    reset_graph.reset()
    lab_run = LabRun(project)
    results: dict[str, bool] = {}
    for lab in LAB_ORDER:
        getattr(lab_run, f"lab{lab.replace('-', '_')}")()
        done = lab_run.check(lab)
        results[lab] = done.returncode == 0
        log(done.stdout.rstrip() if done.stdout.strip() else done.stderr.rstrip())
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="정답 예로 랩 완주")
    parser.add_argument("--project", help="결과를 남길 빈 폴더")
    args = parser.parse_args()
    if args.project:
        project = Path(args.project).resolve()
        project.mkdir(parents=True, exist_ok=True)
        if any(project.iterdir()):
            raise SystemExit(f"{project} 가 비어 있지 않습니다. 빈 폴더를 주세요.")
        results = run_all(project)
    else:
        with tempfile.TemporaryDirectory(prefix="cooler-lab-") as folder:
            results = run_all(Path(folder))
    failed = [lab for lab, ok in results.items() if not ok]
    print(f"\n완주 결과: {len(results) - len(failed)}/{len(results)} 랩 통과" + (f", 미통과 {failed}" if failed else ""))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
