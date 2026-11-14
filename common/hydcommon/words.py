"""학생에게 가는 문장을 만드는 서버 코드가 함께 쓰는 낱말 도우미 — 조사 붙이기 하나.

「단계이(가)」 · 「TAN이(가)」 · 「…을(를)」처럼 두 꼴을 함께 적은 문장을 내지 않으려고 둔다. 이름이 값으로 들어오는 자리(단계 이름 ·
도구 서버 이름 · 측정 항목)에서 쓴다. 글자로 고정된 낱말 뒤에는 쓰지 않고 맞는 조사를 그대로 적는다.
"""
from __future__ import annotations

#: 조사 쌍(받침 있음, 받침 없음). 「으로」는 ㄹ 받침 뒤에서도 「로」다.
PAIRS = {'이': ('이', '가'), '가': ('이', '가'), '을': ('을', '를'), '를': ('을', '를'), '은': ('은', '는'), '는': ('은', '는'),
         '과': ('과', '와'), '와': ('과', '와'), '으로': ('으로', '로'), '로': ('으로', '로'), '이라': ('이라', '라'), '라': ('이라', '라')}
_DIGIT_FINAL = {'0': 'ㅇ', '1': 'ㄹ', '2': '', '3': 'ㅁ', '4': '', '5': '', '6': 'ㄱ', '7': 'ㄹ', '8': 'ㄹ', '9': ''}     # 영 일 이 삼 사 오 육 칠 팔 구
_LETTER_FINAL = {'l': 'ㄹ', 'm': 'ㅁ', 'n': 'ㄴ', 'r': 'ㄹ'}                                                             # 엘 엠 엔 알 — 그 밖의 글자 이름은 받침이 없다
_SKIP = '」』)]}>"\'”’ \t.,·…'


def _final(word: str) -> str | None:
    """마지막으로 소리 나는 글자의 받침('' = 없음, 'ㄹ' = ㄹ 받침, 그 밖의 값 = 다른 받침). 알 수 없으면 None."""
    for ch in reversed(word):
        if ch in _SKIP:
            continue
        if '가' <= ch <= '힣':
            n = (ord(ch) - 0xAC00) % 28
            return '' if n == 0 else 'ㄹ' if n == 8 else 'ㅇ'
        if ch in _DIGIT_FINAL:
            return _DIGIT_FINAL[ch]
        if ch.isascii() and ch.isalpha():
            return _LETTER_FINAL.get(ch.lower(), '')
        if ch in '%℃':                              # 퍼센트 · 도 — 받침 없음(「부하 70 %를」)
            return ''
        return None
    return None


def particle(word, particle: str) -> str:
    """word 뒤에 올 조사만(「을」 또는 「를」). 낱말과 조사 사이에 따옴표 · 괄호가 끼는 문장('{이름}'은 …)에서 쓴다 — josa 와 같은 판정이다."""
    return josa(word, particle)[len(str(word)):]


def josa(word, particle: str) -> str:
    """word 에 맞는 조사를 붙인 글. particle 은 조사 쌍 가운데 아무 쪽(「을」 · 「를」 · 「이」 · 「으로」 …). 마지막 글자의 소리를 알 수
    없으면(기호 · 다른 문자) 두 꼴을 함께 적는다 — 틀린 조사를 내는 것보다 낫다."""
    text = str(word)
    with_final, without = PAIRS[particle]
    final = _final(text)
    if final is None:
        return f'{text}{with_final}({without})'
    if particle in ('으로', '로'):
        return text + (without if final in ('', 'ㄹ') else with_final)
    return text + (with_final if final else without)
