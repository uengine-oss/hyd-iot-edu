"""EdgeX stand-in (L2 device layer): publishes standard OT topics and maps commands to PLC writes.

Publishes  plant/{a}/tag/{name} (1 Hz), plant/{a}/wave/{sensor} (1 s batch), plant/{a}/status (retained)
Subscribes plant/{a}/cmd/manual (FUXA), plant/{a}/cmd/auto (cmd-gateway), plant/{a}/mode (FUXA)
"""
import json
import os
import logging
import threading
import time

from hydcommon import topics
from hydcommon.mqtt import make_client
from hydcommon.timeutil import now_iso
from . import thermal, plc
from .daq import DaqFilter
from .plant import Plant

log = logging.getLogger("plant-sim.edge")
MODE_CODES = {"0": "LOCAL", "1": "REMOTE_MANUAL", "2": "REMOTE_AUTO"}   # FUXA select sends numbers


def source_for(kind, payload):
    """Command ownership comes from the topic, never from the payload: only cmd-gateway publishes cmd/auto (HITL)
    and only FUXA / the local panel publish cmd/manual. A payload claiming another source is ignored."""
    return "HITL" if kind == "cmd/auto" else "FUXA"


class Edge:
    def __init__(self, plant: Plant, publish_wave: bool | None = None, daq_profile: str | None = None):
        self.plant = plant
        self.daq = DaqFilter(daq_profile or os.getenv("DAQ_PROFILE", "lite"))
        self.publish_wave = self.daq.waves if publish_wave is None else publish_wave
        self.client = make_client("plant-sim-edge")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.connected = False
        self.published = 0
        self.commands = 0
        self._stop = threading.Event()

    # ---- lifecycle ----
    def start(self) -> None:
        self.client.loop_start()
        threading.Thread(target=self._run, name="sim-loop", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        self.client.loop_stop()

    # ---- MQTT callbacks ----
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        self.connected = True
        log.info("connected to broker rc=%s", reason_code)
        for a in self.plant.units:
            k = topics.asset_key(a)
            client.subscribe([(topics.mqtt_cmd_manual(k), 1), (topics.mqtt_cmd_auto(k), 1), (topics.mqtt_mode(k), 1)])
        for a in self.plant.units:
            self._publish_status(a)

    def _on_message(self, client, userdata, msg):
        parsed = topics.parse_mqtt(msg.topic)
        if not parsed:
            return
        key, kind, _ = parsed
        asset = topics.asset_id(key)
        if asset not in self.plant.units:
            return
        try:
            payload = json.loads(msg.payload.decode() or "{}")
        except json.JSONDecodeError:
            payload = {"raw": msg.payload.decode(errors="replace")}
        if not isinstance(payload, dict):
            payload = {"raw": str(payload)}
        self.commands += 1
        if kind == "cmd/manual":
            cmd = plc.normalize_manual(payload if isinstance(payload, dict) else {})
            r = self.plant.command(asset, cmd, source="FUXA")
            log.info("%s cmd/manual %s -> %s %s", asset, cmd.get("writes"), r.result, r.reason or "")
        elif kind == "cmd/auto":
            r = self.plant.command(asset, payload, source=source_for(kind, payload))
            log.info("%s cmd/auto %s -> %s %s", asset, payload.get("cmdId"), r.result, r.reason or "")
        elif kind == "mode":
            mode = payload.get("mode") if isinstance(payload, dict) else str(payload)
            if isinstance(payload, dict) and "raw" in payload:
                mode = payload["raw"].strip().strip('"')
            mode = MODE_CODES.get(str(mode).split(".")[0], str(mode))
            ok = self.plant.set_mode(asset, str(mode), requester="FUXA")
            log.info("%s mode -> %s (%s)", asset, mode, "ok" if ok else "rejected")
        self._publish_status(asset)

    # ---- publishing ----
    def _publish_status(self, asset: str) -> None:
        k = topics.asset_key(asset)
        st = self.plant.status(asset)
        # FUXA's MQTT JSON tags skip null updates, otherwise a successful ACK
        # keeps displaying the previous rejection. Preserve the canonical reason.
        st["reason_display"] = st.get("reason") or "–"
        # Display fields do not replace the PLC/API command contract.
        labels = {"REMOTE_AUTO": "원격 자동", "REMOTE_MANUAL": "원격 수동", "LOCAL": "현장 제어",
                  "RUN": "운전 중", "TRIP": "보호 정지", "DONE": "완료", "REJECTED": "거절",
                  "OUT_OF_RANGE": "허용 범위 초과", "MODE_MISMATCH": "운전 모드 확인 필요"}
        for field in ("mode", "state", "result", "reason"):
            st[field + "_text"] = labels.get(st.get(field), st.get(field)) or "–"
        self.client.publish(topics.mqtt_status(k), json.dumps(st), qos=1, retain=True)
        self.plant.units[asset].dirty_status = False

    def _publish_tags(self, asset: str) -> None:
        k = topics.asset_key(asset)
        t = now_iso()
        for name, v in self.daq.select(asset, self.plant.tags(asset), time.monotonic()).items():
            self.client.publish(topics.mqtt_tag(k, name), json.dumps({"t": t, "v": v, "q": "good"}), qos=0)
            self.published += 1

    def _publish_waves(self, asset: str) -> None:
        k = topics.asset_key(asset)
        s = self.plant.units[asset].state
        t0 = now_iso()
        for sensor, hz, fn in (("PS1", 100, thermal.wave_ps1), ("EPS1", 100, thermal.wave_eps1), ("FS1", 10, thermal.wave_fs1)):
            self.client.publish(topics.mqtt_wave(k, sensor), json.dumps({"t0": t0, "hz": hz, "v": fn(s, hz)}), qos=0)
            self.published += 1

    def _run(self) -> None:
        next_t = time.monotonic()
        while not self._stop.is_set():
            next_t += 1.0
            self.plant.tick(1.0)
            if self.connected:
                for a, u in self.plant.units.items():
                    self._publish_tags(a)
                    if self.publish_wave:
                        self._publish_waves(a)
                    if u.dirty_status or int(self.plant.sim_t) % (10 * int(self.plant.time_scale)) == 0:
                        self._publish_status(a)
            time.sleep(max(0.0, next_t - time.monotonic()))
