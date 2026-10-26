"""Key-only startup check; no model call, redirects, or credential output."""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check(url, key, *, opener=None):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('관리 서버 HTTPS 주소가 올바르지 않습니다')
    if not 32 <= len(key) <= 512 or any(c.isspace() for c in key):
        raise ValueError('수업 접속 키 형식이 올바르지 않습니다')
    request = urllib.request.Request(url.rstrip('/')+'/v1/classroom/session',
                                     headers={'Authorization': 'Bearer '+key})
    opener = opener or urllib.request.build_opener(NoRedirect())
    with opener.open(request, timeout=30) as response:
        data = response.read(4097)
        if len(data) > 4096:
            raise ValueError('관리 서버 응답이 올바르지 않습니다')
        value = json.loads(data)
        if value != {'status': 'ok', 'service': 'classroom-execution'}:
            raise ValueError('관리 서버 인증 응답이 올바르지 않습니다')


def main():
    try:
        check(sys.argv[1], sys.stdin.read(513).strip())
    except urllib.error.HTTPError as exc:
        print('관리 서버 인증 실패 (HTTP '+str(exc.code)+'). 주소·키·수업 권한을 확인하세요.')
        return 1
    except Exception:
        # Exceptions from URL/network stacks may contain credentials. Never
        # print them, response bodies, request headers, or supplied arguments.
        print('관리 서버 연결 확인 실패. HTTPS 주소·접속 키·네트워크를 확인하세요.')
        return 1
    print('ok (관리 서버 수업 접속 인증됨 · 유료 AI 호출 없음)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
