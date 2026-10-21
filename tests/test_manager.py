from dataclasses import asdict
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.integration_manager.artifacts import fingerprints, inspect_package
from custom_components.integration_manager.const import DOMAIN
from custom_components.integration_manager.models import ManagerError
from custom_components.integration_manager.update import IntegrationUpdate


async def test_register_install_restart_health_and_uninstall(manager, github, bundle, loaded):
    release, metadata, data = bundle()
    github.add((release, metadata, data))
    await manager.register(release.repository, "demo", True)
    record = manager.get("demo")
    assert record.available.version == "0.1.0"
    entity = IntegrationUpdate(manager, "demo")
    assert entity.latest_version == "0.1.0"
    states = []
    manager.listen(lambda: states.append(record.state))
    await entity.async_install(None, False)
    assert states.index("downloaded") < states.index("installed") < states.index("pending_restart")
    assert record.state == "pending_restart" and record.running_version is None
    assert record.status()["health"] == "unknown"
    with pytest.raises(ManagerError, match="activated"):
        await manager.report_health(
            "demo", "healthy", release.version, release.release_id, release.sha256
        )
    with loaded("demo", release.version):
        await manager.verify()
        assert record.state == "pending_restart"  # Config reload is not an HA restart.
        record.install_boot = "previous-process"
        await manager.verify()
        assert record.state == "verifying"
        await manager.report_health(
            "demo", "healthy", release.version, release.release_id, release.sha256
        )
        assert record.state == "active" and record.status()["health"] == "healthy"
        await manager.check()
        assert record.health == "healthy"  # Update checks must not blank valid health.
        assert github.statuses["sandbox"]["integrations"]["demo"]["running_version"] == "0.1.0"
    await manager.uninstall("demo", "uninstall demo")
    assert "demo" not in manager.records
    assert not (manager.installer.components / "demo").exists()
    assert github.statuses["sandbox"]["integrations"]["demo"]["state"] == "not_installed"


async def test_existing_unmanaged_install_is_never_overwritten(manager, github, bundle):
    b = bundle()
    github.add(b)
    await manager.register(b[0].repository, "demo", True)
    target = manager.installer.components / "demo"
    target.mkdir(parents=True)
    (target / "user-file").write_text("preserve")
    with pytest.raises(ManagerError, match="adoption"):
        await manager.install("demo")
    assert (target / "user-file").read_text() == "preserve"


async def test_integrity_failure_and_network_recovery(manager, github, bundle):
    b = bundle()
    github.add(b)
    await manager.register(b[0].repository, "demo", True)
    original_asset = github.asset
    github.asset = AsyncMock(return_value=b"corrupt")
    with pytest.raises(ManagerError, match="SHA-256"):
        await manager.install("demo")
    assert not (manager.installer.components / "demo").exists()
    github.asset = original_asset
    await manager.install("demo")
    assert manager.get("demo").state == "pending_restart"
    github.validate.side_effect = ManagerError("GitHub temporarily unavailable")
    await manager.check()
    assert manager.get("demo").installed.version == "0.1.0"
    assert manager.error == "GitHub temporarily unavailable"
    github.validate.side_effect = None
    await manager.check()
    assert manager.error is None


async def test_production_only_offers_stable_at_least_one(manager, github, bundle):
    github.add(bundle(ver="0.9.0", prerelease=False))
    github.add(bundle(ver="1.0.0", prerelease=False, rid=11))
    github.add(bundle(ver="1.1.0", prerelease=True, rid=12))
    manager.environment = (
        "production"  # Tests business policy without enabling 0.x production setup.
    )
    await manager.register("THEFLDR/demo", "demo", True)
    assert manager.get("demo").available.version == "1.0.0"
    await manager.install("demo")
    assert manager.get("demo").installed.version == "1.0.0"


async def test_promotion_dispatch_and_missing_production_bootstrap(manager, github, bundle, loaded):
    b = bundle()
    github.add(b)
    await manager.register(b[0].repository, "demo", True)
    await manager.install("demo")
    record = manager.get("demo")
    record.install_boot = "previous-process"
    with loaded("demo", record.installed.version):
        await manager.report_health(
            "demo",
            "healthy",
            record.installed.version,
            record.installed.release_id,
            record.installed.sha256,
        )
        with pytest.raises(ManagerError, match="production"):
            await manager.promote("demo")
        await manager.confirm_absent("demo", "production has not installed demo")
        assert manager.snapshot()["integrations"][1]["promotion_eligible"]
        with patch.object(manager, "_watch"):
            await manager.promote("demo")
        args = github.dispatch.call_args.args
        assert args[1] == "promote.yml"
        assert args[2]["sha256"] == record.installed.sha256
        assert record.promotion["state"] == "dispatched"


async def test_status_ownership_and_single_writer(manager, github):
    github.statuses["sandbox"] = {"instance_id": "another-instance"}
    await manager.heartbeat()
    assert "Another instance" in manager.error
    assert not github.writes


async def test_manager_verified_adoption_and_self_update(manager, github, bundle, loaded):
    b = bundle(domain=DOMAIN, repo=manager.registry)
    github.add(b)
    target = manager.installer.components / DOMAIN
    target.mkdir(parents=True)
    for name, content in inspect_package(b[2], b[1]).items():
        (target / name).write_bytes(content)
    with loaded(DOMAIN, "0.1.0"):
        await manager.check()
        await manager.install(DOMAIN, adopt=True)
        assert manager.get(DOMAIN).health == "healthy"
        next_bundle = bundle(domain=DOMAIN, ver="0.1.1", repo=manager.registry, rid=11)
        github.add(next_bundle)
        await manager.check()
        await manager.install(DOMAIN)
        assert manager.get(DOMAIN).running_version == "0.1.0"
        assert manager.get(DOMAIN).installed.version == "0.1.1"
        assert manager.get(DOMAIN).state == "pending_restart"
        assert manager.get(DOMAIN).health != "healthy"
    manager.get(DOMAIN).install_boot = "previous-process"
    with loaded(DOMAIN, "0.1.1"):
        await manager.heartbeat()
        assert manager.get(DOMAIN).health == "healthy"
        assert manager.get(DOMAIN).state == "active"


async def test_stale_health_and_disk_tampering_fail_closed(manager, github, bundle, loaded):
    b = bundle()
    github.add(b)
    await manager.register(b[0].repository, "demo", True)
    await manager.install("demo")
    record = manager.get("demo")
    record.install_boot = "previous-process"
    with loaded("demo", "0.1.0"):
        await manager.report_health("demo", "healthy", "0.1.0", b[0].release_id, b[0].sha256)
        record.health_at = "2000-01-01T00:00:00+00:00"
        assert record.status()["health"] == "unknown"
        (manager.installer.components / "demo/__init__.py").write_text("tampered")
        await manager.verify()
        assert record.state == "error" and record.health == "unhealthy"


async def test_registry_invalidation_must_succeed_before_any_file_change(manager, github, bundle):
    b = bundle()
    github.add(b)
    await manager.register(b[0].repository, "demo", True)
    github.write_status = AsyncMock(side_effect=ManagerError("registry write unavailable"))
    with pytest.raises(ManagerError, match="registry write unavailable"):
        await manager.install("demo")
    assert not (manager.installer.components / "demo").exists()
    assert manager.get("demo").installed is None


async def test_crash_after_swap_reconciles_pending_identity(manager, github, bundle):
    b = bundle()
    github.add(b)
    await manager.register(b[0].repository, "demo", True)
    record = manager.get("demo")
    files = inspect_package(b[2], b[1])
    record.pending = {
        "release": asdict(b[0]),
        "files": fingerprints(files),
        "boot": "previous-process",
    }
    record.state = "downloaded"
    await manager.save()
    await manager.hass.async_add_executor_job(manager.installer.install, "demo", files, False)
    await manager.load()
    recovered = manager.get("demo")
    assert recovered.installed.identity() == b[0].identity()
    assert recovered.pending is None and recovered.health == "unknown"
    assert recovered.state == "verifying"


async def test_specific_rc_selection_and_no_silent_downgrade(manager, github, bundle):
    github.add(bundle(ver="0.1.0"))
    github.add(bundle(ver="0.2.0", rid=11))
    await manager.register("THEFLDR/demo", "demo", True)
    assert manager.get("demo").available.version == "0.2.0"
    await manager.install("demo", target_version="0.1.0")
    assert manager.get("demo").installed.version == "0.1.0"
    with pytest.raises(ManagerError, match="Restart"):
        await manager.install("demo", target_version="0.2.0")


async def test_sandbox_cannot_overwrite_owned_production_registry(manager, github, bundle):
    github.add(bundle())
    await manager.register("THEFLDR/demo", "demo", True)
    github.statuses["production"] = {"instance_id": "actual-production", "integrations": {}}
    with pytest.raises(ManagerError, match="Production owns"):
        await manager.confirm_absent("demo", "production has not installed demo")
    assert github.statuses["production"] == {"instance_id": "actual-production", "integrations": {}}


async def test_production_confirms_own_absence_and_detects_unmanaged_code(
    manager, github, bundle, loaded
):
    github.add(bundle(ver="1.0.0", prerelease=False))
    manager.environment = "production"
    await manager.register("THEFLDR/demo", "demo", True)
    await manager.confirm_absent("demo", "production has not installed demo")
    assert github.statuses["production"]["integrations"]["demo"]["owner_confirmed"]
    with loaded("demo", "1.0.0"):
        await manager.verify()
        assert not manager.get("demo").absence_confirmed
        assert manager.get("demo").state == "unmanaged"


@pytest.mark.parametrize("conclusion,expected", [("success", "succeeded"), ("failure", "failed")])
async def test_promotion_result_is_audited_and_verified(
    manager, github, bundle, conclusion, expected
):
    b = bundle()
    github.add(b)
    await manager.register(b[0].repository, "demo", True)
    await manager.install("demo")
    record = manager.get("demo")
    record.promotion = {"state": "dispatched", "request_id": "request", "release": asdict(b[0])}
    b[0].prerelease = False
    original_request = github.request

    async def request(method, path, **kwargs):
        if "promote.yml/runs" in path:
            return {
                "workflow_runs": [
                    {
                        "display_title": "promote-request",
                        "status": "completed",
                        "conclusion": conclusion,
                        "html_url": "https://github.com/THEFLDR/demo/actions/runs/123",
                    }
                ]
            }
        return await original_request(method, path, **kwargs)

    github.request = request
    with patch("custom_components.integration_manager.manager.asyncio.sleep", new=AsyncMock()):
        await manager._watch_promotion("demo", "request")
    assert record.promotion["state"] == expected
    assert record.promotion["url"].endswith("/runs/123")
    if expected == "succeeded":
        assert record.installed.prerelease is False and record.available is None


@pytest.mark.parametrize("files_reappear", [False, True])
async def test_absence_tombstone_never_confirms_unmanaged_files(
    manager, github, bundle, files_reappear
):
    github.add(bundle())
    manager.environment = "production"
    await manager.register("THEFLDR/demo", "demo", True)
    target = manager.installer.components / "demo"
    if not files_reappear:
        target.mkdir()
        (target / "__init__.py").write_text("unmanaged")
    await manager.uninstall("demo", "uninstall demo")
    if files_reappear:
        assert manager.tombstones["demo"]["owner_confirmed"]
        target.mkdir()
        (target / "__init__.py").write_text("reappeared")
        await manager.heartbeat()
    status = github.statuses["production"]["integrations"]["demo"]
    assert status["state"] == "unmanaged" and not status["owner_confirmed"]
    assert target.exists()


@pytest.mark.parametrize("same_version", [False, True])
async def test_failed_registry_write_preserves_backup_identity(
    manager, github, bundle, same_version
):
    first = bundle()
    github.add(first)
    await manager.register("THEFLDR/demo", "demo", True)
    await manager.install("demo")
    manager.get("demo").install_boot = "previous-process"
    github.add(bundle(ver="0.1.1", rid=11))
    await manager.check()
    await manager.install("demo")
    record = manager.get("demo")
    record.install_boot = "previous-process"
    assert record.backup_snapshot["installed"]["version"] == "0.1.0"
    if not same_version:
        github.add(bundle(ver="0.1.2", rid=12))
    await manager.check()
    record.state = "error"
    original_write = github.write_status
    github.write_status = AsyncMock(side_effect=ManagerError("registry unavailable"))
    with pytest.raises(ManagerError, match="registry unavailable"):
        await manager.install("demo")
    assert record.installed.version == "0.1.1"
    assert record.backup_snapshot["installed"]["version"] == "0.1.0"
    assert record.pending is None
    github.write_status = original_write
    await manager.restore("demo", "restore demo")
    assert record.installed.identity() == first[0].identity()
    await manager.verify()
    assert record.state == "pending_restart"


async def test_crash_after_update_swap_preserves_prospective_backup(manager, github, bundle):
    first = bundle()
    github.add(first)
    await manager.register("THEFLDR/demo", "demo", True)
    await manager.install("demo")
    record = manager.get("demo")
    second = bundle(ver="0.1.1", rid=11)
    files = inspect_package(second[2], second[1])
    record.pending = {
        "release": asdict(second[0]),
        "files": fingerprints(files),
        "boot": "previous-process",
        "backup_snapshot": {"installed": asdict(first[0]), "files": dict(record.files)},
    }
    await manager.save()
    await manager.hass.async_add_executor_job(manager.installer.install, "demo", files, True)
    await manager.load()
    record = manager.get("demo")
    assert record.installed.identity() == second[0].identity()
    assert record.backup_snapshot["installed"]["version"] == "0.1.0"
    await manager.restore("demo", "restore demo")
    assert record.installed.identity() == first[0].identity()


async def test_error_recovery_rejects_downgrade_but_allows_same_version(manager, github, bundle):
    github.add(bundle())
    github.add(bundle(ver="0.2.0", rid=11))
    await manager.register("THEFLDR/demo", "demo", True)
    await manager.install("demo")
    record = manager.get("demo")
    record.state = "error"
    with pytest.raises(ManagerError, match="newer"):
        await manager.install("demo", target_version="0.1.0")
    await manager.install("demo", target_version="0.2.0")
    assert record.installed.version == "0.2.0"


async def test_promotion_verifies_dispatched_release_after_another_install(manager, github, bundle):
    first = bundle()
    github.add(first)
    await manager.register("THEFLDR/demo", "demo", True)
    await manager.install("demo")
    record = manager.get("demo")
    record.promotion = {"state": "dispatched", "request_id": "request", "release": asdict(first[0])}
    record.install_boot = "previous-process"
    second = bundle(ver="0.1.1", rid=11)
    github.add(second)
    await manager.check()
    await manager.install("demo")
    first[0].prerelease = False
    original_request = github.request

    async def request(method, path, **kwargs):
        if "promote.yml/runs" in path:
            return {
                "workflow_runs": [
                    {
                        "display_title": "promote-request",
                        "status": "completed",
                        "conclusion": "success",
                        "html_url": "https://github.com/THEFLDR/demo/actions/runs/123",
                    }
                ]
            }
        return await original_request(method, path, **kwargs)

    github.request = request
    with patch("custom_components.integration_manager.manager.asyncio.sleep", new=AsyncMock()):
        await manager._watch_promotion("demo", "request")
    assert record.promotion["state"] == "succeeded"
    assert record.installed.identity() == second[0].identity()
    assert record.installed.prerelease


async def test_health_survives_entry_reload_but_not_process_restart(
    manager, github, bundle, loaded
):
    b = bundle()
    github.add(b)
    await manager.register(b[0].repository, "demo", True)
    await manager.install("demo")
    manager.get("demo").install_boot = "previous-install-process"
    with loaded("demo", "0.1.0"):
        await manager.report_health("demo", "healthy", "0.1.0", b[0].release_id, b[0].sha256)
        await manager.load()
        assert manager.get("demo").health == "healthy"
        with patch("custom_components.integration_manager.manager.BOOT_ID", "next-process"):
            await manager.load()
            assert manager.get("demo").health == "unknown"
