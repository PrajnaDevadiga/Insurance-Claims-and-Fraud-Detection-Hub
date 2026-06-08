"""Run the Insurance Claim Validation & Fraud Detection Engine."""

from claim_engine import run_engine


if __name__ == "__main__":
    summary = run_engine()
    print("Processing complete.")
    print(f"  Total claims:    {summary['total_claims']}")
    print(f"  Approved:        {summary['approved_claims']}")
    print(f"  Rejected:        {summary['rejected_claims']}")
    print(f"  Suspicious:      {summary['suspicious_claims']}")
    print(f"  Approved amount: {summary['total_approved_amount']}")
