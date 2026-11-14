"""paho-mqtt v2 — how every OT client (plant-sim · cmd-gateway · connect-ingest) joins the broker, in one place.

Identity: the client connects to the inner listener (1883 on the OT net and the OT–DMZ boundary net, not published to the host) with its service name as
the username. The broker's topic rules (ot/emqx/acl.conf) are written against that name — only cmd-gateway may publish
plant/+/cmd/auto, only plant-sim publishes measurements and status. A publish the rules refuse ends the connection.

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

log = logging.getLogger("hydcommon.mqtt")
ERROR_WINDOW_S = 60.0


class Link:
    def __init__(self, username: str, on_message, on_connect=None, host: str | None = None, port: int | None = None):
        self.username = username
        self.connected = False
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
        log.info("mqtt %s connected", self.username)
        if self._on_connect:
            self._on_connect(client)

    def _disconnected(self, client, userdata, flags, reason_code, properties=None):
        self.connected = False
        log.warning("mqtt %s disconnected (%s); reconnecting", self.username, reason_code)

    def _message(self, client, userdata, msg):
        try:
            self._on_message(client, msg)
        except Exception as exc:  # noqa: BLE001 — see the module docstring: counted, logged, shown in health
            self.handler_errors += 1
            self.last_error = f"{msg.topic}: {type(exc).__name__}: {exc}"[:300]
            self.last_error_at = time.time()
            log.exception("mqtt %s: handler failed on %s", self.username, msg.topic)

    def healthy(self, now: float | None = None) -> bool:
        recent = self.last_error_at is not None and (time.time() if now is None else now) - self.last_error_at < ERROR_WINDOW_S
        return self.connected and not recent

    def health(self) -> dict:
        return {"mqtt": self.connected, "mqtt_handler_errors": self.handler_errors, "mqtt_last_error": self.last_error}

    def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> bool:
        """True when paho accepted the message for sending (not a delivery receipt).

        False means the message is NOT sent — now or later. paho 2.1 keeps a QoS 1/2 message it could not send
        (MQTT_ERR_NO_CONN) in its outgoing queue and sends it by itself after the next reconnect. A caller that was told
        "not sent" has already recorded the refusal (cmd-gateway writes CMD_REJECTED and process closes the case), so a
        late delivery would move the plant behind a record that says nothing was sent — and a second approval would run
        the command twice. So a disconnected link refuses before handing the message to paho, and a message paho refused
        anyway (the socket went away before the disconnect event) is taken back out of its queue."""
        if not self.connected:
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
