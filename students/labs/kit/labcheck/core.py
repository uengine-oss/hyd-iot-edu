"""확인 결과를 모으는 틀과, 학생 결과를 실행·읽는 공용 도구."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from labkit.settings import KIT_ROOT, project_dir

CLI_TIMEOUT_SECONDS = 60


class Stop(Exception):
    """앞의 기준이 채워지지 않아 이 랩의 나머지 확인을 이어 갈 수 없을 때."""


@dataclass
class Item:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Report:
    lab: str
    title: str
    items: list[Item] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.items) and all(item.ok for item in self.items)

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.items.append(Item(name, bool(ok), "" if ok else detail))
        return bool(ok)

    def require(self, name: str, ok: bool, detail: str = "") -> None:
        if not self.check(name, ok, detail):
            raise Stop

    def equal(self, name: str, actual: Any, expected: Any) -> bool:
        return self.check(name, actual == expected, f"나온 값 {show(actual)} / 기대한 값 {show(expected)}")

    def failed_names(self) -> list[str]:
        return [item.name for item in self.items if not item.ok]


def show(value: Any) -> str:
    if isinstance(value, (set, frozenset)):
        value = sorted(value, key=str)
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= 400 else text[:400] + " …"


def work_path(relative: str) -> Path:
    return project_dir() / "work" / relative


def need_file(report: Report, path: Path, what: str) -> None:
    shown = path.relative_to(project_dir()) if path.is_relative_to(project_dir()) else path
    report.require(f"{what} 파일이 있다({shown})", path.is_file(), "이 랩에서 만들어야 하는 파일이 아직 없습니다.")


def read_json(report: Report, path: Path, what: str) -> Any:
    need_file(report, path, what)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        report.require(f"{what} 파일을 JSON 으로 읽을 수 있다", False, f"{path.name}: {error}")


def run_script(script: Path, *args: str) -> subprocess.CompletedProcess:
    """학생이 만든 프로그램을 키트 폴더에서 실행한다(labkit 을 쓸 수 있게 경로를 잡아 준다)."""
    env = {**os.environ, "PYTHONPATH": f"{KIT_ROOT}{os.pathsep}{script.parent}", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, str(script), *args], cwd=KIT_ROOT, env=env,
                          capture_output=True, text=True, timeout=CLI_TIMEOUT_SECONDS)


def run_json(report: Report, script: Path, *args: str) -> Any:
    """프로그램을 실행해 표준 출력의 JSON 을 읽는다. 실행 실패나 JSON 이 아니면 그 자리에서 멈춘다."""
    command = f"python work/{script.name} {' '.join(args)}"
    done = run_script(script, *args)
    report.require(f"실행된다: {command}", done.returncode == 0, f"종료 코드 {done.returncode}. 오류 출력: {done.stderr.strip()[-600:]}")
    try:
        return json.loads(done.stdout)
    except json.JSONDecodeError:
        report.require(f"JSON 을 출력한다: {command}", False, f"출력 앞부분: {done.stdout.strip()[:300]}")


def ids(items: list[dict], key: str = "id") -> set:
    return {item.get(key) for item in items}
