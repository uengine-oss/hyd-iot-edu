"""paho-mqtt v2 helper."""
import os
import paho.mqtt.client as mqtt


def make_client(client_id: str, host: str | None = None, port: int | None = None) -> mqtt.Client:
    host = host or os.getenv("MQTT_HOST", "emqx")
    port = port or int(os.getenv("MQTT_PORT", "1883"))
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id, clean_session=True)
    c.reconnect_delay_set(min_delay=1, max_delay=5)
    c.connect_async(host, port, keepalive=30)
    return c
