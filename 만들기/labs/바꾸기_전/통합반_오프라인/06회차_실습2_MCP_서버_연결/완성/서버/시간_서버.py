"""시간 MCP 서버 — 지금 시각을 알려 주고, 시각을 다른 시간대로 바꾸는 도구를 내준다.

실행 방법
    python 시간_서버.py [--local-timezone <시간대>]

    --local-timezone <시간대>   이 서버를 쓰는 사람의 시간대(IANA 이름. 예: Asia/Seoul). 없으면 UTC.
                                도구의 설명에 이 값이 적혀 나가서, 요청에 시간대가 없을 때 모델이 이 값을 넘긴다.

이 서버는 파일도 저장소도 보지 않는다. 접근 범위를 정할 것이 없다.
모델은 오늘이 며칠인지 스스로 알지 못한다. 「내일」「다음 주 금요일」을 날짜로 풀려면 이 도구가 필요하다.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

from mcp_기본 import 기록, 도구_오류, 서버

# 시간대 자료가 없는 PC에서 쓰는 표(서머타임이 없는 곳만 둔다)
고정_차이 = {"UTC": 0, "Asia/Seoul": 9, "Asia/Tokyo": 9, "Asia/Shanghai": 8, "Asia/Singapore": 8,
            "Asia/Ho_Chi_Minh": 7, "Asia/Bangkok": 7, "Asia/Jakarta": 7, "Asia/Kolkata": 5.5, "Asia/Dubai": 4}
요일 = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]


def 시간대(이름: str):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(이름)
    except Exception:
        if 이름 in 고정_차이:
            return timezone(timedelta(hours=고정_차이[이름]), 이름)
    raise 도구_오류(f"입력 오류: 모르는 시간대다 — {이름}. IANA 이름으로 적는다(예: Asia/Seoul, UTC).")


인수들 = sys.argv[1:]
기본 = "UTC"
if "--local-timezone" in 인수들:
    자리 = 인수들.index("--local-timezone") + 1
    if 자리 >= len(인수들):
        기록("시작하지 못함: --local-timezone 뒤에 시간대를 적어야 한다.")
        sys.exit(2)
    기본 = 인수들[자리]
try:
    시간대(기본)
except 도구_오류 as e:
    기록(f"시작하지 못함: {e}")
    sys.exit(2)

s = 서버("time", "1.0.0")


def 적기(t: datetime, 이름: str) -> dict:
    return {"timezone": 이름, "datetime": t.isoformat(timespec="seconds"), "day_of_week": 요일[t.weekday()]}


@s.도구("get_current_time", f"지금 시각을 그 시간대의 날짜, 시각, 요일로 돌려준다. 이 서버의 기본 시간대는 {기본} 이다. 요청에 시간대가 없으면 이 값을 넘긴다.",
        {"timezone": {"type": "string", "description": f"IANA 시간대 이름(예: Asia/Seoul, UTC). 말이 없으면 {기본}"}}, 필수=("timezone",))
def get_current_time(timezone):
    return json.dumps(적기(datetime.now(시간대(timezone)), timezone), ensure_ascii=False, indent=2)


@s.도구("convert_time", f"한 시간대의 시각을 다른 시간대의 시각으로 바꾼다. 날짜는 오늘로 본다. 이 서버의 기본 시간대는 {기본} 이다.",
        {"source_timezone": {"type": "string", "description": "바꾸기 전의 IANA 시간대 이름"},
         "time": {"type": "string", "description": "바꿀 시각. 24시간제 HH:MM (예: 14:30)"},
         "target_timezone": {"type": "string", "description": "바꾼 뒤의 IANA 시간대 이름"}},
        필수=("source_timezone", "time", "target_timezone"))
def convert_time(source_timezone, time, target_timezone):
    try:
        시, 분 = (int(x) for x in time.split(":"))
        출발 = datetime.now(시간대(source_timezone)).replace(hour=시, minute=분, second=0, microsecond=0)
    except ValueError:
        raise 도구_오류(f"입력 오류: time 은 24시간제 HH:MM 으로 적는다 — {time}")
    도착 = 출발.astimezone(시간대(target_timezone))
    차이 = (도착.utcoffset() - 출발.utcoffset()).total_seconds() / 3600
    return json.dumps({"source": 적기(출발, source_timezone), "target": 적기(도착, target_timezone),
                       "time_difference": f"{차이:+g}h"}, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    기록(f"기본 시간대: {기본}")
    s.실행()
