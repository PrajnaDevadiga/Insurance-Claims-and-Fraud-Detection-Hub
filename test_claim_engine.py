"""Tests for Insurance Claim Validation & Fraud Detection Engine."""

import csv
import json
import tempfile
from pathlib import Path

import pytest

from claim_engine import (
    Claim,
    Policy,
    build_summary,
    is_valid_date,
    load_claims,
    load_policies,
    process_claims,
    run_engine,
    validate_claim,
    write_suspicious_report,
    write_validated_report,
)

@pytest.fixture
def sample_policies() -> dict[str, Policy]:
    return {
        "POL001": Policy("POL001", "CUST001", "HEALTH", 105000, "ACTIVE"),
        "POL007": Policy("POL007", "CUST007", "HEALTH", 135000, "EXPIRED"),
        "POL017": Policy("POL017", "CUST017", "HOME", 185000, "ACTIVE"),
        "POL022": Policy("POL022", "CUST022", "HEALTH", 210000, "ACTIVE"),
    }


def test_invalid_policy_rejected(sample_policies):
    claim = Claim("CLM006", "POL999", 9500, "2025-06-07", "MEDICAL")
    result = validate_claim(claim, sample_policies)
    assert result.status == "REJECTED"
    assert result.rejection_reason == "INVALID_POLICY"
    assert result.approved_amount == 0.0


def test_expired_policy_rejected(sample_policies):
    claim = Claim("CLM036", "POL007", 32000, "2025-06-09", "ACCIDENT")
    result = validate_claim(claim, sample_policies)
    assert result.status == "REJECTED"
    assert result.rejection_reason == "EXPIRED_POLICY"
    assert result.approved_amount == 0.0


def test_invalid_date_rejected(sample_policies):
    claim = Claim("CLM016", "POL017", 17000, "invalid_date", "ACCIDENT")
    result = validate_claim(claim, sample_policies)
    assert result.status == "REJECTED"
    assert result.rejection_reason == "INVALID_DATE"
    assert result.approved_amount == 0.0


def test_negative_claim_amount_rejected(sample_policies):
    claim = Claim("CLM011", "POL012", -1000, "2025-06-12", "FIRE")
    policies = {
        **sample_policies,
        "POL012": Policy("POL012", "CUST012", "AUTO", 160000, "ACTIVE"),
    }
    result = validate_claim(claim, policies)
    assert result.status == "REJECTED"
    assert result.rejection_reason == "NEGATIVE_AMOUNT"
    assert result.approved_amount == 0.0


def test_claim_exceeding_coverage_rejected(sample_policies):
    claim = Claim("CLM021", "POL022", 500000, "2025-06-22", "THEFT")
    result = validate_claim(claim, sample_policies)
    assert result.status == "REJECTED"
    assert result.rejection_reason == "EXCEEDS_COVERAGE"
    assert result.approved_amount == 0.0


def test_suspicious_claim_detection(sample_policies):
    claim = Claim("CLM_SUSP", "POL022", 205000, "2025-06-22", "THEFT")
    result = validate_claim(claim, sample_policies)
    assert result.status == "APPROVED"
    assert result.is_suspicious is True
    assert result.approved_amount == 205000


def test_approved_claim_calculation(sample_policies):
    claim = Claim("CLM001", "POL001", 5750, "2025-06-02", "THEFT")
    result = validate_claim(claim, sample_policies)
    assert result.status == "APPROVED"
    assert result.approved_amount == 5750
    assert result.is_suspicious is False
    assert result.rejection_reason is None


def test_policy_claim_summary():
    policies = {
        "POL001": Policy("POL001", "CUST001", "HEALTH", 105000, "ACTIVE"),
        "POL002": Policy("POL002", "CUST002", "HOME", 110000, "ACTIVE"),
        "POL022": Policy("POL022", "CUST022", "HEALTH", 210000, "ACTIVE"),
    }
    claims = [
        Claim("CLM001", "POL001", 5000, "2025-06-01", "MEDICAL"),
        Claim("CLM002", "POL001", 3000, "2025-06-02", "FIRE"),
        Claim("CLM003", "POL002", -100, "2025-06-03", "THEFT"),
        Claim("CLM_SUSP", "POL022", 205000, "2025-06-22", "THEFT"),
    ]
    results = process_claims(policies, claims)
    summary = build_summary(results)

    assert summary["total_claims"] == 4
    assert summary["approved_claims"] == 3
    assert summary["rejected_claims"] == 1
    assert summary["suspicious_claims"] == 1
    assert summary["total_approved_amount"] == 213000

    pol001 = summary["policy_claim_summary"]["POL001"]
    assert pol001["total_claims"] == 2
    assert pol001["approved_claims"] == 2
    assert pol001["rejected_claims"] == 0
    assert pol001["suspicious_claims"] == 0
    assert pol001["total_approved_amount"] == 8000

    pol022 = summary["policy_claim_summary"]["POL022"]
    assert pol022["suspicious_claims"] == 1

    pol002 = summary["policy_claim_summary"]["POL002"]
    assert pol002["total_claims"] == 1
    assert pol002["approved_claims"] == 0
    assert pol002["rejected_claims"] == 1


def test_is_valid_date():
    assert is_valid_date("2025-06-15") is True
    assert is_valid_date("not-a-date") is False


def test_load_policies_and_claims_from_csv():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        policy_file = tmp_path / "policies.csv"
        claims_file = tmp_path / "claims.csv"
        policy_file.write_text(
            "policy_id,customer_id,policy_type,coverage_amount,policy_status\n"
            "POL001,CUST001,HEALTH,105000,ACTIVE\n",
            encoding="utf-8",
        )
        claims_file.write_text(
            "claim_id,policy_id,claim_amount,claim_date,claim_type\n"
            "CLM001,POL001,5000,2025-06-01,MEDICAL\n",
            encoding="utf-8",
        )
        policies = load_policies(policy_file)
        claims = load_claims(claims_file)
        assert len(policies) == 1
        assert policies["POL001"].coverage_amount == 105000
        assert len(claims) == 1
        assert claims[0].claim_id == "CLM001"


def test_write_suspicious_report():
    policies = {"POL022": Policy("POL022", "CUST022", "HEALTH", 210000, "ACTIVE")}
    claim = Claim("CLM_SUSP", "POL022", 205000, "2025-06-22", "THEFT")
    results = process_claims(policies, [claim])

    with tempfile.TemporaryDirectory() as tmp:
        report_path = Path(tmp) / "suspicious.csv"
        write_suspicious_report(results, report_path)
        with open(report_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["fraud_flag"] == "SUSPICIOUS_HIGH_AMOUNT"
        assert float(rows[0]["claim_amount"]) == 205000


def test_write_validated_report():
    policies = {"POL001": Policy("POL001", "CUST001", "HEALTH", 105000, "ACTIVE")}
    claim = Claim("CLM001", "POL001", 5000, "2025-06-01", "MEDICAL")
    results = process_claims(policies, [claim])

    with tempfile.TemporaryDirectory() as tmp:
        report_path = Path(tmp) / "validated.csv"
        write_validated_report(results, report_path)
        with open(report_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["status"] == "APPROVED"
        assert float(rows[0]["approved_amount"]) == 5000


def test_run_engine_integration():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        policy_file = tmp_path / "policies.csv"
        claims_file = tmp_path / "claims.csv"
        policy_file.write_text(
            "policy_id,customer_id,policy_type,coverage_amount,policy_status\n"
            "POL001,CUST001,HEALTH,105000,ACTIVE\n"
            "POL007,CUST007,HEALTH,135000,EXPIRED\n",
            encoding="utf-8",
        )
        claims_file.write_text(
            "claim_id,policy_id,claim_amount,claim_date,claim_type\n"
            "CLM001,POL001,5000,2025-06-01,MEDICAL\n"
            "CLM002,POL999,1000,2025-06-02,FIRE\n"
            "CLM003,POL007,2000,2025-06-03,ACCIDENT\n",
            encoding="utf-8",
        )

        summary = run_engine(
            policy_path=policy_file,
            claims_path=claims_file,
            validated_output=tmp_path / "validated.csv",
            suspicious_output=tmp_path / "suspicious.csv",
            summary_output=tmp_path / "summary.json",
        )

        assert summary["approved_claims"] == 1
        assert summary["rejected_claims"] == 2

        with open(tmp_path / "summary.json", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["total_claims"] == 3
