"""업무 DB 구조(DDL) 해석(procsvc/ddl.py) — 올린 SQL 을 실행하지 않고 CREATE TABLE · COMMENT ON 만 읽는다."""
import pytest

from procsvc import ddl


def test_문자열과_따옴표_이름_속의_세미콜론은_문장을_가르지_않는다():
    text = "CREATE TABLE a (x text DEFAULT 'p;q'); COMMENT ON TABLE \"we;ird\" IS 'a;b'; CREATE TABLE b (y int);"
    tables = [t.this.name for t, _ in ddl.create_tables(text)]
    assert tables == ['a', 'b']
    assert list(ddl.source_comments(text)) == [('public', 'we;ird', None, 'a;b')]


@pytest.mark.parametrize('text, expected', [
    ("COMMENT ON TABLE ent.orders IS '주문';", [('ent', 'orders', None, '주문')]),
    ('COMMENT ON COLUMN ent.orders.due IS NULL;', [('ent', 'orders', 'due', '')]),          # 지우기(IS NULL)
    ("COMMENT ON COLUMN \"Ent\".\"Orders\".\"Due\" IS 'x';", [('Ent', 'Orders', 'Due', 'x')]),  # 따옴표 이름은 대소문자 그대로
    ("CREATE INDEX i ON t(x); COMMENT ON INDEX i IS 'x';", []),                              # 표 · 열 주석이 아님
])
def test_원천_주석은_표와_열만_읽는다(text, expected):
    assert list(ddl.source_comments(text)) == expected


@pytest.mark.parametrize('text, words', [
    ('CREATE TABLE (a int)', '1번째 줄 14번째 칸 「(」 근처'),
    ("CREATE TABLE t (a 'x)", '따옴표나 괄호가 닫히지 않았거나'),
    ('CREATE TABLE t AS SELECT 1', 'CREATE TABLE'),
])
def test_구문_오류는_줄_칸을_쉬운_말로_말하고_토큰_덤프나_색_코드를_싣지_않는다(text, words):
    """P1-25: 전에는 sqlglot 영문 토큰 덤프와 터미널 색 코드(ESC[4m)가 업무 데이터 구조 등록 화면에 보였다."""
    with pytest.raises(ValueError) as caught:
        list(ddl.create_tables(text))
    message = str(caught.value)
    assert words in message and '\x1b' not in message and 'Token' not in message


@pytest.mark.parametrize('name, shown', [('orders', 'orders'), ('Orders', '"Orders"'), ('order date', '"order date"'), ('a"b', '"a""b"')])
def test_식별자는_필요할_때만_따옴표로_보인다(name, shown):
    assert ddl.display_identifier(name) == shown


@pytest.mark.parametrize('name', ['', 'a\x00b', None])
def test_비었거나_널_문자가_든_식별자는_거절한다(name):
    with pytest.raises(ValueError, match='식별자'):
        ddl.quoted(name)
