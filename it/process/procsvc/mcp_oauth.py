"""Shared educational HTTP MCP OAuth connections; drafts never confer execution rights.

Tokens and PKCE material live only in encrypted, tenant-scoped secret-store records.
No portal identity is inferred from an external or ChatGPT account.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import ipaddress
import json
import os
import re
import secrets
import socket
import ssl
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit
from fastapi import Request

from . import mcp_check, mcp_registry, mcp_secrets

PREFIX = "HYD_OAUTH_"
MAX_BODY = 262144
TTL = 600
LOCK = threading.RLock()
CATALOG = [
    {"id": "google-drive", "title": "Google Drive", "url": "https://drivemcp.googleapis.com/mcp/v1",
     "scopes": ["https://www.googleapis.com/auth/drive.readonly"], "preview": True},
    {"id": "google-calendar", "title": "Google Calendar", "url": "https://calendarmcp.googleapis.com/mcp/v1",
     "scopes": ["https://www.googleapis.com/auth/calendar.calendarlist.readonly", "https://www.googleapis.com/auth/calendar.events.freebusy", "https://www.googleapis.com/auth/calendar.events.readonly"], "preview": True},
]


class OAuthError(Exception):
    def __init__(self, code, reason, status=422):
        super().__init__(reason)
        self.code, self.reason, self.status = code, reason, status


def fail(code, reason, status=422):
    raise OAuthError(code, reason, status)


def cipher(environ=None):
    from cryptography.fernet import Fernet
    env = os.environ if environ is None else environ
    key = env.get("HYD_MCP_OAUTH_KEY")
    try:
        if not key and env.get("HYD_MCP_OAUTH_KEY_FILE"):
            key = Path(env["HYD_MCP_OAUTH_KEY_FILE"]).read_bytes().strip()
        if not key:
            fail("storage_not_configured", "운영자가 암호화 키 파일을 준비해야 합니다.", 503)
        return Fernet(key.encode() if isinstance(key, str) else key)
    except OAuthError:
        raise
    except Exception:
        fail("storage_unavailable", "암호화 키 파일을 사용할 수 없습니다.", 503)


def origin(url):
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}"


def validate_url(url, environ=None):
    env = os.environ if environ is None else environ
    try:
        p = urlsplit(url)
        allowed = set(filter(None, env.get("HYD_MCP_OAUTH_PRIVATE_ORIGINS", "").split(",")))
        private = origin(url) in allowed
        if not p.hostname or p.username or p.password or p.fragment or p.query or len(url) > 2048:
            raise ValueError()
        if p.scheme != "https" and not (private and p.scheme == "http"):
            raise ValueError()
        port = p.port or (443 if p.scheme == "https" else 80)
        addresses = socket.getaddrinfo(p.hostname, port, type=socket.SOCK_STREAM)
        ips = list(dict.fromkeys(a[4][0] for a in addresses))
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips) and not private:
            raise ValueError()
        # Link-local/cloud metadata are never allowed, even by private-origin policy.
        if any(ipaddress.ip_address(ip).is_link_local or ipaddress.ip_address(ip).is_unspecified for ip in ips):
            raise ValueError()
        return p, ips[0], port
    except Exception:
        fail("unsafe_endpoint", "연결 주소가 안전한 HTTPS 주소인지 확인하세요.")


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, ip, port, timeout=8):
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self.ip = ip

    def connect(self):
        sock = socket.create_connection((self.ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class Transport:
    """DNS-pinned requests, no redirects, bounded bodies; errors never include payloads."""
    def __init__(self, environ=None):
        self.environ = environ

    def request(self, method, url, data=None, headers=None):
        conn = None
        try:
            body = None
            hdr = {"Accept": "application/json", **(headers or {})}
            if data is not None:
                body = urlencode(data).encode() if hdr.get("Content-Type") == "application/x-www-form-urlencoded" else json.dumps(data).encode()
                hdr.setdefault("Content-Type", "application/json")
            conn, r = self.open(method, url, body, hdr)
            raw = r.read(MAX_BODY + 1)
            if len(raw) > MAX_BODY:
                fail("response_too_large", "인증 서버 응답이 허용 크기를 초과했습니다.", 502)
            if 300 <= r.status < 400:
                fail("redirect_rejected", "인증 서버의 다른 주소로 이동하는 응답을 허용하지 않습니다.", 502)
            try:
                value = json.loads(raw) if raw else {}
            except ValueError:
                value = {}
            return r.status, {k.lower(): v for k, v in r.getheaders()}, value
        except OAuthError:
            raise
        except Exception:
            fail("endpoint_unavailable", "인증 서버에 연결할 수 없습니다. 잠시 후 다시 확인하세요.", 502)
        finally:
            if conn is not None:
                conn.close()

    def open(self, method, url, body=None, headers=None, timeout=8):
        """Pinned finite-time streaming response; caller must bound reads and close both."""
        p, ip, port = validate_url(url, self.environ)
        conn = _PinnedHTTPS(p.hostname, ip, port, timeout) if p.scheme == "https" else http.client.HTTPConnection(ip, port, timeout=timeout)
        try:
            hdr = dict(headers or {})
            # Host follows validated URL, never an upstream/user supplied header.
            hdr = {k: v for k, v in hdr.items() if k.lower() != "host"}
            hdr["Host"] = p.netloc
            conn.request(method, p.path or "/", body=body, headers=hdr)
            response = conn.getresponse()
            if 300 <= response.status < 400:
                fail("redirect_rejected", "인증 서버의 다른 주소로 이동하는 응답을 허용하지 않습니다.", 502)
            return conn, response
        except OAuthError:
            conn.close()
            raise
        except Exception:
            conn.close()
            fail("endpoint_unavailable", "인증 서버에 연결할 수 없습니다. 잠시 후 다시 확인하세요.", 502)


def metadata(transport, urls):
    for url in dict.fromkeys(urls):
        status, _, body = transport.request("GET", url)
        if status == 200 and isinstance(body, dict):
            return body
    fail("discovery_failed", "서버가 표준 인증 설정을 제공하지 않습니다.")


def discover(url, transport):
    status, headers, _ = transport.request("GET", url)
    challenge = headers.get("www-authenticate", "")
    match = re.search(r'resource_metadata="([^"\r\n]+)"', challenge, re.I)
    p = urlsplit(url)
    root = origin(url)
    resources = [match[1]] if match else [root + "/.well-known/oauth-protected-resource" + p.path, root + "/.well-known/oauth-protected-resource"]
    resource = metadata(transport, resources)
    if resource.get("resource") != url:
        fail("resource_mismatch", "인증 대상 주소가 선택한 도구 서버와 다릅니다.")
    issuers = resource.get("authorization_servers")
    if not isinstance(issuers, list) or not issuers or not isinstance(issuers[0], str):
        fail("discovery_failed", "인증 서버 정보가 없습니다.")
    issuer = issuers[0].rstrip("/")
    q = urlsplit(issuer)
    root = origin(issuer)
    auth = metadata(transport, [root + "/.well-known/oauth-authorization-server" + q.path,
                                root + "/.well-known/openid-configuration" + q.path,
                                issuer + "/.well-known/openid-configuration"])
    if auth.get("issuer", "").rstrip("/") != issuer:
        fail("issuer_mismatch", "인증 서버 발급자 정보가 일치하지 않습니다.")
    if not isinstance(auth.get("code_challenge_methods_supported"), list) or "S256" not in auth["code_challenge_methods_supported"]:
        fail("pkce_unsupported", "서버가 안전한 로그인 방식(PKCE S256)을 지원하지 않습니다.")
    for field in ("authorization_endpoint", "token_endpoint"):
        if not isinstance(auth.get(field), str):
            fail("discovery_failed", "필수 인증 주소가 없습니다.")
        # Endpoints may use separate hosts (e.g. Google); transport validates each.
        validate_url(auth[field], getattr(transport, "environ", None))
    scope = re.search(r'scope="([^"\r\n]+)"', challenge, re.I)
    scopes = scope[1].split() if scope else resource.get("scopes_supported", [])
    if not isinstance(scopes, list) or len(scopes) > 30 or any(not isinstance(s, str) or len(s) > 256 for s in scopes):
        fail("discovery_failed", "인증 권한 범위 정보가 올바르지 않습니다.")
    return {"issuer": issuer, "resource": url, "metadata": auth,
            "scopes": scopes}


class Store:
    def __init__(self, repo, tenant, environ=None):
        self.repo, self.tenant, self.environ = repo, tenant, environ

    @contextmanager
    def atomic(self, key):
        with LOCK:
            if hasattr(self.repo, "dsn"):
                lock_key = "mcp-oauth:" + self.tenant + ":" + key
                if getattr(getattr(self.repo, "_local", None), "connection", None) is not None:
                    with self.repo._conn() as c:
                        c.execute("select pg_advisory_xact_lock(hashtextextended(%s, 0))", (lock_key,))
                    yield
                else:
                    with self.repo.event_transaction(lock_key):
                        yield
            else:
                yield

    def rows(self):
        box = cipher(self.environ)
        try:
            values = mcp_secrets.store_for(self.repo).values(self.tenant)
            return [json.loads(box.decrypt(v.encode())) for k, v in values.items() if k.startswith(PREFIX)]
        except OAuthError:
            raise
        except Exception:
            fail("storage_unavailable", "암호화된 연결 기록을 읽을 수 없습니다.", 503)

    def get(self, ident):
        for row in self.rows():
            if row["id"] == ident:
                return row
        fail("connection_missing", "연결 준비 기록이 없습니다.", 404)

    def put(self, row):
        value = cipher(self.environ).encrypt(json.dumps(row, ensure_ascii=False).encode()).decode()
        try:
            mcp_secrets.store_for(self.repo).put(self.tenant, PREFIX + row["id"].replace("-", "").upper(), value, "OAuth 연결", str(time.time()))
        except Exception:
            fail("storage_unavailable", "연결 기록을 안전하게 저장할 수 없습니다.", 503)


def public(row):
    return {k: row.get(k) for k in ("id", "name", "url", "preset", "status", "reason", "reason_code", "expires_at", "auth_mode")} | {"shared": True, "account_label": None}


class Service:
    def __init__(self, repo, tenant, environ=None, transport=None, now=time.time):
        self.repo, self.tenant = repo, tenant
        self.env = os.environ if environ is None else environ
        self.store = Store(repo, tenant, self.env)
        self.transport = transport or Transport(self.env)
        self.now = now

    def config(self):
        reason = reason_code = None
        try:
            cipher(self.env)
            storage = True
        except OAuthError as exc:
            storage = False
            reason, reason_code = exc.reason, exc.code
        try:
            self.callback_url()
            callback = True
        except OAuthError as exc:
            callback = False
            reason, reason_code = reason or exc.reason, reason_code or exc.code
        return {"storage_ready": storage, "callback_ready": callback, "shared": True, "reason": reason, "reason_code": reason_code}

    def listing(self):
        config = self.config()
        rows = self.store.rows() if config["storage_ready"] else []
        return {"catalog": [dict(c, shared=True, operator_requirements="Google Cloud 프로젝트의 MCP API 활성화(미리보기)와 OAuth 앱 사전 등록이 필요합니다.") for c in CATALOG],
                "connections": [public(r) for r in rows], "configuration": config}

    def prepare(self, body):
        with self.store.atomic("prepare"):
            return self._prepare(body)

    def _prepare(self, body):
        rows = self.store.rows()
        if len(rows) >= 100:
            fail("connection_limit", "연결 준비 기록이 너무 많습니다. 운영자에게 정리를 요청하세요.", 409)
        preset = next((c for c in CATALOG if c["id"] == body.get("preset")), None)
        url = preset["url"] if preset else str(body.get("url") or "")
        validate_url(url, self.env)
        name = mcp_registry._validate_name(body.get("name") or (preset["id"] if preset else "personal-" + hashlib.sha256(url.encode()).hexdigest()[:8]))
        mode = "oauth" if preset else body.get("auth_mode", "auto")
        if mode not in ("auto", "oauth", "none", "api_key"):
            fail("invalid_auth_mode", "연결 인증 방식을 확인하세요.")
        key_headers = None
        if mode == "api_key":
            key, header, prefix = body.get("access_key"), body.get("key_header"), body.get("key_prefix")
            if not isinstance(key, str) or not key or len(key) > 16384 or any(ord(c) < 32 for c in key) or header not in ("Authorization", "X-API-Key") or prefix not in ("Bearer", ""):
                fail("invalid_access_key", "접속키와 인증 방식을 확인하세요.")
            key_headers = {header: (prefix + " " if prefix else "") + key}
        previous = None
        for existing in rows:
            if existing["name"] == name:
                if existing["url"] == url:
                    if mode != "api_key":
                        return public(existing)
                    previous = existing
                    break
                fail("name_in_use", "이 이름은 다른 도구 서버의 연결 준비에 사용 중입니다.", 409)
        if name in mcp_registry.BASE_SERVERS or not previous and name in mcp_registry.store_for(self.repo).servers(self.tenant):
            fail("name_in_use", "이미 사용 중인 도구 연결 이름입니다.", 409)
        row = {"id": previous["id"] if previous else secrets.token_hex(16), "name": name, "url": url, "preset": preset["id"] if preset else None, "auth_mode": mode,
               "scopes": preset["scopes"] if preset else body.get("scopes", []), "status": "login_required", "reason_code": None, "reason": "외부 계정 동의가 필요합니다."}
        if not isinstance(row["scopes"], list) or any(not isinstance(s, str) or len(s) > 256 for s in row["scopes"]) or len(row["scopes"]) > 30:
            fail("invalid_scopes", "권한 범위 형식을 확인하세요.")
        if key_headers is not None:
            row["key_headers"] = key_headers
        self.store.put(row)
        if mode in ("auto", "none", "api_key"):
            row.update(status="login_complete")
            self.store.put(row)
            result = self.check(row["id"])
            if result["status"] == "connected" or mode != "auto":
                return result
            row = self.store.get(row["id"])
            if row.get("check_error_kind") == "auth":
                try:
                    row["discovery"] = discover(url, self.transport)
                    row.update(auth_mode="oauth", status="login_required", reason_code=None, reason="외부 계정 동의가 필요합니다.")
                except OAuthError as exc:
                    row.update(status="preparation_required", reason_code="api_key_required" if exc.code == "discovery_failed" else exc.code, reason="서버가 표준 로그인 정보를 제공하지 않습니다. 접속키가 필요한지와 인증 방식을 확인하세요." if exc.code == "discovery_failed" else exc.reason)
                self.store.put(row)
                return public(row)
            return result
        return public(row)

    def callback_url(self):
        url = self.env.get("HYD_MCP_OAUTH_CALLBACK_URL", "")
        p = urlsplit(url)
        if not url or p.path != "/api/mcp/connections/callback" or p.query or p.fragment or p.username or p.password or not p.hostname or (p.scheme != "https" and not (p.scheme == "http" and p.hostname in ("localhost", "127.0.0.1"))):
            fail("callback_not_configured", "운영자가 포털의 로그인 완료 주소를 설정해야 합니다.", 503)
        return url

    def start(self, ident, binding):
        try:
            return self._start(ident, binding)
        except OAuthError as exc:
            with self.store.atomic(ident):
                row = self.store.get(ident)
                row.update(status="preparation_required" if exc.code in ("client_not_configured", "callback_not_configured", "storage_not_configured") else "failed", reason_code=exc.code, reason=exc.reason)
                self.store.put(row)
            raise

    def _start(self, ident, binding):
        with self.store.atomic(ident):
            row = self.store.get(ident)
            if row.get("auth_mode", "oauth") != "oauth":
                fail("oauth_not_required", "이 연결은 외부 계정 로그인 방식이 아닙니다.", 409)
            callback = self.callback_url()
            disc = discover(row["url"], self.transport)
            auth = disc["metadata"]
            try:
                clients = json.loads(self.env.get("HYD_MCP_OAUTH_CLIENTS", "{}"))
                client = clients.get(disc["issuer"], {})
                if not isinstance(client, dict):
                    raise ValueError()
            except Exception:
                fail("client_not_configured", "운영자의 OAuth 앱 설정을 확인하세요.", 503)
            if not client.get("client_id"):
                endpoint = auth.get("registration_endpoint")
                if not endpoint:
                    fail("client_not_configured", "이 서비스의 OAuth 앱을 운영자가 사전 등록해야 합니다.", 503)
                status, _, client = self.transport.request("POST", endpoint, {"client_name": "HYD shared educational MCP", "redirect_uris": [callback], "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"], "token_endpoint_auth_method": "none"})
                if status not in (200, 201) or not isinstance(client, dict) or not client.get("client_id"):
                    fail("registration_failed", "서버의 OAuth 앱 자동 등록에 실패했습니다.", 502)
            method = client.get("token_endpoint_auth_method") or ("client_secret_post" if client.get("client_secret") else "none")
            if method not in ("none", "client_secret_post", "client_secret_basic"):
                fail("client_auth_unsupported", "OAuth 앱의 인증 방식이 지원되지 않습니다.")
            verifier = secrets.token_urlsafe(48)
            state = secrets.token_urlsafe(32)
            attempt = secrets.token_hex(16)
            front = secrets.token_urlsafe(24)
            scopes = row["scopes"] or disc["scopes"]
            row.update(discovery=disc, client=client, client_method=method, status="login_required", reason="외부 계정에 로그인하고 권한을 동의하세요.", reason_code=None,
                       attempt={"id": attempt, "state": state, "frontend_state": front, "binding": hashlib.sha256(binding.encode()).hexdigest(), "verifier": verifier, "expires": self.now() + TTL, "consumed": False}, expires_at=self.now() + TTL)
            self.store.put(row)
            params = {"response_type": "code", "client_id": client["client_id"], "redirect_uri": callback, "state": state, "code_challenge": base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode(), "code_challenge_method": "S256", "resource": row["url"], "scope": " ".join(scopes)}
            return {"authorization_url": auth["authorization_endpoint"] + "?" + urlencode(params), "connection_id": ident, "attempt_id": attempt, "state": front, "expires_at": row["expires_at"]}

    def token(self, row, params):
        client = row["client"]
        params["client_id"] = client["client_id"]
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        method = row["client_method"]
        if method == "client_secret_post":
            params["client_secret"] = client.get("client_secret", "")
        elif method == "client_secret_basic":
            from urllib.parse import quote
            pair = quote(client["client_id"], safe="") + ":" + quote(client.get("client_secret", ""), safe="")
            headers["Authorization"] = "Basic " + base64.b64encode(pair.encode()).decode()
        status, _, body = self.transport.request("POST", row["discovery"]["metadata"]["token_endpoint"], params, headers)
        if status != 200 or not isinstance(body, dict) or not isinstance(body.get("access_token"), str) or not body["access_token"] or body.get("token_type", "").lower() != "bearer":
            fail("token_rejected", "인증 서버가 연결을 승인하지 않았습니다. 다시 로그인하세요.", 401)
        try:
            duration = int(body["expires_in"]) if "expires_in" in body else None
            if duration is not None and not 0 < duration <= 31536000 or len(body["access_token"]) > 16384 or any(ord(c) < 32 for c in body["access_token"]):
                raise ValueError()
            refresh = body.get("refresh_token")
            if refresh is not None and (not isinstance(refresh, str) or not refresh or len(refresh) > 16384 or any(ord(c) < 32 for c in refresh)):
                raise ValueError()
        except Exception:
            fail("token_invalid", "인증 서버 응답의 만료 정보가 올바르지 않습니다.", 502)
        return {"access_token": body["access_token"], "refresh_token": body.get("refresh_token") or (row.get("tokens") or {}).get("refresh_token"), "expires": self.now() + duration if duration is not None else None}

    def callback(self, state, binding, code=None, error=None, issuer=None):
        # Find by unpredictable state, then atomically consume before any token exchange.
        matches = [r for r in self.store.rows() if hmac.compare_digest(str((r.get("attempt") or {}).get("state", "")), str(state or ""))]
        if len(matches) != 1 or not state:
            fail("invalid_state", "로그인 요청을 확인할 수 없습니다.", 400)
        ident = matches[0]["id"]
        with self.store.atomic(ident):
            row = self.store.get(ident)
            attempt = row["attempt"]
            if not binding or not hmac.compare_digest(attempt["binding"], hashlib.sha256(binding.encode()).hexdigest()):
                fail("invalid_binding", "로그인을 시작한 브라우저에서 완료하세요.", 400)
            if attempt["consumed"]:
                fail("replayed_state", "이미 완료된 로그인 요청입니다.", 400)
            attempt["consumed"] = True
            if attempt["expires"] <= self.now():
                row.update(status="failed", reason_code="expired", reason="로그인 요청이 만료되었습니다.")
            elif error:
                row.update(status="failed", reason_code="denied", reason="외부 계정 동의가 완료되지 않았습니다.")
            elif issuer is not None and issuer != row["discovery"]["issuer"]:
                row.update(status="failed", reason_code="issuer_mismatch", reason="로그인 응답의 발급자가 다릅니다.")
            elif not code or len(code) > 4096:
                row.update(status="failed", reason_code="code_missing", reason="로그인 완료 정보가 없습니다.")
            else:
                row.update(status="checking", reason="로그인 결과를 확인하고 있습니다.")
            self.store.put(row)
        if row["status"] == "checking":
            try:
                row["tokens"] = self.token(row, {"grant_type": "authorization_code", "code": code, "code_verifier": attempt["verifier"], "redirect_uri": self.callback_url(), "resource": row["url"]})
                row.update(status="login_complete", reason="로그인이 완료되었습니다. 도구 연결을 확인합니다.", reason_code=None)
            except OAuthError as exc:
                row.update(status="failed", reason_code=exc.code, reason=exc.reason)
            # Cancel during exchange cannot resurrect the connection.
            with self.store.atomic(ident):
                current = self.store.get(ident)
                if current.get("status") != "checking" or current["attempt"]["id"] != attempt["id"]:
                    return public(current), None
                row["attempt"].pop("verifier", None)
                self.store.put(row)
        return public(row), {"type": "mcp-connection-return", "connection_id": ident, "attempt_id": attempt["id"], "state": attempt["frontend_state"]}

    def headers(self, row):
        if row.get("auth_mode") in ("none", "auto"):
            return {}
        if row.get("auth_mode") == "api_key":
            return dict(row["key_headers"])
        tokens = row.get("tokens") or {}
        expiry = tokens.get("expires", 0)
        if expiry is not None and expiry <= self.now() + 30:
            if not tokens.get("refresh_token"):
                fail("login_expired", "외부 계정 연결이 만료되었습니다. 다시 로그인하세요.", 401)
            try:
                tokens = self.token(row, {"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "resource": row["url"]})
            except OAuthError:
                row.update(status="failed", reason_code="refresh_rejected", reason="외부 계정 연결을 갱신하지 못했습니다. 다시 로그인하세요.")
                row.pop("tokens", None)
                self.store.put(row)
                fail("refresh_rejected", row["reason"], 401)
            row["tokens"] = tokens
            self.store.put(row)
        return {"Authorization": "Bearer " + tokens["access_token"]}

    def check(self, ident):
        with self.store.atomic(ident):
            row = self.store.get(ident)
            if row["status"] not in ("login_complete", "connected"):
                fail("login_required", "먼저 외부 계정 로그인을 완료하세요.", 409)
            headers = self.headers(row)
            record = mcp_registry.run_check({"type": "url", "url": row["url"], "transport": "streamable_http", "headers": headers, "_oauth_transport": True}, 8)
            record = mcp_secrets.redact(record, [mcp_secrets.OAuthSecret(v) for v in headers.values()] + [mcp_secrets.OAuthSecret(v.removeprefix("Bearer ")) for v in headers.values()])
            if record.get("status") != "ok":
                row.update(status="failed", reason_code="tools_check_failed", check_error_kind=record.get("error_kind"), reason="도구 연결 검사에 실패했습니다. 권한과 서버 준비 상태를 확인하세요.")
                self.store.put(row)
                return public(row)
            entry = {"type": "url", "url": row["url"], "transport": "streamable_http", "headers": {}, "hyd": {"origin": "user", "oauth_connection": ident, "gate": mcp_registry.gate_of(record), "created_at": mcp_registry._now()}}
            # Gate fingerprints describe the credential-free runtime configuration.
            record["fingerprint"] = mcp_registry.fingerprint(entry)
            entry["hyd"]["gate"]["fingerprint"] = record["fingerprint"]
            registry = mcp_registry.store_for(self.repo)
            existing = registry.servers(self.tenant).get(row["name"])
            if existing and (existing.get("hyd") or {}).get("oauth_connection") != ident:
                fail("name_in_use", "이름이 다른 연결에서 사용되고 있습니다.", 409)
            if existing:
                registry.replace_server(self.tenant, row["name"], entry)
            elif not registry.insert_server(self.tenant, row["name"], entry):
                fail("name_in_use", "이미 사용 중인 도구 연결 이름입니다.", 409)
            registry.save_check(self.tenant, row["name"], record, "OAuth 연결")
            row.update(status="connected", reason="공유 교육 도구 연결 검사를 통과했습니다.", reason_code=None)
            self.store.put(row)
            return public(row)

    def cancel(self, ident, disconnect=False):
        with self.store.atomic(ident):
            row = self.store.get(ident)
            row.pop("tokens", None)
            row.pop("key_headers", None)
            if row.get("attempt"):
                row["attempt"]["consumed"] = True
                row["attempt"].pop("verifier", None)
            registry = mcp_registry.store_for(self.repo)
            existing = registry.servers(self.tenant).get(row["name"])
            if existing and (existing.get("hyd") or {}).get("oauth_connection") == ident:
                registry.delete_server(self.tenant, row["name"])
                registry.delete_checks(self.tenant, [row["name"]])
            row.update(status="disconnected" if disconnect else "failed", reason_code="disconnected" if disconnect else "cancelled", reason="포털의 연결을 해제했습니다. 외부 계정의 동의 철회는 해당 서비스에서 관리하세요." if disconnect else "로그인을 취소했습니다.")
            self.store.put(row)
            return public(row)


def access_headers(repo, tenant_id, name, entry, environ=None):
    ident = (entry.get("hyd") or {}).get("oauth_connection")
    if not ident:
        return {}
    svc = Service(repo, tenant_id, environ)
    with svc.store.atomic(ident):
        row = svc.store.get(ident)
        if row["status"] != "connected" or row["name"] != name or row["url"] != entry.get("url"):
            fail("connection_not_ready", "이 도구의 외부 계정 연결을 다시 확인하세요.", 401)
        validate_url(row["url"], svc.env)
        return svc.headers(row)


def mark_auth_failure(repo, tenant_id, name, entry, reason_code="login_required", environ=None):
    """An observed upstream auth rejection invalidates local authority, without replay."""
    ident = (entry.get("hyd") or {}).get("oauth_connection")
    if not ident:
        return
    svc = Service(repo, tenant_id, environ)
    with svc.store.atomic(ident):
        row = svc.store.get(ident)
        if row["name"] != name or row["url"] != entry.get("url"):
            fail("connection_not_ready", "도구 연결 정보가 일치하지 않습니다.", 401)
        code = "missing_scope" if reason_code == "missing_scope" else "login_required"
        row.update(status="login_required", reason_code=code, reason="외부 계정의 권한이 부족합니다. 연결 권한을 다시 확인하세요." if code == "missing_scope" else "외부 계정 연결을 다시 확인하세요.")
        row.pop("tokens", None)
        svc.store.put(row)


def mount(app, *, runtime_factory, audit):
    import asyncio
    from fastapi import HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse

    def service():
        rt = runtime_factory()
        if rt is None:
            fail("runtime_unavailable", "연결 서비스가 준비되지 않았습니다.", 503)
        return Service(rt.repo, rt.tenant_id)

    async def run(fn):
        try:
            return await asyncio.to_thread(fn)
        except OAuthError as exc:
            raise HTTPException(exc.status, {"reason_code": exc.code, "reason": exc.reason}) from None
        except mcp_registry.RegistryError as exc:
            raise HTTPException(exc.status, {"reason_code": "invalid_configuration", "reason": exc.reason}) from None
        except mcp_secrets.SecretError:
            raise HTTPException(503, {"reason_code": "storage_unavailable", "reason": "연결 저장소가 준비되지 않았습니다."}) from None

    def browser_guard(request):
        supplied = request.headers.get("origin")
        if supplied and supplied != origin(service().callback_url()) or request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(403, {"reason_code": "cross_origin_rejected", "reason": "포털에서 연결을 시작하세요."})

    @app.get("/api/mcp/connections")
    async def listing():
        return await run(lambda: service().listing())

    @app.post("/api/mcp/connections/prepare")
    async def prepare(body: dict, request: Request):
        browser_guard(request)
        return await run(lambda: service().prepare(body))

    @app.get("/api/mcp/connections/callback")
    async def callback(request: Request):
        try:
            svc = service()
            q = request.query_params
            _, message = await asyncio.to_thread(svc.callback, q.get("state"), request.cookies.get("hyd_mcp_oauth"), q.get("code"), q.get("error"), q.get("iss"))
            target = origin(svc.callback_url())
            script = "if(window.opener)window.opener.postMessage(" + json.dumps(message).replace("<", "\\u003c") + "," + json.dumps(target) + ");"
            html = "<!doctype html><meta charset=utf-8><title>도구 연결</title><p>로그인 결과를 확인했습니다. 포털로 돌아가세요.</p><script>" + script + "</script>"
            return HTMLResponse(html, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        except OAuthError:
            return HTMLResponse("<!doctype html><meta charset=utf-8><p>로그인 요청을 확인할 수 없습니다. 포털에서 다시 시작하세요.</p>", status_code=400, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})

    @app.get("/api/mcp/connections/{ident}")
    async def detail(ident: str):
        return await run(lambda: public(service().store.get(ident)))

    @app.post("/api/mcp/connections/{ident}/start")
    async def start(ident: str, request: Request):
        browser_guard(request)
        binding = request.cookies.get("hyd_mcp_oauth") or secrets.token_urlsafe(32)
        result = await run(lambda: service().start(ident, binding))
        response = JSONResponse(result, headers={"Cache-Control": "no-store"})
        response.set_cookie("hyd_mcp_oauth", binding, httponly=True, secure=urlsplit(service().callback_url()).scheme == "https", samesite="lax", max_age=TTL, path="/api/mcp/connections")
        return response

    @app.post("/api/mcp/connections/{ident}/check")
    async def check(ident: str, request: Request):
        browser_guard(request)
        return await run(lambda: service().check(ident))

    @app.post("/api/mcp/connections/{ident}/cancel")
    async def cancel(ident: str, request: Request):
        browser_guard(request)
        return await run(lambda: service().cancel(ident))

    @app.post("/api/mcp/connections/{ident}/disconnect")
    async def disconnect(ident: str, request: Request):
        browser_guard(request)
        return await run(lambda: service().cancel(ident, True))
