from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from .config import load_database_config


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """Open one PostgreSQL connection and close it after the request work ends."""

    config = load_database_config()
    conn = psycopg.connect(
        host=config.host,
        port=config.port,
        dbname=config.name,
        user=config.user,
        password=config.password,
        connect_timeout=5,
        row_factory=dict_row,
    )
    try:
        yield conn
    finally:
        conn.close()
