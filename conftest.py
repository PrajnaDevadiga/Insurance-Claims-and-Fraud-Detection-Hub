"""Pytest hooks: verify coverage report artifacts after pytest-cov writes them."""

from pathlib import Path

import pytest

COVERAGE_REPORT_DIR = Path(__file__).resolve().parent / "coverage_report"


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    """After pytest-cov emits reports, ensure HTML/XML coverage outputs exist."""
    html_report = COVERAGE_REPORT_DIR / "index.html"
    xml_report = COVERAGE_REPORT_DIR / "coverage.xml"

    assert html_report.exists(), (
        f"Missing HTML coverage report at {html_report}. "
        "Run: pytest (configured in pytest.ini)."
    )
    assert xml_report.exists(), (
        f"Missing XML coverage report at {xml_report}."
    )


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print coverage report locations."""
    html_report = COVERAGE_REPORT_DIR / "index.html"
    if html_report.exists():
        terminalreporter.write_line(
            f"Coverage HTML report: {html_report.resolve()}"
        )
        terminalreporter.write_line(
            f"Coverage XML report:  {(COVERAGE_REPORT_DIR / 'coverage.xml').resolve()}"
        )
