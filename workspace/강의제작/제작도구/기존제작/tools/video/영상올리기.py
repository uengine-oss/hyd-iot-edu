"""학생이 보는 영상 mp4를 GitHub Release 「영상」에 올리고(같은 이름의 이전 판은 바꿔 끼움), 학생 주소로 다시 받아 바이트를 대조하고, 노션에 걸 주소를 찍는다.
언제: 영상(이론 · 실습)의 검사와 검토가 끝나 학생에게 낼 때. 새 영상 파일은 git에 넣지 않는다(CLAUDE.md 2절, 영상 V-7).
명령: <py> workspace/강의제작/제작도구/기존제작/tools/video/영상올리기.py <영상.mp4 …> [--시험]

- 파일 이름은 V-7의 `<과정>_<NN>회차_<번호>_<이론|실습>_<이름>.mp4`여야 한다. GitHub는 한글 첨부 이름을 「default.mp4」로 바꾸므로
  첨부 이름은 `<int|pro>-<NN>-<번호>-<theory|lab>.mp4`로 바꿔 올린다(과정 · 회차 · 번호 · 종류로 영상 하나가 정해진다).
- 같은 영상의 옛 판이 `산출물/영상/<과정>/`(git)에 있으면 지운다. 그 판은 git 이력에 남고, 최신 판은 Release 한 곳에만 있다.
- 자격은 이 PC의 git 자격 증명(`git credential fill`)을 쓰고 값은 찍지 않는다. --시험: 이름 · 크기만 보고 올리지 않는다.
"""
import argparse, hashlib, json, re, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path

REPO = "uengine-oss/hyd-iot-edu"
TAG = "영상"
API = f"https://api.github.com/repos/{REPO}"
LIMIT = 2 * 1024 ** 3                     # Release 첨부 한도 2 GiB
G = Path(__file__).resolve().parents[4]   # workspace/강의제작
NAME = re.compile(r"(통합반|실전반)_(\d\d)회차_(\d\d)_(이론|실습)_.+\.mp4")


def asset_name(p):
    m = NAME.fullmatch(p.name)
    if not m:
        sys.exit(f"{p}: 이름이 <과정>_<NN>회차_<번호>_<이론|실습>_<이름>.mp4 꼴이 아니다(영상 V-7)")
    course, nn, no, kind = m.groups()
    return f"{'int' if course == '통합반' else 'pro'}-{nn}-{no}-{'theory' if kind == '이론' else 'lab'}.mp4", course


def token():
    r = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n", capture_output=True, text=True)
    pw = dict(l.split("=", 1) for l in r.stdout.splitlines() if "=" in l).get("password")
    if r.returncode or not pw:
        sys.exit("github.com 자격 증명이 없다 — 이 PC의 git으로 push가 되는지 먼저 본다")
    return pw


def call(url, tok, data=None, method=None, ctype="application/json"):
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json", "Content-Type": ctype})
    with urllib.request.urlopen(req) as f:
        body = f.read()
    return json.loads(body) if body else None


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--시험", dest="test", action="store_true")
    a = ap.parse_args()
    jobs = []
    for v in map(Path, a.videos):
        if not v.is_file():
            sys.exit(f"{v}: 파일이 없다")
        if v.stat().st_size >= LIMIT:
            sys.exit(f"{v}: 2 GiB 이상 — Release 첨부 한도를 넘는다")
        jobs.append((v, *asset_name(v)))
    if a.test:
        for v, name, _ in jobs:
            print(f"시험 {v.name} → {name} ({v.stat().st_size / 1024 ** 2:.1f} MiB)")
        return
    tok = token()
    rel = call(f"{API}/releases/tags/{urllib.parse.quote(TAG)}", tok)
    for v, name, course in jobs:
        data = v.read_bytes()
        # 새 판을 임시 이름으로 올려 대조한 뒤에만 옛 판을 지우고 이름을 바꾼다 — 실패해도 노션의 옛 링크는 살아 있다
        have = {x["name"]: x["id"] for x in call(f"{API}/releases/{rel['id']}/assets?per_page=100", tok)}
        if name + ".new" in have:
            call(f"{API}/releases/assets/{have[name + '.new']}", tok, method="DELETE")
        up = rel["upload_url"].split("{")[0] + "?name=" + urllib.parse.quote(name + ".new")
        new = call(up, tok, data, "POST", "video/mp4")
        with urllib.request.urlopen(new["browser_download_url"]) as f:
            back = f.read()
        if len(back) != len(data) or sha(back) != sha(data):
            sys.exit(f"{new['browser_download_url']}: 내려받은 바이트가 올린 파일과 다르다({len(back)} / {len(data)}) — 옛 판은 그대로 두었다")
        if name in have:
            call(f"{API}/releases/assets/{have[name]}", tok, method="DELETE")
        url = call(f"{API}/releases/assets/{new['id']}", tok, json.dumps({"name": name}).encode(), "PATCH")["browser_download_url"]
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD")) as f:   # 학생이 받는 최종 주소가 같은 크기로 열리는지
            if int(f.headers["Content-Length"]) != len(data):
                sys.exit(f"{url}: 바꾼 이름의 주소가 다른 크기를 낸다")
        old = G / "산출물" / "영상" / course / v.name
        if old.exists():
            old.unlink()
            print(f"지움 {old.relative_to(G.parent.parent).as_posix()} — 옛 판은 git 이력에 있다. 이 삭제를 커밋한다")
        print(f"올림 {v.name} → {url} ({len(data)}바이트, sha256 {sha(data)[:12]} 일치)")
        print(f"  노션: [영상 열기]({url}) · [MP4 내려받기]({url}), 재생 토글 <video source=\"{url}\">")


if __name__ == "__main__":
    main()
