"""Desktop OAuth. Credentials stay on this host, outside any Git checkout."""
from __future__ import annotations

import json
import os
from pathlib import Path

BASE = "https://www.googleapis.com/auth/"
READ_SCOPES = [BASE + "drive.readonly", BASE + "calendar.events.readonly", BASE + "calendar.events.freebusy"]


def scopes(allow_create=False):
    return [BASE + "drive.readonly", BASE + ("calendar.events" if allow_create else "calendar.events.readonly"),
            BASE + "calendar.events.freebusy"]


def token_path():
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share")
    return Path(os.environ.get("GOOGLE_MEETING_TOKEN_FILE") or base / "HYD" / "google-meeting" / "token.json")


def private_path(path):
    path = Path(path).expanduser().resolve()
    if any((parent / ".git").exists() for parent in [path.parent, *path.parents]):
        raise ValueError("OAuth files must be outside Git checkouts")
    return path


def save_credentials(credentials, path):
    path = private_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive temporary file + atomic replacement; no token in console or trace.
    import tempfile
    fd, temporary = tempfile.mkstemp(prefix=".oauth-", dir=path.parent)
    try:
        os.chmod(temporary, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            info = json.loads(credentials.to_json())
            granted = getattr(credentials, "granted_scopes", None)
            if granted is not None:
                info["scopes"] = list(granted)
            stream.write(json.dumps(info, ensure_ascii=False))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_credentials(path, allow_create=False):
    from google.oauth2.credentials import Credentials
    path = private_path(path)
    if not path.is_file():
        raise ValueError("AUTH_REQUIRED")
    info = json.loads(path.read_text(encoding="utf-8-sig"))
    if info.get("token_uri") != "https://oauth2.googleapis.com/token":
        raise ValueError("INVALID_TOKEN_ENDPOINT")
    needed = set(scopes(allow_create))
    granted = set(info.get("scopes", []))
    # calendar.events permits the read operation too.
    if BASE + "calendar.events" in granted:
        granted.add(BASE + "calendar.events.readonly")
    if not needed.issubset(granted):
        raise ValueError("SCOPES_REQUIRED")
    cred = Credentials.from_authorized_user_info(info)
    if not cred.valid and not cred.refresh_token:
        raise ValueError("AUTH_REQUIRED")
    return cred


def login(client_file, output, allow_create=False, flow_factory=None):
    client_file, output = private_path(client_file), private_path(output)
    config = json.loads(client_file.read_text(encoding="utf-8-sig"))
    installed = config.get("installed", {})
    if (installed.get("auth_uri") != "https://accounts.google.com/o/oauth2/auth"
            or installed.get("token_uri") != "https://oauth2.googleapis.com/token"
            or not installed.get("client_id") or not installed.get("client_secret")):
        raise ValueError("Google Desktop app OAuth client JSON is required")
    if flow_factory is None:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow_factory = InstalledAppFlow.from_client_config
    flow = flow_factory(config, scopes(allow_create), autogenerate_code_verifier=True)
    import logging
    # Library callback request logs could contain an authorization code at INFO.
    logger = logging.getLogger("google_auth_oauthlib.flow")
    previous_level = logger.level
    logger.setLevel(logging.WARNING)
    try:
        credentials = flow.run_local_server(
            host="127.0.0.1", port=0, open_browser=True, timeout_seconds=180,
            authorization_prompt_message="Google 로그인 창에서 직접 계정과 권한을 확인하세요.",
            success_message="Google 승인 응답을 받았습니다. 이 창을 닫아도 됩니다.",
            prompt="consent", access_type="offline")
    finally:
        logger.setLevel(previous_level)
    if credentials is None or not credentials.valid or not credentials.refresh_token:
        raise ValueError("AUTH_INCOMPLETE")
    granted = getattr(credentials, "granted_scopes", None)
    if (granted is not None and not set(scopes(allow_create)).issubset(set(granted))) or not credentials.has_scopes(scopes(allow_create)):
        raise ValueError("SCOPES_REQUIRED")
    save_credentials(credentials, output)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Google browser OAuth; never prints credentials")
    parser.add_argument("command", choices=["status", "login"])
    parser.add_argument("--client-file", type=Path)
    parser.add_argument("--token-file", type=Path, default=token_path())
    parser.add_argument("--allow-create", action="store_true", help="Request event creation scope, after explicit authorization")
    args = parser.parse_args()
    try:
        if args.command == "login":
            if args.client_file is None:
                raise ValueError("CLIENT_FILE_REQUIRED")
            login(args.client_file, args.token_file, args.allow_create)
        cred = load_credentials(args.token_file, args.allow_create)
        print(json.dumps({"credential_configured": True, "token_currently_valid": cred.valid,
                          "google_read_verified": False, "allow_create": args.allow_create}))
        return 0
    except Exception as exc:
        # OAuth failures can embed token-bearing URLs; never format the exception.
        print(json.dumps({"credential_configured": False, "error_type": type(exc).__name__,
                          "action": "Supply a Desktop OAuth client file, then sign in in Google's browser window"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
