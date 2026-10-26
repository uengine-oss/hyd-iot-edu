"""Instructor-only gateway wiring into the existing process runtime.

The external reverse proxy must expose only /classroom, never the process
administration API. Students cannot supply any of these factories or settings.
"""
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException

from . import classroom_api, manual_knowledge
from .classroom_authority import Authority


def build(*, settings, runtime_factory, archive_factory, driver_factory):
    required = ('HYD_CLASSROOM_AUTHORITY_DSN', 'HYD_CLASSROOM_UPSTREAM_URL',
                'HYD_CLASSROOM_UPSTREAM_KEY_FILE', 'HYD_WORKER_RUNTIME_KEY_FILE', 'TENANT_ID')
    if any(not settings.get(name) for name in required):
        raise ValueError('강사 관리 서버의 DB·중계·비밀 파일·교육 공간 설정이 필요합니다')
    url = settings['HYD_CLASSROOM_UPSTREAM_URL'].rstrip('/')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('강사 중계 주소는 인증 정보가 없는 HTTPS 주소여야 합니다')
    # Capture configuration, but read the upstream secret only when an approved
    # live task actually calls the model. No key value enters startup logs.
    tenant = settings['TENANT_ID']
    dsn = settings['HYD_CLASSROOM_AUTHORITY_DSN']
    key_file = Path(settings['HYD_CLASSROOM_UPSTREAM_KEY_FILE'])

    def connect():
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5)

    def runtime(subject):
        value = runtime_factory()
        if subject != tenant or value is None or value.tenant_id != tenant:
            raise HTTPException(503, '승인된 교육 공간의 실행 서비스가 준비되지 않았습니다')
        return value

    def catalog(rt):
        with driver_factory() as driver, driver.session() as session:
            return manual_knowledge.catalog(session)

    def upstream():
        try:
            key = key_file.read_text(encoding='utf8').strip()
        except (OSError, UnicodeError):
            raise HTTPException(503, '강사 중계 인증 파일을 읽을 수 없습니다') from None
        if not 16 <= len(key) <= 4096 or any(char.isspace() for char in key):
            raise HTTPException(503, '강사 중계 인증 파일 형식이 올바르지 않습니다')
        return {'url': url, 'key': key}

    return classroom_api.create_app(Authority(connect),
        source_loader=lambda doc: archive_factory().get(tenant, doc['source_id']),
        runtime_factory=runtime, catalog_factory=catalog,
        archive_factory=lambda subject: archive_factory() if subject == tenant else None,
        upstream_factory=upstream)
