# Source this (`. workspace/개발/scripts/host_libpq.sh`) before any host-side Python that opens Supabase/PostgreSQL on Windows (pytest, workers).
# Windows Smart App Control (2026-10-07부터 이 PC) 가 psycopg_binary 에 들어 있는 서명 없는 libpq/libssl DLL 을 막으면 psycopg 는 순수 파이썬
# 래퍼로 내려가고, 그 래퍼는 PATH 의 *서명된* libpq.dll 을 쓴다 — LibreOffice 가 그런 파일을 갖고 있다(Authenticode 유효).
# 다른 서명된 사본을 쓰려면 LIBPQ_DIR 을 그 폴더로. 제품은 바뀌지 않고 이 PC가 읽는 libpq 만 바뀐다. Smart App Control 을 끄는 것은 사용자 결정(한 방향 스위치).
case "${OSTYPE:-}" in
  msys*|cygwin*)
    LIBPQ_DIR="${LIBPQ_DIR:-/c/Program Files/LibreOffice/program}"
    if [ -f "$LIBPQ_DIR/libpq.dll" ]; then
      case ":$PATH:" in *":$LIBPQ_DIR:"*) ;; *) export PATH="$LIBPQ_DIR:$PATH";; esac
    else
      printf 'host_libpq: 서명된 libpq.dll 이 없습니다(%s) — psycopg 가 DLL 오류로 멈추면 LibreOffice 를 설치하거나 LIBPQ_DIR 에 서명된 libpq.dll 폴더를 지정하세요\n' "$LIBPQ_DIR" >&2
    fi;;
esac
