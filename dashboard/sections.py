"""Dashboard page sections for the insurance analytics portal."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import SUSPICIOUS_THRESHOLD, compute_kpis
from dashboard.ui_components import (
    COLOR_APPROVED,
    COLOR_POLICY,
    COLOR_REJECTED,
    COLOR_SUSPICIOUS,
    amount_range_label,
    format_currency,
    gauge_chart,
    paginate_dataframe,
    plotly_chart,
    render_kpi_row,
    risk_badge,
)


def render_executive_dashboard(data: dict) -> None:
    st.markdown("### Executive Dashboard")
    st.caption("Real-time overview of claim validation and fraud detection performance")

    kpis = data.get("kpis") or compute_kpis(data)
    render_kpi_row(
        [
            ("Total Policies", str(kpis["total_policies"]), COLOR_POLICY),
            ("Claims Submitted", str(kpis["total_claims"]), COLOR_POLICY),
            ("Approved Claims", str(kpis["approved_claims"]), COLOR_APPROVED),
            ("Rejected Claims", str(kpis["rejected_claims"]), COLOR_REJECTED),
        ]
    )
    render_kpi_row(
        [
            ("Suspicious Claims", str(kpis["suspicious_claims"]), COLOR_SUSPICIOUS),
            ("Approved Amount", format_currency(kpis["total_approved_amount"]), COLOR_APPROVED),
            ("Rejected Amount", format_currency(kpis["total_rejected_amount"]), COLOR_REJECTED),
            ("Avg Claim Amount", format_currency(kpis["average_claim_amount"]), COLOR_POLICY),
        ]
    )

    all_df: pd.DataFrame = data["all_claims"]
    if all_df.empty:
        st.info("No claim data available.")
        return

    agg = data.get("aggregates", {})
    col1, col2 = st.columns(2)
    with col1:
        status_counts = agg.get("status_counts", all_df["status"].value_counts().reset_index(name="count"))
        if "status" not in status_counts.columns:
            status_counts.columns = ["status", "count"]
        fig = px.pie(
            status_counts,
            values="count",
            names="status",
            title="Claim Status Distribution",
            color="status",
            color_discrete_map={"APPROVED": COLOR_APPROVED, "REJECTED": COLOR_REJECTED},
        )
        plotly_chart(fig)

    with col2:
        monthly = agg.get("monthly", pd.DataFrame())
        if monthly.empty:
            monthly = (
                all_df.dropna(subset=["claim_date"])
                .groupby("claim_month")["claim_amount"]
                .sum()
                .reset_index()
            )
        fig = px.area(
            monthly,
            x="claim_month",
            y="amount",
            markers=True,
            title="Monthly Claim Volume Trend",
            labels={"amount": "Total Amount (₹)", "claim_month": "Month"},
        )
        fig.update_traces(line_color=COLOR_POLICY, fillcolor="rgba(59,130,246,0.2)")
        plotly_chart(fig)

    _render_fraud_alerts(data, kpis)


def _render_fraud_alerts(data: dict, kpis: dict) -> None:
    high_risk: pd.DataFrame = data.get("high_risk", pd.DataFrame())
    if high_risk.empty:
        return
    st.markdown("#### Fraud Alert Panel")
    for _, row in high_risk.head(5).iterrows():
        st.warning(
            f"**{row['claim_id']}** | Policy {row['policy_id']} | "
            f"{format_currency(row['claim_amount'])} | Status: {row['status']} | "
            f"Exceeds ₹200,000 threshold"
        )


def render_search(data: dict) -> None:
    st.markdown("### Policy & Claim Search")
    policies: pd.DataFrame = data["policies"]
    all_df: pd.DataFrame = data["all_claims"]

    if policies.empty or all_df.empty:
        st.error("Policy or claim data not found.")
        return

    search_type = st.radio(
        "Search by",
        ["Policy ID", "Claim ID", "Customer ID"],
        horizontal=True,
    )

    if search_type == "Policy ID":
        options = sorted(policies["policy_id"].unique())
        selected = st.selectbox("Select Policy ID", [""] + options)
        if not selected:
            st.info("Select a policy to view details.")
            return
        policy = policies[policies["policy_id"] == selected].iloc[0]
        claims = all_df[all_df["policy_id"] == selected]
        _show_policy_detail(policy, claims)
    elif search_type == "Claim ID":
        options = sorted(all_df["claim_id"].unique())
        selected = st.selectbox("Select Claim ID", [""] + options)
        if not selected:
            st.info("Select a claim to view details.")
            return
        claim = all_df[all_df["claim_id"] == selected].iloc[0]
        policy = policies[policies["policy_id"] == claim["policy_id"]]
        policy_row = policy.iloc[0] if not policy.empty else None
        _show_claim_detail(claim, policy_row)
    else:
        cust = st.text_input("Enter Customer ID (e.g. CUST001)")
        if not cust:
            st.info("Enter a customer ID to search.")
            return
        matched = policies[policies["customer_id"].str.upper() == cust.upper()]
        if matched.empty:
            st.warning(f"No records found for customer **{cust}**.")
            return
        for _, policy in matched.iterrows():
            claims = all_df[all_df["policy_id"] == policy["policy_id"]]
            _show_policy_detail(policy, claims)
            st.divider()


def _show_policy_detail(policy: pd.Series, claims: pd.DataFrame) -> None:
    st.success(f"Policy **{policy['policy_id']}** found")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Customer", policy.get("customer_id", "N/A"))
    c2.metric("Policy Type", policy.get("policy_type", "N/A"))
    c3.metric("Coverage", format_currency(float(policy["coverage_amount"])))
    status = policy.get("policy_status", "N/A")
    c4.metric("Status", status)

    if claims.empty:
        st.info("No claims linked to this policy.")
        return
    st.dataframe(
        claims[
            [
                "claim_id",
                "claim_amount",
                "claim_date",
                "status",
                "fraud_flag",
                "rejection_reason",
                "risk_label",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )


def _show_claim_detail(claim: pd.Series, policy: pd.Series | None) -> None:
    st.success(f"Claim **{claim['claim_id']}** found")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Claim Amount", format_currency(claim["claim_amount"]))
    c2.metric("Claim Date", str(claim.get("claim_date", ""))[:10])
    c3.metric("Status", claim["status"])
    c4.metric("Fraud Flag", claim.get("fraud_flag") or "None")

    if policy is not None:
        st.markdown("**Policy Details**")
        p1, p2, p3 = st.columns(3)
        p1.metric("Policy ID", policy["policy_id"])
        p2.metric("Coverage", format_currency(float(policy["coverage_amount"])))
        p3.metric("Policy Status", policy["policy_status"])

    if claim["status"] == "REJECTED":
        st.error(f"Rejection Reason: **{claim['rejection_reason']}**")
    else:
        st.success(f"Approved Amount: **{format_currency(claim['approved_amount'])}**")

    st.markdown(f"Risk Assessment: {risk_badge(claim.get('risk_label', 'Low Risk'))}")


def render_fraud_dashboard(data: dict) -> None:
    st.markdown("### Fraud Detection Dashboard")
    all_df: pd.DataFrame = data["all_claims"]
    suspicious: pd.DataFrame = data["suspicious"]

    if all_df.empty:
        st.warning("No claim data available for fraud analysis.")
        return

    fraud_df = all_df
    agg = data.get("aggregates", {})

    col1, col2 = st.columns(2)
    with col1:
        pie_data = agg.get("fraud_counts", fraud_df["fraud_status"].value_counts().reset_index(name="count"))
        pie_data = pie_data.rename(columns={"fraud_status": "category"}) if "fraud_status" in pie_data.columns else pie_data
        if "category" not in pie_data.columns:
            pie_data.columns = ["category", "count"]
        fig = px.pie(
            pie_data,
            values="count",
            names="category",
            title="Suspicious vs Normal Claims",
            color="category",
            color_discrete_map={"Suspicious": COLOR_SUSPICIOUS, "Normal": COLOR_APPROVED},
        )
        plotly_chart(fig)

    with col2:
        bar_df = agg.get("amount_ranges", pd.DataFrame())
        if bar_df.empty:
            fraud_df = fraud_df.copy()
            fraud_df["amount_range"] = fraud_df["claim_amount"].apply(amount_range_label)
            suspicious_only = fraud_df[fraud_df["fraud_status"] == "Suspicious"]
            bar_df = (
                suspicious_only.groupby("amount_range", as_index=False)["claim_id"]
                .count()
                .rename(columns={"claim_id": "count"})
            )
            if bar_df.empty:
                bar_df = (
                    fraud_df.groupby("amount_range", as_index=False)["claim_id"]
                    .count()
                    .rename(columns={"claim_id": "count"})
                )
        fig = px.bar(
            bar_df,
            x="amount_range",
            y="count",
            title="Claims by Amount Range (Fraud Focus)",
            color_discrete_sequence=[COLOR_SUSPICIOUS],
        )
        plotly_chart(fig)

    col3, col4 = st.columns(2)
    with col3:
        top_policies = (
            fraud_df[fraud_df["fraud_status"] == "Suspicious"]
            .groupby("policy_id", as_index=False)
            .agg(suspicious_count=("claim_id", "count"), total_amount=("claim_amount", "sum"))
            .sort_values("suspicious_count", ascending=False)
            .head(10)
        )
        if top_policies.empty:
            top_policies = (
                fraud_df[fraud_df["claim_amount"] > SUSPICIOUS_THRESHOLD]
                .groupby("policy_id")["claim_amount"]
                .count()
                .reset_index(name="suspicious_count")
                .head(10)
            )
        if not top_policies.empty:
            fig = px.bar(
                top_policies,
                x="policy_id",
                y="suspicious_count" if "suspicious_count" in top_policies.columns else "claim_amount",
                title="Top Suspicious Policies",
                color_discrete_sequence=[COLOR_SUSPICIOUS],
            )
            plotly_chart(fig)
        else:
            st.info("No suspicious policies in current dataset.")

    with col4:
        if "customer_id" in fraud_df.columns:
            top_cust = (
                fraud_df[fraud_df["fraud_status"] == "Suspicious"]
                .groupby("customer_id")
                .size()
                .reset_index(name="count")
                .sort_values("count", ascending=False)
                .head(10)
            )
            if top_cust.empty:
                high_amt = fraud_df[fraud_df["claim_amount"] > 100_000]
                top_cust = (
                    high_amt.groupby("customer_id")
                    .size()
                    .reset_index(name="count")
                    .sort_values("count", ascending=False)
                    .head(10)
                )
            if not top_cust.empty:
                fig = px.bar(
                    top_cust,
                    x="customer_id",
                    y="count",
                    title="Top Suspicious Customers",
                    color_discrete_sequence=[COLOR_REJECTED],
                )
                plotly_chart(fig)

    st.markdown("#### High-Risk Claims (exceeding ₹200,000)")
    high = fraud_df[fraud_df["claim_amount"] > SUSPICIOUS_THRESHOLD]
    if high.empty:
        st.info("No claims exceeding ₹200,000 in the current period.")
    else:
        st.dataframe(high, use_container_width=True, hide_index=True)

    repeat = (
        fraud_df[fraud_df["fraud_status"] == "Suspicious"]
        .groupby("policy_id")
        .filter(lambda x: len(x) > 1)
    )
    if not repeat.empty:
        st.markdown("#### Policies with Repeated Suspicious Claims")
        st.dataframe(repeat, use_container_width=True, hide_index=True)


def render_financial_analysis(data: dict) -> None:
    st.markdown("### Claims Financial Analysis")
    all_df: pd.DataFrame = data["all_claims"]
    policies: pd.DataFrame = data["policies"]

    if all_df.empty:
        st.warning("No financial data available.")
        return

    approved_df = all_df[all_df["status"] == "APPROVED"]
    rejected_df = all_df[all_df["status"] == "REJECTED"]

    m1, m2, m3 = st.columns(3)
    m1.metric("Highest Claim", format_currency(all_df["claim_amount"].max()))
    m2.metric(
        "Largest Approved",
        format_currency(approved_df["claim_amount"].max()) if not approved_df.empty else "₹0",
    )
    m3.metric(
        "Largest Rejected",
        format_currency(rejected_df["claim_amount"].max()) if not rejected_df.empty else "₹0",
    )

    col1, col2 = st.columns(2)
    with col1:
        fig = px.histogram(
            all_df,
            x="claim_amount",
            nbins=25,
            title="Claim Amount Distribution",
            color_discrete_sequence=[COLOR_POLICY],
        )
        plotly_chart(fig)

    with col2:
        value_df = pd.DataFrame(
            {
                "category": ["Approved Value", "Rejected Value"],
                "amount": [
                    approved_df["approved_amount"].sum(),
                    rejected_df["claim_amount"].sum(),
                ],
            }
        )
        fig = px.bar(
            value_df,
            x="category",
            y="amount",
            title="Approved vs Rejected Claim Value",
            color="category",
            color_discrete_map={
                "Approved Value": COLOR_APPROVED,
                "Rejected Value": COLOR_REJECTED,
            },
        )
        plotly_chart(fig)

    col3, col4 = st.columns(2)
    with col3:
        monthly = data.get("aggregates", {}).get("monthly", pd.DataFrame())
        if monthly.empty:
            monthly = (
                all_df.dropna(subset=["claim_date"])
                .groupby("claim_month", as_index=False)
                .agg(claims=("claim_id", "count"), amount=("claim_amount", "sum"))
            )
        fig = px.line(
            monthly,
            x="claim_month",
            y="amount",
            markers=True,
            title="Monthly Claim Trend",
            labels={"amount": "Total Amount (₹)"},
        )
        plotly_chart(fig)

    with col4:
        if "policy_type" in all_df.columns and all_df["policy_type"].notna().any():
            avg_type = (
                all_df.groupby("policy_type")["claim_amount"].mean().reset_index()
            )
            fig = px.bar(
                avg_type,
                x="policy_type",
                y="claim_amount",
                title="Average Claim by Policy Type",
                color="policy_type",
            )
            plotly_chart(fig)
        elif not policies.empty:
            merged = all_df.merge(
                policies[["policy_id", "policy_type"]], on="policy_id", how="left"
            )
            avg_type = merged.groupby("policy_type")["claim_amount"].mean().reset_index()
            fig = px.bar(avg_type, x="policy_type", y="claim_amount", title="Average Claim by Policy Type")
            plotly_chart(fig)

    # Simple forecast
    if len(monthly) >= 3:
        st.markdown("#### Claim Trend Forecast")
        monthly["forecast"] = monthly["amount"].rolling(2, min_periods=1).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=monthly["claim_month"], y=monthly["amount"], name="Actual"))
        fig.add_trace(
            go.Scatter(
                x=monthly["claim_month"],
                y=monthly["forecast"],
                name="Rolling Forecast",
                line=dict(dash="dash", color=COLOR_SUSPICIOUS),
            )
        )
        fig.update_layout(title="Claim Amount Forecast (Rolling Avg)")
        plotly_chart(fig)


def render_policy_analytics(data: dict) -> None:
    st.markdown("### Policy Analytics")
    policies: pd.DataFrame = data["policies"]
    all_df: pd.DataFrame = data["all_claims"]
    summary = data.get("summary", {})

    if policies.empty:
        st.warning("Policy master data not found.")
        return

    active = (policies["policy_status"] == "ACTIVE").sum()
    expired = (policies["policy_status"] == "EXPIRED").sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("Active Policies", int(active), delta=None)
    c2.metric("Expired Policies", int(expired))
    c3.metric("Total Policies", len(policies))

    policy_summary = summary.get("policy_claim_summary", {})
    util_rows = []
    for pid, stats in policy_summary.items():
        pol = policies[policies["policy_id"] == pid]
        coverage = float(pol["coverage_amount"].iloc[0]) if not pol.empty else 0
        approved_amt = float(stats.get("total_approved_amount", 0))
        util_rows.append(
            {
                "policy_id": pid,
                "coverage": coverage,
                "approved_total": approved_amt,
                "utilization_pct": (approved_amt / coverage * 100) if coverage else 0,
                "claim_count": stats.get("total_claims", 0),
                "claim_to_coverage": (approved_amt / coverage) if coverage else 0,
            }
        )
    util_df = pd.DataFrame(util_rows)

    col1, col2 = st.columns(2)
    with col1:
        if not util_df.empty:
            fig = px.scatter(
                util_df,
                x="coverage",
                y="approved_total",
                hover_name="policy_id",
                title="Coverage Amount vs Claim Amount",
                labels={"coverage": "Coverage (₹)", "approved_total": "Approved Claims (₹)"},
                color_discrete_sequence=[COLOR_POLICY],
            )
            plotly_chart(fig)

    with col2:
        if not util_df.empty:
            fig = px.bar(
                util_df.sort_values("claim_count", ascending=False).head(15),
                x="policy_id",
                y="claim_count",
                title="Policy-wise Claim Count",
                color_discrete_sequence=[COLOR_POLICY],
            )
            plotly_chart(fig)

    if not util_df.empty:
        st.markdown("#### Coverage Utilization")
        util_df["risk_tier"] = pd.cut(
            util_df["utilization_pct"],
            bins=[0, 25, 50, 100],
            labels=["Low", "Medium", "High"],
        )
        st.dataframe(
            util_df.sort_values("utilization_pct", ascending=False),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### Policy Risk Scoring")
        util_df["policy_risk_score"] = (
            util_df["utilization_pct"] * 0.5 + util_df["claim_count"] * 5
        ).clip(0, 100)
        st.dataframe(
            util_df[["policy_id", "policy_risk_score", "utilization_pct", "claim_count"]]
            .sort_values("policy_risk_score", ascending=False)
            .head(10),
            use_container_width=True,
            hide_index=True,
        )


def render_claims_table(data: dict) -> None:
    st.markdown("### Claims Management")
    validated: pd.DataFrame = data["validated"]
    all_df: pd.DataFrame = data["all_claims"]

    df = validated if not validated.empty else all_df[all_df["status"] == "APPROVED"]
    if df.empty:
        st.warning("No validated claims to display.")
        return

    st.markdown("Filter and explore approved claims from the validation report.")

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        if "is_suspicious" in df.columns:
            fraud_opts = ["Suspicious", "Normal"]
            fraud_filter = st.multiselect("Fraud Status", options=fraud_opts, default=fraud_opts)
        elif "fraud_status" in df.columns:
            fraud_filter = st.multiselect(
                "Fraud Status",
                options=sorted(df["fraud_status"].dropna().unique()),
            )
        else:
            fraud_filter = []
    with fc2:
        policy_status = st.multiselect(
            "Policy Status",
            options=sorted(df["policy_status"].dropna().unique()) if "policy_status" in df.columns else [],
        )
    with fc3:
        amount_range = st.slider(
            "Claim Amount Range (₹)",
            int(df["claim_amount"].min()),
            int(df["claim_amount"].max()),
            (int(df["claim_amount"].min()), int(df["claim_amount"].max())),
        )

    if "claim_date" in df.columns:
        df = df.copy()
        df["claim_date"] = pd.to_datetime(df["claim_date"], errors="coerce")
        min_d, max_d = df["claim_date"].min(), df["claim_date"].max()
        if pd.notna(min_d) and pd.notna(max_d):
            date_range = st.date_input("Date Range", value=[min_d.date(), max_d.date()])
        else:
            date_range = None
    else:
        date_range = None

    search_q = st.text_input("Search (Claim ID, Policy ID)")

    filtered = df.copy()
    if fraud_filter and "is_suspicious" in filtered.columns:
        want_suspicious = "Suspicious" in fraud_filter
        want_normal = "Normal" in fraud_filter
        if want_suspicious and not want_normal:
            filtered = filtered[filtered["is_suspicious"]]
        elif want_normal and not want_suspicious:
            filtered = filtered[~filtered["is_suspicious"]]
    elif fraud_filter and "fraud_status" in filtered.columns:
        filtered = filtered[filtered["fraud_status"].isin(fraud_filter)]
    if policy_status:
        filtered = filtered[filtered["policy_status"].isin(policy_status)]
    filtered = filtered[
        (filtered["claim_amount"] >= amount_range[0])
        & (filtered["claim_amount"] <= amount_range[1])
    ]
    if date_range and len(date_range) == 2 and "claim_date" in filtered.columns:
        filtered = filtered[
            (filtered["claim_date"].dt.date >= date_range[0])
            & (filtered["claim_date"].dt.date <= date_range[1])
        ]
    if search_q:
        mask = filtered["claim_id"].str.contains(search_q, case=False, na=False) | filtered[
            "policy_id"
        ].str.contains(search_q, case=False, na=False)
        filtered = filtered[mask]

    sort_col = st.selectbox("Sort by", filtered.columns.tolist(), index=0)
    sort_asc = st.checkbox("Ascending", value=True)
    filtered = filtered.sort_values(sort_col, ascending=sort_asc)

    page_size = st.selectbox("Rows per page", [10, 25, 50, 100], index=1)
    page_df = paginate_dataframe(filtered, page_size, "claims_page")

    st.dataframe(page_df, use_container_width=True, hide_index=True)
    st.download_button(
        "Export Filtered Results (CSV)",
        filtered.to_csv(index=False).encode("utf-8"),
        "filtered_claims.csv",
        "text/csv",
    )


def render_suspicious_panel(data: dict) -> None:
    st.markdown("### Suspicious Claims Investigation")
    suspicious: pd.DataFrame = data["suspicious"]
    all_df: pd.DataFrame = data["all_claims"]

    inv_df = suspicious.copy()
    if inv_df.empty:
        inv_df = all_df[
            (all_df["is_suspicious"])
            | (all_df["claim_amount"] > SUSPICIOUS_THRESHOLD)
        ].copy()
        if not inv_df.empty and "fraud_flag" not in inv_df.columns:
            inv_df["fraud_flag"] = "SUSPICIOUS_HIGH_AMOUNT"
            inv_df["suspicion_reason"] = "Claim amount exceeds ₹200,000 threshold"

    if inv_df.empty:
        st.info(
            "No suspicious claims in `suspicious_claims_report.csv`. "
            "Claims exceeding ₹200,000 that were rejected appear in the Fraud Dashboard."
        )
        high = all_df[all_df["claim_amount"] > SUSPICIOUS_THRESHOLD] if not all_df.empty else pd.DataFrame()
        if not high.empty:
            st.markdown("#### High-Amount Claims for Review")
            st.dataframe(high, use_container_width=True, hide_index=True)
        return

    for label, color, icon in [
        ("High Risk", COLOR_REJECTED, "🔴"),
        ("Medium Risk", COLOR_SUSPICIOUS, "🟠"),
        ("Low Risk", COLOR_APPROVED, "🟢"),
    ]:
        subset = inv_df[inv_df["risk_label"] == label] if "risk_label" in inv_df.columns else pd.DataFrame()
        st.markdown(f"#### {icon} {label} ({len(subset)} claims)")

    display_cols = [
        c
        for c in [
            "claim_id",
            "policy_id",
            "claim_amount",
            "claim_date",
            "suspicion_reason",
            "fraud_flag",
            "risk_score",
            "risk_label",
            "status",
        ]
        if c in inv_df.columns
    ]
    st.dataframe(
        inv_df[display_cols].sort_values("risk_score", ascending=False)
        if "risk_score" in inv_df.columns
        else inv_df[display_cols],
        use_container_width=True,
        hide_index=True,
    )

    fig = px.scatter(
        inv_df,
        x="claim_amount",
        y="risk_score",
        color="risk_label" if "risk_label" in inv_df.columns else None,
        hover_name="claim_id",
        title="Risk Score vs Claim Amount",
        color_discrete_map={
            "High Risk": COLOR_REJECTED,
            "Medium Risk": COLOR_SUSPICIOUS,
            "Low Risk": COLOR_APPROVED,
        },
    )
    plotly_chart(fig)

    st.download_button(
        "Download Investigation Report",
        inv_df.to_csv(index=False).encode("utf-8"),
        "suspicious_investigation.csv",
        "text/csv",
    )


def render_summary_analytics(data: dict) -> None:
    st.markdown("### Summary Analytics")
    summary = data.get("summary", {})
    kpis = data.get("kpis") or compute_kpis(data)

    if not summary:
        st.warning("claim_summary.json not found.")
        return

    render_kpi_row(
        [
            ("Approved Claims", str(kpis["approved_claims"]), COLOR_APPROVED),
            ("Rejected Claims", str(kpis["rejected_claims"]), COLOR_REJECTED),
            ("Suspicious Claims", str(kpis["suspicious_claims"]), COLOR_SUSPICIOUS),
            ("Total Claims", str(kpis["total_claims"]), COLOR_POLICY),
        ]
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        plotly_chart(gauge_chart("Approval Rate", kpis["approval_rate"], color=COLOR_APPROVED))
    with col2:
        plotly_chart(gauge_chart("Rejection Rate", kpis["rejection_rate"], color=COLOR_REJECTED))
    with col3:
        plotly_chart(gauge_chart("Fraud Detection Rate", kpis["fraud_rate"], color=COLOR_SUSPICIOUS))

    breakdown = summary.get("rejection_breakdown", {})
    if breakdown:
        st.markdown("#### Rejection Breakdown")
        bd_df = pd.DataFrame(
            list(breakdown.items()), columns=["reason", "count"]
        )
        col_a, col_b = st.columns(2)
        with col_a:
            st.dataframe(bd_df, use_container_width=True, hide_index=True)
        with col_b:
            fig = px.bar(
                bd_df,
                x="reason",
                y="count",
                title="Rejections by Reason",
                color_discrete_sequence=[COLOR_REJECTED],
            )
            plotly_chart(fig)

    policy_summary = summary.get("policy_claim_summary", {})
    if policy_summary:
        st.markdown("#### Policy Claim Summary Table")
        rows = [{"policy_id": k, **v} for k, v in policy_summary.items()]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.download_button(
        "Download Summary JSON",
        pd.Series(summary).to_json(indent=2).encode("utf-8"),
        "claim_summary_export.json",
        "application/json",
    )
