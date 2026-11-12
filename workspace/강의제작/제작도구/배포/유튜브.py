"""유튜브 일부 공개 올리기(배포 B-2).

언제: 확정 영상 mp4를 사용자 채널에 「일부 공개 · 아동용 아님」으로 올리고 제목을 대조할 때.
무엇: 표준 라이브러리만 쓴다(YouTube Data API v3, OAuth 데스크톱 클라이언트, 이어 올리기).
  인증   <py> workspace/강의제작/제작도구/배포/유튜브.py 인증
         작업/_로컬/배포/유튜브_클라이언트.json(Google Cloud에서 받은 데스크톱 OAuth 클라이언트)을 읽어
         동의 주소를 브라우저로 열고, 사용자가 로그인 · 동의하면 갱신 토큰을 작업/_로컬/배포/유튜브토큰.json에 쓴다.
  올리기 <py> workspace/강의제작/제작도구/배포/유튜브.py 올리기 <mp4> --제목 "1-1 이론 · 지식 자산화" [--설명 "…"] [--dry]
         일부 공개(unlisted) · 아동용 아님 · 교육 분류(27)로 올리고, 받은 영상 id를 작업/_로컬/배포/영상제목.json에 더한 뒤
         oEmbed 제목을 대조한다. --dry는 네트워크 없이 올릴 파일 · 크기 · 제목만 찍는다.
  대조   <py> workspace/강의제작/제작도구/배포/유튜브.py 대조 <영상 id> --제목 "…"
비밀: 클라이언트 비밀값과 토큰은 화면에 찍지 않고 git 밖 작업/_로컬/배포/에만 둔다. 게시는 외부 공개이므로 작업자는 올리기 전에
  파일 · 제목 목록으로 사용자 승인을 받는다(배포 B-6).
"""
import argparse, base64, hashlib, http.client, http.server, json, secrets, sys, threading, time, urllib.error, urllib.parse, urllib.request, webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
LOCAL = ROOT / "작업" / "_로컬" / "배포"
CLIENT = LOCAL / "유튜브_클라이언트.json"
TOKEN = LOCAL / "유튜브토큰.json"
TITLES = LOCAL / "영상제목.json"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"
CHUNK = 8 * 1024 * 1024  # 256 KiB의 배수


def fail(msg):
    sys.exit(f"유튜브.py: {msg}")


def client():
    if not CLIENT.exists():
        fail(f"{CLIENT}가 없다 — Google Cloud 콘솔 「API 및 서비스 → 사용자 인증 정보」에서 데스크톱 앱 OAuth 클라이언트의 JSON을 받아 이 자리에 둔다")
    c = json.loads(CLIENT.read_text(encoding="utf-8")).get("installed")
    if not c:
        fail(f"{CLIENT}: 「installed」 항목이 없다 — 클라이언트 종류가 「데스크톱 앱」이어야 한다")
    return c["client_id"], c["client_secret"]


def post_form(url, fields):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(fields).encode(), method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        fail(f"{url} {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")


def cmd_auth(_):
    cid, csec = client()
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
            self.wfile.write("동의를 받았습니다. 이 창을 닫아도 됩니다.".encode("utf-8"))

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    redirect = f"http://127.0.0.1:{srv.server_port}"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": redirect, "response_type": "code", "scope": SCOPE,
        "access_type": "offline", "prompt": "consent", "code_challenge": challenge,
        "code_challenge_method": "S256", "state": state})
    print("브라우저에서 YouTube 채널 계정으로 로그인하고 동의한다. 창이 열리지 않으면 이 주소를 연다:\n" + url, flush=True)
    webbrowser.open(url)
    t = threading.Thread(target=srv.handle_request, daemon=True); t.start(); t.join(timeout=600)
    srv.server_close()
    if got.get("state") != state or "code" not in got:
        fail(f"동의를 받지 못했다({got.get('error', '10분 안에 응답 없음')})")
    tok = post_form("https://oauth2.googleapis.com/token", {
        "client_id": cid, "client_secret": csec, "code": got["code"], "code_verifier": verifier,
        "grant_type": "authorization_code", "redirect_uri": redirect})
    if "refresh_token" not in tok:
        fail("갱신 토큰이 오지 않았다 — 계정의 「서드 파티 액세스」에서 이 앱을 지운 뒤 다시 인증한다")
    LOCAL.mkdir(parents=True, exist_ok=True)
    TOKEN.write_text(json.dumps({"refresh_token": tok["refresh_token"], "scope": tok.get("scope"),
                                 "받은 때": time.strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False), encoding="utf-8")
    print(f"토큰을 {TOKEN}에 썼다(범위 {tok.get('scope')})")


def access_token():
    if not TOKEN.exists():
        fail(f"{TOKEN}가 없다 — 먼저 「인증」을 돌린다")
    cid, csec = client()
    rt = json.loads(TOKEN.read_text(encoding="utf-8"))["refresh_token"]
    return post_form("https://oauth2.googleapis.com/token", {
        "client_id": cid, "client_secret": csec, "refresh_token": rt, "grant_type": "refresh_token"})["access_token"]


def oembed_title(vid):
    u = "https://www.youtube.com/oembed?" + urllib.parse.urlencode({"url": f"https://youtu.be/{vid}", "format": "json"})
    for _ in range(12):
        try:
            with urllib.request.urlopen(u, timeout=30) as r:
                return json.loads(r.read())["title"]
        except urllib.error.HTTPError:
            time.sleep(10)  # 막 올린 영상은 처리 중이라 잠시 404를 돌려준다
    fail(f"{vid}: oEmbed가 2분 동안 제목을 돌려주지 않는다 — Studio에서 처리 상태를 본다")


def cmd_check(a):
    t = oembed_title(a.id)
    if t != a.제목:
        fail(f"{a.id}: 유튜브 제목 「{t}」이 제목표 「{a.제목}」과 다르다")
    print(f"{a.id}: 제목 일치 「{t}」")


def put_chunk(loc, sess, data, start, size):
    end = start + len(data) - 1
    for attempt in range(5):
        try:
            c = http.client.HTTPSConnection(loc.netloc, timeout=300)
            c.request("PUT", sess, body=data, headers={"Content-Length": str(len(data)),
                                                        "Content-Range": f"bytes {start}-{end}/{size}"})
            r = c.getresponse(); txt = r.read().decode("utf-8", "replace"); rng = r.getheader("Range"); c.close()
            return r.status, txt, rng
        except (OSError, http.client.HTTPException) as e:
            if attempt == 4:
                fail(f"{start} 바이트에서 연결이 다섯 번 끊겼다: {e}")
            time.sleep(5 * (attempt + 1))


def cmd_upload(a):
    f = Path(a.mp4)
    if not f.is_file():
        fail(f"{f}가 없다")
    size = f.stat().st_size
    meta = {"snippet": {"title": a.제목, "description": a.설명 or "", "categoryId": "27", "defaultLanguage": "ko"},
            "status": {"privacyStatus": "unlisted", "selfDeclaredMadeForKids": False, "embeddable": True}}
    print(f"올릴 것: {f.name} · {size / 1e6:.1f} MB · 제목 「{a.제목}」 · 일부 공개 · 아동용 아님")
    if a.dry:
        return
    tok = access_token()
    c = http.client.HTTPSConnection("www.googleapis.com", timeout=120)
    c.request("POST", "/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
              body=json.dumps(meta, ensure_ascii=False).encode("utf-8"), headers={
                  "Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8",
                  "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"})
    r = c.getresponse(); txt = r.read().decode("utf-8", "replace"); location = r.getheader("Location"); c.close()
    if r.status != 200 or not location:
        fail(f"올리기 시작 {r.status}: {txt[:400]}")
    loc = urllib.parse.urlparse(location)
    sess = loc.path + "?" + loc.query
    sent, result = 0, None
    with f.open("rb") as fh:
        while result is None:
            fh.seek(sent)
            status, txt, rng = put_chunk(loc, sess, fh.read(CHUNK), sent, size)
            if status in (200, 201):
                result = json.loads(txt)
            elif status == 308:
                sent = int(rng.split("-")[1]) + 1 if rng else 0
                print(f"  {sent * 100 // size}%", flush=True)
            else:
                fail(f"{sent} 바이트에서 {status}: {txt[:400]}")
    vid = result["id"]
    privacy = result.get("status", {}).get("privacyStatus")
    if privacy != "unlisted":
        fail(f"{vid}: 공개 상태가 {privacy}로 올라갔다 — Studio에서 바로 「일부 공개」로 바꾼다")
    titles = json.loads(TITLES.read_text(encoding="utf-8")) if TITLES.exists() else {}
    titles[vid] = a.제목
    TITLES.write_text(json.dumps(titles, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"올림: {vid} · 일부 공개 · 주소표 {TITLES.name}에 더함")
    a.id = vid
    cmd_check(a)


def main():
    p = argparse.ArgumentParser(description="유튜브 일부 공개 올리기(배포 B-2)")
    s = p.add_subparsers(dest="cmd", required=True)
    s.add_parser("인증").set_defaults(fn=cmd_auth)
    u = s.add_parser("올리기"); u.add_argument("mp4"); u.add_argument("--제목", required=True)
    u.add_argument("--설명"); u.add_argument("--dry", action="store_true"); u.set_defaults(fn=cmd_upload)
    k = s.add_parser("대조"); k.add_argument("id"); k.add_argument("--제목", required=True); k.set_defaults(fn=cmd_check)
    a = p.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
