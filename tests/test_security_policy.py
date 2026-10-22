from datetime import date

import pytest

from scripts.audit_dependencies import evaluate


def test_exceptions_are_specific_and_expire():
    policy = {
        "schema_version": 1,
        "expires_on": "2026-11-04",
        "exceptions": [{"package": "pillow", "version": "12.3.0", "id": "CVE-known"}],
    }
    report = {
        "dependencies": [
            {
                "name": "pillow",
                "version": "12.3.0",
                "vulns": [{"id": "GHSA-alias", "aliases": ["CVE-known"]}],
            }
        ]
    }
    accepted, rejected = evaluate(report, policy, date(2026, 10, 21))
    assert len(accepted) == 1 and not rejected
    report["dependencies"][0]["vulns"].append({"id": "CVE-new"})
    assert len(evaluate(report, policy, date(2026, 10, 21))[1]) == 1
    report["dependencies"][0]["version"] = "12.3.1"
    assert len(evaluate(report, policy, date(2026, 10, 21))[1]) == 2
    with pytest.raises(ValueError, match="expired"):
        evaluate(report, policy, date(2026, 11, 4))
    with pytest.raises(ValueError, match="Production"):
        evaluate(report, policy, date(2026, 10, 21), "1.0.0")
