# Insurance Claims & Fraud Detection Dashboard

## Overview

Streamlit analytics portal for insurance analysts and managers. It reads validation outputs and enriches them with policy master data for end-to-end monitoring.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the URL shown in the terminal (typically `http://localhost:8501`).

### Performance

- Data is cached in memory (Streamlit) and on disk (`.dashboard_cache/all_claims.parquet`).
- First load builds the cache (~1s); later loads and page switches are much faster.
- Use **Refresh Data** only after regenerating CSV/JSON reports.
- If startup still feels slow, that is mostly Streamlit/Plotly import time on first launch.

## Dashboard Sections

| Section | Purpose |
|---------|---------|
| **Executive Dashboard** | KPI cards, status pie chart, monthly trend, fraud alerts |
| **Policy & Claim Search** | Lookup by Policy ID, Claim ID, or Customer ID |
| **Fraud Detection** | Suspicious vs normal charts, amount ranges, top policies/customers, high-risk list |
| **Financial Analysis** | Distributions, approved vs rejected value, monthly trends, forecasting |
| **Policy Analytics** | Active/expired counts, coverage utilization, risk scoring |
| **Claims Management** | Filterable, sortable, paginated validated claims table with CSV export |
| **Suspicious Investigation** | Risk labels (High/Medium/Low), risk scores, investigation export |
| **Summary Analytics** | Gauges for approval/rejection/fraud rates, rejection breakdown |

## Data Sources

- `validated_claims_report.csv`
- `suspicious_claims_report.csv`
- `claim_summary.json`
- `insurance_policy_master.csv` (policy search & analytics)
- `insurance_claims.csv` (full claim lifecycle via validation engine)

## Color Coding

- Green — Approved claims
- Red — Rejected claims
- Orange — Suspicious / fraud
- Blue — Policy analytics

## Project Structure

```
app.py                 # Streamlit entry point
dashboard/
  data_loader.py       # Data loading & KPI computation
  ui_components.py     # KPI cards, charts, styling
  sections.py          # Page section renderers
```
