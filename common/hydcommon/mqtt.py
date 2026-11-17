"""paho-mqtt v2 — how every MQTT client of ours (plant-sim · cmd-gateway · connect-ingest) joins its broker, in one place.

Who connects where (compose.yaml MQTT_HOST): plant-sim joins the plant broker (emqx, OT net only). The DMZ services
(cmd-gateway · connect-ingest) join the DMZ broker (dmz-broker) and never the plant broker — nothing outside the plant opens
a connection into it. The plant-side bridge (ot-bridge, ot/bridge/mosquitto.conf) is the one that connects, from inside the
plant, to both brokers: it pushes measurements and status out to the DMZ broker and fetches approved commands from it.

Identity: the client connects with its service name as the username, no password (the brokers' listeners for services are
not published to the host). Each broker's topic rules are written against that name (ot/emqx/acl.conf · dmz/broker/acl) —
on the DMZ broker only cmd-gateway may publish plant/+/cmd/auto, on the plant broker only the bridge that carries it down.

Behind the bridge (`behind_bridge=True`, the DMZ services): being connected to the DMZ broker says nothing about the plant.
The bridge reports its two legs on bridge/ot/broker · bridge/ot/dmz (retained "1"/"0"; the broker publishes "0" as the
bridge's last will). The link subscribes to them itself and
  - `healthy()` is false and `health()` says `ot_bridge: false` (with each leg) while either leg is down or not yet reported
    — a service must not answer "ok" while no value can come up and no command can go down;
  - `publish()` refuses, exactly as when the broker connection is down — the DMZ broker would take the message, but nobody
    would carry it to the plant, and the bridge does not deliver it later (cleansession).

Health: `connected` follows the real connect / disconnect events (paho reconnects by itself), so /healthz never says
"connected" for a dead leg.

A handler that raises does not end the network loop. paho 2.1 re-raises callback exceptions (suppress_exceptions is False)
and the loop thread dies — commands and status then silently stop arriving until a restart. Handlers validate their own
input and reject bad payloads explicitly (counted by the service); an exception still escaping is a bug or an input the
handler did not foresee: that one message is logged with its topic and traceback, counted, and `healthy()` stays false for
ERROR_WINDOW_S so the service's /healthz shows it.
"""
import logging
import os
import time

import paho.mqtt.client as mqtt

from . import topics

log = logging.getLogger("hydcommon.mqtt")
ERROR_WINDOW_S = 60.0


class Link:
    def __init__(self, username: str, on_message, on_connect=None, host: str | None = None, port: int | None = None,
                 behind_bridge: bool = False, on_bridge_up=None):
        self.username = username
        self.connected = False
        self.behind_bridge = behind_bridge
        self.bridge: dict[str, bool] = {}          # leg -> up, as last reported on this connection (empty = not reported yet)
        self._on_bridge_up = on_bridge_up
        self.handler_errors = 0
        self.last_error: str | None = None
        self.last_error_at: float | None = None
        self._on_message, self._on_connect = on_message, on_connect
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=username, clean_session=True)
        c.username_pw_set(username)
        c.reconnect_delay_set(min_delay=1, max_delay=5)
        c.on_connect, c.on_disconnect, c.on_message = self._connected, self._disconnected, self._message
        self.client = c
        c.connect_async(host or os.getenv("MQTT_HOST", "emqx"), port or int(os.getenv("MQTT_PORT", "1883")), keepalive=30)

    def _connected(self, client, userdata, flags, reason_code, properties=None):
        if reason_code.is_failure:
            self.connected = False
            log.error("mqtt %s: broker refused the connection (%s)", self.username, reason_code)
            return
        self.connected = True
        self.bridge = {}                               # the retained leg states arrive again on this subscription
        log.info("mqtt %s connected", self.username)
        if self.behind_bridge:
            client.subscribe(topics.MQTT_BRIDGE_STATE, 1)
        if self._on_connect:
            self._on_connect(client)

    def _disconnected(self, client, userdata, flags, reason_code, properties=None):
        self.connected = False
        self.bridge = {}
        log.warning("mqtt %s disconnected (%s); reconnecting", self.username, reason_code)

    @property
    def bridge_up(self) -> bool:
        """Both legs of the plant-side bridge reported up on this connection."""
        return all(self.bridge.get(leg) is True for leg in topics.BRIDGE_LEGS)

    def _bridge_state(self, client, leg: str, payload: bytes) -> None:
        was = self.bridge_up
        self.bridge[leg] = payload == b"1"
        if self.bridge_up != was:
            (log.info if self.bridge_up else log.error)("mqtt %s: plant-side bridge %s (%s)", self.username,
                                                        "up" if self.bridge_up else "DOWN — no value comes up, no command goes down", self.bridge)
            if self.bridge_up and self._on_bridge_up:
                self._on_bridge_up(client)

    def _message(self, client, userdata, msg):
        leg = topics.bridge_leg(msg.topic) if self.behind_bridge else None
        if leg:
            self._bridge_state(client, leg, msg.payload)
            return
        try:
            self._on_message(client, msg)
        except Exception as exc:  # noqa: BLE001 — see the module docstring: counted, logged, shown in health
            self.handler_errors += 1
            self.last_error = f"{msg.topic}: {type(exc).__name__}: {exc}"[:300]
            self.last_error_at = time.time()
            log.exception("mqtt %s: handler failed on %s", self.username, msg.topic)

    def healthy(self, now: float | None = None) -> bool:
        recent = self.last_error_at is not None and (time.time() if now is None else now) - self.last_error_at < ERROR_WINDOW_S
        return self.connected and not recent and (self.bridge_up or not self.behind_bridge)

    def health(self) -> dict:
        body = {"mqtt": self.connected, "mqtt_handler_errors": self.handler_errors, "mqtt_last_error": self.last_error}
        if self.behind_bridge:
            body.update(ot_bridge=self.bridge_up, ot_bridge_legs={leg: self.bridge.get(leg) for leg in topics.BRIDGE_LEGS})
        return body

    def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> bool:
        """True when paho accepted the message for sending (not a delivery receipt).

        False means the message is NOT sent — now or later. paho 2.1 keeps a QoS 1/2 message it could not send
        (MQTT_ERR_NO_CONN) in its outgoing queue and sends it by itself after the next reconnect. A caller that was told
        "not sent" has already recorded the refusal (cmd-gateway writes CMD_REJECTED and process closes the case), so a
        late delivery would move the plant behind a record that says nothing was sent — and a second approval would run
        the command twice. So a disconnected link refuses before handing the message to paho, and a message paho refused
        anyway (the socket went away before the disconnect event) is taken back out of its queue. Behind the bridge the
        same holds while the bridge is down: the message would sit on the DMZ broker with nobody to carry it."""
        if not self.connected or (self.behind_bridge and not self.bridge_up):
            return False
        info = self.client.publish(topic, payload, qos=qos, retain=retain)
        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            return True
        with self.client._out_message_mutex:        # paho-mqtt is pinned to 2.1.0 (requirements.txt) — this is its queue
            self.client._out_messages.pop(info.mid, None)
        return False

    def start(self) -> None:
        self.client.loop_start()

    def stop(self) -> None:
        self.client.loop_stop()
