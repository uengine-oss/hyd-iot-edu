"""Topic names exactly as in the v3 design document (sections 5.1 and 5.2)."""
import re

ASSETS = ("HYD-01", "HYD-02", "HYD-03")

# ---- Kafka (IT event ledger) ----
K_TAG = "plant.tag"
K_WAVE = "plant.wave"
K_STATUS = "plant.status"
K_FEAT = "feat.1s"
K_ALERTS = "alerts"
K_CMD = "action.cmd"
K_AUDIT = "audit"
ALL_KAFKA_TOPICS = (K_TAG, K_WAVE, K_STATUS, K_FEAT, K_ALERTS, K_CMD, K_AUDIT)


def asset_key(asset_id: str) -> str:
    """'HYD-01' -> 'hyd01' (topic / Kafka key form)."""
    return asset_id.replace("-", "").lower()


def asset_id(key: str) -> str:
    """'hyd01' -> 'HYD-01'."""
    m = re.fullmatch(r"([a-z]+)(\d+)", key)
    if not m:
        return key.upper()
    return f"{m.group(1).upper()}-{m.group(2)}"


# ---- OT MQTT (emqx) ----
def mqtt_tag(key: str, name: str) -> str:
    return f"plant/{key}/tag/{name}"


def mqtt_wave(key: str, sensor: str) -> str:
    return f"plant/{key}/wave/{sensor}"


def mqtt_status(key: str) -> str:
    return f"plant/{key}/status"


def mqtt_mode(key: str) -> str:
    return f"plant/{key}/mode"


def mqtt_cmd_manual(key: str) -> str:
    return f"plant/{key}/cmd/manual"


def mqtt_cmd_auto(key: str) -> str:
    return f"plant/{key}/cmd/auto"


def mqtt_alert(key: str) -> str:
    return f"plant/{key}/alert"


def parse_mqtt(topic: str):
    """'plant/hyd02/tag/CE' -> ('hyd02', 'tag', 'CE'); 'plant/hyd02/status' -> ('hyd02', 'status', None)."""
    parts = topic.split("/")
    if len(parts) < 3 or parts[0] != "plant":
        return None
    key, kind = parts[1], parts[2]
    if kind == "cmd" and len(parts) == 4:
        return key, f"cmd/{parts[3]}", None
    rest = parts[3] if len(parts) > 3 else None
    return key, kind, rest
