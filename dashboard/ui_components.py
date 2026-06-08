"""Reusable UI components, styling, and chart helpers for the dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st

# Brand colors
COLOR_APPROVED = "#22c55e"
COLOR_REJECTED = "#ef4444"
COLOR_SUSPICIOUS = "#f97316"
COLOR_POLICY = "#3b82f6"
COLOR_NEUTRAL = "#64748b"

THEME_CSS = {
    "light": """
    .stApp { background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); }
    .kpi-card {
        background: #ffffff; border-radius: 12px; padding: 1rem 1.25rem;
        border-left: 4px solid var(--accent); box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        margin-bottom: 0.5rem;
    }
    .kpi-title { color: #64748b; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; }
    .kpi-value { color: #0f172a; font-size: 1.5rem; font-weight: 700; }
    .section-header { color: #0f172a; font-weight: 700; margin-top: 0.5rem; }
    """,
    "dark": """
    .stApp { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); }
    .kpi-card {
        background: #1e293b; border-radius: 12px; padding: 1rem 1.25rem;
        border-left: 4px solid var(--accent); box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        margin-bottom: 0.5rem;
    }
    .kpi-title { color: #94a3b8; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; }
    .kpi-value { color: #f1f5f9; font-size: 1.5rem; font-weight: 700; }
    .section-header { color: #f1f5f9; font-weight: 700; margin-top: 0.5rem; }
    """,
}


def inject_custom_css(theme: str = "light") -> None:
    st.markdown(
        f"<style>{THEME_CSS.get(theme, THEME_CSS['light'])}</style>",
        unsafe_allow_html=True,
    )


def kpi_card(title: str, value: str, accent: str = COLOR_POLICY, delta: str | None = None) -> None:
    delta_html = f'<div style="font-size:0.75rem;color:#64748b;">{delta}</div>' if delta else ""
    st.markdown(
        f"""
        <div class="kpi-card" style="--accent:{accent};">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_row(metrics: list[tuple[str, str, str]], cols_per_row: int = 4) -> None:
    for i in range(0, len(metrics), cols_per_row):
        chunk = metrics[i : i + cols_per_row]
        cols = st.columns(len(chunk))
        for col, (title, value, accent) in zip(cols, chunk):
            with col:
                kpi_card(title, value, accent)


def format_currency(amount: float) -> str:
    return f"₹{amount:,.0f}"


def plotly_chart(fig, use_container_width: bool = True) -> None:
    fig.update_layout(  # noqa: plotly figure
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12),
        hovermode="closest",
    )
    st.plotly_chart(fig, use_container_width=use_container_width)


def gauge_chart(title: str, value: float, max_val: float = 100, color: str = COLOR_POLICY):
    import plotly.graph_objects as go

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            title={"text": title, "font": {"size": 14}},
            number={"suffix": "%"},
            gauge={
                "axis": {"range": [0, max_val]},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, max_val * 0.5], "color": "rgba(0,0,0,0.05)"},
                    {"range": [max_val * 0.5, max_val], "color": "rgba(0,0,0,0.02)"},
                ],
            },
        )
    )
    fig.update_layout(height=220)
    return fig


def paginate_dataframe(df: pd.DataFrame, page_size: int, page_key: str) -> pd.DataFrame:
    total_pages = max(1, (len(df) - 1) // page_size + 1) if len(df) else 1
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, key=page_key)
    start = (page - 1) * page_size
    st.caption(f"Showing {start + 1}–{min(start + page_size, len(df))} of {len(df)} records")
    return df.iloc[start : start + page_size]


def risk_badge(label: str) -> str:
    colors = {
        "High Risk": COLOR_REJECTED,
        "Medium Risk": COLOR_SUSPICIOUS,
        "Low Risk": COLOR_APPROVED,
    }
    color = colors.get(label, COLOR_NEUTRAL)
    return f":{('red' if 'High' in label else 'orange' if 'Medium' in label else 'green')}[{label}]"


def amount_range_label(amount: float) -> str:
    if amount <= 50_000:
        return "₹0 – ₹50K"
    if amount <= 100_000:
        return "₹50K – ₹1L"
    if amount <= 200_000:
        return "₹1L – ₹2L"
    return "₹2L+"
