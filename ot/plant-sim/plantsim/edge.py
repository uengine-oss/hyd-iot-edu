"""EdgeX stand-in (L2 device layer): publishes standard OT topics and maps commands to PLC writes.

Publishes  plant/{a}/tag/{name} (1 Hz, DAQ filter), plant/{a}/wave/{sensor} (1 s batch, full profile), plant/{a}/status (1 Hz,
           retained, and right after each command / mode change)
Subscribes plant/{a}/cmd/manual (FUXA), plant/{a}/cmd/auto (cmd-gateway), plant/{a}/mode (FUXA)
Command ownership comes from the topic, never from the payload: the broker lets only cmd-gateway publish cmd/auto (HITL) and
only FUXA publish cmd/manual · mode (ot/emqx/acl.conf). A payload claiming another source is ignored.
One tick has one measurement time: its tags and its status carry the same `t`, so a reader pairing them (the detector's PLC
state check) never sees the status "after" the measurement it belongs with.
"""
import json
import logging
import threading
import time

from hydcommon import topics
from hydcommon.mqtt import Link
from hydcommon.schemas import MODES
from hydcommon.timeutil import now_iso
from . import thermal, plc
from .daq import DaqFilter
from .plant import Plant

log = logging.getLogger("plant-sim.edge")
MODE_CODES = {"0": "LOCAL", "1": "REMOTE_MANUAL", "2": "REMOTE_AUTO"}   # FUXA select sends numbers


def decode(payload: bytes):
    """MQTT payload -> JSON value, or None when it is not UTF-8 JSON (the handler then refuses the message)."""
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def mode_of(value) -> str | None:
    """FUXA mode message: {"mode": 2} · 2 · "REMOTE_AUTO" -> the mode name; None when it names no mode."""
    if isinstance(value, dict):
        value = value.get("mode")
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    text = str(value).strip().strip('"')
    mode = MODE_CODES.get(text.split(".")[0], text)
    return mode if mode in MODES else None


class Edge:
    def __init__(self, plant: Plant, daq_profile: str):
        self.plant = plant
        self.daq = DaqFilter(daq_profile)
        self.link = Link("plant-sim", self._on_message, on_connect=self._on_connect)
        self.published = 0
        self.commands = 0
        self.refused = 0
        self._stop = threading.Event()

    # ---- lifecycle ----
    def start(self) -> None:
        self.link.start()
        threading.Thread(target=self._run, name="sim-loop", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        self.link.stop()

    def health(self) -> dict:
        return {"ok": self.link.healthy(), **self.link.health(), "published": self.published, "commands": self.commands,
                "refused": self.refused, "daq": self.daq.profile, "waves": self.daq.waves}

    # ---- MQTT callbacks ----
    def _on_connect(self, client) -> None:
        for a in self.plant.units:
            k = topics.asset_key(a)
            client.subscribe([(topics.mqtt_cmd_manual(k), 1), (topics.mqtt_cmd_auto(k), 1), (topics.mqtt_mode(k), 1)])
        t = now_iso()
        for a in self.plant.units:
            self.publish_status(a, t)

    def _on_message(self, client, msg) -> None:
        parsed = topics.parse_mqtt(msg.topic)
        if not parsed or parsed[0] not in self.plant.units:
            return
        asset, kind, _ = parsed
        payload = decode(msg.payload)
        self.commands += 1
        if kind == "cmd/manual":
            r = self.plant.command(asset, plc.normalize_manual(payload, "FUXA"), source="FUXA")
            log.info("%s cmd/manual %s -> %s %s", asset, r.writes_applied, r.result, r.reason or "")
        elif kind == "cmd/auto":
            r = self.plant.command(asset, payload, source="HITL")
            log.info("%s cmd/auto %s -> %s %s", asset, r.cmd_id, r.result, r.reason or "")
        elif kind == "mode":
            mode = mode_of(payload)
            if mode is None or not self.plant.set_mode(asset, mode, requester="FUXA"):
                self.refused += 1
                log.warning("%s mode message refused: %r", asset, msg.payload[:80])
            else:
                log.info("%s mode -> %s", asset, mode)
        else:
            return
        self.publish_status(asset, now_iso())

    # ---- publishing ----
    def publish_status(self, asset: str, t: str) -> None:
        if self.link.publish(topics.mqtt_status(topics.asset_key(asset)), json.dumps(self.plant.status(asset, t)), qos=1, retain=True):
            self.published += 1

    def _publish_tags(self, asset: str, t: str) -> None:
        k = topics.asset_key(asset)
        mono = time.monotonic()
        for name, v in self.daq.due(asset, self.plant.tags(asset), mono).items():
            if not self.link.publish(topics.mqtt_tag(k, name), json.dumps({"t": t, "v": v, "q": "good"})):
                return            # not connected any more: this value is offered again next tick
            self.daq.sent(asset, name, v, mono)
            self.published += 1

    def _publish_waves(self, asset: str, t: str) -> None:
        k = topics.asset_key(asset)
        s = self.plant.units[asset].state
        for sensor, hz, fn in (("PS1", 100, thermal.wave_ps1), ("EPS1", 100, thermal.wave_eps1), ("FS1", 10, thermal.wave_fs1)):
            if self.link.publish(topics.mqtt_wave(k, sensor), json.dumps({"t0": t, "hz": hz, "v": fn(s, hz)})):
                self.published += 1

    def tick(self) -> None:
        """One wall second: advance the plant, then publish every unit's measurements and status with one time."""
        self.plant.tick(1.0)
        if not self.link.connected:
            return
        t = now_iso()
        for a in self.plant.units:
            self._publish_tags(a, t)
            if self.daq.waves:
                self._publish_waves(a, t)
            # The status includes continuously evolving model inputs, not only PLC modes/ACKs. Forecast review must see
            # each measured wall tick, independent of simulation speed.
            self.publish_status(a, t)

    def _run(self) -> None:
        next_t = time.monotonic()
        while not self._stop.is_set():
            next_t += 1.0
            self.tick()
            time.sleep(max(0.0, next_t - time.monotonic()))
