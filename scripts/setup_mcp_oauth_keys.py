"""Provision persistent OAuth/worker keys outside Git without printing values.

This command never changes an existing key. Losing/replacing the OAuth key
would make existing encrypted connections unreadable, so invalid files fail.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets


def default_directory() -> Path:
    if os.name == 'nt':
        local = os.environ.get('LOCALAPPDATA')
        if not local:
            raise ValueError('LOCALAPPDATA is required on Windows')
        return Path(local) / 'HYD' / 'mcp'
    base = os.environ.get('XDG_STATE_HOME')
    return (Path(base) if base else Path.home() / '.local' / 'state') / 'hyd' / 'mcp'


def provision(directory: Path) -> dict:
    from cryptography.fernet import Fernet

    directory = directory.expanduser().resolve()
    if any((parent / '.git').exists() for parent in (directory, *directory.parents)):
        raise ValueError('Keys must be stored outside Git checkouts')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    items = []
    for name in ('oauth.key', 'worker-runtime.key'):
        path = directory / name
        created = False
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if path.is_symlink() or not path.is_file():
                raise ValueError(f'{name}: existing path must be a regular file')
        else:
            created = True
            value = Fernet.generate_key() if name == 'oauth.key' else secrets.token_urlsafe(48).encode('ascii')
            with os.fdopen(fd, 'wb') as handle:
                handle.write(value + b'\n')
                handle.flush()
                os.fsync(handle.fileno())
        data = path.read_bytes().strip()
        if name == 'oauth.key':
            Fernet(data)
        elif len(data) < 32 or any(c not in b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-' for c in data):
            raise ValueError('worker-runtime.key: existing key is invalid; it was not replaced')
        items.append({'file': str(path), 'created': created})
    return {'ok': True, 'files': items, 'key_values_printed': False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path)
    args = parser.parse_args()
    try:
        result = provision(args.directory or default_directory())
    except (OSError, ValueError):
        print(json.dumps({'ok': False, 'reason': '키 파일 위치·권한·형식을 확인하세요. 기존 파일은 교체하지 않았습니다.'}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
