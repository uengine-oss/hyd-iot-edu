"""Meeting-specific Google contracts; no Google network or real OAuth account."""
import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from pydantic import ValidationError
from starlette.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from students._template.google_meeting_mcp import auth
from students._template.google_meeting_mcp.server import (
    Attendee, Attachment, BearerGate, Failure, GoogleAPI, MeetingTools, build,
)

START, END, ZONE = "2026-10-20T14:00:00+09:00", "2026-10-20T15:00:00+09:00", "Asia/Seoul"
PERSON, ROOM = "participant@company.co.kr", "room@resource.calendar.google.com"


class FakeAPI:
    def __init__(self, events=None, failure=None):
        self.events, self.calls, self.failure = events or {}, [], failure

    def request(self, method, url, *, params=None, body=None, raw=False):
        self.calls.append((method, url, params, body))
        if self.failure:
            raise self.failure
        if method == "GET":
            key = url.rsplit("/", 1)[-1]
            if key not in self.events:
                raise Failure("GOOGLE_HTTP_ERROR", 404, 404)
            return self.events[key]
        if method == "POST":
            self.events[body["id"]] = body
            return body
        raise AssertionError(method)


def create(tools, **overrides):
    arguments = dict(calendar_id="primary", idempotency_key="approved-instance/task-invite", summary="고객 리뷰",
                     start=START, end=END, time_zone=ZONE, room_email=ROOM,
                     attendees=[Attendee(email=PERSON)], attachments=[])
    arguments.update(overrides)
    return tools.invoke(tools.create_event, **arguments)


def test_create_is_disabled_and_calendar_is_explicit():
    api = FakeAPI()
    assert create(MeetingTools(api))["status"] == 403
    assert create(MeetingTools(api, True, ["other"]))["status"] == 403
    assert api.calls == []


def test_idempotent_create_invites_only_once_and_conflicting_payload_is_rejected():
    api = FakeAPI()
    tools = MeetingTools(api, True, ["primary"])
    first, replay = create(tools), create(tools)
    assert first["result"] == replay["result"] == "ok"
    assert first["document"]["event_id"] == replay["document"]["event_id"]
    assert replay["document"]["idempotent_replay"] is True
    posts = [call for call in api.calls if call[0] == "POST"]
    assert len(posts) == 1
    assert posts[0][2] == {"sendUpdates": "all", "supportsAttachments": "true"}
    body = posts[0][3]
    assert body["attendees"] == [{"email": PERSON, "optional": False}, {"email": ROOM, "resource": True}]
    assert not any("responseStatus" in row for row in body["attendees"])
    assert create(tools, summary="변경된 승인안")["error_kind"] == "IDEMPOTENCY_CONFLICT"
    assert len([call for call in api.calls if call[0] == "POST"]) == 1


def test_timeout_after_insert_is_unknown_then_lookup_recovers_without_replay():
    class TimeoutAPI(FakeAPI):
        def request(self, method, url, **kwargs):
            result = super().request(method, url, **kwargs)
            if method == "POST":
                raise Failure("NETWORK_RESULT_UNKNOWN", 502)
            return result
    api = TimeoutAPI()
    tools = MeetingTools(api, True, ["primary"])
    assert create(tools)["error_kind"] == "NETWORK_RESULT_UNKNOWN"
    assert create(tools)["document"]["idempotent_replay"] is True
    assert len([call for call in api.calls if call[0] == "POST"]) == 1


def test_concurrent_duplicate_409_verifies_existing_fingerprint():
    class ConcurrentAPI(FakeAPI):
        def request(self, method, url, **kwargs):
            result = super().request(method, url, **kwargs)
            if method == "POST":
                raise Failure("GOOGLE_HTTP_ERROR", 409, 409)
            return result
    result = create(MeetingTools(ConcurrentAPI(), True, ["primary"]))
    assert result["result"] == "ok" and result["document"]["idempotent_replay"]


@pytest.mark.parametrize("change", [
    {"start": "2026-10-20T14:00:00"}, {"end": START}, {"time_zone": "fictional/zone"},
    {"start": "2026-10-20T14:00:00+00:00"}, {"room_email": "room@example.com"},
    {"attendees": [Attendee(email=PERSON), Attendee(email=PERSON)]},
    {"attendees": [Attendee(email=ROOM)]}, {"attendees": []},
    {"attendees": [Attendee(email=PERSON, required=False)]}, {"idempotency_key": " "},
])
def test_invalid_inputs_never_reach_google(change):
    api = FakeAPI()
    result = create(MeetingTools(api, True, ["primary"]), **change)
    assert result["result"] == "error" and result["status"] == 422
    assert api.calls == []


@pytest.mark.parametrize("address", ["admin@example.com", "bad", "someone@domain.test"])
def test_demo_or_invalid_attendee_rejected_at_schema_boundary(address):
    with pytest.raises(ValidationError):
        Attendee(email=address)


@pytest.mark.parametrize("url", ["http://drive.google.com/x", "https://evil.test/doc", "https://drive.google.com@evil.test/x"])
def test_attachment_requires_google_file_url(url):
    with pytest.raises(ValidationError):
        Attachment(file_url=url, title="자료")


def test_duplicate_attachments_rejected_before_google():
    api = FakeAPI()
    attachment = Attachment(file_url="https://docs.google.com/document/d/real-file/edit", title="자료")
    assert create(MeetingTools(api, True, ["primary"]), attachments=[attachment, attachment])["status"] == 422
    assert api.calls == []


@pytest.mark.parametrize("response,expected", [("accepted", True), ("declined", False), ("tentative", False), ("needsAction", False), (None, False)])
def test_required_attendance_checks_actual_roster(response, expected):
    event = {"id": "event1", "attendees": [{"email": "optional@company.co.kr", "responseStatus": "declined"}]}
    if response:
        event["attendees"].append({"email": PERSON, "responseStatus": response})
    tools = MeetingTools(FakeAPI({"event1": event}))
    result = tools.invoke(tools.get_event, "primary", "event1", [PERSON])
    assert result["document"]["all_required_accepted"] is expected


@pytest.mark.parametrize("extra", [{"status": "cancelled"}, {"attendeesOmitted": True}])
def test_cancelled_or_omitted_event_cannot_confirm_meeting(extra):
    event = {"id": "event1", "attendees": [{"email": PERSON, "responseStatus": "accepted"}], **extra}
    tools = MeetingTools(FakeAPI({"event1": event}))
    assert tools.get_event("primary", "event1", [PERSON])["all_required_accepted"] is False


@pytest.mark.parametrize("required", [[], [PERSON, PERSON.upper()]])
def test_empty_or_duplicate_required_roster_is_failure(required):
    api = FakeAPI()
    tools = MeetingTools(api)
    assert tools.invoke(tools.get_event, "primary", "event1", required)["status"] == 422
    assert api.calls == []


def test_freebusy_inaccessible_calendar_is_not_reported_free():
    class BusyAPI(FakeAPI):
        def request(self, *args, **kwargs):
            return {"calendars": {"primary": {"errors": [{"reason": "notFound"}]}}}
    tools = MeetingTools(BusyAPI())
    assert tools.invoke(tools.free_busy, ["primary"], START, END, ZONE)["error_kind"] == "AVAILABILITY_UNVERIFIED"


def test_drive_search_escapes_query_and_doc_read_preserves_korean():
    class DriveAPI(FakeAPI):
        def request(self, method, url, **kwargs):
            self.calls.append((method, url, kwargs))
            if kwargs.get("raw"):
                return "회의 원문: 자료 공유 48시간".encode()
            if url.endswith("/files"):
                return {"files": [], "nextPageToken": "next"}
            return {"id": "file1", "mimeType": "application/vnd.google-apps.document", "webViewLink": "https://docs.google.com/document/d/file1/edit"}
    api = DriveAPI()
    tools = MeetingTools(api)
    assert tools.search_files("고객's", 2)["nextPageToken"] == "next"
    assert "고객\\'s" in api.calls[0][2]["params"]["q"]
    assert tools.read_file("file1")["text"] == "회의 원문: 자료 공유 48시간"
    assert api.calls[-1][1].endswith("/file1/export")


def test_missing_auth_health503_and_mcp_tool_error(tmp_path):
    tools = MeetingTools(GoogleAPI(tmp_path / "missing.json"))
    server = build(tools)
    with TestClient(server.http_app()) as http:
        response = http.get("/healthz")
        assert response.status_code == 503
        assert response.json()["google_read_verified"] is False

    async def check():
        async with Client(server) as client:
            listed = await client.list_tools()
            assert {tool.name for tool in listed} == {"search_files", "read_file", "free_busy", "get_event", "create_event"}
            hints = {tool.name: tool.annotations.readOnlyHint for tool in listed}
            assert hints == {"search_files": True, "read_file": True, "free_busy": True, "get_event": True, "create_event": False}
            event_schema = next(tool.inputSchema for tool in listed if tool.name == "get_event")
            assert set(event_schema["required"]) == {"calendar_id", "event_id", "required_emails"}
            result = await client.call_tool("search_files", {"text": "회의"}, raise_on_error=False)
            assert result.is_error is True
            document = json.loads(result.content[0].text)
            assert document["result"] == "error" and document["status"] == 503
            assert document["error_kind"] == "AUTH_REQUIRED"
            assert len(document["trace_id"]) == 32
    asyncio.run(check())


def test_host_mcp_bearer_is_separate_and_required(tmp_path):
    from starlette.middleware import Middleware
    server = build(MeetingTools(GoogleAPI(tmp_path / "missing.json")))
    key = "test-local-mcp-key-0123456789abcdef"
    with TestClient(server.http_app(middleware=[Middleware(BearerGate, key=key)])) as client:
        assert client.get("/healthz").status_code == 401
        assert client.get("/healthz", headers={"Authorization": "Bearer " + key}).status_code == 503


def test_oauth_rejects_checkout_and_non_google_client_before_browser(tmp_path):
    with pytest.raises(ValueError):
        auth.private_path(ROOT / "token.json")
    wrong = tmp_path / "client.json"
    wrong.write_text(json.dumps({"installed": {"auth_uri": "https://evil.test/login"}}))
    with pytest.raises(ValueError):
        auth.login(wrong, tmp_path / "token.json", flow_factory=lambda *_a, **_k: pytest.fail("browser must not open"))


def test_oauth_uses_official_browser_loopback_pkce_and_does_not_print_token(tmp_path, capsys):
    client = tmp_path / "client.json"
    client.write_text(json.dumps({"installed": {"client_id": "test-client", "client_secret": "test-secret",
                                              "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                                              "token_uri": "https://oauth2.googleapis.com/token"}}))
    seen = {}
    class Credentials:
        valid, refresh_token = True, "test-refresh-secret"
        def has_scopes(self, value):
            return value == auth.scopes(False)
        def to_json(self):
            return '{"fixture": "test-refresh-secret"}'
    class Flow:
        def run_local_server(self, **kwargs):
            seen.update(kwargs)
            return Credentials()
    def factory(_config, requested, **kwargs):
        assert requested == auth.READ_SCOPES and kwargs["autogenerate_code_verifier"] is True
        return Flow()
    output = tmp_path / "token.json"
    auth.login(client, output, flow_factory=factory)
    assert seen["host"] == "127.0.0.1" and seen["port"] == 0 and seen["open_browser"] is True
    assert "{url}" not in seen["authorization_prompt_message"]
    assert json.loads(output.read_text())["fixture"] == "test-refresh-secret"
    assert "test-refresh-secret" not in capsys.readouterr().out
    assert list(tmp_path.glob(".oauth-*")) == []


def test_manually_edited_event_cannot_replay_stale_private_fingerprint():
    api = FakeAPI()
    tools = MeetingTools(api, True, ["primary"])
    first = create(tools)
    event_id = first["document"]["event_id"]
    api.events[event_id]["summary"] = "원래 승인 뒤 수동 변경"
    assert create(tools)["error_kind"] == "IDEMPOTENCY_CONFLICT"


def test_partial_oauth_consent_is_rejected_without_writing_token(tmp_path):
    client = tmp_path / "client.json"
    client.write_text(json.dumps({"installed": {"client_id": "fixture", "client_secret": "fixture",
                                              "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                                              "token_uri": "https://oauth2.googleapis.com/token"}}))
    class Partial:
        valid, refresh_token, granted_scopes = True, "fixture", [auth.BASE + "drive.readonly"]
        def has_scopes(self, _scopes):
            return True  # Official Credentials.has_scopes may reflect requested scopes.
    class Flow:
        def run_local_server(self, **_kwargs):
            return Partial()
    output = tmp_path / "token.json"
    with pytest.raises(ValueError, match="SCOPES_REQUIRED"):
        auth.login(client, output, flow_factory=lambda *_a, **_k: Flow())
    assert not output.exists()


def test_http_timeout_is_failure_with_trace_and_does_not_replay_post(tmp_path, monkeypatch, caplog):
    from google.auth.transport import requests as transport
    from requests.exceptions import Timeout
    calls = []
    class Session:
        def __init__(self, _credentials, **kwargs):
            assert kwargs["max_refresh_attempts"] == 0
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            pass
        def request(self, method, url, **kwargs):
            calls.append((method, url, kwargs))
            raise Timeout("must-not-leak-token-in-exception-fixture")
    monkeypatch.setattr(transport, "AuthorizedSession", Session)
    api = GoogleAPI(tmp_path / "missing")
    monkeypatch.setattr(api, "credentials", lambda: object())
    tools = MeetingTools(api)
    result = tools.invoke(api.request, "POST", "https://www.googleapis.com/calendar/v3/calendars/primary/events")
    assert result["result"] == "error" and result["status"] == 502
    assert result["error_kind"] == "NETWORK_RESULT_UNKNOWN" and len(result["trace_id"]) == 32
    assert len(calls) == 1 and calls[0][2]["allow_redirects"] is False
    assert "must-not-leak-token" not in json.dumps(result) + caplog.text


@pytest.mark.parametrize("http_status,expected", [(401, 401), (403, 403), (429, 429), (500, 502), (302, 502)])
def test_google_http_errors_do_not_become_success_or_leak_body(tmp_path, monkeypatch, http_status, expected):
    from google.auth.transport import requests as transport
    class Response:
        status_code = http_status
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            pass
        def iter_content(self, _size):
            pytest.fail("Error or redirect body must not be read or logged")
    class Session:
        def __init__(self, *_args, **_kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            pass
        def request(self, *_args, **_kwargs):
            return Response()
    monkeypatch.setattr(transport, "AuthorizedSession", Session)
    api = GoogleAPI(tmp_path / "missing")
    monkeypatch.setattr(api, "credentials", lambda: object())
    result = MeetingTools(api).invoke(api.request, "GET", "https://www.googleapis.com/drive/v3/files")
    assert result["status"] == expected and result["upstream_status"] == http_status
    assert result["error_kind"] == "GOOGLE_HTTP_ERROR"


def test_contract_paths_are_from_actual_mcp_success_envelopes():
    contract = json.loads((ROOT / "students/_template/google_meeting_mcp/meeting-contract.json").read_text(encoding="utf-8"))
    created = create(MeetingTools(FakeAPI(), True, ["primary"]))
    assert isinstance(created["document"]["event_id"], str)
    assert contract["Activity_invite"]["extract"]["event_id"]["path"] == "document.event_id"
    tools = MeetingTools(FakeAPI({"event1": {"id": "event1", "attendees": []}}))
    checked = tools.invoke(tools.get_event, "primary", "event1", [PERSON])
    assert isinstance(checked["document"]["all_required_accepted"], bool)
    assert contract["Activity_check"]["extract"]["all_required_accepted"]["path"] == "document.all_required_accepted"
    assert contract["Activity_check"]["effect"] is False
