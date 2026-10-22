"""Fail-closed environment and promotion rules, shared with GitHub Actions."""

from .const import HEALTH_MAX_AGE, STATUS_MAX_AGE
from .models import ManagerError, Release, fresh, version


def status_entry(document: dict, environment: str, domain: str) -> dict:
    if not isinstance(document, dict) or (
        document.get("schema_version") != 1 or document.get("environment") != environment
    ):
        raise ManagerError(f"Invalid {environment} status schema")
    if not fresh(document.get("updated_at"), STATUS_MAX_AGE.total_seconds()):
        raise ManagerError(f"Missing or stale {environment} status")
    integrations = document.get("integrations", {})
    if not isinstance(integrations, dict) or not isinstance(integrations.get(domain, {}), dict):
        raise ManagerError(f"Invalid {environment} integrations status")
    return integrations.get(domain, {})


def allowed(release: Release, environment: str) -> bool:
    if environment == "sandbox":
        return release.prerelease
    if environment == "production":
        return not release.prerelease and version(release.version) >= (1, 0, 0)
    return False


def validate_promotion(release: Release, sandbox: dict, production: dict, domain: str) -> None:
    """Revalidate authenticated status, exact identity, freshness and activation."""
    if not release.immutable:
        raise ManagerError("Release must be immutable")
    version(release.version)
    status = status_entry(sandbox, "sandbox", domain)
    identity = status.get("release")
    if isinstance(identity, dict):
        identity = dict(identity)
        if isinstance(identity.get("repository"), str):
            identity["repository"] = identity["repository"].lower()
    if (
        identity != release.identity()
        or status.get("installed_version") != release.version
        or status.get("running_version") != release.version
        or status.get("state") != "active"
        or status.get("restart_pending") is not False
        or status.get("health") != "healthy"
        or status.get("health_release_id") != release.release_id
        or not fresh(status.get("health_at"), HEALTH_MAX_AGE.total_seconds())
    ):
        raise ManagerError("Sandbox must be active and healthy for this exact release and artifact")
    validate_production(release, production, domain)


def validate_production(release: Release, production: dict, domain: str) -> None:
    """Production version safety starts at the first Production release, including overrides."""
    if version(release.version) < (1, 0, 0):
        return
    prod = status_entry(production, "production", domain)
    if (
        not isinstance(prod.get("repository"), str)
        or prod["repository"].lower() != release.repository
    ):
        raise ManagerError("Production repository mapping is missing or inconsistent")
    if not fresh(prod.get("updated_at"), STATUS_MAX_AGE.total_seconds()):
        raise ManagerError("Missing or stale Production integration status")
    if (
        prod.get("state") == "not_installed"
        and prod.get("owner_confirmed") is True
        and prod.get("installed_version") is None
        and prod.get("release") is None
        and not prod.get("running_version")
        and prod.get("restart_pending") is False
    ):
        return
    if (
        not prod.get("running_version")
        or prod.get("state") != "active"
        or prod.get("installed_version") != prod.get("running_version")
        or prod.get("restart_pending") is not False
    ):
        raise ManagerError("Production is unknown; owner must explicitly confirm initial absence")
    if version(release.version) <= version(prod["running_version"]):
        raise ManagerError("Release must be newer than Production")
