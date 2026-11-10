"""02 노션 대본 윤문 — 고친 단위의 새 글 · 뺄 단위 · 잇기를 한 곳에 두고, 대본 md(통합 · 실전) · 노션_큐.json · 02_계획.json 쉼뒤에 반영한다.
언제: 노션 대본을 다듬어 확정받고 음성을 살 때(실습쉼/노션_윤문_메모.md). 이 일이 끝나면 작업 폴더와 함께 지운다.
명령: <py> 노션_고침.py            # 이 파일 옆 02_계획.json 기준. 다시 돌려도 같은 결과(md는 옛 글 → 새 글을 찾아 바꾼다)
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
MD = [ROOT / f'workspace/강의제작/산출물/{c}/실습/01회차/대본/02_실습_학습노트.md' for c in ('통합반', '실전반')]
PLAN = HERE / '02_계획.json'
CUES = HERE / '노션_큐.json'

새글 = {
    'b0': '이번 시간에는 노션으로 학습노트를 만들어 볼게요. 노션은 글과 표, 그림을 페이지에 자유롭게 담아 정리하는 기록 도구예요. 글을 쓰는 것부터 시작해서, 주제별로 카드를 만들고 그 안에 페이지를 나누어 보겠습니다. 처음 쓰는 분도 화면의 순서대로 따라오시면 됩니다.',
    'b10': '다른 메뉴는 필요할 때마다 하나씩 짚어 드릴게요.',
    'b11': '왼쪽 목록에서 새 페이지 버튼을 눌러 주세요.',
    'b17': '제목은 위에, 내용은 이 본문에 적는다고 구별해 두시면 돼요.',
    'b19': '왼쪽에 같은 이름이 하나 더 보이는 건 제가 미리 만들어 둔 완성본이에요.',
    'b20': '우리는 방금 만든 이 페이지에서 계속할게요.',
    'b23': '이 페이지는 노트를 열면 맨 먼저 보는 첫 화면으로 쓸 거예요. 이런 첫 화면을 홈이라고 할게요. 홈에서는 안내와 주제 카드가 바로 보이게 만들 겁니다.',
    'b24': '그래서 위쪽에 큰 표지는 넣지 않고, 그림은 나중에 주제 카드에 쓰겠습니다.',
    'b32': '노션에서는 글 한 줄, 그림 하나를 각각 한 덩어리로 다루는데요, 이 덩어리를 블록이라고 해요.',
    'b33': '이 손잡이를 잡으면 블록을 통째로 옮기거나 모양을 바꿀 수 있어요.',
    'b35': '소개 다음에는 안내 상자를 하나 넣겠습니다. 노션에서는 이런 안내 상자를 콜아웃이라고 해요.',
    'b36': '여기에 슬래시를 입력해 주세요. 빈 줄에 슬래시를 치면 넣을 수 있는 블록 메뉴가 열려요.',
    'b60': '노션에서는 이렇게 페이지를 모아 두는 목록을 데이터베이스라고 해요.',
    'b67': '노션에서는 목록을 어떤 모양으로 보여 줄지 정한 것을 보기라고 해요. 주제 모음은 이 목록의 이름이고, 주제 카드는 카드 모양으로 보여 주는 보기의 이름이에요.',
    'b68': '뒤에서 같은 목록을 표 모양의 보기로 하나 더 만들면서 이 차이를 다시 볼게요.',
    'b92': '여기서는 중간 크기인 제목 2를 고르겠습니다.',
    'b96': '슬래시 뒤에 페이지라고 적어 볼게요. 이 주제 페이지 안에 페이지를 하나 더 넣으려는 거예요. 이렇게 페이지 안에 든 페이지를 하위 페이지라고 해요.',
    'b99': '위쪽에는 지금 페이지가 어디 안에 들어 있는지 보여 주는 줄이 있어요. 이 줄을 경로라고 해요.',
    'b102': '하위 페이지를 품은 바깥 페이지는 부모 페이지라고 하는데요, 부모 페이지로 돌아갈 때는 이 경로에서 노션 익히기를 누르면 돼요.',
    'b108': '이번에도 제목 2를 고를게요.',
    'b139': '접는다고 내용이 지워지는 건 아니에요.',
    'b143': '글이 토글 안쪽이 아니라 바깥 줄에서 시작하는지 볼게요.',
    'b159': '앞의 네모는 다 했을 때 눌러서 체크하는 곳이에요.',
    'b160': '지금은 아직 할 일이니까 그대로 둘게요.',
    'b169': '목차 항목은 따로 적지 않아도 돼요.',
    'b170': '제목 블록을 따라 저절로 만들어지거든요.',
    'b175': '이제 위쪽 경로의 노션 익히기를 클릭해 부모 페이지로 돌아가겠습니다.',
    'b176': '첫 페이지 꾸미기 링크가 그대로 남아 있죠.',
    'b178': '슬래시 뒤에 페이지라고 적을게요.',
    'b206': '제목 2로 할게요.',
    'b281': '제목 2로 할게요.',
    'b410': '제목 2로 할게요.',
    'b217': '이렇게 한 줄 적어 두면, 나중에 이 링크를 왜 남겼는지 바로 알 수 있어요.',
    'b293': '제목에는 어떻게 다시 찾아볼까라고 적을게요.',
    'b306': '목록을 새로 만든 게 아니라, 같은 주제 모음에 표 모양의 보기를 하나 더 만든 거예요.',
    'b358': '이번에도 같은 메뉴를 열게요.',
    'b474': '오늘 만든 학습노트를 다시 둘러볼게요.',
    'b488': '기능을 모두 쓰려고 칸을 채울 필요는 없어요. 짧게 적다가 길어지면 페이지로 나누면서, 앞으로 배우는 내용을 이 노트에 하나씩 쌓아 가시면 됩니다. 수고하셨습니다.',
}
뺌 = {'b61', 'b62', 'b88', 'b307'}
# 한 문맥이라 쉼을 넣지 않는 사이(앞 단위 id)
잇기 = {'b5', 'b6', 'b9', 'b16', 'b18', 'b19', 'b23', 'b31', 'b32', 'b50', 'b67', 'b99', 'b100', 'b101',
        'b138', 'b159', 'b169', 'b372', 'b444', 'b445', 'b452', 'b486'}


def main():
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    U = plan['단위']
    ids = {u['id'] for u in U}
    for k in set(새글) | 뺌 | 잇기:
        if k not in ids: sys.exit(f'계획에 없는 단위 {k}')
    if set(새글) & 뺌: sys.exit(f'새 글과 뺌이 겹친다: {set(새글) & 뺌}')
    # 대본 md — 문단이 단위 글과 하나씩 맞아야 한다
    for md in MD:
        raw = md.read_bytes(); crlf = b'\r\n' in raw
        text = raw.decode('utf-8').replace('\r\n', '\n')
        blocks = text.split('\n\n')
        speech = [i for i, b in enumerate(blocks) if b.strip() and not b.lstrip().startswith(('>', '#'))]
        if len(speech) != len(U): sys.exit(f'{md}: 낭독 문단 {len(speech)} ≠ 계획 단위 {len(U)}')
        drop = set()
        for i, u in zip(speech, U):
            cur = blocks[i].strip()
            if u['id'] in 뺌:
                if cur != u['글'].strip(): sys.exit(f'{md}: {u["id"]} 문단이 옛 글과 다르다')
                drop.add(i)
                # 뺄 단위 뒤에 조작 줄이 있으면 그 조작은 앞 문단으로 간다 — 지금 뺄 넷은 조작 줄이 없어야 한다
                if i + 1 < len(blocks) and blocks[i + 1].lstrip().startswith('> 조작'): sys.exit(f'{md}: 뺄 단위 {u["id"]} 뒤에 조작 줄')
            elif u['id'] in 새글:
                if cur not in (u['글'].strip(), 새글[u['id']]): sys.exit(f'{md}: {u["id"]} 문단이 옛 글도 새 글도 아니다')
                blocks[i] = 새글[u['id']]
            elif cur != u['글'].strip() and u['id'] != 'N-card-url':
                sys.exit(f'{md}: {u["id"]} 문단이 게시본 글과 다르다')
        out = '\n\n'.join(b for i, b in enumerate(blocks) if i not in drop)
        md.write_bytes((out.replace('\n', '\r\n') if crlf else out).encode('utf-8'))
    # 큐 파일 — 남는 단위 모두, 고친 단위는 새 글(바꿈이 큐에 없는 단위를 뺌으로 본다)
    head = json.loads((HERE / '노션_바꿀큐.json').read_text(encoding='utf-8'))
    card = {c['id']: c['text'] for c in head['cues']}
    cues = [{'id': u['id'], 'segment': 0, 'text': 새글.get(u['id'], card.get(u['id'], u['글']))} for u in U if u['id'] not in 뺌]
    CUES.write_text(json.dumps({'voice_id': head['voice_id'], 'model_id': head['model_id'], 'cues': cues}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    # 계획 — 잇기
    for u in U:
        if u['id'] in 잇기: u['쉼뒤'] = '잇기'
    PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    n = sum(len(v) for v in 새글.values())
    print(f'새 글 {len(새글)}단위 {n}자(견적 약 {n * 0.485:.0f}크레딧) · 뺌 {len(뺌)} · 잇기 {len(잇기)} · 큐 {len(cues)}')


if __name__ == '__main__':
    main()
