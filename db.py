"""Persistence layer: saves parsed reports to Neon (Postgres) so they can be
reloaded later, individually or combined, instead of re-uploading every time.
"""

import hashlib
import json
import time

import pandas as pd
import streamlit as st
from sqlalchemy import text

SCHEMA_SQL = """
create table if not exists reports (
    id serial primary key,
    filename text not null,
    sheet_name text,
    file_hash text unique not null,
    uploaded_at timestamptz not null default now(),
    row_count int not null
);

create table if not exists tickets (
    id serial primary key,
    report_id int not null references reports(id) on delete cascade,
    title text,
    status text,
    category text,
    primary_responsibility text,
    modified timestamptz,
    raw jsonb not null
);

create index if not exists tickets_report_id_idx on tickets(report_id);
"""

# Maps the promoted ticket columns to the column names the dashboard already
# detects (has_title/has_status/has_category/has_tech/has_modified).
PROMOTED_COLUMNS = {
    "title": "Title",
    "status": "Status",
    "category": "Category",
    "primary_responsibility": "Primary Responsibility",
    "modified": "Modified",
}


def get_conn():
    # Neon closes idle connections when its compute auto-suspends. Without
    # pool_pre_ping, SQLAlchemy's cached engine hands out those dead pooled
    # connections as-is instead of testing and transparently replacing them,
    # so a query minutes after the last one throws "server closed the
    # connection unexpectedly". pool_recycle proactively retires connections
    # before that happens; pool_pre_ping catches whatever slips through.
    return st.connection(
        "neon", type="sql", pool_pre_ping=True, pool_recycle=280
    )


def call_with_retry(fn, attempts=4, backoff=1.0):
    """Retry a DB call before giving up.

    Neon's compute auto-suspends after a few idle minutes, and a Streamlit
    Cloud app that's been asleep cold-starts its container on the next visit —
    either can make the very first connection attempt fail while the database
    resumes, even though a rerun a couple seconds later would succeed. Retry
    with backoff so that transient window doesn't surface as a user-facing
    error.
    """
    last_err = None
    for attempt in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if attempt < attempts - 1:
                time.sleep(backoff * (attempt + 1))
    raise last_err


def init_schema(conn):
    with conn.session as s:
        for statement in SCHEMA_SQL.strip().split(";\n\n"):
            statement = statement.strip()
            if statement:
                s.execute(text(statement))
        s.commit()


def file_hash(raw_bytes):
    return hashlib.sha256(raw_bytes).hexdigest()


def _clean_scalar(value):
    """NaN/NaT can't round-trip through json.dumps into valid jsonb; treat
    them (and None) uniformly as SQL NULL."""
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _row_raw_json(row):
    cleaned = {col: _clean_scalar(val) for col, val in row.items()}
    return json.dumps(cleaned, default=str)


def save_report(conn, filename, sheet_name, df, raw_bytes):
    """Insert a parsed report + its tickets, unless an identical file (by
    content hash) was already saved. Returns (report_id, is_new)."""
    init_schema(conn)
    hash_ = file_hash(raw_bytes)

    with conn.session as s:
        result = s.execute(
            text(
                """
                insert into reports (filename, sheet_name, file_hash, row_count)
                values (:filename, :sheet_name, :file_hash, :row_count)
                on conflict (file_hash) do nothing
                returning id
                """
            ),
            {
                "filename": filename,
                "sheet_name": sheet_name,
                "file_hash": hash_,
                "row_count": len(df),
            },
        )
        report_id = result.scalar()

        if report_id is None:
            existing = s.execute(
                text("select id from reports where file_hash = :file_hash"),
                {"file_hash": hash_},
            )
            s.commit()
            return existing.scalar(), False

        params = []
        for _, row in df.iterrows():
            modified_val = row.get("Modified") if "Modified" in df.columns else None
            modified_val = None if pd.isna(modified_val) else modified_val.to_pydatetime()
            params.append(
                {
                    "report_id": report_id,
                    "title": _clean_scalar(row.get("Title")),
                    "status": _clean_scalar(row.get("Status")),
                    "category": _clean_scalar(row.get("Category")),
                    "primary_responsibility": _clean_scalar(row.get("Primary Responsibility")),
                    "modified": modified_val,
                    "raw": _row_raw_json(row),
                }
            )

        if params:
            s.execute(
                text(
                    """
                    insert into tickets
                        (report_id, title, status, category, primary_responsibility, modified, raw)
                    values
                        (:report_id, :title, :status, :category, :primary_responsibility,
                         :modified, cast(:raw as jsonb))
                    """
                ),
                params,
            )
        s.commit()
        return report_id, True


def list_reports(conn):
    init_schema(conn)
    return conn.query(
        "select id, filename, sheet_name, uploaded_at, row_count "
        "from reports order by uploaded_at desc",
        ttl=0,
    )


def load_tickets(conn, report_ids):
    """Load tickets for the given report ids, tagged with which report each
    row came from so combined views stay traceable."""
    if not report_ids:
        return pd.DataFrame()

    with conn.session as s:
        result = s.execute(
            text(
                """
                select t.title, t.status, t.category, t.primary_responsibility,
                       t.modified, r.filename as source_report
                from tickets t
                join reports r on r.id = t.report_id
                where t.report_id = any(:report_ids)
                """
            ),
            {"report_ids": list(report_ids)},
        )
        rows = result.mappings().all()

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.rename(
        columns={
            "title": "Title",
            "status": "Status",
            "category": "Category",
            "primary_responsibility": "Primary Responsibility",
            "modified": "Modified",
            "source_report": "Source Report",
        }
    )
    df["Modified"] = pd.to_datetime(df["Modified"], errors="coerce")
    return df
