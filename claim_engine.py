"""Insurance Claim Validation & Fraud Detection Engine."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SUSPICIOUS_THRESHOLD = 200_000
DATE_FORMAT = "%Y-%m-%d"


@dataclass
class Policy:
    policy_id: str
    customer_id: str
    policy_type: str
    coverage_amount: float
    policy_status: str


@dataclass
class Claim:
    claim_id: str
    policy_id: str
    claim_amount: float
    claim_date: str
    claim_type: str


@dataclass
class ValidationResult:
    claim: Claim
    status: str
    rejection_reason: str | None
    approved_amount: float
    is_suspicious: bool
    coverage_amount: float | None
    policy_status: str | None


def load_policies(path: str | Path) -> dict[str, Policy]:
    policies: dict[str, Policy] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            policy = Policy(
                policy_id=row["policy_id"],
                customer_id=row["customer_id"],
                policy_type=row["policy_type"],
                coverage_amount=float(row["coverage_amount"]),
                policy_status=row["policy_status"],
            )
            policies[policy.policy_id] = policy
    return policies


def load_claims(path: str | Path) -> list[Claim]:
    claims: list[Claim] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            claims.append(
                Claim(
                    claim_id=row["claim_id"],
                    policy_id=row["policy_id"],
                    claim_amount=float(row["claim_amount"]),
                    claim_date=row["claim_date"],
                    claim_type=row["claim_type"],
                )
            )
    return claims


def is_valid_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, DATE_FORMAT)
        return True
    except ValueError:
        return False


def validate_claim(claim: Claim, policies: dict[str, Policy]) -> ValidationResult:
    policy = policies.get(claim.policy_id)
    if policy is None:
        return ValidationResult(
            claim=claim,
            status="REJECTED",
            rejection_reason="INVALID_POLICY",
            approved_amount=0.0,
            is_suspicious=False,
            coverage_amount=None,
            policy_status=None,
        )

    if policy.policy_status != "ACTIVE":
        return ValidationResult(
            claim=claim,
            status="REJECTED",
            rejection_reason="EXPIRED_POLICY",
            approved_amount=0.0,
            is_suspicious=False,
            coverage_amount=policy.coverage_amount,
            policy_status=policy.policy_status,
        )

    if not is_valid_date(claim.claim_date):
        return ValidationResult(
            claim=claim,
            status="REJECTED",
            rejection_reason="INVALID_DATE",
            approved_amount=0.0,
            is_suspicious=False,
            coverage_amount=policy.coverage_amount,
            policy_status=policy.policy_status,
        )

    if claim.claim_amount <= 0:
        return ValidationResult(
            claim=claim,
            status="REJECTED",
            rejection_reason="NEGATIVE_AMOUNT",
            approved_amount=0.0,
            is_suspicious=False,
            coverage_amount=policy.coverage_amount,
            policy_status=policy.policy_status,
        )

    if claim.claim_amount > policy.coverage_amount:
        return ValidationResult(
            claim=claim,
            status="REJECTED",
            rejection_reason="EXCEEDS_COVERAGE",
            approved_amount=0.0,
            is_suspicious=False,
            coverage_amount=policy.coverage_amount,
            policy_status=policy.policy_status,
        )

    is_suspicious = claim.claim_amount > SUSPICIOUS_THRESHOLD
    return ValidationResult(
        claim=claim,
        status="APPROVED",
        rejection_reason=None,
        approved_amount=claim.claim_amount,
        is_suspicious=is_suspicious,
        coverage_amount=policy.coverage_amount,
        policy_status=policy.policy_status,
    )


def process_claims(
    policies: dict[str, Policy], claims: list[Claim]
) -> list[ValidationResult]:
    return [validate_claim(claim, policies) for claim in claims]


def build_summary(results: list[ValidationResult]) -> dict[str, Any]:
    approved = [r for r in results if r.status == "APPROVED"]
    rejected = [r for r in results if r.status == "REJECTED"]
    suspicious = [r for r in approved if r.is_suspicious]

    rejection_breakdown: dict[str, int] = {}
    for r in rejected:
        reason = r.rejection_reason or "UNKNOWN"
        rejection_breakdown[reason] = rejection_breakdown.get(reason, 0) + 1

    policy_summary: dict[str, dict[str, Any]] = {}
    for r in results:
        pid = r.claim.policy_id
        if pid not in policy_summary:
            policy_summary[pid] = {
                "total_claims": 0,
                "approved_claims": 0,
                "rejected_claims": 0,
                "suspicious_claims": 0,
                "total_approved_amount": 0.0,
            }
        entry = policy_summary[pid]
        entry["total_claims"] += 1
        if r.status == "APPROVED":
            entry["approved_claims"] += 1
            entry["total_approved_amount"] += r.approved_amount
            if r.is_suspicious:
                entry["suspicious_claims"] += 1
        else:
            entry["rejected_claims"] += 1

    return {
        "total_claims": len(results),
        "approved_claims": len(approved),
        "rejected_claims": len(rejected),
        "suspicious_claims": len(suspicious),
        "total_approved_amount": sum(r.approved_amount for r in approved),
        "rejection_breakdown": rejection_breakdown,
        "policy_claim_summary": policy_summary,
    }


def _result_row(result: ValidationResult) -> dict[str, Any]:
    return {
        "claim_id": result.claim.claim_id,
        "policy_id": result.claim.policy_id,
        "claim_amount": result.claim.claim_amount,
        "claim_date": result.claim.claim_date,
        "claim_type": result.claim.claim_type,
        "status": result.status,
        "rejection_reason": result.rejection_reason or "",
        "approved_amount": result.approved_amount,
        "coverage_amount": result.coverage_amount if result.coverage_amount is not None else "",
        "policy_status": result.policy_status or "",
        "is_suspicious": result.is_suspicious,
    }


def write_validated_report(results: list[ValidationResult], path: str | Path) -> None:
    approved = [r for r in results if r.status == "APPROVED"]
    fieldnames = [
        "claim_id",
        "policy_id",
        "claim_amount",
        "claim_date",
        "claim_type",
        "status",
        "rejection_reason",
        "approved_amount",
        "coverage_amount",
        "policy_status",
        "is_suspicious",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in approved:
            writer.writerow(_result_row(result))


def write_suspicious_report(results: list[ValidationResult], path: str | Path) -> None:
    suspicious = [r for r in results if r.status == "APPROVED" and r.is_suspicious]
    fieldnames = [
        "claim_id",
        "policy_id",
        "claim_amount",
        "claim_date",
        "claim_type",
        "status",
        "approved_amount",
        "coverage_amount",
        "fraud_flag",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in suspicious:
            writer.writerow(
                {
                    "claim_id": result.claim.claim_id,
                    "policy_id": result.claim.policy_id,
                    "claim_amount": result.claim.claim_amount,
                    "claim_date": result.claim.claim_date,
                    "claim_type": result.claim.claim_type,
                    "status": result.status,
                    "approved_amount": result.approved_amount,
                    "coverage_amount": result.coverage_amount,
                    "fraud_flag": "SUSPICIOUS_HIGH_AMOUNT",
                }
            )


def write_summary(summary: dict[str, Any], path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def run_engine(
    policy_path: str | Path = "insurance_policy_master.csv",
    claims_path: str | Path = "insurance_claims.csv",
    validated_output: str | Path = "validated_claims_report.csv",
    suspicious_output: str | Path = "suspicious_claims_report.csv",
    summary_output: str | Path = "claim_summary.json",
) -> dict[str, Any]:
    policies = load_policies(policy_path)
    claims = load_claims(claims_path)
    results = process_claims(policies, claims)
    summary = build_summary(results)

    write_validated_report(results, validated_output)
    write_suspicious_report(results, suspicious_output)
    write_summary(summary, summary_output)

    return summary
