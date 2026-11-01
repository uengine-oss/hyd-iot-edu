"""Generate provisioning/dashboards/hyd-trend.json (Grafana 11, TimescaleDB datasource uid 'tsdb').

Design rules applied (dataviz skill): one y-axis per panel, fixed hue per series, reserved status
colors for the oil-temperature warning / trip lines (ts1_limits — 정본에서 읽는다), legend on every multi-series panel, 2 px lines, no dual axes.
표 · 주석의 글은 학생이 읽는 한국어다: 경보 이름은 alerts.name(connect-sink 가 그래프의 패턴 이름을 붙인다), 열 이름은 한국어.
Run: .venv314/Scripts/python.exe workspace/개발/scripts/build_grafana_dashboard.py   (저장소 루트에서)
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[3] / "it" / "grafana" / "provisioning" / "dashboards" / "hyd-trend.json"
DS = {"type": "grafana-postgresql-datasource", "uid": "tsdb"}


def ts1_limits() -> tuple[float, float]:
    """유온 경고선 · 보호 정지선 — 정본에서 읽는다: 경고 = 쿨러 성능 저하 패턴의 TS1 검사(그래프 시드 it/neo4j/v2/instances.cypher, HM-8.3
    「55 ℃ 초과 경고」), 정지 = PLC 인터록(hydcommon.plant_model.TRIP_TS1). 시드 행을 못 찾으면 멈춘다(다른 값으로 그리지 않는다)."""
    import re
    import sys
    root = Path(__file__).resolve().parents[3]
    m = re.search(r"\['pattern:cooler-degradation'.*?\['in:ts1','TS1','>',(\d+(?:\.\d+)?)", (root / "it/neo4j/v2/instances.cypher").read_text(encoding="utf-8"), re.S)
    if not m:
        raise RuntimeError("it/neo4j/v2/instances.cypher 에서 쿨러 성능 저하 패턴의 TS1 검사 행을 찾지 못했습니다")
    sys.path.insert(0, str(root / "common"))
    from hydcommon.plant_model import TRIP_TS1
    return float(m.group(1)), float(TRIP_TS1)


WARN_TS1, TRIP_TS1 = ts1_limits()

# validated categorical palette (light surface): blue, green, purple, amber, teal
BLUE, GREEN, PURPLE, AMBER, TEAL = "#2563eb", "#059669", "#7c3aed", "#d97706", "#0891b2"
WARN, CRIT, GOOD = "#d97706", "#dc2626", "#059669"

_pid = 0


def pid():
    global _pid
    _pid += 1
    return _pid


def sql_target(sql, ref="A", fmt="time_series"):
    return {"datasource": DS, "refId": ref, "rawQuery": True, "rawSql": sql, "format": fmt, "editorMode": "code"}


def tag_sql(name, alias=None):
    return (f"SELECT time, value AS \"{alias or name}\" FROM tag_1s "
            f"WHERE asset = '$asset' AND name = '{name}' AND $__timeFilter(time) ORDER BY time")


def timeseries(title, targets, x, y, w, h, unit="", colors=None, thresholds=None, ymin=None, ymax=None, desc=""):
    overrides = []
    for series, color in (colors or {}).items():
        overrides.append({"matcher": {"id": "byName", "options": series},
                          "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": color}}]})
    fc = {"defaults": {"unit": unit, "color": {"mode": "palette-classic"},
                       "custom": {"lineWidth": 2, "fillOpacity": 0, "pointSize": 4, "showPoints": "never",
                                  "spanNulls": True, "lineInterpolation": "linear", "axisSoftMin": ymin, "axisSoftMax": ymax},
                       "thresholds": {"mode": "absolute", "steps": [{"color": "transparent", "value": None}]}},
          "overrides": overrides}
    if thresholds:
        fc["defaults"]["thresholds"]["steps"] += [{"color": c, "value": v} for v, c in thresholds]
        fc["defaults"]["custom"]["thresholdsStyle"] = {"mode": "line+area"}
    return {"id": pid(), "type": "timeseries", "title": title, "description": desc, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": targets, "fieldConfig": fc,
            "options": {"legend": {"displayMode": "list", "placement": "bottom", "showLegend": len(targets) > 1},
                        "tooltip": {"mode": "multi", "sort": "none"}}}


def stat(title, sql, x, y, w, h, unit="", thresholds=None, mappings=None):
    steps = [{"color": GOOD, "value": None}] + [{"color": c, "value": v} for v, c in (thresholds or [])]
    return {"id": pid(), "type": "stat", "title": title, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": [sql_target(sql, fmt="table")],
            "fieldConfig": {"defaults": {"unit": unit, "thresholds": {"mode": "absolute", "steps": steps},
                                         "mappings": mappings or []}, "overrides": []},
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "colorMode": "background", "graphMode": "none", "textMode": "value", "justifyMode": "center"}}


def table(title, sql, x, y, w, h):
    return {"id": pid(), "type": "table", "title": title, "datasource": DS,
            "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": [sql_target(sql, fmt="table")],
            "fieldConfig": {"defaults": {"custom": {"align": "auto", "cellOptions": {"type": "auto"}}}, "overrides": []},
            "options": {"showHeader": True, "cellHeight": "sm", "sortBy": []}}


panels = [
    stat("유온 TS1 (현재)", "SELECT value FROM tag_1s WHERE asset='$asset' AND name='TS1' ORDER BY time DESC LIMIT 1",
         0, 0, 4, 4, unit="celsius", thresholds=[(WARN_TS1, WARN), (TRIP_TS1, CRIT)]),
    stat("냉각 효율 CE", "SELECT value FROM tag_1s WHERE asset='$asset' AND name='CE' ORDER BY time DESC LIMIT 1",
         4, 0, 4, 4, unit="percent", thresholds=[(0, CRIT), (70, WARN), (80, GOOD)]),
    stat("이상 점수 · 통계 기반", "SELECT score AS value FROM feat_1s WHERE asset='$asset' AND sensor='TS1' ORDER BY time DESC LIMIT 1",
         8, 0, 4, 4, unit="percentunit", thresholds=[(0.5, WARN), (0.8, CRIT)]),
    stat("활성 경보", "SELECT count(*) AS value FROM alerts WHERE asset='$asset' AND state='RAISE'",
         12, 0, 4, 4, thresholds=[(1, CRIT)]),
    stat("팬 속도 SP", "SELECT value FROM tag_1s WHERE asset='$asset' AND name='FanSpeedSP' ORDER BY time DESC LIMIT 1",
         16, 0, 4, 4, unit="percent", thresholds=[(0, BLUE)]),
    stat("펌프 부하 SP", "SELECT value FROM tag_1s WHERE asset='$asset' AND name='LoadSP' ORDER BY time DESC LIMIT 1",
         20, 0, 4, 4, unit="percent", thresholds=[(0, BLUE)]),

    timeseries("유온 TS1 · 경보와 조치 전후 추이", [sql_target(tag_sql("TS1"))],
               0, 4, 16, 9, unit="celsius", colors={"TS1": BLUE},
               thresholds=[(WARN_TS1, WARN), (TRIP_TS1, CRIT)], ymin=40, ymax=70,
               desc=f"{WARN_TS1:g} ℃ 경고 · {TRIP_TS1:g} ℃ 보호 정지. 빨강은 경보 발생, 초록은 해제, 파랑은 관문을 통과한 설비 명령입니다. 경보·명령 이력과 유온 변화를 함께 비교하세요."),
    timeseries("이상 점수 · 통계 기반", [sql_target(
        "SELECT time, score AS \"score\" FROM feat_1s WHERE asset='$asset' AND sensor='TS1' AND $__timeFilter(time) ORDER BY time")],
        16, 4, 8, 9, unit="percentunit", colors={"score": PURPLE}, thresholds=[(0.8, CRIT)], ymin=0, ymax=1,
        desc="TS1·CE·VS1의 표준화 편차(z-score)를 합산한 실습용 점수입니다. 값이 클수록 정상 기준에서 멀어집니다. 학습된 오토인코더의 출력은 아닙니다."),

    timeseries("냉각 효율 CE · 시스템 효율 SE (%)", [sql_target(tag_sql("CE"), "A"), sql_target(tag_sql("SE"), "B")],
               0, 13, 8, 8, unit="percent", colors={"CE": GREEN, "SE": TEAL}, ymin=0, ymax=100),
    timeseries("냉각 능력 CP (kW 상당)", [sql_target(tag_sql("CP"))],
               8, 13, 8, 8, colors={"CP": PURPLE}),
    timeseries("설정값: 팬 속도 · 펌프 부하 (%)", [sql_target(tag_sql("FanSpeedSP", "FanSpeedSP"), "A"), sql_target(tag_sql("LoadSP", "LoadSP"), "B")],
               16, 13, 8, 8, unit="percent", colors={"FanSpeedSP": AMBER, "LoadSP": BLUE}, ymin=0, ymax=100),

    table("경보 이력", "SELECT name, severity, state, raised_at AS \"발생\", cleared_at AS \"해제\", alert_id "
                          "FROM alerts WHERE asset='$asset' ORDER BY raised_at DESC LIMIT 20", 0, 21, 12, 8),
    table("설비 명령 — 관문을 통과한 명령과 PLC 응답",
          "SELECT issued_at AS \"발행\", cmd_id AS \"명령 번호\", incident AS \"사건\", actions::text AS \"조치 내용\", approved_by AS \"승인한 사람\", "
          "ack_result AS \"PLC 응답\", ack_reason AS \"응답 사유\", ack_at AS \"응답 시각\" "
          "FROM actions WHERE asset='$asset' ORDER BY issued_at DESC LIMIT 20", 12, 21, 12, 8),
    table("처리 기록(감사)", "SELECT time AS \"시각\", incident AS \"사건\", actor AS \"누가\", event AS \"무엇을\", detail::text AS \"내용\" FROM audit "
                              "WHERE $__timeFilter(time) ORDER BY time DESC LIMIT 50", 0, 29, 24, 9),
]

# Presentation aliases preserve query values and the source identifiers.
for panel in panels:
    aliases = {"CE": "냉각 효율 CE", "SE": "시스템 효율 SE", "FanSpeedSP": "팬 속도", "LoadSP": "펌프 부하"}
    for name, label in aliases.items():
        panel["fieldConfig"]["overrides"].append({"matcher": {"id": "byName", "options": name},
            "properties": [{"id": "displayName", "value": label}]})

alert_labels = {"name": ("경보", 180), "severity": ("심각도", 90), "state": ("상태", 100),
                "발생": ("발생 시각", 170), "해제": ("해제 시각", 170), "alert_id": ("경보 번호", 230)}
alert_values = {                                   # 감지기가 내는 심각도 넷(it/detector) · 경보 상태 둘 — 경보 이름은 alerts.name 이 이미 한국어다
    "severity": {"LOW": "낮음", "MEDIUM": "보통", "HIGH": "높음", "CRITICAL": "긴급"},
    "state": {"RAISE": "발생", "CLEAR": "해제"},
}
for name, (label, width) in alert_labels.items():
    props = [{"id": "displayName", "value": label}, {"id": "custom.width", "value": width}]
    if name in alert_values:
        props.append({"id": "mappings", "value": [{"type": "value", "options": {
            key: {"text": text, "index": i} for i, (key, text) in enumerate(alert_values[name].items())}}]})
    panels[11]["fieldConfig"]["overrides"].append({"matcher": {"id": "byName", "options": name}, "properties": props})

dashboard = {
    "uid": "hyd-trend", "title": "HYD 설비 추세 · 경보 · 조치", "tags": ["hyd-iot-edu", "L6"],
    "timezone": "browser", "editable": True, "schemaVersion": 39, "version": 1,
    "refresh": "5s", "time": {"from": "now-10m", "to": "now"},
    "templating": {"list": [{"name": "asset", "label": "설비", "type": "custom", "query": "HYD-01,HYD-02,HYD-03",
                             "current": {"text": "HYD-01", "value": "HYD-01"},
                             "options": [{"text": a, "value": a, "selected": a == "HYD-01"} for a in ("HYD-01", "HYD-02", "HYD-03")]}]},
    "annotations": {"list": [
        {"name": "경보 RAISE", "datasource": DS, "enable": True, "iconColor": CRIT, "hide": False,
         "target": {"rawQuery": True, "format": "table", "editorMode": "code",
                    "rawSql": "SELECT raised_at AS time, '경보 발생 · ' || name || ' (' || alert_id || ')' AS text, asset AS tags "
                              "FROM alerts WHERE asset='$asset' AND raised_at IS NOT NULL AND $__timeFilter(raised_at)"}},
        {"name": "경보 CLEAR", "datasource": DS, "enable": True, "iconColor": GOOD, "hide": False,
         "target": {"rawQuery": True, "format": "table", "editorMode": "code",
                    "rawSql": "SELECT cleared_at AS time, '경보 해제 · ' || name AS text, asset AS tags "
                              "FROM alerts WHERE asset='$asset' AND cleared_at IS NOT NULL AND $__timeFilter(cleared_at)"}},
        {"name": "설비 명령", "datasource": DS, "enable": True, "iconColor": BLUE, "hide": False,
         "target": {"rawQuery": True, "format": "table", "editorMode": "code",
                    "rawSql": "SELECT issued_at AS time, '설비 명령 ' || cmd_id || ' · 승인 ' || approved_by || ' · ' || actions::text AS text, asset AS tags "
                              "FROM actions WHERE asset='$asset' AND $__timeFilter(issued_at)"}},
    ]},
    "panels": panels,
}

if __name__ == "__main__":
    OUT.write_text(json.dumps(dashboard, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({len(panels)} panels)")
