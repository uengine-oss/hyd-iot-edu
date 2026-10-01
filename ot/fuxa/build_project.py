"""Generate ot/fuxa/project.json — a FUXA 1.3 project bound to the OT MQTT topics.

FUXA facts used here (read from the server source in the frangoteam/fuxa image):
  * devices[id] = {id, name, type:'MQTTclient', property:{address}, tags:{tagId:{id,name,type:'json',address,memaddress,options:{subs:[key]}}}}
  * a json tag with options.subs + memaddress reads payload[memaddress]; writing it publishes {memaddress: value}
  * view items reference tags with property.variableId = f"{deviceId}^~^{tagId}"
  * svgcontent must contain an element whose id == item id (widget markup copied from the demo project)
  * alarms[] = {name, property:{variableId}, high:{enabled,checkdelay,min,max,text,group,bkcolor,color,ackmode}, highhigh:{...}, ...}
Run:  python ot/fuxa/build_project.py
"""
import json
import uuid
from pathlib import Path

ASSETS = ["HYD-01", "HYD-02", "HYD-03"]
DEV = "emqx"
OUT = Path(__file__).with_name("project.json")

W, H = 1180, 720
COL_W = 372
COL_X0 = 20


def uid(prefix):
    return f"{prefix}_{uuid.uuid4()}"


def key(asset):
    return asset.replace("-", "").lower()


# ------------------------------------------------------------------ tags
def build_tags():
    tags = {}
    for a in ASSETS:
        k = key(a)
        for name in ("TS1", "CE", "CP", "SE", "FanSpeedSP", "LoadSP", "VS1", "PS1"):
            tags[f"{k}_{name}"] = {"id": f"{k}_{name}", "name": f"{a} {name}", "type": "json",
                                   "address": f"plant/{k}/tag/{name}", "memaddress": "v", "options": {"subs": ["v"]}}
        for fld in ("mode", "state", "result", "reason"):
            source = fld + "_text"
            tags[f"{k}_{fld}"] = {"id": f"{k}_{fld}", "name": f"{a} {fld}", "type": "json",
                                  "address": f"plant/{k}/status", "memaddress": source, "options": {"subs": [source]}}
        tags[f"{k}_alert"] = {"id": f"{k}_alert", "name": f"{a} IT alert level", "type": "json",
                              "address": f"plant/{k}/alert", "memaddress": "level", "options": {"subs": ["level"]}}
        tags[f"{k}_alert_text"] = {"id": f"{k}_alert_text", "name": f"{a} IT alert text", "type": "json",
                                   "address": f"plant/{k}/alert", "memaddress": "display_text", "options": {"subs": ["display_text"]}}
        # writes (FUXA -> PLC). retain must be false for command topics (v3: cmd retained 금지)
        for res in ("FanSpeedSP", "LoadSP", "Reset"):
            tags[f"{k}_cmd_{res}"] = {"id": f"{k}_cmd_{res}", "name": f"{a} write {res}", "type": "json",
                                      "address": f"plant/{k}/cmd/manual", "memaddress": res,
                                      "options": {"subs": [res], "retain": False}}
        tags[f"{k}_mode_set"] = {"id": f"{k}_mode_set", "name": f"{a} set mode", "type": "json",
                                 "address": f"plant/{k}/mode", "memaddress": "mode",
                                 "options": {"subs": ["mode"], "retain": False}}
    return tags


# ------------------------------------------------------------------ widgets (markup copied from FUXA demo)
class View:
    def __init__(self):
        self.items = {}
        self.svg = []

    def text(self, x, y, s, size=14, color="#1f2937", weight="normal", anchor="start"):
        self.svg.append(f'<text x="{x}" y="{y}" font-family="sans-serif" font-size="{size}" font-weight="{weight}" '
                        f'fill="{color}" text-anchor="{anchor}" xml:space="preserve">{s}</text>')

    def rect(self, x, y, w, h, fill="#ffffff", stroke="#d1d5db", rx=8):
        self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>')

    def value(self, x, y, tag, name, unit="", w=90, size=16, color="#111827"):
        iid = uid("VAL")
        self.items[iid] = {"id": iid, "type": "svg-ext-value", "name": name, "label": "Value",
                           "property": {"events": [], "variable": name, "variableId": tag, "variableSrc": DEV,
                                        "alarmId": "", "alarmSrc": "", "alarm": "", "alarmColor": "",
                                        "ranges": [{"type": "unit", "min": 0, "max": 0, "text": unit}]}}
        self.svg.append(
            f'<g id="{iid}" text-anchor="end" font-family="sans-serif" stroke-width="0" font-size="{size}" fill="none" type="svg-ext-value">'
            f'<text id="{uid("VAL")}" y="{y}" x="{x + w}" xml:space="preserve" text-anchor="end" font-family="sans-serif" '
            f'font-size="{size}" fill="{color}" stroke-width="0">–</text></g>')

    def progress(self, x, y, w, h, tag, name, vmin=0, vmax=100, color="#4f8df5"):
        iid = uid("GXP")
        self.items[iid] = {"id": iid, "type": "svg-ext-gauge_progress", "name": name, "label": "HtmlProgress",
                           "property": {"events": [], "alarmId": "", "alarmSrc": "", "alarm": "", "alarmColor": "",
                                        "ranges": [{"type": "minmax", "min": vmin, "max": vmax, "style": [True, True], "color": color}],
                                        "variable": name, "variableId": tag, "variableSrc": DEV}}
        self.svg.append(
            f'<g font-family="sans-serif" font-size="14" type="svg-ext-gauge_progress" id="{iid}" stroke="null">'
            f'<rect fill="#e5e7eb" height="{h}" width="{w}" y="{y}" x="{x}" id="A-{uid("GXP")}" stroke="null"/>'
            f'<rect fill="{color}" height="{h // 2}" width="{w}" y="{y + h // 2}" x="{x}" id="B-{uid("GXP")}" stroke="null"/>'
            f'<foreignObject font-size="14" id="H-{uid("GXP")}" width="{w}" height="{h}" y="{y}" x="{x}"/></g>')

    def semaphore(self, x, y, tag, name, r=14):
        iid = uid("GSE")
        self.items[iid] = {"id": iid, "type": "svg-ext-gauge_semaphore", "name": name, "label": "HtmlSemaphore",
                           "property": {"events": [], "variable": name, "variableId": tag, "variableSrc": DEV,
                                        "alarmId": "", "alarmSrc": "", "alarm": "", "alarmColor": "",
                                        "ranges": [{"type": "range", "min": "0", "max": "0", "color": "#22c55e"},
                                                   {"type": "range", "min": "2", "max": "2", "color": "#ef4444"}]}}
        self.svg.append(
            f'<g type="svg-ext-gauge_semaphore" fill="#000000" font-size="14" stroke="#000000" font-family="sans-serif" id="{iid}">'
            f'<ellipse cx="{x}" cy="{y}" rx="{r}" ry="{r}" fill="#bfbfbf" stroke="#9ca3af" id="{uid("GSE")}"/></g>')

    def input(self, x, y, w, h, tag, name):
        iid = uid("HXI")
        self.items[iid] = {"id": iid, "type": "svg-ext-html_input", "name": name, "label": "HtmlInput",
                           "property": {"events": [], "variable": name, "variableId": tag, "variableSrc": DEV,
                                        "alarmId": "", "alarmSrc": "", "alarm": "", "alarmColor": ""}}
        h1, h2 = uid("HXI"), uid("HXI")
        self.svg.append(
            f'<g id="{iid}" stroke="#000000" text-anchor="right" font-family="sans-serif" font-size="14" fill="#f1f1f1ff" type="svg-ext-html_input">'
            f'<rect id="{uid("svg")}" stroke="null" fill="#ffffff" height="{h}" width="{w}" y="{y}" x="{x}" stroke-width="0"/>'
            f'<foreignObject id="H-{h1}" width="{w}" height="{h}" y="{y}" x="{x}">'
            f'<INPUT id="I-{h2}" aria-label="{name}" title="값을 입력하고 Enter로 적용" style="width: calc(100% - 7px); height: calc(100% - 7px); text-align: right; border: 1px solid #9ca3af; '
            f'background-color: rgb(255, 255, 255); color: rgb(0, 0, 0); vector-effect: non-scaling-stroke;" type="text"/>'
            f'</foreignObject></g>')

    def button(self, x, y, w, h, tag, name, label, value, bg="#2563eb"):
        iid = uid("HXB")
        self.items[iid] = {"id": iid, "type": "svg-ext-html_button", "name": name, "label": "HtmlButton",
                           "property": {"events": [{"type": "click", "action": "onSetValue", "actparam": str(value)}],
                                        "variable": name, "variableId": tag, "variableSrc": DEV,
                                        "alarmId": "", "alarmSrc": "", "alarm": "", "alarmColor": ""}}
        h1 = uid("HXB")
        self.svg.append(
            f'<g id="{iid}" type="svg-ext-html_button" fill="#FFFFFF" font-size="14" font-family="sans-serif" text-anchor="right" stroke="#000000">'
            f'<rect stroke-width="0" x="{x}" y="{y}" width="{w}" height="{h}" fill="{bg}" id="{uid("svg")}" stroke="#ffffff"/>'
            f'<foreignObject x="{x}" y="{y}" height="{h}" width="{w}" id="H-{h1}">'
            f'<BUTTON style="width: 100%; height: 100%; vector-effect: non-scaling-stroke; background-color: {bg}; color: rgb(255, 255, 255);" '
            f'class="md-btn  md-btn-raised" id="B-{h1}">{label}</BUTTON></foreignObject></g>')

    def select(self, x, y, w, h, tag, name, steps):
        iid = uid("HXS")
        self.items[iid] = {"id": iid, "type": "svg-ext-html_select", "name": name, "label": "HtmlSelect",
                           "property": {"events": [], "variable": name, "variableId": tag, "variableSrc": DEV,
                                        "alarmId": "", "alarmSrc": "", "alarm": "", "alarmColor": "",
                                        "ranges": [{"type": "step", "min": str(v), "max": str(v), "text": t} for v, t in steps]}}
        h1 = uid("HXS")
        self.svg.append(
            f'<g text-anchor="right" font-family="sans-serif" font-size="14" fill="#000000" type="svg-ext-html_select" id="{iid}">'
            f'<rect id="{uid("svg")}" fill="#ffffff" height="{h}" width="{w}" y="{y}" x="{x}" stroke-width="0"/>'
            f'<foreignObject id="H-{h1}" width="{w}" height="{h}" y="{y}" x="{x}">'
            f'<SELECT aria-label="{name}" style="width:100%;height:100%;text-align: right;margin-top:unset;" id="S-{h1}"><OPTION/></SELECT>'
            f'</foreignObject></g>')

    def render(self):
        body = "\n".join(self.svg)
        return (f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" xmlns:svg="http://www.w3.org/2000/svg" '
                f'xmlns:html="http://www.w3.org/1999/xhtml"><g><title>Layer 1</title>\n{body}\n</g></svg>')


def build_view():
    v = View()
    v.text(30, 40, "유압설비 운전 화면 — HYD-01 ~ 03 (OT · FUXA)", size=22, weight="bold", color="#111827")
    v.text(30, 62, "설비 상태를 확인하고 팬 속도·부하·운전 모드를 직접 조작합니다.",
           size=12, color="#6b7280")
    for i, a in enumerate(ASSETS):
        k = key(a)
        v.svg.append(f'<svg class="hyd-unit hyd-unit-{i}" x="{COL_X0+i*(COL_W+15)}" y="85" width="{COL_W}" height="630" viewBox="0 0 {COL_W} 630" preserveAspectRatio="xMinYMin meet">')
        x, y = 0, 0
        v.rect(x, y, COL_W, 625, fill="#f9fafb")
        v.text(x + 16, y + 30, a, size=20, weight="bold", color="#1e3a8a")
        v.text(x + 104, y + 30, "경보", size=12, color="#6b7280")
        v.semaphore(x + 150, y + 25, f"{k}_alert", f"{a} alert", r=10)
        v.text(x + 175, y + 30, "현재 모드", size=12, color="#6b7280")
        v.value(x + 240, y + 30, f"{k}_mode", f"{a} mode", w=112, size=12, color="#374151")
        v.text(x + 175, y + 52, "PLC 상태", size=11, color="#6b7280")
        v.value(x + 277, y + 52, f"{k}_state", f"{a} state", w=75, size=13, color="#374151")

        # TS1 bar + big number
        v.text(x + 16, y + 70, "유온 TS1 (℃)", size=13, color="#374151")
        v.progress(x + 16, y + 80, 40, 220, f"{k}_TS1", f"{a} TS1", 0, 100, "#f97316")
        v.text(x + 62, y + 90, "100", size=10, color="#9ca3af")
        v.text(x + 62, y + 152, "65 정지", size=11, color="#bd3547")
        v.text(x + 62, y + 220, "48 정상", size=10, color="#22c55e")
        v.text(x + 62, y + 300, "0", size=10, color="#9ca3af")
        v.value(x + 110, y + 130, f"{k}_TS1", f"{a} TS1", " ℃", w=150, size=38, color="#111827")

        rows = [("냉각 효율 CE", f"{k}_CE", " %"), ("냉각 능력 CP", f"{k}_CP", " kW"), ("시스템 효율 SE", f"{k}_SE", " %"),
                ("진동 VS1", f"{k}_VS1", " mm/s"), ("압력 PS1", f"{k}_PS1", " bar"),
                ("팬 속도 SP", f"{k}_FanSpeedSP", " %"), ("펌프 부하 SP", f"{k}_LoadSP", " %")]
        ry = y + 175
        for label, tag, unit in rows:
            v.text(x + 120, ry, f"{label} ({unit.strip()})", size=12, color="#6b7280")
            v.value(x + 220, ry, tag, label, unit, w=130, size=14)
            ry += 24

        # manual controls
        cy = y + 330
        v.rect(x + 16, cy, COL_W - 32, 180, fill="#eef2ff", stroke="#c7d2fe")
        v.text(x + 28, cy + 22, "수동 조작 · 입력 후 Enter로 적용", size=12, weight="bold", color="#3730a3")
        v.text(x + 28, cy + 50, "팬 속도 % (0~100)", size=12, color="#374151")
        v.input(x + 190, cy + 34, 80, 24, f"{k}_cmd_FanSpeedSP", f"{a} fan write")
        v.text(x + 28, cy + 80, "펌프 부하 % (60~100)", size=12, color="#374151")
        v.input(x + 190, cy + 64, 80, 24, f"{k}_cmd_LoadSP", f"{a} load write")
        v.button(x + 285, cy + 34, 70, 28, f"{k}_cmd_Reset", "정지 해제", "정지 해제", 1, bg="#3859d6")
        v.text(x + 28, cy + 110, "모드 변경 명령", size=12, color="#374151")
        v.select(x + 190, cy + 94, 165, 24, f"{k}_mode_set", f"{a} mode set",
                 [("", "전환할 모드 선택"), (1, "원격 수동"), (2, "원격 자동"), (0, "현장 제어")])
        v.text(x + 28, cy + 140, "최근 명령 결과", size=12, color="#374151")
        v.value(x + 190, cy + 140, f"{k}_result", f"{a} ack", w=80, size=12, color="#111827")
        v.text(x + 28, cy + 164, "확인 사항", size=12, color="#374151")
        v.value(x + 145, cy + 164, f"{k}_reason", f"{a} ack reason", w=200, size=12, color="#b91c1c")

        # IT alert text
        v.text(x + 16, y + 542, "최근 경보 · IT 분석망에서 전달", size=12, weight="bold", color="#4b5c73")
        v.value(x + 16, y + 566, f"{k}_alert_text", f"{a} alert text", w=335, size=13, color="#374151")
        v.text(x + 16, y + 606, "분석망과 별개로 현장 제어·보호 정지는 유지됩니다.", size=11, color="#65748b")
        v.svg.append('</svg>')

    view_id = "v_hyd_overview"
    return {"id": view_id, "name": "설비 현황",
            "profile": {"width": W, "height": H, "bkcolor": "#ffffffff", "margin": 10},
            "items": v.items, "variables": {}, "svgcontent": v.render()}


def build_alarms():
    alarms = []
    off = {"enabled": False, "checkdelay": 1, "min": 0, "max": 0, "text": "", "group": "", "bkcolor": "", "color": "", "ackmode": 0}
    for a in ASSETS:
        k = key(a)
        alarms.append({"name": f"{a} TS1", "property": {"variableId": f"{k}_TS1", "variableSrc": DEV, "variable": f"{a} TS1"},
                       "high": {"enabled": True, "checkdelay": 1, "min": 60, "max": 65, "text": f"{a} 유온 높음 (60 ℃ 초과)",
                                "group": a, "bkcolor": "#f59e0b", "color": "#000000", "ackmode": 0},
                       "highhigh": {"enabled": True, "checkdelay": 1, "min": 65, "max": 200, "text": f"{a} 유온 트립 구간 (65 ℃ 초과) — 인터록",
                                    "group": a, "bkcolor": "#dc2626", "color": "#ffffff", "ackmode": 0},
                       "low": dict(off), "info": dict(off), "actions": {"enabled": False, "values": []}})
        alarms.append({"name": f"{a} IT ALERT", "property": {"variableId": f"{k}_alert", "variableSrc": DEV, "variable": f"{a} IT alert level"},
                       "highhigh": {"enabled": True, "checkdelay": 1, "min": 2, "max": 2, "text": f"{a} IT 경보: 쿨러 성능 저하 (Flink CEP RAISE)",
                                    "group": a, "bkcolor": "#7c3aed", "color": "#ffffff", "ackmode": 0},
                       "high": dict(off), "low": dict(off), "info": dict(off), "actions": {"enabled": False, "values": []}})
    return alarms


def build_project():
    view = build_view()
    return {
        "version": "1.00",
        "name": "hyd-iot-edu",
        "server": {"id": "0", "name": "FUXA Server", "type": "FuxaServer", "property": {}},
        "devices": {DEV: {"id": DEV, "name": DEV, "type": "MQTTclient", "enabled": True,
                          "property": {"address": "mqtt://emqx:1883", "clientId": "fuxa-ot", "timeout": 10000},
                          "tags": build_tags()}},
        "hmi": {"views": [view],
                "layout": {"start": view["id"], "zoom": "disabled",
                           "customStyles": """
                           #container { width: 100% !important; }
                           #home { display: block; width: 100% !important; }
                           #home #content { width: 100% !important; }
                           #home #content > svg { width: 100%; height: 730px; display: block; }
                           .hyd-unit { overflow: visible; }
                           @media (max-width: 1399px) {
                             #home #content > svg { height: 1390px; }
                             .hyd-unit-2 { transform: translate(-774px, 660px); }
                           }
                           @media (max-width: 999px) {
                             #home #content > svg { height: 2050px; }
                             .hyd-unit-1 { transform: translate(-387px, 660px); }
                             .hyd-unit-2 { transform: translate(-774px, 1320px); }
                           }
                           """,
                           "header": {"bkcolor": "#ffffff", "fgcolor": "#1f2937"},
                           "navigation": {"mode": "fix", "type": "inline",
                                          "bkcolor": "#f4f5f7", "fgcolor": "#1f2937",
                                          "items": [{"icon": "home", "view": view["id"], "link": "", "text": "설비 현황"}]}}},
        "alarms": build_alarms(),
        "texts": [],
        "charts": [],
    }


if __name__ == "__main__":
    prj = build_project()
    OUT.write_text(json.dumps(prj, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB, {len(prj['devices'][DEV]['tags'])} tags, {len(prj['alarms'])} alarms)")
