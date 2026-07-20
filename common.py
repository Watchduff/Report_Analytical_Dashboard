"""Shared colors, theming, and chart helpers used by both app pages."""

import streamlit as st
import pandas as pd

# -----------------------------
# BYU-Hawaii Brand Colors (official, from marcom.byuh.edu/colors)
# -----------------------------
BYUH_RED = "#BA0C2F"        # Primary
BYUH_GOLD = "#C69214"       # Secondary
BYUH_WHITE = "#FFFFFF"
BYUH_DARK_RED = "#8A0923"   # Darker shade for hover/contrast
BYUH_GRAY = "#6B7280"

BRAND_SEQUENCE = [BYUH_RED, BYUH_GOLD, BYUH_DARK_RED, "#D9A441", BYUH_GRAY,
                  "#E8899B", "#E8C77A", "#5C0719", "#C9CED6", "#A6ABB2"]

STATUS_COLORS = {
    "Closed": BYUH_RED,
    "In Process": BYUH_GOLD,
    "New": "#D9A441",
    "On Hold": BYUH_GRAY,
}

# -----------------------------
# Theme palette (light/dark) — modeled after the financial aid admin console
# -----------------------------
PALETTES = {
    "dark": {
        "text": "#ECECEC",
        "muted": "#9A9A9A",
        "border": "rgba(255, 255, 255, 0.08)",
        "up": "#5BBF7A",
        "warn": "#E0A23A",
        "chart_font": "#ECECEC",
        "chart_grid": "rgba(255, 255, 255, 0.08)",
    },
    "light": {
        "text": "#0F172A",
        "muted": "#475569",
        "border": "#E2E4E8",
        "up": "#166534",
        "warn": "#B45309",
        "chart_font": "#26221F",
        "chart_grid": "rgba(15, 23, 42, 0.08)",
    },
}


def get_palette():
    theme_type = st.context.theme.type or "light"
    return theme_type, PALETTES[theme_type]


def chart_theme(fig, pal, **layout_kwargs):
    """Apply a transparent, theme-aware look so Plotly charts read well in both modes."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=pal["chart_font"],
        legend_font_color=pal["chart_font"],
        margin=dict(t=30, b=30, l=10, r=10),
        **layout_kwargs,
    )
    fig.update_xaxes(gridcolor=pal["chart_grid"], zerolinecolor=pal["chart_grid"])
    fig.update_yaxes(gridcolor=pal["chart_grid"], zerolinecolor=pal["chart_grid"])
    return fig


def normalize_text_column(series):
    """Collapse casing differences (e.g. "Hardware" vs "hardware") into one canonical label."""
    stripped = series.astype(str).str.strip()
    stripped = stripped.replace({"nan": pd.NA})
    lower_map = stripped.str.lower()
    canonical = (
        stripped.dropna().groupby(lower_map).agg(lambda x: x.value_counts().idxmax())
    )
    return lower_map.map(canonical).fillna(stripped)


def inject_base_css(pal):
    st.markdown(
        f"""
        <style>
        /* Header */
        .main-header {{
            color: {BYUH_RED};
            font-weight: 700;
            letter-spacing: -0.02em;
            margin-bottom: 0.1rem;
        }}
        .main-subheader {{
            color: {pal["muted"]};
            text-transform: uppercase;
            letter-spacing: 0.15em;
            font-size: 0.75rem;
            font-weight: 600;
            margin-bottom: 1.5rem;
        }}

        /* Buttons */
        div.stButton > button, div.stDownloadButton > button {{
            background-color: {BYUH_RED};
            color: white;
            border: none;
            transition: background-color 0.15s ease-in-out;
        }}
        div.stButton > button:hover, div.stDownloadButton > button:hover {{
            background-color: {BYUH_DARK_RED};
            color: white;
        }}

        /* Only one report can be uploaded at a time — hide the "add another file" affordance */
        [data-testid="stFileUploader"] button[aria-label="Add files"] {{ display: none; }}

        /* Give the sidebar checklist dropdowns (Category/Status/Technician) more room to scroll */
        [data-testid="stPopoverBody"] {{ max-height: min(75vh, 560px) !important; }}

        /* KPI metric cards: colored left accent per metric, admin-console style */
        [data-testid="stMetric"] {{ border-radius: 10px; }}
        .st-key-kpi_total [data-testid="stMetric"], .st-key-summary_total [data-testid="stMetric"] {{
            border-left: 3px solid {BYUH_RED} !important;
        }}
        .st-key-kpi_closed [data-testid="stMetric"], .st-key-summary_closed [data-testid="stMetric"] {{
            border-left: 3px solid {pal["up"]} !important;
        }}
        .st-key-kpi_open [data-testid="stMetric"], .st-key-summary_open [data-testid="stMetric"] {{
            border-left: 3px solid {pal["warn"]} !important;
        }}
        .st-key-kpi_completion [data-testid="stMetric"], .st-key-summary_completion [data-testid="stMetric"] {{
            border-left: 3px solid {BYUH_RED} !important;
        }}
        .st-key-kpi_categories [data-testid="stMetric"], .st-key-summary_categories [data-testid="stMetric"] {{
            border-left: 3px solid {pal["muted"]} !important;
        }}
        [data-testid="stMetricLabel"] {{
            color: {pal["muted"]};
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            font-size: 0.7rem;
        }}

        /* KPI cards on the Dashboard are clickable — jump to their tab. The button
           sits invisibly on top. (Presentation page reuses the color styling above
           but never adds a button, so it stays read-only.) */
        [class*="st-key-kpi_"] {{ position: relative; }}
        [class*="st-key-kpi_"] div[data-testid="stButton"] {{
            position: absolute;
            inset: 0;
            z-index: 2;
        }}
        [class*="st-key-kpi_"] div[data-testid="stButton"] button {{
            width: 100%;
            height: 100%;
            opacity: 0;
            border: none;
            background: transparent;
            cursor: pointer;
        }}
        [class*="st-key-kpi_"]:hover [data-testid="stMetric"] {{
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.14);
            transform: translateY(-1px);
            transition: box-shadow 0.15s ease, transform 0.15s ease;
        }}

        /* Sidebar section headings */
        [data-testid="stSidebar"] h2 {{
            color: {BYUH_RED};
            font-size: 1.05rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.75rem;
        }}

        /* Tabs: clearer active state for easier navigation */
        button[data-baseweb="tab"] {{
            font-weight: 500;
        }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            font-weight: 700;
            color: {BYUH_RED};
        }}
        div[data-baseweb="tab-highlight"] {{
            background-color: {BYUH_RED};
        }}

        /* Section subheaders */
        h3 {{ color: {BYUH_RED}; }}
        </style>
        """,
        unsafe_allow_html=True,
    )
