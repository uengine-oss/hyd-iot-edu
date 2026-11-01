"""Topic names exactly as in the v3 design document (sections 5.1 and 5.2)."""

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


ASSET_BY_KEY = {asset_key(a): a for a in ASSETS}


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
    """'plant/hyd02/tag/CE' -> ('HYD-02', 'tag', 'CE'); 'plant/hyd02/status' -> ('HYD-02', 'status', None);
    'plant/hyd02/cmd/auto' -> ('HYD-02', 'cmd/auto', None). None for anything else, including an asset key that is not one
    of ASSETS — a topic does not create an asset (no state, row or metric is made for an unknown key)."""
    parts = topic.split("/")
    if len(parts) < 3 or parts[0] != "plant" or parts[1] not in ASSET_BY_KEY:
        return None
    asset, kind = ASSET_BY_KEY[parts[1]], parts[2]
    if kind == "cmd":
        return (asset, f"cmd/{parts[3]}", None) if len(parts) == 4 else None
    if len(parts) > 4:
        return None
    return asset, kind, parts[3] if len(parts) == 4 else None
