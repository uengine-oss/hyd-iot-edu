"""Exclude OAuth callbacks from access logs; request processing remains intact."""
from __future__ import annotations

import logging
from urllib.parse import urlsplit

CALLBACK_PATH = '/api/mcp/connections/callback'


class CallbackFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Uvicorn passes (client, method, path_with_query, http_version, status).
        # Do not rewrite the request itself or retain the authorization code.
        if isinstance(record.args, tuple) and len(record.args) >= 3:
            path = record.args[2]
            if isinstance(path, str) and urlsplit(path).path == CALLBACK_PATH:
                return False
        return True


def install() -> None:
    logger = logging.getLogger('uvicorn.access')
    if not any(isinstance(item, CallbackFilter) for item in logger.filters):
        logger.addFilter(CallbackFilter())
