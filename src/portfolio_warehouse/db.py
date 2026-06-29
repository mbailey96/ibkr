from __future__ import annotations

from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from portfolio_warehouse.settings import get_settings


def connect() -> psycopg.Connection:
    settings = get_settings()
    return psycopg.connect(settings.database_url, row_factory=dict_row)


def execute_sql_file(path: str | Path) -> None:
    sql = Path(path).read_text()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

