"""Export the source-backed tender workflow CSV pack from PostgreSQL.

Reads the named, read-only queries in sql/tender_workflow/tender_source_export.sql
and writes their results to the configured data2/tender_exports directory.
Database credentials are read only from .env/environment variables and are never
written into the exports.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
import psycopg


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "config" / "tender_export_manifest.json"


def named_queries(sql_text: str) -> Iterator[tuple[str, str]]:
    matches = list(re.finditer(r"^--\s*name:\s*([a-z0-9_]+)\s*$", sql_text, re.MULTILINE))
    for index, match in enumerate(matches):
        query = sql_text[match.end(): matches[index + 1].start() if index + 1 < len(matches) else len(sql_text)].strip()
        if query.endswith(";"):
            query = query[:-1]
        if query:
            yield match.group(1), query


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    sql_path = PROJECT_ROOT / manifest["sql_file"]
    output_directory = PROJECT_ROOT / manifest["output_directory"]
    output_directory.mkdir(parents=True, exist_ok=True)
    query_map = dict(named_queries(sql_path.read_text(encoding="utf-8")))

    required = {item["name"]: item for item in manifest["exports"]}
    missing = sorted(set(required) - set(query_map))
    if missing:
        raise RuntimeError(f"SQL file does not define the configured export(s): {', '.join(missing)}")

    connection_settings = {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "dbname": os.getenv("POSTGRES_DB", "postgres"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", ""),
    }
    if not connection_settings["password"]:
        raise RuntimeError("POSTGRES_PASSWORD is not configured in .env or the environment.")

    with psycopg.connect(**connection_settings) as connection:
        with connection.cursor() as cursor:
            for name, export in required.items():
                cursor.execute(query_map[name])
                columns = [description.name for description in cursor.description]
                destination = output_directory / export["filename"]
                row_count = 0
                with destination.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(columns)
                    for row in cursor:
                        writer.writerow(row)
                        row_count += 1
                print(f"{destination.relative_to(PROJECT_ROOT)}: {row_count} rows")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Tender source export failed: {error}", file=sys.stderr)
        raise SystemExit(1)
