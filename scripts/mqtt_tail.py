"""Tail OT MQTT topics from the host: python scripts/mqtt_tail.py 'plant/+/tag/TS1' 10"""
import json, sys, time
import paho.mqtt.client as mqtt

pattern = sys.argv[1] if len(sys.argv) > 1 else "plant/#"
seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 5
count = 0

def on_msg(c, u, m):
    global count
    count += 1
    if count <= 20:
        print(m.topic, m.payload.decode()[:160], flush=True)

c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="tail")
c.on_message = on_msg
c.connect("localhost", 1883)
c.subscribe(pattern)
c.loop_start()
time.sleep(seconds)
c.loop_stop()
print(f"-- {count} messages in {seconds}s on {pattern}")
