"""수업 모델(OpenAI 호환 /chat/completions)에 요청을 보내는 도구. 접속 값(접속 주소 · 키 · 모델 이름)은 이 실습 폴더의 .env에서 읽는다.

    python llm_client.py                       연결 확인 — 짧은 질문 하나를 보내고 모델 이름과 답을 보인다
    python llm_client.py --count               결과/응답_기록/의 기록 수와 이 폴더의 안내용 상한까지 남은 수를 보인다(보내지 않는다)
    python llm_client.py --paste <요청 해시> --model <모델 이름>
                                               키가 없을 때 — 결과/요청/<요청 해시>.md의 글을 폴더를 모르는 채팅에 보내 받은 답을 터미널에 붙여 넣어
                                               응답 기록으로 남긴다(모델 이름은 채팅 화면에 보인 이름, 끝낼 때 새 줄에서 Windows는 Ctrl+Z 뒤 Enter, 그 밖은 Ctrl+D)
    코드에서:  from llm_client import ask, count_to_send
               reply = ask(요청)               요청은 글 하나 또는 [{"role": "system"|"user", "content": "..."}] 목록
               reply["response_text"]          받은 답 글. reply의 다른 키는 결과/응답_기록/의 기록과 같고, 더해서
                                               file(기록 파일) · sent(이번에 보냈는지) · reused_from(늘 None — 다른 폴더의 기록은 쓰지 않는다)
               count_to_send(요청 목록)          보내지 않고, 그 가운데 응답 기록이 없어 실제로 보낼 요청 수를 세어 남은 수와 함께 보인다

- 보낸 요청과 받은 답은 결과/응답_기록/<요청 해시>.json에 남는다: 모델 이름(.env) · 응답의 model · system_fingerprint · 끝난 까닭 ·
  받은 시각 · 보낸 방법 · 이 폴더의 표지(결과/폴더_표지.txt) · 답을 쓸 수 있는지(usable) · 토큰 수. 키 · 헤더는 어디에도 남기지 않는다.
- 같은 모델 · 같은 요청이면 다시 보내지 않고 이 폴더의 그 기록을 돌려준다. 일부러 한 번 더 보내려면 ask(요청, again=True) — 같은 요청은 두 번까지 보낸다.
  같은 요청에도 답은 매번 다를 수 있으므로, 어느 답을 검토했는지는 기록 파일 이름으로 남긴다.
- 답이 비었거나 서버가 내용을 걸러 낸 답(끝난 까닭 content_filter · 거절)은 usable이 false인 기록으로 남기고 알린다. 그 기록은 다시 쓰지 않으므로
  같은 요청을 다시 실행하면 한 번 더 보낸다(같은 요청은 두 번까지).
- 기록의 폴더 표지가 이 폴더와 다르면(다른 폴더에서 옮겨 온 기록) 다시 쓰지 않는다 — 그렇다고 알리고, 이 폴더에서 새로 보낸다(키가 없으면 보내지 않고 멈춘다).
- 결과/응답_기록/에 모델 서버로 보낸 기록이 100개가 되면 더 보내지 않는다 — 비용을 지키는 이 폴더의 안내용 상한이다.
  요청마다 답은 4,000토큰까지, 기다리는 시간은 180초까지다.
- 키가 없으면 요청을 보내지 않는다 — 보낼 글을 결과/요청/<요청 해시>.md에 남기고, 무엇을 했는지 알린 뒤 멈춘다.
"""
from datetime import datetime
from pathlib import Path
import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
import uuid

HERE = Path(__file__).resolve().parent
ENV = HERE / '.env'
RESULT = HERE / '결과'
RECORDS = RESULT / '응답_기록'
REQUESTS = RESULT / '요청'
MARK = RESULT / '폴더_표지.txt'
NAMES = ('OPENAI_BASE_URL', 'LLM_API_KEY', 'LLM_MODEL')
SENT = '모델 서버'            # 보낸 방법 — 이 도구가 모델 서버에 보내 받은 답
PASTED = '채팅으로 받음'       # 보낸 방법 — 키 없이 채팅에서 받아 붙여 넣은 답
MAX_SENT = 100
MAX_TOKENS = 4000
TIMEOUT_S = 180
MAX_SAME = 2
EMPTY_REASONS = ('content_filter',)
CHECK_REQUEST = [{'role': 'user', 'content': '연결 확인입니다. 한 문장으로 답해 주세요.'}]


class Stop(SystemExit):
    """무엇이 일어났는지 알리고 멈춘다(조용히 다른 길로 가지 않는다)."""
    def __init__(self, message, code=1):
        print(message)
        super().__init__(code)


def settings():
    """.env의 세 값. 파일이 없으면 빈 값으로 돌려준다(키가 없는 길)."""
    found = {name: '' for name in NAMES}
    if ENV.is_file():
        for line in ENV.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                if key.strip() in found:
                    found[key.strip()] = value.strip().strip('"\'')
    return found


def folder_mark(create=True):
    """이 폴더의 표지 — 처음 보낼 때 결과/폴더_표지.txt에 임의 값을 만든다(create=False면 만들지 않고 없으면 None). 다른 폴더에서 옮겨 온 기록을 알아보는 데 쓴다."""
    if not MARK.is_file():
        if not create:
            return None
        RESULT.mkdir(exist_ok=True)
        MARK.write_text(uuid.uuid4().hex[:16] + '\n', encoding='utf-8')
    return MARK.read_text(encoding='utf-8').strip()


def mine(found, mark):
    """이 폴더에서 받은 기록만 — 폴더 표지가 다른 기록(다른 폴더에서 옮겨 온 것)은 다시 쓰지 않는다."""
    return [(p, d) for p, d in found if mark is not None and d.get('folder_mark') == mark]


def as_messages(request):
    if isinstance(request, str):
        return [{'role': 'user', 'content': request}]
    if isinstance(request, list) and all(isinstance(m, dict) and m.get('role') in ('system', 'user', 'assistant') and isinstance(m.get('content'), str) for m in request):
        return request
    raise Stop('요청은 글 하나 또는 {"role": ..., "content": ...} 목록이어야 합니다.')


def body_of(messages, model):
    return {'model': model, 'messages': messages, 'max_completion_tokens': MAX_TOKENS}


def request_hash(body):
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()[:12]


def records(digest=None):
    """이 폴더의 응답 기록 [(경로, 내용)] — 보낸 차례 순. 읽지 못한 파일은 내용이 빈 기록으로 둔다(세는 데는 들어간다)."""
    out = []
    for path in sorted(RECORDS.glob('*.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = {'method': SENT, 'usable': False, 'note': '읽지 못한 기록'}
        if digest is None or data.get('request_hash') == digest:
            out.append((path, data))
    return sorted(out, key=lambda x: (x[1].get('attempt') or 0, x[0].name))


def sent_count():
    """결과/응답_기록/에 모델 서버로 보낸 기록 수 — 이 폴더의 안내용 상한을 이것으로 센다(읽지 못한 기록도 센다)."""
    return sum(1 for _, d in records() if d.get('method') == SENT)


def usable(data):
    return data.get('usable', True) is not False


def answer(path, data, note, sent=False):
    reply = dict(data, file=path.relative_to(HERE).as_posix(), reused_from=None, sent=sent)
    print(f'{note}: {reply["file"]} ({data.get("method")}, 받은 시각 {data.get("received_at")})')
    return reply


def record_path(digest):
    """새 기록 파일 — 같은 요청 해시의 파일이 이미 있으면(다른 폴더에서 옮겨 온 기록 포함) 뒤에 차례를 붙여 덮어쓰지 않는다."""
    n = len(records(digest))
    path = RECORDS / (f'{digest}.json' if not n else f'{digest}-{n + 1}.json')
    while path.exists():
        n += 1
        path = RECORDS / f'{digest}-{n + 1}.json'
    return path


def _reason(error):
    """서버가 거절한 까닭을 고칠 곳으로 옮긴다. 모델 서버는 오류 본문에 종류(type)와 설명(message)을 적는다."""
    try:
        detail = json.loads(error.read().decode('utf-8')).get('error') or {}
    except ValueError:
        detail = {}
    kind, message = str(detail.get('type')), str(detail.get('message'))
    if error.code == 401 and message.startswith('litellm.AuthenticationError'):   # 내 키는 받았는데 서버 쪽 인증이 실패했다는 글
        return '내 키는 받았지만 모델 서버 쪽 설정이 맞지 않습니다. 내 .env 문제가 아니니 강사에게 알립니다'
    if error.code == 401:
        return '.env의 키(LLM_API_KEY)가 받은 키와 다릅니다. 받은 세 줄을 그대로 다시 붙여 넣습니다'
    if kind == 'key_model_access_denied' or 'Invalid model name' in message:
        return '.env의 모델 이름(LLM_MODEL)이 서버에 없는 이름입니다. 받은 세 줄을 그대로 다시 붙여 넣습니다'
    if error.code == 404:
        return '.env의 접속 주소(OPENAI_BASE_URL)가 받은 주소와 다릅니다. 받은 세 줄을 그대로 다시 붙여 넣습니다'
    if error.code == 429 or 'budget' in message.lower():
        return '서버가 지금 이 키의 요청을 받지 않습니다(요청이 많거나 한도에 닿음). 1분 뒤 다시 실행하고, 같으면 강사에게 알립니다'
    if error.code == 400:
        return f'서버가 요청의 모양을 받지 않았습니다 — {message[:200]}'
    return '서버가 요청을 받지 않았습니다. 강사에게 알립니다'


def send(body, conf):
    request = urllib.request.Request(conf['OPENAI_BASE_URL'].rstrip('/') + '/chat/completions', data=json.dumps(body).encode('utf-8'),
                                     headers={'Authorization': 'Bearer ' + conf['LLM_API_KEY'], 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise Stop(f'요청을 보내지 못했습니다({error.code}): {_reason(error)}.')
    except (urllib.error.URLError, TimeoutError) as error:
        raise Stop(f'모델 서버에 닿지 못했습니다({getattr(error, "reason", error)}). 네트워크와 .env의 접속 주소(OPENAI_BASE_URL)를 보고, '
                   '첫 요청이면 서버가 준비되는 데 1분쯤 걸리므로 1분 뒤 다시 실행합니다.')


def write_request(digest, messages):
    REQUESTS.mkdir(parents=True, exist_ok=True)
    path = REQUESTS / f'{digest}.md'
    path.write_text(''.join(f'## {m["role"]}\n\n{m["content"]}\n\n' for m in messages), encoding='utf-8')
    return path


def ask(request, again=False):
    """요청을 보내고 받은 답(응답 기록 하나)을 돌려준다. 같은 요청의 쓸 수 있는 기록이 있으면 보내지 않고 그 기록을 돌려준다."""
    messages = as_messages(request)
    conf = settings()
    mark = folder_mark()
    body = body_of(messages, conf['LLM_MODEL'])
    digest = request_hash(body)
    found = records(digest)
    same = mine(found, mark)
    if len(found) > len(same):
        print(f'다른 폴더의 응답 기록 {len(found) - len(same)}개(요청 해시 {digest})는 이 폴더에서 받은 답이 아니라 다시 쓰지 않습니다.')
    good = [(p, d) for p, d in same if usable(d)]
    sent_same = [d for _, d in same if d.get('method') == SENT]
    if good and not again:
        return answer(*good[-1], '같은 요청의 응답 기록을 씁니다')
    if len(sent_same) >= MAX_SAME and (again or same):
        if good:
            return answer(*good[-1], f'같은 요청은 {MAX_SAME}번까지 보냅니다 — 이미 {len(sent_same)}번 보냈으므로 마지막 응답 기록을 씁니다')
        raise Stop(f'같은 요청을 이미 {len(sent_same)}번 보냈지만 쓸 내용이 있는 답을 받지 못했습니다(기록: {", ".join(p.name for p, _ in same)}). '
                   '더 보내지 않습니다 — 요청 글이나 조각을 바꿔 다시 보냅니다.')
    if not conf['LLM_API_KEY']:
        path = write_request(digest, messages)
        raise Stop(f'키가 없어 요청을 보내지 않았습니다. 보낼 글을 {path.relative_to(HERE).as_posix()}에 남겼습니다.\n'
                   f'키 없이 이 한 조각만 받아 보려면: 그 글을 이 폴더를 모르는 채팅에 붙여 보내고, 받은 답을 `python llm_client.py --paste {digest} --model <채팅 화면의 모델 이름>`으로 남긴 뒤 '
                   '같은 코드를 다시 실행합니다.\n'
                   '키를 받았으면 .env에 받은 세 줄을 붙여 넣고 다시 실행합니다.', 2)
    empty = [name for name in NAMES if not conf[name]]
    if empty:
        raise Stop(f'.env의 {", ".join(empty)} 값이 비어 있습니다. 강의에서 받은 세 줄을 그대로 붙여 넣었는지 봅니다.')
    count = sent_count()
    if count >= MAX_SENT:
        raise Stop(f'결과/응답_기록/에 모델 서버로 보낸 기록이 {count}개라 비용을 지키는 이 폴더의 안내용 상한 {MAX_SENT}개에 닿았습니다. 더 보내지 않습니다. '
                   '같은 요청을 되풀이하는 코드가 있는지, 조각을 더 크게 묶을 수 있는지 봅니다.')
    print(f'수업 모델에 요청을 보냅니다(요청 해시 {digest}, 이 폴더 기록 {count + 1}번째 · 안내용 상한 {MAX_SENT}개) — 첫 요청은 1분쯤 걸릴 수 있습니다.')
    raw = send(body, conf)
    choice = (raw.get('choices') or [{}])[0]
    message = choice.get('message') or {}
    text = message.get('content') or ''
    finish = choice.get('finish_reason')
    refusal = message.get('refusal')
    ok = bool(text.strip()) and finish not in EMPTY_REASONS and not refusal
    data = {'request_hash': digest, 'model': conf['LLM_MODEL'], 'response_model': raw.get('model'), 'system_fingerprint': raw.get('system_fingerprint'),
            'finish_reason': finish, 'method': SENT, 'attempt': len(same) + 1,
            'received_at': datetime.now().astimezone().isoformat(timespec='seconds'), 'folder_mark': mark, 'request': body,
            'response_text': text, 'usable': ok, 'response_raw': raw, 'usage': raw.get('usage')}
    if not ok:
        data['note'] = f'서버가 거절함: {refusal}' if refusal else f'끝난 까닭 {finish}' + (', 답 글이 비어 있음' if not text.strip() else '')
    RECORDS.mkdir(parents=True, exist_ok=True)
    path = record_path(digest)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if not ok:
        print(f'경고: 받은 답에 쓸 내용이 없습니다({data["note"]}). 기록은 {path.relative_to(HERE).as_posix()}에 남기되 다시 쓰지 않습니다. '
              f'같은 요청을 다시 실행하면 한 번 더 보내고(같은 요청은 {MAX_SAME}번까지), 그래도 같으면 요청 글이나 조각을 바꿉니다.')
    elif finish == 'length':
        print(f'응답이 길이 상한({MAX_TOKENS}토큰)에서 잘렸습니다 — 조각을 더 작게 나눠 다시 보냅니다.')
    return answer(path, data, '응답 기록을 남겼습니다', sent=True)


def count_to_send(requests):
    """보내지 않고 센다 — 요청 목록 가운데 이 폴더에서 받은 쓸 수 있는 응답 기록이 없어 ask()가 실제로 보낼 요청 수. 남은 수와 함께 보이고 그 수를 돌려준다.
    폴더 표지를 새로 만들지 않는다. 요청 해시에는 .env의 모델 이름이 들어가므로, 모델 이름이 비어 있으면 그렇다고 알린다."""
    model = settings()['LLM_MODEL']
    mark = folder_mark(create=False)
    digests = [request_hash(body_of(as_messages(r), model)) for r in requests]
    new = [d for d in dict.fromkeys(digests) if not any(usable(x) for _, x in mine(records(d), mark))]
    left = MAX_SENT - sent_count()
    others = sum(1 for _, d in records() if d.get('folder_mark') != mark)
    if not model:
        print('.env의 모델 이름(LLM_MODEL)이 비어 있어, 모델 이름 없이 요청 해시를 셉니다 — 모델 이름을 넣으면 해시가 달라져 보낼 수도 달라집니다.')
    if others:
        print(f'결과/응답_기록/에 이 폴더에서 받은 것이 아닌 기록 {others}개가 있습니다 — 다시 쓰지 않으므로 보낼 수에서 빼지 않습니다.')
    print(f'요청 {len(requests)}개(서로 다른 것 {len(set(digests))}개) 가운데 이 폴더의 응답 기록이 없어 보낼 것 {len(new)}개 · '
          f'이 폴더의 안내용 상한 {MAX_SENT}개까지 남은 수 {left}개' + (' — 남은 수보다 많습니다. 조각을 다시 묶거나 범위를 줄입니다.' if len(new) > left else ''))
    return len(new)


def paste(digest, model):
    """키가 없을 때: 결과/요청/<요청 해시>.md를 채팅에 보내 받은 답을 응답 기록으로 남긴다."""
    source = REQUESTS / f'{digest}.md'
    if not source.is_file():
        raise Stop(f'{source.relative_to(HERE).as_posix()}가 없습니다. 먼저 내 코드를 실행해 보낼 글을 남깁니다.')
    good = [(p, d) for p, d in mine(records(digest), folder_mark()) if usable(d)]
    if good:
        raise Stop(f'요청 해시 {digest}의 응답 기록이 이미 있습니다: {good[-1][0].relative_to(HERE).as_posix()}')
    print('채팅에서 받은 답을 붙여 넣습니다. 끝나면 새 줄에서 Windows는 Ctrl+Z 뒤 Enter, 그 밖은 Ctrl+D를 누릅니다.')
    text = sys.stdin.read().strip()
    if not text:
        raise Stop('붙여 넣은 답이 비어 있어 남기지 않았습니다.')
    conf = settings()
    same = mine(records(digest), folder_mark())
    data = {'request_hash': digest, 'model': model, 'response_model': None, 'system_fingerprint': None, 'finish_reason': None,
            'method': PASTED, 'attempt': len(same) + 1, 'received_at': datetime.now().astimezone().isoformat(timespec='seconds'), 'folder_mark': folder_mark(),
            'request': {'model': conf['LLM_MODEL'], 'request_file': source.relative_to(HERE).as_posix()}, 'response_text': text, 'usable': True,
            'response_raw': None, 'usage': None}
    RECORDS.mkdir(parents=True, exist_ok=True)
    path = record_path(digest)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'채팅으로 받은 답을 {path.relative_to(HERE).as_posix()}에 남겼습니다. 이 기록은 내가 붙여 넣은 것이라 수업 모델을 부른 기록으로 세지 않습니다. 같은 코드를 다시 실행하면 이 기록을 씁니다.')


def show_count():
    recs = [d for _, d in records()]
    mark = folder_mark(create=False)
    sent = [d for d in recs if d.get('method') == SENT]
    bad = sum(1 for d in sent if not usable(d))
    chat = sum(1 for d in recs if d.get('method') == PASTED)
    others = sum(1 for d in recs if d.get('folder_mark') != mark)
    answered = {d.get('request_hash') for d in recs if usable(d) and d.get('folder_mark') == mark}
    waiting = [p.stem for p in sorted(REQUESTS.glob('*.md')) if p.stem not in answered] if REQUESTS.is_dir() else []
    print(f'결과/응답_기록/: 모델 서버로 보낸 기록 {len(sent)}개(쓸 내용이 없던 답 {bad}개) · 채팅으로 받은 기록 {chat}개'
          + (f' · 이 폴더에서 받은 것이 아닌 기록 {others}개(다시 쓰지 않음, 상한에는 셈)' if others else ''))
    print(f'비용을 지키는 이 폴더의 안내용 상한 {MAX_SENT}개까지 남은 수: {MAX_SENT - len(sent)}개. 같은 요청의 기록이 있으면 다시 보내지 않습니다.')
    if waiting:
        print(f'결과/요청/에 답이 없는 요청 글 {len(waiting)}개: {", ".join(waiting[:10])}{" …" if len(waiting) > 10 else ""}')
    print('코드에서 보내기 전에 세려면: from llm_client import count_to_send 뒤 count_to_send(요청 목록)')


def main(argv=None):
    parser = argparse.ArgumentParser(description='수업 모델 연결 확인 · 기록 수 보기 · 채팅으로 받은 답 남기기')
    parser.add_argument('--paste', metavar='요청_해시')
    parser.add_argument('--model', help='--paste와 함께(꼭): 채팅 화면에 보인 모델 이름')
    parser.add_argument('--count', action='store_true', help='보내지 않고 결과/응답_기록/의 기록 수와 남은 수를 보인다')
    args = parser.parse_args(argv)
    if args.paste:
        if not (args.model or '').strip():
            raise Stop('--paste에는 --model <채팅 화면에 보인 모델 이름>을 함께 적습니다 — 응답 기록에 답을 낸 모델 이름이 있어야 합니다.')
        paste(args.paste, args.model.strip())
        return 0
    if args.count:
        show_count()
        return 0
    conf = settings()
    if not conf['LLM_API_KEY']:
        raise Stop('키가 없어 연결을 확인하지 않았습니다(.env가 없거나 LLM_API_KEY가 비어 있음).\n'
                   '키를 받았으면 .env.example을 복사해 이름을 .env로 바꾸고, 강의에서 받은 세 줄을 그대로 붙여 넣어 저장한 뒤 다시 실행합니다.\n'
                   '키가 없으면 내 코드가 모델을 부를 때 보낼 글을 결과/요청/에 남기고 멈춥니다 — 그 글을 폴더를 모르는 채팅에 보내 받은 답을 --paste(채팅 화면의 모델 이름은 --model)로 남길 수 있습니다.', 2)
    reply = ask(CHECK_REQUEST)
    if reply['sent'] and reply.get('usable', True):
        print(f'연결됨 · {conf["LLM_MODEL"]} · 응답의 model {reply.get("response_model") or "(없음)"}')
    elif reply['sent']:
        print(f'서버에는 닿았지만 쓸 내용이 있는 답이 오지 않았습니다 · {conf["LLM_MODEL"]} · 응답의 model {reply.get("response_model") or "(없음)"}')
    else:
        print('이 폴더에서 이미 연결을 확인했습니다 — 위 응답 기록이 그때 받은 답입니다.')
    print('받은 답:', (reply.get('response_text') or '').strip() or '(비어 있음)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
