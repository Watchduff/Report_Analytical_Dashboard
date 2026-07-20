"""Presentation page: a read-only breakdown of the report, for screen-sharing.

Mirrors whatever filters are currently set on the Dashboard page. Has no
upload, filter, search, or download controls — just the charts and KPIs.
"""

import streamlit as st
import pandas as pd
import plotly.express as px

from common import BYUH_RED, BYUH_GOLD, STATUS_COLORS, get_palette, chart_theme, inject_base_css

theme_type, pal = get_palette()
inject_base_css(pal)

st.markdown("<h1 class='main-header'>📊 Report Summary</h1>", unsafe_allow_html=True)
st.markdown(
    "<p class='main-subheader'>BYU–Hawaii · Office of Information Technology — read-only view</p>",
    unsafe_allow_html=True,
)

filtered_df = st.session_state.get("report_filtered_df")
flags = st.session_state.get("report_flags")

if filtered_df is None or flags is None or filtered_df.empty:
    st.info(
        "No report loaded yet. Go to the **Dashboard** page, upload a report, and this "
        "view will mirror whatever filters you've set there."
    )
    st.page_link("app_pages/dashboard.py", label="Go to Dashboard", icon=":material/dashboard:")
    st.stop()

has_status = flags["has_status"]
has_category = flags["has_category"]
has_tech = flags["has_tech"]
has_modified = flags["has_modified"]

# -----------------------------
# KPI summary (plain cards, no click-through — this view is read-only)
# -----------------------------
def summary_card(col, key, label, value):
    with col.container(key=f"summary_{key}"):
        st.metric(label, value, border=True)

total_tickets = len(filtered_df)
kpi_cols = st.columns(5)
summary_card(kpi_cols[0], "total", "Total Tickets", f"{total_tickets:,}")

if has_status:
    closed_count = (filtered_df["Status"] == "Closed").sum()
    open_count = total_tickets - closed_count
    completion_rate = (closed_count / total_tickets * 100) if total_tickets else 0
    summary_card(kpi_cols[1], "closed", "Closed", f"{closed_count:,}")
    summary_card(kpi_cols[2], "open", "Open", f"{open_count:,}")
    summary_card(kpi_cols[3], "completion", "Completion Rate", f"{completion_rate:.1f}%")

if has_category:
    summary_card(kpi_cols[4], "categories", "Categories", filtered_df["Category"].nunique())

st.markdown("---")

# -----------------------------
# Status distribution
# -----------------------------
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

# -----------------------------
# Ticket volume over time
# -----------------------------
if has_modified and filtered_df["Modified"].notna().any():
    st.subheader("Ticket Volume Over Time")
    ts = filtered_df.dropna(subset=["Modified"]).copy()
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

# -----------------------------
# Category breakdown
# -----------------------------
if has_category:
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

# -----------------------------
# Technician workload
# -----------------------------
if has_tech:
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
