"""Load and enrich insurance claim data for the Streamlit dashboard."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SUSPICIOUS_THRESHOLD = 200_000
BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / ".dashboard_cache"
CACHE_FILE = CACHE_DIR / "all_claims.parquet"
CACHE_META = CACHE_DIR / "cache_meta.json"

_SOURCE_FILES = (
    "insurance_claims.csv",
    "insurance_policy_master.csv",
    "validated_claims_report.csv",
    "claim_summary.json",
)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def source_cache_key(base_dir: Path | None = None) -> str:
    """Fingerprint of source files for Streamlit cache invalidation."""
    root = base_dir or BASE_DIR
    parts = []
    for name in _SOURCE_FILES:
        path = root / name
        if path.exists():
            stat = path.stat()
            parts.append(f"{name}:{stat.st_mtime_ns}:{stat.st_size}")
        else:
            parts.append(f"{name}:missing")
    return "|".join(parts)


def _disk_meta(root: Path) -> dict:
    return {name: (root / name).stat().st_mtime for name in _SOURCE_FILES if (root / name).exists()}


def _disk_cache_valid(root: Path) -> bool:
    if not CACHE_FILE.exists() or not CACHE_META.exists():
        return False
    try:
        with open(CACHE_META, encoding="utf-8") as f:
            saved = json.load(f)
        return saved == _disk_meta(root)
    except (json.JSONDecodeError, OSError):
        return False


def _save_disk_cache(df: pd.DataFrame, root: Path) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CACHE_FILE, index=False)
    with open(CACHE_META, "w", encoding="utf-8") as f:
        json.dump(_disk_meta(root), f)


def _vectorized_risk_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add risk_label, risk_score, fraud_status without row-wise apply."""
    df = df.copy()
    amount = df["claim_amount"].astype(float)
    is_suspicious = df["is_suspicious"].fillna(False).astype(bool)
    status = df["status"].astype(str)

    score = np.full(len(df), 10.0)
    score = np.where(amount > SUSPICIOUS_THRESHOLD, 92.0, score)
    score = np.where(
        (amount <= SUSPICIOUS_THRESHOLD) & (is_suspicious | (amount > 150_000)),
        65.0,
        score,
    )
    score = np.where(
        (score == 10.0) & (amount > 100_000),
        40.0,
        score,
    )
    score = np.where(
        (score == 10.0) & (status == "REJECTED") & (amount > SUSPICIOUS_THRESHOLD),
        85.0,
        score,
    )
    score = np.where(
        (score == 10.0) & (status == "REJECTED"),
        25.0,
        score,
    )

    df["risk_score"] = score
    df["risk_label"] = np.select(
        [score >= 75, score >= 45],
        ["High Risk", "Medium Risk"],
        default="Low Risk",
    )
    df["fraud_status"] = np.where(
        is_suspicious | (amount > SUSPICIOUS_THRESHOLD),
        "Suspicious",
        "Normal",
    )
    return df


def build_full_claims_df(base_dir: Path | None = None) -> pd.DataFrame:
    """Build unified claims dataset using vectorized CSV merge (fast path)."""
    root = base_dir or BASE_DIR

    if _disk_cache_valid(root):
        return pd.read_parquet(CACHE_FILE)

    claims = _read_csv(root / "insurance_claims.csv")
    policies = _read_csv(root / "insurance_policy_master.csv")
    if claims.empty:
        return pd.DataFrame()

    df = claims.merge(policies, on="policy_id", how="left")

    parsed_dates = pd.to_datetime(df["claim_date"], format="%Y-%m-%d", errors="coerce")
    invalid_policy = df["policy_status"].isna()
    expired = df["policy_status"].eq("EXPIRED")
    invalid_date = parsed_dates.isna()
    negative = df["claim_amount"] <= 0
    exceeds = df["claim_amount"] > df["coverage_amount"]

    df["rejection_reason"] = np.select(
        [invalid_policy, expired, invalid_date, negative, exceeds],
        [
            "INVALID_POLICY",
            "EXPIRED_POLICY",
            "INVALID_DATE",
            "NEGATIVE_AMOUNT",
            "EXCEEDS_COVERAGE",
        ],
        default="",
    )
    df["status"] = np.where(df["rejection_reason"] == "", "APPROVED", "REJECTED")
    df["approved_amount"] = np.where(df["status"] == "APPROVED", df["claim_amount"], 0.0)
    df["is_suspicious"] = (df["status"] == "APPROVED") & (
        df["claim_amount"] > SUSPICIOUS_THRESHOLD
    )
    df["fraud_flag"] = np.select(
        [df["is_suspicious"], df["claim_amount"] > SUSPICIOUS_THRESHOLD],
        ["SUSPICIOUS_HIGH_AMOUNT", "HIGH_AMOUNT_ALERT"],
        default="",
    )
    df["suspicion_reason"] = np.where(
        df["claim_amount"] > SUSPICIOUS_THRESHOLD,
        "Claim amount exceeds ₹200,000 threshold",
        "",
    )
    df["claim_date"] = parsed_dates
    df["claim_month"] = df["claim_date"].dt.to_period("M").astype(str)

    keep_cols = [
        "claim_id",
        "policy_id",
        "customer_id",
        "policy_type",
        "claim_amount",
        "claim_date",
        "claim_type",
        "status",
        "rejection_reason",
        "approved_amount",
        "coverage_amount",
        "policy_status",
        "is_suspicious",
        "fraud_flag",
        "suspicion_reason",
        "claim_month",
    ]
    out = df[[c for c in keep_cols if c in df.columns]].copy()
    out = _vectorized_risk_columns(out)

    _save_disk_cache(out, root)
    return out


def compute_kpis(data: dict) -> dict:
    """Compute executive KPI metrics (prefer precomputed cache on data dict)."""
    if "kpis" in data:
        return data["kpis"]

    summary = data.get("summary", {})
    all_df: pd.DataFrame = data.get("all_claims", pd.DataFrame())
    policies: pd.DataFrame = data.get("policies", pd.DataFrame())

    total_policies = len(policies) if not policies.empty else 0
    total_claims = int(summary.get("total_claims", len(all_df)))
    approved = int(summary.get("approved_claims", 0))
    rejected = int(summary.get("rejected_claims", 0))
    suspicious = int(summary.get("suspicious_claims", 0))

    if not all_df.empty:
        suspicious = int(
            ((all_df["status"] == "APPROVED") & all_df["is_suspicious"]).sum()
            or suspicious
        )
        approved_amt = float(
            all_df.loc[all_df["status"] == "APPROVED", "approved_amount"].sum()
        )
        rejected_amt = float(
            all_df.loc[all_df["status"] == "REJECTED", "claim_amount"].sum()
        )
        avg_claim = float(all_df["claim_amount"].mean())
    else:
        approved_amt = float(summary.get("total_approved_amount", 0))
        rejected_amt = 0.0
        avg_claim = 0.0

    return {
        "total_policies": total_policies,
        "total_claims": total_claims,
        "approved_claims": approved,
        "rejected_claims": rejected,
        "suspicious_claims": suspicious,
        "total_approved_amount": approved_amt,
        "total_rejected_amount": rejected_amt,
        "average_claim_amount": avg_claim,
        "approval_rate": (approved / total_claims * 100) if total_claims else 0,
        "rejection_rate": (rejected / total_claims * 100) if total_claims else 0,
        "fraud_rate": (suspicious / total_claims * 100) if total_claims else 0,
    }


def load_dashboard_data(base_dir: Path | None = None) -> dict:
    """Load all data sources used by the dashboard."""
    root = base_dir or BASE_DIR

    policies_df = _read_csv(root / "insurance_policy_master.csv")
    validated_df = _read_csv(root / "validated_claims_report.csv")
    suspicious_df = _read_csv(root / "suspicious_claims_report.csv")
    summary = _read_json(root / "claim_summary.json")
    all_claims_df = build_full_claims_df(root)

    if not policies_df.empty:
        policies_df["customer_name"] = policies_df["customer_id"]

    if not validated_df.empty and "claim_date" in validated_df.columns:
        validated_df["claim_date"] = pd.to_datetime(
            validated_df["claim_date"], errors="coerce"
        )

    if suspicious_df.empty and not all_claims_df.empty:
        suspicious_df = all_claims_df[
            (all_claims_df["status"] == "APPROVED") & all_claims_df["is_suspicious"]
        ].copy()
        if not suspicious_df.empty:
            suspicious_df["fraud_flag"] = "SUSPICIOUS_HIGH_AMOUNT"

    if not suspicious_df.empty and "risk_score" not in suspicious_df.columns:
        suspicious_df = _vectorized_risk_columns(suspicious_df.copy())
        suspicious_df["suspicion_reason"] = "Claim amount exceeds ₹200,000 threshold"

    high_risk_df = (
        all_claims_df[all_claims_df["claim_amount"] > SUSPICIOUS_THRESHOLD].copy()
        if not all_claims_df.empty
        else pd.DataFrame()
    )

    payload = {
        "policies": policies_df,
        "validated": validated_df,
        "suspicious": suspicious_df,
        "summary": summary,
        "all_claims": all_claims_df,
        "high_risk": high_risk_df,
    }
    payload["kpis"] = compute_kpis(payload)
    payload["aggregates"] = _precompute_aggregates(all_claims_df)
    return payload


def _precompute_aggregates(all_df: pd.DataFrame) -> dict:
    """Pre-aggregate chart data once to avoid repeated groupby on each UI rerun."""
    if all_df.empty:
        return {}

    valid = all_df.dropna(subset=["claim_date"])
    monthly = valid.groupby("claim_month", as_index=False).agg(
        claims=("claim_id", "count"),
        amount=("claim_amount", "sum"),
    )
    return {
        "status_counts": all_df["status"].value_counts().reset_index(name="count"),
        "fraud_counts": all_df["fraud_status"].value_counts().reset_index(name="count"),
        "monthly": monthly,
        "amount_ranges": all_df.assign(
            amount_range=all_df["claim_amount"].map(
                lambda a: (
                    "₹0 – ₹50K"
                    if a <= 50_000
                    else "₹50K – ₹1L"
                    if a <= 100_000
                    else "₹1L – ₹2L"
                    if a <= 200_000
                    else "₹2L+"
                )
            )
        )
        .groupby("amount_range", as_index=False)
        .size()
        .rename(columns={"size": "count"}),
    }
