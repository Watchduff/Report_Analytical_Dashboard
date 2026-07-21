# Report Analytics Dashboard

A Streamlit dashboard for BYU–Hawaii's Office of Information Technology to explore TDX ticket reports: upload an Excel export, filter and drill into it, and optionally save it to a persistent report library so past reports can be reloaded — or combined — without re-uploading.

## What's built

**Dashboard page** (`app_pages/dashboard.py`)
- Upload an Excel (`.xlsx`/`.xls`) TDX report; auto-detects which sheet holds the ticket data (looks for `Status` + `Category` columns) and which row is the real header — some TDX exports put a title row above the header, which this scans past instead of misreading as data.
- Sidebar filters: Modified date range, Category, Status, Technician (checklist-style popovers).
- KPI cards (Total Tickets, Closed, Open, Completion Rate, Categories) that are clickable and jump to the relevant tab, optionally drilling into just that subset on the Raw Data tab.
- Tabs:
  - **Overview** — status distribution (pie + bar).
  - **Trends** — ticket volume over time (day/week granularity), with exact counts labeled on every bar/point plus an expandable exact-numbers table.
  - **Categories** — tickets by category, category × status cross-tab, completion rate by category.
  - **Technicians** — workload by technician, broken down by status.
  - **Raw Data** — searchable table of the filtered tickets with CSV export.

**Presentation page** (`app_pages/presentation.py`)
- Read-only mirror of whatever is currently filtered on the Dashboard page, meant for screen-sharing — no upload/filter/search controls, just the KPIs and charts.

**Report library** (`db.py`)
- Backed by a Neon (serverless Postgres) database.
- Uploading a report auto-saves it — deduplicated by a hash of the file's contents, so re-uploading the same file is a no-op rather than creating duplicate tickets.
- A "Load saved reports" mode lets you multi-select previously saved reports and load them combined into one filtered view (each row tagged with which source report it came from).
- Schema: a `reports` table (one row per upload: filename, sheet, hash, upload time, row count) and a `tickets` table (one row per ticket, with `Status`/`Category`/`Primary Responsibility`/`Modified`/`Title` as queryable columns plus the full original row preserved as JSON, so unexpected columns aren't lost).

**Shared theming** (`common.py`, `.streamlit/config.toml`)
- BYU–Hawaii brand colors (red/gold), light/dark palettes, and consistent chart styling across both pages.

## Tech stack

Python, [Streamlit](https://streamlit.io/), pandas, Plotly, openpyxl, SQLAlchemy + psycopg2 (Neon/Postgres).

## Project structure

```
app.py                          Entry point / page router
app_pages/dashboard.py          Main dashboard: upload, filters, KPIs, tabs, charts
app_pages/presentation.py       Read-only presentation view
common.py                       Shared theme colors, chart styling, text-normalization helper
db.py                           Neon/Postgres persistence layer (report library)
.streamlit/config.toml          BYUH color theme, fonts
.streamlit/secrets.toml.example Template for the Neon connection string (copy to secrets.toml)
requirements.txt                Python dependencies
```

## Setup

1. Clone the repo and create a virtual environment:
   ```
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   ```
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. **(Optional — only needed for the report library / "Load saved reports" feature.)** Uploading and exploring a single report works with no database at all. To enable saving/loading reports:
   - Create a free project at [neon.tech](https://neon.tech).
   - Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and paste in your Neon connection string (keep `?sslmode=require`).
   - `secrets.toml` is gitignored — it never gets committed.
4. Run the app:
   ```
   streamlit run app.py
   ```

## Data expectations

Uploaded reports should be TDX Excel exports containing at least `Status` and `Category` columns. `Primary Responsibility`, `Modified`, and `Title` are optional but unlock the Technicians/Trends tabs and title search, respectively.
