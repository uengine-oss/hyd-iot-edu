"""Choose host ports for Compose and Supabase before starting either stack.

Only host-side addresses change; container-to-container addresses stay the same.
The saved map is also consumed by check_windows.ps1. No services are started here.
"""
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit


DB_FIELDS = {
    ("api", "port"): 54321, ("db", "port"): 54322,
    ("db", "shadow_port"): 54320, ("db.pooler", "port"): 54329,
    ("studio", "port"): 54323, ("inbucket", "port"): 54324,
    ("inbucket", "smtp_port"): 54325, ("inbucket", "pop3_port"): 54326,
    ("analytics", "port"): 54327, ("analytics", "vector_port"): 54328,
}


def env_values(text):
    return {m[1]: m[2].strip().strip('"\'') for line in text.splitlines()
            if (m := re.match(r"^\s*([A-Z_0-9]+)\s*=\s*(.*?)\s*$", line))}


def set_values(text, updates):
    remaining = dict(updates)
    lines = []
    for line in text.splitlines():
        m = re.match(r"^\s*([A-Z_0-9]+)\s*=", line)
        if m and m[1] in updates:
            line = f"{m[1]}={updates[m[1]]}"
            remaining.pop(m[1], None)
        lines.append(line)
    lines.extend(f"{key}={value}" for key, value in remaining.items())
    return "\n".join(lines) + "\n"


def config_ports(text):
    section = ""
    result = {}
    for line in text.splitlines():
        if m := re.match(r"\s*\[([^]]+)\]", line):
            section = m[1]
        if m := re.match(r"\s*(\w+)\s*=\s*(\d+)", line):
            if (section, m[1]) in DB_FIELDS:
                result[DB_FIELDS[section, m[1]]] = int(m[2])
    if set(result) != set(DB_FIELDS.values()):
        raise RuntimeError("Supabase port configuration is incomplete")
    return result


def available(port):
    # Binding catches other Docker projects and Windows reserved ports as well
    # as ordinary processes; a process-name whitelist cannot distinguish them.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if os.name == "nt":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def docker_ports(root, project_id):
    ids = subprocess.check_output(["docker", "ps", "-q"], text=True).split()
    owned, occupied = set(), set()
    if not ids:
        return owned, occupied
    containers = json.loads(subprocess.check_output(["docker", "inspect", *ids], text=True))
    for container in containers:
        labels = container["Config"].get("Labels") or {}
        workdir = labels.get("com.docker.compose.project.working_dir", "")
        same_root = workdir.replace("\\", "/").rstrip("/").casefold() == root.as_posix().casefold()
        own = (labels.get("com.docker.compose.project") == "hyd-iot-edu" and same_root)
        own |= container.get("Name", "").startswith("/supabase_") and container["Name"].endswith("_" + project_id)
        for bindings in (container["NetworkSettings"].get("Ports") or {}).values():
            for binding in bindings or []:
                port = int(binding["HostPort"])
                occupied.add(port)
                if own:
                    owned.add(port)
    return owned, occupied


def allocate(defaults, previous, owned, occupied, probe=available):
    selected = {}
    reserved = set(defaults)
    for default in sorted(defaults):
        current = int(previous.get(default, default))
        if not 1 <= current <= 65535:
            raise RuntimeError(f"Invalid saved port for {default}")
        def usable(port):
            return port not in selected.values() and ((port == current and port in owned) or (port not in occupied and probe(port)))
        if usable(current):
            selected[default] = current
            continue
        # Search the entire non-privileged range, including when a saved port
        # or the usual +10000 fallback is itself occupied.
        start = default + 10000 if default + 10000 <= 65535 else 1024
        for candidate in list(range(start, 65536)) + list(range(1024, start)):
            if candidate not in reserved and usable(candidate):
                selected[default] = candidate
                break
        else:
            raise RuntimeError(f"No free host port for {default}")
    return selected


def rewrite_url(value, replacements):
    """Only rewrite local host endpoints, preserving custom remote DB settings."""
    url = urlsplit(value)
    if url.hostname not in {"localhost", "127.0.0.1", "host.docker.internal"}:
        return value
    if url.port not in replacements:
        return value
    netloc = url.netloc.rsplit(":", 1)[0] + ":" + str(replacements[url.port])
    return urlunsplit(url._replace(netloc=netloc))


def update_config(text, ports, previous):
    section = ""
    lines = []
    for line in text.splitlines():
        if m := re.match(r"\s*\[([^]]+)\]", line):
            section = m[1]
        if m := re.match(r"(\s*)(\w+)(\s*=\s*)\d+(.*)", line):
            if (section, m[2]) in DB_FIELDS:
                line = f"{m[1]}{m[2]}{m[3]}{ports[DB_FIELDS[section, m[2]]]}{m[4]}"
        if section == "auth":
            line = re.sub(r'http://(localhost|127\.0\.0\.1):' + str(previous.get(8088, 8088)) + r'(?=[/"\s])',
                          lambda m: f"http://{m[1]}:{ports[8088]}", line)
        lines.append(line)
    return "\n".join(lines) + "\n"


def atomic_write(path, text):
    temp = path.with_name(path.name + ".ports-tmp")
    temp.write_text(text, encoding="utf-8", newline="\n")
    temp.replace(path)


def prepare(root):
    compose = (root / "compose.yaml").read_text(encoding="utf-8")
    service_ports = {int(p) for p in re.findall(r"\$\{HYD_PORT_(\d+):-", compose)}
    config_path = root / "it/supabase/config.toml"
    config = config_path.read_text(encoding="utf-8")
    project_id = re.search(r'^project_id\s*=\s*"([^"]+)"', config, re.M)[1]
    env_path = root / ".env"
    env_text = env_path.read_text(encoding="utf-8-sig")
    values = env_values(env_text)
    previous = {p: int(values.get(f"HYD_PORT_{p}", p)) for p in service_ports}
    previous.update(config_ports(config))
    owned, occupied = docker_ports(root, project_id)
    ports = allocate(service_ports | set(DB_FIELDS.values()), previous, owned, occupied)
    updates = {f"HYD_PORT_{p}": str(port) for p, port in ports.items()}
    updates["HYD_PORTS"] = '"' + " ".join(f"{p}={port}" for p, port in ports.items() if p != port) + '"'
    for key, default in {
        "SUPABASE_DSN": "postgresql://postgres:postgres@host.docker.internal:54322/postgres",
        "ENTERPRISE_READ_DSN": "postgresql://hyd_enterprise_reader:hyd-enterprise-read-local@host.docker.internal:54322/postgres",
        "HYD_MCP_OAUTH_CALLBACK_URL": "http://localhost:8088/api/mcp/connections/callback",
    }.items():
        replacements = {54322: ports[54322], 8088: ports[8088],
                        previous[54322]: ports[54322], previous[8088]: ports[8088]}
        updates[key] = rewrite_url(values.get(key, default), replacements)
    if values.get("EFFECTS_SMTP_PORT", str(previous[54325])) == str(previous[54325]):
        updates["EFFECTS_SMTP_PORT"] = str(ports[54325])
    # Host-worker rewrites use host ports; internal Docker endpoints are kept.
    if "MCP_HOST_REWRITE" in values:
        rewrite = values["MCP_HOST_REWRITE"]
        for p in (7687, 8199, 8198, 8196, 8195):
            rewrite = re.sub(r"(=127\.0\.0\.1:)" + str(previous[p]) + r"(?=,|$)",
                             lambda m: m[1] + str(ports[p]), rewrite)
        updates["MCP_HOST_REWRITE"] = rewrite
    runtime = root / ".hyd-runtime"
    runtime.mkdir(exist_ok=True)
    atomic_write(config_path, update_config(config, ports, previous))
    atomic_write(env_path, set_values(env_text, updates))
    atomic_write(runtime / "ports.json", json.dumps(ports, indent=2) + "\n")
    for default, port in ports.items():
        if default != port:
            print(f"Host port {default} -> {port}")


if __name__ == "__main__":
    try:
        prepare(Path(__file__).resolve().parents[1])
    except Exception:
        # Environment values and command output may contain credentials.
        print("Port preparation failed; check Docker, Python and writable project files.", file=sys.stderr)
        sys.exit(1)
