"""Dashboard page: upload, filter, and explore a report in full detail."""

import io

import streamlit as st
import pandas as pd
import plotly.express as px

from common import (
    BYUH_RED, BYUH_GOLD, STATUS_COLORS,
    get_palette, chart_theme, normalize_text_column, inject_base_css,
)

theme_type, pal = get_palette()
inject_base_css(pal)

st.markdown("<h1 class='main-header'>📊 Report Analytics Dashboard</h1>", unsafe_allow_html=True)
st.markdown("<p class='main-subheader'>BYU–Hawaii · Office of Information Technology</p>", unsafe_allow_html=True)

# -----------------------------
# File upload
# -----------------------------
# st.file_uploader loses its file when navigating to another page and back
# (the widget is torn down on unmount), so the raw bytes are cached in session
# state. Once a file is cached, a custom chip stands in for the native
# uploader so the page still visibly shows "a file is loaded" instead of an
# empty drop zone; the "x" clears it and brings the real uploader back.
st.markdown("Upload an Excel report (.xlsx)")

if st.session_state.get("report_bytes"):
    size_kb = len(st.session_state["report_bytes"]) / 1024
    with st.container(border=True):
        icon_col, name_col, remove_col = st.columns([0.06, 0.84, 0.10])
        icon_col.markdown("📊")
        name_col.markdown(
            f"**{st.session_state['report_filename']}**  \n"
            f"<span style='color:{pal['muted']}; font-size:0.8rem;'>{size_kb:,.1f} KB</span>",
            unsafe_allow_html=True,
        )
        if remove_col.button("✕", key="remove_report_file", help="Remove file"):
            st.session_state.pop("report_bytes", None)
            st.session_state.pop("report_filename", None)
            st.rerun()
else:
    uploaded_file = st.file_uploader(
        "Upload an Excel report (.xlsx)", type=["xlsx", "xls"], label_visibility="collapsed",
    )
    if uploaded_file is not None:
        st.session_state["report_bytes"] = uploaded_file.getvalue()
        st.session_state["report_filename"] = uploaded_file.name
        st.rerun()

report_bytes = st.session_state.get("report_bytes")

if report_bytes is None:
    st.info("Upload an Excel report to generate the dashboard.")
    st.stop()

try:
    excel_data = pd.ExcelFile(io.BytesIO(report_bytes))
except Exception as e:
    st.error(f"Could not read this file: {e}")
    st.stop()

# Prefer the main raw ticket sheet (has Status/Category/Modified columns);
# skip empty "Comments" sheets that TDX exports often include.
def looks_like_ticket_sheet(df):
    cols = set(df.columns.astype(str))
    return {"Status", "Category"}.issubset(cols) and len(df) > 0

candidate_sheets = []
for s in excel_data.sheet_names:
    try:
        preview = pd.read_excel(excel_data, sheet_name=s)
        if looks_like_ticket_sheet(preview):
            candidate_sheets.append(s)
    except Exception:
        continue

if candidate_sheets:
    default_sheet = candidate_sheets[0]
else:
    default_sheet = excel_data.sheet_names[0]

sheet_name = st.selectbox(
    "Select sheet",
    excel_data.sheet_names,
    index=excel_data.sheet_names.index(default_sheet),
)

df = pd.read_excel(excel_data, sheet_name=sheet_name)
df.columns = [str(c).strip() for c in df.columns]

if df.empty:
    st.warning("This sheet has no data. Try selecting a different sheet above.")
    st.stop()

# -----------------------------
# Detect TDX ticket columns
# -----------------------------
has_status = "Status" in df.columns
has_category = "Category" in df.columns
has_tech = "Primary Responsibility" in df.columns
has_modified = "Modified" in df.columns
has_title = "Title" in df.columns

if has_modified:
    df["Modified"] = pd.to_datetime(df["Modified"], errors="coerce")

for col in ["Category", "Status", "Primary Responsibility"]:
    if col in df.columns:
        df[col] = normalize_text_column(df[col])

# -----------------------------
# Sidebar filters
# -----------------------------
def checklist_dropdown(label, options, key):
    """Sidebar popover with a checkbox per option, like a report-style filter dropdown."""
    for opt in options:
        st.session_state.setdefault(f"{key}_{opt}", True)

    selected = [opt for opt in options if st.session_state.get(f"{key}_{opt}", True)]
    if len(selected) == len(options):
        summary = "All"
    elif not selected:
        summary = "None"
    else:
        summary = f"{len(selected)} selected"

    with st.sidebar.popover(f"{label}: {summary}", width="stretch"):
        col1, col2 = st.columns(2)
        if col1.button("Select all", key=f"{key}_select_all", width="stretch"):
            for opt in options:
                st.session_state[f"{key}_{opt}"] = True
            st.rerun()
        if col2.button("Clear", key=f"{key}_clear", width="stretch"):
            for opt in options:
                st.session_state[f"{key}_{opt}"] = False
            st.rerun()
        st.divider()
        for opt in options:
            st.checkbox(opt, key=f"{key}_{opt}")

    return [opt for opt in options if st.session_state.get(f"{key}_{opt}", True)]


st.sidebar.header("Filters")
filtered_df = df.copy()

if has_modified and df["Modified"].notna().any():
    min_date = df["Modified"].min()
    max_date = df["Modified"].max()
    date_range = st.sidebar.date_input(
        "Modified date range",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date(),
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = date_range
        mask = (filtered_df["Modified"].dt.date >= start) & (filtered_df["Modified"].dt.date <= end)
        filtered_df = filtered_df[mask]

if has_category:
    cat_options = sorted(filtered_df["Category"].dropna().unique().tolist())
    selected_cats = checklist_dropdown("Category", cat_options, key="cat")
    if selected_cats:
        filtered_df = filtered_df[filtered_df["Category"].isin(selected_cats)]

if has_status:
    status_options = sorted(filtered_df["Status"].dropna().unique().tolist())
    selected_status = checklist_dropdown("Status", status_options, key="status")
    if selected_status:
        filtered_df = filtered_df[filtered_df["Status"].isin(selected_status)]

if has_tech:
    tech_options = sorted(filtered_df["Primary Responsibility"].dropna().unique().tolist())
    selected_techs = checklist_dropdown("Technician", tech_options, key="tech")
    if selected_techs:
        filtered_df = filtered_df[filtered_df["Primary Responsibility"].isin(selected_techs)]

st.sidebar.markdown("---")
st.sidebar.caption(f"{len(filtered_df):,} of {len(df):,} tickets shown")

# Mirror the current filtered view into session state so the read-only
# Presentation page can show the same slice without its own upload/filters.
st.session_state["report_filtered_df"] = filtered_df
st.session_state["report_flags"] = {
    "has_status": has_status,
    "has_category": has_category,
    "has_tech": has_tech,
    "has_modified": has_modified,
    "has_title": has_title,
}

if filtered_df.empty:
    st.warning("No tickets match the current filters.")
    st.stop()

# -----------------------------
# Tab definitions (computed early so KPI cards can jump to a tab on click)
# -----------------------------
tab_keys = ["Overview"]
if has_modified:
    tab_keys.append("Trends")
if has_category:
    tab_keys.append("Categories")
if has_tech:
    tab_keys.append("Technicians")
tab_keys.append("Raw Data")

tab_icons = {
    "Overview": "dashboard",
    "Trends": "trending_up",
    "Categories": "category",
    "Technicians": "engineering",
    "Raw Data": "table_chart",
}
tab_labels = [f":material/{tab_icons[key]}: {key}" for key in tab_keys]
tab_label_map = dict(zip(tab_keys, tab_labels))

# -----------------------------
# KPI row (always visible, above tabs) — cards jump to their tab when clicked
# -----------------------------
def kpi_card(col, key, label, value, target_tab, drill=None):
    """A clickable KPI card that jumps to a tab, optionally drilling into the
    matching subset of tickets on the Raw Data tab (e.g. Closed -> closed tickets)."""
    with col.container(key=f"kpi_{key}"):
        st.metric(label, value, border=True)
        clicked = target_tab in tab_label_map and st.button(
            f"View {label} in {target_tab}", key=f"kpi_{key}_btn", width="stretch",
        )
        if clicked:
            st.session_state["main_tabs"] = tab_label_map[target_tab]
            st.session_state["raw_data_drill"] = drill

kpi_cols = st.columns(5)
total_tickets = len(filtered_df)
kpi_card(kpi_cols[0], "total", "Total Tickets", f"{total_tickets:,}", "Raw Data")

if has_status:
    closed_count = (filtered_df["Status"] == "Closed").sum()
    open_count = total_tickets - closed_count
    completion_rate = (closed_count / total_tickets * 100) if total_tickets else 0
    kpi_card(kpi_cols[1], "closed", "Closed", f"{closed_count:,}", "Raw Data", drill="Closed")
    kpi_card(kpi_cols[2], "open", "Open", f"{open_count:,}", "Raw Data", drill="Open")
    kpi_card(kpi_cols[3], "completion", "Completion Rate", f"{completion_rate:.1f}%", "Raw Data")

if has_category:
    kpi_card(kpi_cols[4], "categories", "Categories", filtered_df["Category"].nunique(), "Categories")

st.markdown("---")

# -----------------------------
# Tabbed sections
# -----------------------------
tabs = st.tabs(tab_labels, key="main_tabs", on_change="rerun")
tab_map = dict(zip(tab_keys, tabs))

# --- Overview tab: status distribution ---
with tab_map["Overview"]:
    if has_status:
        st.subheader("Status Distribution")
        col1, col2 = st.columns([1, 1])
        status_counts = filtered_df["Status"].value_counts().reset_index()
        status_counts.columns = ["Status", "count"]

        with col1:
            fig_pie = px.pie(
                status_counts, names="Status", values="count",
                color="Status", color_discrete_map=STATUS_COLORS, hole=0.4,
            )
            fig_pie.update_traces(textinfo="label+percent+value")
            chart_theme(fig_pie, pal)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col2:
            fig_bar = px.bar(
                status_counts.sort_values("count", ascending=True),
                x="count", y="Status", orientation="h",
                color="Status", color_discrete_map=STATUS_COLORS, text="count",
            )
            chart_theme(fig_bar, pal, showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No Status column found in this sheet.")

# --- Trends tab: ticket volume over time ---
if "Trends" in tab_map:
    with tab_map["Trends"]:
        if filtered_df["Modified"].notna().any():
            st.subheader("Ticket Volume Over Time")
            granularity = st.radio("Group by", ["Day", "Week"], horizontal=True, key="time_granularity")
            ts = filtered_df.dropna(subset=["Modified"]).copy()

            if granularity == "Day":
                ts["_period"] = ts["Modified"].dt.to_period("D").dt.to_timestamp()
            else:
                ts["_period"] = ts["Modified"].dt.to_period("W").dt.to_timestamp()

            if has_status:
                trend = ts.groupby(["_period", "Status"]).size().reset_index(name="count")
                fig = px.bar(
                    trend, x="_period", y="count", color="Status",
                    color_discrete_map=STATUS_COLORS, barmode="stack",
                )
            else:
                trend = ts.groupby("_period").size().reset_index(name="count")
                fig = px.line(trend, x="_period", y="count", markers=True, color_discrete_sequence=[BYUH_RED])

            chart_theme(fig, pal, xaxis_title="Date", yaxis_title="Ticket Count")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No valid Modified dates found in the current selection.")

# --- Categories tab: breakdown, cross-tab, completion rate ---
if "Categories" in tab_map:
    with tab_map["Categories"]:
        st.subheader("Tickets by Category")
        cat_counts = filtered_df["Category"].value_counts().reset_index()
        cat_counts.columns = ["Category", "count"]
        cat_counts = cat_counts.sort_values("count", ascending=True)

        fig_cat = px.bar(
            cat_counts, x="count", y="Category", orientation="h",
            color_discrete_sequence=[BYUH_RED], text="count",
        )
        chart_theme(fig_cat, pal, height=max(350, len(cat_counts) * 35))
        st.plotly_chart(fig_cat, use_container_width=True)

        if has_status:
            st.subheader("Category Breakdown by Status")
            cross = pd.crosstab(filtered_df["Category"], filtered_df["Status"])
            cross = cross.loc[cross.sum(axis=1).sort_values(ascending=True).index]
            cross_long = cross.reset_index().melt(id_vars="Category", var_name="Status", value_name="count")

            fig_cross = px.bar(
                cross_long, x="count", y="Category", color="Status", orientation="h",
                color_discrete_map=STATUS_COLORS, barmode="stack",
            )
            chart_theme(fig_cross, pal, height=max(350, len(cross) * 35))
            st.plotly_chart(fig_cross, use_container_width=True)

            with st.expander("View category x status table"):
                st.dataframe(cross, use_container_width=True)

            st.subheader("Completion Rate by Category")
            comp = filtered_df.groupby("Category")["Status"].apply(
                lambda s: (s == "Closed").sum() / len(s) * 100
            ).reset_index(name="completion_rate")
            comp = comp.sort_values("completion_rate", ascending=True)

            fig_comp = px.bar(
                comp, x="completion_rate", y="Category", orientation="h",
                color="completion_rate", color_continuous_scale=[BYUH_GOLD, BYUH_RED],
                text=comp["completion_rate"].round(1).astype(str) + "%",
            )
            chart_theme(fig_comp, pal, height=max(350, len(comp) * 35),
                        coloraxis_showscale=False, xaxis_title="Completion Rate (%)")
            st.plotly_chart(fig_comp, use_container_width=True)

# --- Technicians tab: workload ---
if "Technicians" in tab_map:
    with tab_map["Technicians"]:
        st.subheader("Workload by Technician")
        tech_counts = filtered_df["Primary Responsibility"].value_counts().reset_index()
        tech_counts.columns = ["Technician", "count"]
        tech_counts = tech_counts.sort_values("count", ascending=True)

        if has_status:
            tech_status = filtered_df.groupby(["Primary Responsibility", "Status"]).size().reset_index(name="count")
            tech_order = filtered_df["Primary Responsibility"].value_counts().index.tolist()[::-1]
            fig_tech = px.bar(
                tech_status, x="count", y="Primary Responsibility", color="Status",
                orientation="h", color_discrete_map=STATUS_COLORS, barmode="stack",
                category_orders={"Primary Responsibility": tech_order},
            )
        else:
            fig_tech = px.bar(
                tech_counts, x="count", y="Technician", orientation="h",
                color_discrete_sequence=[BYUH_RED], text="count",
            )

        chart_theme(fig_tech, pal, height=max(350, len(tech_counts) * 35), yaxis_title="Technician")
        st.plotly_chart(fig_tech, use_container_width=True)

# --- Raw Data tab ---
with tab_map["Raw Data"]:
    display_df = filtered_df
    drill = st.session_state.get("raw_data_drill")
    if drill and has_status:
        display_df = display_df[display_df["Status"] == "Closed"] if drill == "Closed" \
            else display_df[display_df["Status"] != "Closed"]
        drill_col1, drill_col2 = st.columns([5, 1])
        drill_col1.caption(f"Showing **{drill.lower()}** tickets only (from the KPI card above).")
        if drill_col2.button("Clear", key="clear_drill", width="stretch"):
            st.session_state["raw_data_drill"] = None
            st.rerun()

    search = st.text_input("Search titles", "")
    if search and has_title:
        display_df = display_df[display_df["Title"].astype(str).str.contains(search, case=False, na=False)]
    st.dataframe(display_df, use_container_width=True)
    csv = display_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download filtered data as CSV", csv, "filtered_tickets.csv", "text/csv")
