"""Immutable manual originals and extraction coordinates, separate from graph commit.

The archive is tenant scoped. A filename never identifies a document. Uploading a
revision requires an existing document UUID; a new upload creates a new document.
PDF coordinates refer to extracted text, not visual bounding boxes or OCR truth.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4


MAX_BYTES = 30 * 1024 * 1024
MAX_PAGES = 500


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class Extraction:
    pages: tuple[str, ...]
    extractor: str
    media_type: str
    warnings: tuple[str, ...] = ()
    status: str = 'READY'


PRIVATE_USE = re.compile('[-]')


def normalize_glyphs(text: str) -> str:
    """A094 (real Daikin manual): symbol-font bullets come out of pypdf as private-use code points (U+F06C …) that carry
    no text, are invisible to a reader and get dropped from an agent's quote — which then fails the exact-citation
    contract and costs a correction round. They become a visible bullet at archive time, so anchors are deterministic
    on what the agent actually reads. text-v2 of the extractor; a replayed source keeps its old extraction by design."""
    return PRIVATE_USE.sub('•', text)


def extract(raw: bytes, filename: str) -> Extraction:
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError('빈 파일 또는 30 MiB를 초과한 파일입니다')
    suffix = Path(filename).suffix.lower()
    is_pdf = raw.startswith(b'%PDF-')
    if suffix == '.pdf' or is_pdf:
        if not is_pdf:
            raise ValueError('PDF 파일 서명이 일치하지 않습니다')
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(raw))
        if reader.is_encrypted:
            raise ValueError('암호화된 PDF는 먼저 복호화해야 합니다')
        if not 0 < len(reader.pages) <= MAX_PAGES:
            raise ValueError('PDF는 1~500페이지여야 합니다')
        pages = tuple(normalize_glyphs(page.extract_text() or '') for page in reader.pages)
        empty = [str(i) for i, text in enumerate(pages, 1) if not text.strip()]
        warnings = (f"텍스트가 없는 페이지 {', '.join(empty)}: OCR 또는 빈 페이지 여부 검토 필요",) if empty else ()
        return Extraction(pages, f'pypdf:{pypdf.__version__}:text-v2', 'application/pdf',
                          warnings, 'OCR_REQUIRED' if empty else 'READY')
    if suffix not in ('.md', '.txt', '.markdown'):
        raise ValueError('지원 파일은 Markdown, TXT, PDF입니다')
    text = None
    encoding = None
    for candidate in ('utf-8-sig', 'cp949'):
        try:
            text = raw.decode(candidate)
            encoding = candidate
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError('UTF-8 또는 CP949로 해독할 수 없습니다. 문자를 대체하지 않았습니다')
    if '\x00' in text or not text.strip():
        raise ValueError('텍스트 파일이 비어 있거나 바이너리 NUL을 포함합니다')
    return Extraction((text,), f'text:{encoding}:v1', 'text/markdown' if suffix != '.txt' else 'text/plain')


def _document_id(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('문서 ID는 UUID여야 합니다') from exc


def _source_id(document_id: str, sha256: str) -> str:
    return f'manual:{document_id}:{sha256}'


class ManualSources:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS manual_documents (
                    tenant TEXT NOT NULL, id TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant, id));
                CREATE TABLE IF NOT EXISTS manual_sources (
                    tenant TEXT NOT NULL, document_id TEXT NOT NULL, sha256 TEXT NOT NULL,
                    filename TEXT NOT NULL, original BLOB NOT NULL, extraction TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (tenant, document_id, sha256),
                    FOREIGN KEY (tenant, document_id) REFERENCES manual_documents (tenant, id));
            ''')

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, tenant: str, filename: str, raw: bytes, *, document_id: str | None = None) -> dict:
        if not isinstance(tenant, str) or not tenant.strip():
            raise ValueError('tenant가 필요합니다')
        if not isinstance(filename, str) or not filename.strip() or len(filename) > 255:
            raise ValueError('파일명은 1~255자여야 합니다')
        if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
            raise ValueError('원문 바이트는 1바이트~30 MiB여야 합니다')
        supplied = document_id is not None
        document_id = _document_id(document_id) if supplied else str(uuid4())
        sha256 = _hash(raw)
        if supplied:
            # A retry uses the old extraction, even after the extractor is upgraded.
            with self._connection() as db:
                if not db.execute('SELECT 1 FROM manual_documents WHERE tenant=? AND id=?',
                                  (tenant, document_id)).fetchone():
                    raise KeyError('문서를 찾을 수 없습니다')
                old = db.execute('SELECT * FROM manual_sources WHERE tenant=? AND document_id=? AND sha256=?',
                                 (tenant, document_id, sha256)).fetchone()
                if old:
                    return self._view(old) | {'replayed': True}
        extracted = extract(raw, filename)
        pages = [{'page': i, 'text': text, 'sha256': _hash(text.encode('utf-8'))}
                 for i, text in enumerate(extracted.pages, 1)]
        payload = {'pages': pages, 'extractor': extracted.extractor, 'media_type': extracted.media_type,
                   'warnings': list(extracted.warnings), 'status': extracted.status}
        at = datetime.now(timezone.utc).isoformat()
        with self._connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if not supplied:
                db.execute('INSERT INTO manual_documents VALUES (?,?,?)', (tenant, document_id, at))
            cur = db.execute('INSERT OR IGNORE INTO manual_sources VALUES (?,?,?,?,?,?,?)',
                             (tenant, document_id, sha256, filename, raw,
                              json.dumps(payload, ensure_ascii=False), at))
            row = db.execute('SELECT * FROM manual_sources WHERE tenant=? AND document_id=? AND sha256=?',
                             (tenant, document_id, sha256)).fetchone()
            return self._view(row) | {'replayed': cur.rowcount == 0}

    @staticmethod
    def _view(row) -> dict:
        if _hash(row['original']) != row['sha256']:
            raise ValueError('보관된 원문 해시가 일치하지 않습니다')
        extraction = json.loads(row['extraction'])
        for page in extraction['pages']:
            if _hash(page['text'].encode('utf-8')) != page['sha256']:
                raise ValueError('보관된 추출 텍스트 해시가 일치하지 않습니다')
        return {'source_id': _source_id(row['document_id'], row['sha256']),
                'document_id': row['document_id'], 'sha256': row['sha256'],
                'filename': row['filename'], 'size': len(row['original']), 'created_at': row['created_at'],
                **extraction}

    def _read(self, tenant: str, source_id: str):
        parts = source_id.split(':') if isinstance(source_id, str) else []
        if len(parts) != 3 or parts[0] != 'manual':
            raise KeyError('문서 판본을 찾을 수 없습니다')
        with self._connection() as db:
            row = db.execute('SELECT * FROM manual_sources WHERE tenant=? AND document_id=? AND sha256=?',
                             (tenant, parts[1], parts[2])).fetchone()
        if row is None:
            raise KeyError('문서 판본을 찾을 수 없습니다')
        if _hash(row['original']) != row['sha256']:
            raise ValueError('보관된 원문 해시가 일치하지 않습니다')
        return row

    def get(self, tenant: str, source_id: str) -> dict:
        return self._view(self._read(tenant, source_id))

    def original(self, tenant: str, source_id: str) -> bytes:
        return bytes(self._read(tenant, source_id)['original'])

    def list(self, tenant: str, limit: int = 50, offset: int = 0) -> dict:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError('목록 크기는1~100, 시작 위치는0 이상입니다')
        with self._connection() as db:
            total = db.execute('SELECT count(*) FROM manual_sources WHERE tenant=?', (tenant,)).fetchone()[0]
            rows = db.execute('SELECT document_id,sha256,filename,created_at,length(original) AS size,extraction '
                              'FROM manual_sources WHERE tenant=? ORDER BY created_at DESC,document_id,sha256 LIMIT ? OFFSET ?',
                              (tenant, limit, offset)).fetchall()
        items = []
        for row in rows:
            extraction = json.loads(row['extraction'])
            items.append({key: row[key] for key in ('document_id', 'sha256', 'filename', 'created_at', 'size')} |
                         {'source_id': _source_id(row['document_id'], row['sha256']), 'status': extraction['status']})
        return dict(items=items, total=total, offset=offset, limit=limit,
                    next_offset=offset + limit if offset + limit < total else None)

    def validate_anchor(self, tenant: str, anchor: dict) -> dict:
        if not isinstance(anchor, dict):
            raise ValueError('인용 좌표가 필요합니다')
        page, start, end = (anchor.get(key) for key in ('page', 'start', 'end'))
        if any(type(value) is not int for value in (page, start, end)):
            raise ValueError('페이지/문자 좌표는 정수여야 합니다')
        source = self.get(tenant, anchor.get('source_id'))
        if not 1 <= page <= len(source['pages']):
            raise ValueError('인용 페이지가 범위를 벗어났습니다')
        text = source['pages'][page - 1]['text']
        if not 0 <= start < end <= len(text) or anchor.get('quote') != text[start:end]:
            raise ValueError('인용 문자열 또는 문자 좌표가 원문과 일치하지 않습니다')
        return {key: anchor[key] for key in ('source_id', 'page', 'start', 'end', 'quote')}
