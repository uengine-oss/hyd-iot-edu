"""A graph write is complete only when its exact source receipt is returned."""
import hashlib
import json


class ProjectionConflict(RuntimeError):
    """Operator comparison is required; retry must not count up past the fence."""


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()


def require(rows,key,revision,payload_hash):
    expected=dict(projection_key=key,projection_revision=revision,projection_hash=payload_hash)
    if not isinstance(rows,list) or len(rows)!=1 or not isinstance(rows[0],dict) or any(rows[0].get(k)!=v for k,v in expected.items()):
        raise ProjectionConflict(f'graph receipt mismatch for {key} revision {revision}; compare source and graph before explicit repair')
