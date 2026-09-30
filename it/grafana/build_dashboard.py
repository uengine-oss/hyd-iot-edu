"""Generate provisioning/dashboards/hyd-trend.json (Grafana 11, TimescaleDB datasource uid 'tsdb').

Design rules applied (dataviz skill): one y-axis per panel, fixed hue per series, reserved status
colors for the 60/65 C thresholds, legend on every multi-series panel, 2 px lines, no dual axes.
Run: python it/grafana/build_dashboard.py
"""
import json
from pathlib import Path

OUT = Path(__file__).with_name("provisioning") / "dashboards" / "hyd-trend.json"
DS = {"type": "grafana-postgresql-datasource", "uid": "tsdb"}

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
         0, 0, 4, 4, unit="celsius", thresholds=[(60, WARN), (65, CRIT)]),
    stat("냉각 효율 CE", "SELECT value FROM tag_1s WHERE asset='$asset' AND name='CE' ORDER BY time DESC LIMIT 1",
         4, 0, 4, 4, unit="percent", thresholds=[(0, CRIT), (70, WARN), (80, GOOD)]),
    stat("이상 점수 (AE 대용)", "SELECT score AS value FROM feat_1s WHERE asset='$asset' AND sensor='TS1' ORDER BY time DESC LIMIT 1",
         8, 0, 4, 4, unit="percentunit", thresholds=[(0.5, WARN), (0.8, CRIT)]),
    stat("활성 경보", "SELECT count(*) AS value FROM alerts WHERE asset='$asset' AND state='RAISE'",
         12, 0, 4, 4, thresholds=[(1, CRIT)]),
    stat("팬 속도 SP", "SELECT value FROM tag_1s WHERE asset='$asset' AND name='FanSpeedSP' ORDER BY time DESC LIMIT 1",
         16, 0, 4, 4, unit="percent", thresholds=[(0, BLUE)]),
    stat("펌프 부하 SP", "SELECT value FROM tag_1s WHERE asset='$asset' AND name='LoadSP' ORDER BY time DESC LIMIT 1",
         20, 0, 4, 4, unit="percent", thresholds=[(0, BLUE)]),

    timeseries("유온 TS1 — 경보(빨강/초록)·승인 조치(파랑) 주석과 함께 감쇠를 확인", [sql_target(tag_sql("TS1"))],
               0, 4, 16, 9, unit="celsius", colors={"TS1": BLUE},
               thresholds=[(60, WARN), (65, CRIT)], ymin=40, ymax=70,
               desc="60 ℃ 경고 · 65 ℃ 인터록 트립. 주석은 alerts / actions 테이블에서 온다."),
    timeseries("이상 점수 (Flink ONNX 오토인코더 자리)", [sql_target(
        "SELECT time, score AS \"score\" FROM feat_1s WHERE asset='$asset' AND sensor='TS1' AND $__timeFilter(time) ORDER BY time")],
        16, 4, 8, 9, unit="percentunit", colors={"score": PURPLE}, thresholds=[(0.8, CRIT)], ymin=0, ymax=1),

    timeseries("냉각 효율 CE · 시스템 효율 SE (%)", [sql_target(tag_sql("CE"), "A"), sql_target(tag_sql("SE"), "B")],
               0, 13, 8, 8, unit="percent", colors={"CE": GREEN, "SE": TEAL}, ymin=0, ymax=100),
    timeseries("냉각 능력 CP (kW 상당)", [sql_target(tag_sql("CP"))],
               8, 13, 8, 8, colors={"CP": PURPLE}),
    timeseries("설정값: 팬 속도 · 펌프 부하 (%)", [sql_target(tag_sql("FanSpeedSP", "FanSpeedSP"), "A"), sql_target(tag_sql("LoadSP", "LoadSP"), "B")],
               16, 13, 8, 8, unit="percent", colors={"FanSpeedSP": AMBER, "LoadSP": BLUE}, ymin=0, ymax=100),

    table("경보 (alerts)", "SELECT raised_at AS \"발생\", cleared_at AS \"해제\", alert_id, pattern, severity, state "
                          "FROM alerts WHERE asset='$asset' ORDER BY raised_at DESC LIMIT 20", 0, 21, 12, 8),
    table("조치 (actions) — 승인된 action.cmd와 PLC ACK",
          "SELECT issued_at AS \"발행\", cmd_id, incident, actions::text AS actions, approved_by, ack_result, ack_reason, ack_at "
          "FROM actions WHERE asset='$asset' ORDER BY issued_at DESC LIMIT 20", 12, 21, 12, 8),
    table("감사 로그 (audit)", "SELECT time, incident, actor, event, detail::text AS detail FROM audit "
                              "WHERE $__timeFilter(time) ORDER BY time DESC LIMIT 50", 0, 29, 24, 9),
]

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
                    "rawSql": "SELECT raised_at AS time, 'RAISE ' || pattern || ' (' || alert_id || ')' AS text, asset AS tags "
                              "FROM alerts WHERE asset='$asset' AND raised_at IS NOT NULL AND $__timeFilter(raised_at)"}},
        {"name": "경보 CLEAR", "datasource": DS, "enable": True, "iconColor": GOOD, "hide": False,
         "target": {"rawQuery": True, "format": "table", "editorMode": "code",
                    "rawSql": "SELECT cleared_at AS time, 'CLEAR ' || pattern AS text, asset AS tags "
                              "FROM alerts WHERE asset='$asset' AND cleared_at IS NOT NULL AND $__timeFilter(cleared_at)"}},
        {"name": "승인 조치", "datasource": DS, "enable": True, "iconColor": BLUE, "hide": False,
         "target": {"rawQuery": True, "format": "table", "editorMode": "code",
                    "rawSql": "SELECT issued_at AS time, '승인 조치 ' || cmd_id || ' by ' || coalesce(approved_by,'?') || ': ' || actions::text AS text, asset AS tags "
                              "FROM actions WHERE asset='$asset' AND $__timeFilter(issued_at)"}},
    ]},
    "panels": panels,
}

if __name__ == "__main__":
    OUT.write_text(json.dumps(dashboard, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({len(panels)} panels)")
