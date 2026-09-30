"""mcp-ent (read-only): GET the enterprise-system endpoints that InfoType nodes of the ontology point to.

The agent never hard-codes which system holds a fact: it asks the ontology (T3-a) and calls the endpoint found there.
Only GET is possible through this tool; writes to ERP/MES/CMMS/QMS/EMS belong to the process service after approval.
"""
import json
import os
import urllib.parse
import urllib.request

ENTERPRISE_URL = os.getenv("ENTERPRISE_URL", "http://enterprise-sim:8095")


def fetch(endpoint: str, asset: str, timeout: float = 5.0) -> dict:
    path = endpoint.replace("{asset}", urllib.parse.quote(asset))
    if not path.startswith("/") or ".." in path:
        raise ValueError(f"endpoint not allowed: {endpoint}")
    with urllib.request.urlopen(ENTERPRISE_URL + path, timeout=timeout) as r:
        return json.loads(r.read())
