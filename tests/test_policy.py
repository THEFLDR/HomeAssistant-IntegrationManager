from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.integration_manager.models import ManagerError, utcnow, version
from custom_components.integration_manager.policy import allowed, validate_promotion


def documents(release):
    sandbox = {
        "schema_version": 1,
        "environment": "sandbox",
        "updated_at": utcnow(),
        "integrations": {
            "demo": {
                "release": release.identity(),
                "installed_version": release.version,
                "running_version": release.version,
                "state": "active",
                "restart_pending": False,
                "health": "healthy",
                "health_release_id": release.release_id,
                "health_at": utcnow(),
            }
        },
    }
    production = {
        "schema_version": 1,
        "environment": "production",
        "updated_at": utcnow(),
        "integrations": {
            "demo": {
                "repository": release.repository,
                "state": "not_installed",
                "owner_confirmed": True,
                "running_version": None,
                "restart_pending": False,
                "updated_at": utcnow(),
            }
        },
    }
    return sandbox, production


def test_channel_and_semver(bundle):
    rc, _, _ = bundle()
    stable = deepcopy(rc)
    stable.prerelease = False
    assert allowed(rc, "sandbox") and not allowed(stable, "sandbox")
    assert not allowed(rc, "production") and not allowed(stable, "production")
    stable.version, stable.tag = "1.0.0", "v1.0.0"
    assert allowed(stable, "production")
    assert version("0.10.0") > version("0.9.9")
    for invalid in ("0.1.0-rc.1", "01.2.3", "../v1", "1.0"):
        with pytest.raises(ManagerError):
            version(invalid)


def test_normal_promotion_and_explicit_bootstrap(bundle):
    release, _, _ = bundle(ver="1.0.0")
    sandbox, production = documents(release)
    validate_promotion(release, sandbox, production, "demo")
    with pytest.raises(ManagerError, match="production"):
        validate_promotion(release, sandbox, {}, "demo")
    production["integrations"] = {}
    with pytest.raises(ManagerError, match="Production"):
        validate_promotion(release, sandbox, production, "demo")


@pytest.mark.parametrize(
    "field,value",
    [
        ("health", "unknown"),
        ("health", "unhealthy"),
        ("running_version", "0.0.9"),
        ("restart_pending", True),
        ("state", "verifying"),
        ("health_release_id", 999),
        ("health_at", "2000-01-01T00:00:00+00:00"),
        ("release", {"sha256": "tampered"}),
    ],
)
def test_bad_sandbox_status_blocks(bundle, field, value):
    release, _, _ = bundle()
    sandbox, production = documents(release)
    sandbox["integrations"]["demo"][field] = value
    with pytest.raises(ManagerError, match="exact release"):
        validate_promotion(release, sandbox, production, "demo")


def test_stale_or_old_production_blocks(bundle):
    release, _, _ = bundle(ver="1.2.0")
    sandbox, production = documents(release)
    production["integrations"]["demo"] = {
        "repository": release.repository,
        "installed_version": "1.2.0",
        "running_version": "1.2.0",
        "state": "active",
        "restart_pending": False,
        "updated_at": utcnow(),
    }
    with pytest.raises(ManagerError, match="newer"):
        validate_promotion(release, sandbox, production, "demo")
    production["integrations"]["demo"]["running_version"] = "1.1.0"
    production["integrations"]["demo"]["installed_version"] = "1.1.0"
    validate_promotion(release, sandbox, production, "demo")
    production["updated_at"] = (datetime.now(UTC) - timedelta(hours=3)).isoformat()
    with pytest.raises(ManagerError, match="stale"):
        validate_promotion(release, sandbox, production, "demo")


def test_pre_one_promotion_needs_no_production_record_but_keeps_sandbox_gates(bundle):
    release, _, _ = bundle(ver="0.9.9")
    sandbox, _ = documents(release)
    validate_promotion(release, sandbox, {}, "demo")
    sandbox["integrations"]["demo"]["health"] = "unknown"
    with pytest.raises(ManagerError, match="exact release"):
        validate_promotion(release, sandbox, {}, "demo")
