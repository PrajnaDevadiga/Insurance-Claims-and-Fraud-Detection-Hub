"""
Insurance Claim Validation & Fraud Detection Dashboard

Run: streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from dashboard.data_loader import load_dashboard_data, source_cache_key
from dashboard.sections import (
    render_claims_table,
    render_executive_dashboard,
    render_financial_analysis,
    render_fraud_dashboard,
    render_policy_analytics,
    render_search,
    render_summary_analytics,
    render_suspicious_panel,
)
from dashboard.ui_components import inject_custom_css

st.set_page_config(
    page_title="Insurance Claims & Fraud Analytics",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGES = {
    "Executive Dashboard": render_executive_dashboard,
    "Policy & Claim Search": render_search,
    "Fraud Detection": render_fraud_dashboard,
    "Financial Analysis": render_financial_analysis,
    "Policy Analytics": render_policy_analytics,
    "Claims Management": render_claims_table,
    "Suspicious Investigation": render_suspicious_panel,
    "Summary Analytics": render_summary_analytics,
}


@st.cache_data(show_spinner="Loading data…", ttl=3600)
def get_data(cache_key: str) -> dict:
    """Cached loader; invalidates when source CSV/JSON files change."""
    return load_dashboard_data()


def main() -> None:
    if "theme" not in st.session_state:
        st.session_state.theme = "light"
    if "page" not in st.session_state:
        st.session_state.page = "Executive Dashboard"

    cache_key = source_cache_key()

    with st.sidebar:
        st.markdown("## 🛡️ Claims & Fraud Hub")
        st.caption("Insurance operations analytics portal")

        theme = st.toggle("Dark Mode", value=st.session_state.theme == "dark")
        st.session_state.theme = "dark" if theme else "light"
        inject_custom_css(st.session_state.theme)

        st.divider()
        page = st.radio(
            "Navigation",
            list(PAGES.keys()),
            index=list(PAGES.keys()).index(st.session_state.page),
            label_visibility="collapsed",
            key="nav_page",
        )
        st.session_state.page = page

        st.divider()
        if st.button("Refresh Data", use_container_width=True):
            get_data.clear()
            from dashboard.data_loader import CACHE_FILE, CACHE_META

            for path in (CACHE_FILE, CACHE_META):
                if path.exists():
                    path.unlink()
            st.rerun()

        st.caption("© Insurance Fraud Analytics v1.0")

    # Load data once per session / cache key (not on theme-only reruns if cached)
    data = get_data(cache_key)
    page = st.session_state.page

    st.markdown(
        """
        <h1 style='margin-bottom:0;'>🛡️ Insurance Claim Validation & Fraud Detection</h1>
        <p style='color:#64748b;margin-top:0;'>
        Monitor claims · Validate policies · Detect fraud · Analyze trends
        </p>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    PAGES[page](data)


if __name__ == "__main__":
    main()
