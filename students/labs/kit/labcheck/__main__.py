"""랩 자동 확인 실행.

    python -m labcheck 2-1       랩 하나(2일차 첫째 랩)
    python -m labcheck day2      하루치
    python -m labcheck list      랩 목록
"""
from __future__ import annotations

import sys

from labcheck import day2, day3, day4, day5, day6, day7
from labcheck.core import Report, Stop

DAYS = {"day2": day2, "day3": day3, "day4": day4, "day5": day5, "day6": day6, "day7": day7}
LABS = {number: entry for module in DAYS.values() for number, entry in module.LABS.items()}
EXIT_FAILED = 1
EXIT_BLOCKED = 2


def run_lab(number: str) -> Report:
    title, function = LABS[number]
    report = Report(number, title)
    try:
        function(report)
    except Stop:
        pass
    return report


def print_report(report: Report) -> None:
    print(f"\n랩 {report.lab} · {report.title}")
    for item in report.items:
        print(f"  [{'통과' if item.ok else '미통과'}] {item.name}")
        if item.detail:
            print(f"           → {item.detail}")
    failed = len(report.failed_names())
    print(f"  결과: {'성공 기준을 모두 채웠습니다.' if report.passed else f'{failed}개가 아직 채워지지 않았습니다.'}")


def selected(argument: str) -> list[str]:
    if argument in LABS:
        return [argument]
    if argument in DAYS:
        return list(DAYS[argument].LABS)
    raise SystemExit(f"모르는 랩입니다: {argument}. 'python -m labcheck list' 로 목록을 볼 수 있습니다.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    if sys.argv[1] == "list":
        for number, (title, _) in LABS.items():
            print(f"{number}  {title}")
        return
    reports = []
    for number in selected(sys.argv[1]):
        try:
            reports.append(run_lab(number))
        except Exception as error:  # 연결 실패처럼 확인 자체를 못 한 경우: 통과로도 미통과로도 세지 않는다
            print(f"\n랩 {number} 을 확인할 수 없습니다: {type(error).__name__}: {error}", file=sys.stderr)
            print("연습용 그래프 · DB · 판단 MCP 가 켜져 있는지(docker compose ps), .env 값이 맞는지 확인하세요.", file=sys.stderr)
            raise SystemExit(EXIT_BLOCKED) from error
        print_report(reports[-1])
    raise SystemExit(0 if all(report.passed for report in reports) else EXIT_FAILED)


if __name__ == "__main__":
    main()
