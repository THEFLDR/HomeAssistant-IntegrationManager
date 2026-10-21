"""Serialized repository operations and durable HA state; no inbound GitHub endpoints."""

import asyncio
import json
import os
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from homeassistant import loader
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store

from .artifacts import fingerprints, inspect_package, tree_fingerprints
from .const import BOOT_ID, DOMAIN, VERSION
from .installer import Installer
from .models import Managed, ManagerError, Release, domain_name, repository, utcnow, version
from .policy import allowed, validate_promotion


class Manager:
    def __init__(self, hass, client, config: dict) -> None:
        self.hass = hass
        self.client = client
        self.config = config
        self.environment = config["environment"]
        self.registry = repository(config["registry_repository"])
        self.store = Store(hass, 1, DOMAIN, private=True)
        self.installer = Installer(Path(hass.config.config_dir))
        self.records: dict[str, Managed] = {}
        self.tombstones: dict[str, dict] = {}
        self.lock = asyncio.Lock()
        self.listeners = set()
        self.checking = False
        self.error = None
        self.last_check = None
        self.last_registry = None
        self.interfaces_ready = False
        self.tasks: set[asyncio.Task] = set()
        self.watched: set[str] = set()
        self.production_snapshot: dict = {}

    async def load(self) -> None:
        data = await self.store.async_load() or {}
        if data and (
            data.get("environment") != self.environment or data.get("registry") != self.registry
        ):
            raise ManagerError("Stored state belongs to a different environment or registry")
        self.records = {d: Managed.restore(r) for d, r in data.get("records", {}).items()}
        self.tombstones = data.get("tombstones", {})
        self.last_check = data.get("last_check")
        self.last_registry = data.get("last_registry")
        if DOMAIN not in self.records and DOMAIN not in self.tombstones:
            self.records[DOMAIN] = Managed(
                self.registry,
                DOMAIN,
                "Integration Manager",
                running_version=VERSION,
                state="bootstrap",
            )
        for record in self.records.values():
            record.progress = 0
            recovered = await self.hass.async_add_executor_job(
                self.installer.recover, record.domain
            )
            if recovered:
                record.error = "Recovered an interrupted file operation; inspect retained backup"
            if record.pending:
                await self.reconcile_pending(record)
            # Health observations never survive a process restart as proof of active health.
            if record.health_boot != BOOT_ID:
                record.health, record.health_at, record.health_release_id = "unknown", None, None
            if record.promotion and record.promotion.get("state") in ("dispatched", "unconfirmed"):
                self._watch(record.domain, record.promotion["request_id"])
        await self.verify()
        await self.save()

    async def reconcile_pending(self, record: Managed) -> None:
        """Bind committed target and backup bytes to the persisted transaction identities."""
        pending = record.pending
        if not pending:
            return
        disk = await self.hass.async_add_executor_job(
            tree_fingerprints, self.installer.components / record.domain
        )
        restore = pending.get("operation") == "restore"
        backup_exists = await self.hass.async_add_executor_job(
            os.path.lexists, self.installer.work / f"{record.domain}.backup"
        )
        if disk == pending["files"] and (not restore or not backup_exists):
            record.installed = Release(**pending["release"])
            record.files = pending["files"]
            record.install_boot = pending["boot"]
            prospective = pending.get("backup_snapshot")
            backup_files = await self.hass.async_add_executor_job(
                tree_fingerprints, self.installer.work / f"{record.domain}.backup"
            )
            if restore:
                record.backup_snapshot = None
            elif (
                prospective
                and prospective.get("installed")
                and backup_files == prospective["files"]
            ):
                record.backup_snapshot = prospective
            elif record.backup_snapshot and backup_files != record.backup_snapshot["files"]:
                record.backup_snapshot = None
            record.state = "pending_restart"
        else:
            record.error = "Interrupted installation did not commit; retained previous identity"
            record.state = "error"
        record.pending = None

    async def save(self) -> None:
        await self.store.async_save(
            {
                "environment": self.environment,
                "registry": self.registry,
                "records": {d: r.serialize() for d, r in self.records.items()},
                "tombstones": self.tombstones,
                "last_check": self.last_check,
                "last_registry": self.last_registry,
            }
        )
        self.notify()

    def notify(self) -> None:
        for listener in tuple(self.listeners):
            listener()

    def listen(self, callback):
        self.listeners.add(callback)
        return lambda: self.listeners.discard(callback)

    def snapshot(self) -> dict:
        integrations = []
        for record in self.records.values():
            item = record.serialize()
            item["health"] = record.status()["health"]
            item["config_entries"] = [
                entry.title for entry in self.hass.config_entries.async_entries(record.domain)
            ]
            item["promotion_eligible"] = False
            if self.environment == "sandbox" and record.installed and record.installed.prerelease:
                try:
                    if self.error:
                        raise ManagerError(self.error)
                    validate_promotion(
                        record.installed,
                        self.status_document(),
                        self.production_snapshot,
                        record.domain,
                    )
                    item["promotion_eligible"] = True
                except ManagerError as err:
                    item["promotion_blocker"] = str(err)
            integrations.append(item)
        return {
            "environment": self.environment,
            "running_manager_version": VERSION,
            "checking": self.checking,
            "error": self.error,
            "last_check": self.last_check,
            "last_registry": self.last_registry,
            "permissions": self.client.permissions,
            "registry_repository": self.registry,
            "integrations": integrations,
            "removed_integrations": [
                {"domain": domain, **tombstone} for domain, tombstone in self.tombstones.items()
            ],
            "updates": sum(
                bool(
                    r.available
                    and r.installed
                    and version(r.available.version) > version(r.installed.version)
                )
                for r in self.records.values()
            ),
            "errors": sum(bool(r.error) for r in self.records.values()),
        }

    async def verify(self) -> None:
        for domain, tombstone in self.tombstones.items():
            running = None
            try:
                integration = loader.async_get_loaded_integration(self.hass, domain)
                if domain in self.hass.config.components:
                    running = str(integration.version)
            except loader.IntegrationNotLoaded:
                pass
            exists = await self.hass.async_add_executor_job(
                os.path.lexists, self.installer.components / domain
            )
            if exists or running:
                tombstone["owner_confirmed"] = False
                tombstone["state"] = "unmanaged" if exists else "verifying"
                if exists:
                    tombstone["absence_requested"] = False
            else:
                tombstone["state"] = "not_installed"
                if tombstone.get("absence_requested") is True:
                    tombstone["owner_confirmed"] = True
            tombstone.update(
                {
                    "running_version": running,
                    "restart_pending": running is not None,
                    "updated_at": utcnow(),
                }
            )
        for record in self.records.values():
            record.running_version = None
            if not record.installed:
                if record.domain == DOMAIN:
                    record.running_version = VERSION
                else:
                    try:
                        integration = loader.async_get_loaded_integration(self.hass, record.domain)
                        if record.domain in self.hass.config.components:
                            record.running_version = str(integration.version)
                    except loader.IntegrationNotLoaded:
                        pass
                    exists = await self.hass.async_add_executor_job(
                        os.path.lexists, self.installer.components / record.domain
                    )
                    if exists or record.running_version:
                        record.absence_confirmed = False
                        record.state = "unmanaged"
                    elif record.state == "unmanaged":
                        record.state = "not_installed"
                continue
            try:
                integration = loader.async_get_loaded_integration(self.hass, record.domain)
                if record.domain in self.hass.config.components:
                    record.running_version = str(integration.version)
            except loader.IntegrationNotLoaded:
                pass
            try:
                disk = await self.hass.async_add_executor_job(
                    tree_fingerprints, self.installer.components / record.domain
                )
            except (ManagerError, OSError) as err:
                record.state, record.health = "error", "unhealthy"
                record.health_at, record.health_release_id = utcnow(), record.installed.release_id
                record.health_boot = BOOT_ID
                record.error = (
                    str(err) if isinstance(err, ManagerError) else "Cannot verify installed files"
                )
                continue
            if disk != record.files:
                record.state, record.health = "error", "unhealthy"
                record.health_at = utcnow()
                record.health_release_id = record.installed.release_id
                record.health_boot = BOOT_ID
                record.error = (
                    "Installed files differ from verified package; restore backup or reinstall"
                )
            elif record.install_boot == BOOT_ID:
                record.state = "pending_restart"
            elif record.running_version != record.installed.version:
                record.state, record.health = "verifying", "unknown"
            elif (
                record.domain != DOMAIN and record.health_release_id != record.installed.release_id
            ):
                record.state = "verifying"
            else:
                record.state = "active"

    async def check(self, _now=None) -> None:
        async with self.lock:
            self.checking = True
            self.notify()
            try:
                await self.client.validate(self.registry)
                for record in self.records.values():
                    try:
                        raw = await self.client.releases(record.repository)
                        candidates = []
                        for item in raw:
                            try:
                                ver = item["tag_name"].removeprefix("v")
                                version(ver)
                            except ManagerError:
                                continue
                            if item["tag_name"] != f"v{ver}":
                                continue
                            if (self.environment == "sandbox" and not item["prerelease"]) or (
                                self.environment == "production"
                                and (item["prerelease"] or version(ver) < (1, 0, 0))
                            ):
                                continue
                            candidates.append(item)
                        record.available = None
                        record.offers = [
                            {"version": i["tag_name"][1:], "release_id": i["id"]}
                            for i in sorted(
                                candidates, key=lambda i: version(i["tag_name"][1:]), reverse=True
                            )
                        ]
                        if candidates:
                            selected = max(candidates, key=lambda i: version(i["tag_name"][1:]))
                            release, metadata = await self.client.release(
                                record.repository, selected
                            )
                            if metadata["domain"] != record.domain:
                                raise ManagerError(
                                    "Release domain differs from approved registration"
                                )
                            record.available = release
                        record.checked_at, record.error = utcnow(), None
                    except ManagerError as err:
                        record.error = str(err)
                self.last_check = utcnow()
                for record in self.records.values():
                    if record.promotion and record.promotion.get("state") in (
                        "unconfirmed",
                        "dispatched",
                    ):
                        record.promotion["state"] = "dispatched"
                        self._watch(record.domain, record.promotion["request_id"])
                await self.verify()
                await self._heartbeat()
            except ManagerError as err:
                self.failure(str(err))
            finally:
                self.checking = False
                await self.save()

    async def heartbeat(self, _now=None) -> None:
        async with self.lock:
            try:
                await self.verify()
                await self._heartbeat()
            except ManagerError as err:
                self.failure(str(err))
            await self.save()

    async def _heartbeat(self) -> None:
        try:
            await self._publish_status()
        except ManagerError as err:
            self.failure(str(err))
            self.notify()
            raise

    async def _publish_status(self) -> None:
        await self.client.validate(self.registry)
        existing = await self.client.read_status(self.registry, self.environment)
        if existing and existing.get("instance_id") not in (None, self.config["instance_id"]):
            raise ManagerError(
                "Another instance owns this environment variable; resolve ownership explicitly"
            )
        required = {"contents": "read", "actions_variables": "write", "actions": "write"}
        missing = [
            name
            for name, level in required.items()
            if self.client.permissions.get(name)
            not in ({"read", "write"} if level == "read" else {"write"})
        ]
        own = self.records.get(DOMAIN)
        if own:
            usable = (
                self.interfaces_healthy()
                and not missing
                and all(not r.error for r in self.records.values())
                and own.installed is not None
                and own.running_version == own.installed.version
                and own.install_boot != BOOT_ID
                and own.state in ("verifying", "active")
            )
            own.health = "healthy" if usable else "unhealthy" if missing else "unknown"
            own.health_at = utcnow()
            own.health_boot = BOOT_ID
            own.health_release_id = own.installed.release_id if usable else None
            if usable:
                own.state = "active"
        # Persistence must succeed before declaring the manager's storage health.
        await self.save()
        await self.client.write_status(self.registry, self.environment, self.status_document())
        self.production_snapshot = await self.client.read_status(self.registry, "production")
        self.last_registry = utcnow()
        self.error = f"Missing GitHub App permissions: {', '.join(missing)}" if missing else None

    def interfaces_healthy(self) -> bool:
        if not self.interfaces_ready or not self.hass.services.has_service(DOMAIN, "report_health"):
            return False
        registry = er.async_get(self.hass)
        for domain in self.records:
            for platform, suffix in (("update", "update"), ("sensor", "health")):
                entity_id = registry.async_get_entity_id(
                    platform, DOMAIN, f"{DOMAIN}_{self.environment}_{domain}_{suffix}"
                )
                if not entity_id or self.hass.states.get(entity_id) is None:
                    return False
        return True

    def status_document(self) -> dict:
        return {
            "schema_version": 1,
            "environment": self.environment,
            "instance_id": self.config["instance_id"],
            "updated_at": utcnow(),
            "integrations": {**self.tombstones, **{d: r.status() for d, r in self.records.items()}},
        }

    async def register(self, repo: str, domain: str, approved: bool) -> None:
        repository(repo)
        domain_name(domain)
        if not approved:
            raise ManagerError("Explicit repository approval is required")
        async with self.lock:
            if domain in self.records or any(
                r.repository.lower() == repo.lower() for r in self.records.values()
            ):
                raise ManagerError("Repository or domain already registered")
            if repo.split("/")[0].lower() != self.registry.split("/")[0].lower():
                raise ManagerError("Only repositories owned by the registry owner may be managed")
            info = await self.client.request("GET", f"/repos/{repo}")
            if info["archived"] or info["disabled"]:
                raise ManagerError("Repository is archived or disabled")
            raw = await self.client.releases(repo)
            if not raw:
                raise ManagerError("Repository has no release implementing the package contract")
            valid = []
            for item in raw:
                try:
                    rel, metadata = await self.client.release(repo, item)
                except ManagerError:
                    continue
                if metadata.get("domain") == domain:
                    package = await self.client.asset(repo, rel.asset_id)
                    package_files = await self.hass.async_add_executor_job(
                        inspect_package, package, metadata
                    )
                    display_name = json.loads(package_files["manifest.json"])["name"]
                    valid.append(rel)
                    break
            if not valid:
                raise ManagerError("No immutable release has the approved integration domain")
            self.records[domain] = Managed(repo, domain, display_name)
            self.tombstones.pop(domain, None)
            await self.save()
        await self.check()

    async def install(self, domain: str, *, adopt=False, target_version=None) -> None:
        async with self.lock:
            record = self.get(domain)
            if record.installed and record.install_boot == BOOT_ID and record.state != "error":
                raise ManagerError(
                    "Restart and verify the pending installation before another update"
                )
            if not record.available:
                raise ManagerError("No eligible release; check for updates first")
            selected_id = record.available.release_id
            if target_version is not None:
                version(target_version)
                selected = next(
                    (offer for offer in record.offers if offer["version"] == target_version), None
                )
                if not selected:
                    raise ManagerError("Requested version is not offered for this environment")
                selected_id = selected["release_id"]
            raw = await self.client.request(
                "GET", f"/repos/{record.repository}/releases/{selected_id}"
            )
            release, metadata = await self.client.release(record.repository, raw)
            if (
                not allowed(release, self.environment)
                or release.release_id != selected_id
                or (target_version is not None and release.version != target_version)
                or (
                    selected_id == record.available.release_id
                    and release.identity() != record.available.identity()
                )
            ):
                raise ManagerError("Release channel or identity changed; check again")
            if metadata["domain"] != domain:
                raise ManagerError("Release domain mismatch")
            if record.installed and (
                version(release.version) < version(record.installed.version)
                or (
                    version(release.version) == version(record.installed.version)
                    and record.state != "error"
                )
            ):
                raise ManagerError("Only newer versions may be installed")
            record.progress, record.error = 10, None
            self.notify()
            try:
                package = await self.client.asset(record.repository, release.asset_id)
                files = await self.hass.async_add_executor_job(inspect_package, package, metadata)
                expected = fingerprints(files)
                record.progress = 40
                if adopt:
                    actual = await self.hass.async_add_executor_job(
                        tree_fingerprints, self.installer.components / domain
                    )
                    if actual != expected:
                        raise ManagerError(
                            "Existing files do not exactly match the release; adoption refused"
                        )
                else:
                    target = self.installer.components / domain
                    exists = await self.hass.async_add_executor_job(target.exists)
                    if exists and not record.installed:
                        raise ManagerError("Existing files require explicit verified adoption")
                was_managed = record.installed is not None
                prospective_backup = (
                    record.backup_snapshot
                    if adopt
                    else {
                        "installed": record.serialize()["installed"],
                        "files": dict(record.files),
                    }
                )
                record.pending = {
                    "release": asdict(release),
                    "files": expected,
                    "boot": BOOT_ID,
                    "backup_snapshot": prospective_backup,
                }
                record.state, record.health, record.health_at = "downloaded", "unknown", None
                record.health_release_id, record.health_boot = None, None
                await self.save()  # Persist intended identity before the atomic replacement.
                # Invalidate prior promotion eligibility remotely before touching installed files.
                await self._heartbeat()
                if not adopt:
                    await self.hass.async_add_executor_job(
                        self.installer.install, domain, files, was_managed
                    )
                record.installed, record.files, record.install_boot = release, expected, BOOT_ID
                record.backup_snapshot = prospective_backup
                record.pending = None
                record.state, record.progress = "installed", 75
                await self.save()
                record.state, record.progress = "pending_restart", 100
                if adopt:
                    record.install_boot = "verified-adoption"
                    await self.verify()
                await self.save()
                await self._heartbeat()
            except (ManagerError, OSError) as err:
                await self.reconcile_pending(record)
                record.error = (
                    str(err)
                    if isinstance(err, ManagerError)
                    else "File operation failed; inspect retained backup"
                )
                record.state = "error"
                await self.save()
                raise ManagerError(record.error) from err
            finally:
                record.progress = 0
                self.notify()

    async def uninstall(self, domain: str, confirmation: str) -> None:
        async with self.lock:
            record = self.get(domain)
            if confirmation != f"uninstall {domain}":
                raise ManagerError("Explicit domain confirmation is required")
            await self.verify()
            record.state, record.health = "uninstalling", "unknown"
            await self.save()
            await self._heartbeat()
            if record.installed:
                await self.hass.async_add_executor_job(self.installer.uninstall, domain)
            exists = await self.hass.async_add_executor_job(
                os.path.lexists, self.installer.components / domain
            )
            self.tombstones[domain] = {
                "repository": record.repository,
                "state": "unmanaged"
                if exists
                else "verifying"
                if record.running_version
                else "not_installed",
                "owner_confirmed": not exists and not record.running_version,
                "absence_requested": not exists,
                "updated_at": utcnow(),
                "running_version": record.running_version,
                "restart_pending": bool(record.running_version),
                "health": "unknown",
            }
            del self.records[domain]
            await self.save()
            await self._heartbeat()

    async def restore(self, domain: str, confirmation: str) -> None:
        async with self.lock:
            record = self.get(domain)
            if confirmation != f"restore {domain}":
                raise ManagerError("Explicit restore confirmation is required")
            backup = record.backup_snapshot
            actual = await self.hass.async_add_executor_job(
                tree_fingerprints, self.installer.work / f"{domain}.backup"
            )
            if not backup or not backup.get("installed") or actual != backup["files"]:
                raise ManagerError("Retained backup does not match its verified identity")
            record.pending = {
                "operation": "restore",
                "release": backup["installed"],
                "files": backup["files"],
                "boot": BOOT_ID,
            }
            record.state, record.health, record.health_at = "restoring", "unknown", None
            record.health_release_id, record.health_boot = None, None
            try:
                await self.save()
                await self._heartbeat()
                await self.hass.async_add_executor_job(self.installer.restore, domain)
                await self.reconcile_pending(record)
                record.error = "Backup restored; restart HA and verify activation"
                await self.save()
                await self._heartbeat()
            except (ManagerError, OSError) as err:
                await self.reconcile_pending(record)
                record.state = "error"
                record.error = (
                    str(err)
                    if isinstance(err, ManagerError)
                    else "Backup restore failed; previous files retained where possible"
                )
                await self.save()
                raise ManagerError(record.error) from err

    async def report_health(
        self, domain: str, health: str, reported_version: str, release_id: int, sha256: str
    ) -> None:
        async with self.lock:
            record = self.get(domain)
            if domain == DOMAIN or health not in ("healthy", "unhealthy"):
                raise ManagerError("External health contract accepts managed integrations only")
            await self.verify()
            if (
                not record.installed
                or record.running_version != reported_version
                or record.installed.version != reported_version
                or record.installed.release_id != release_id
                or record.installed.sha256 != sha256
                or record.install_boot == BOOT_ID
                or record.state not in ("verifying", "active")
            ):
                raise ManagerError("Health observation does not match an activated release")
            record.health, record.health_at, record.health_release_id = health, utcnow(), release_id
            record.health_boot = BOOT_ID
            record.state = "active"
            await self.save()
            await self._heartbeat()

    async def confirm_absent(self, domain: str, confirmation: str) -> None:
        if confirmation != f"production has not installed {domain}":
            raise ManagerError("Explicit owner confirmation of Production absence is required")
        async with self.lock:
            if self.environment == "production":
                await self.verify()
                if domain in self.tombstones:
                    tombstone = self.tombstones[domain]
                    if (
                        tombstone["state"] != "not_installed"
                        or tombstone["running_version"]
                        or tombstone["restart_pending"]
                    ):
                        raise ManagerError(
                            "Production files or running code prevent absence confirmation"
                        )
                    tombstone.update({"owner_confirmed": True, "absence_requested": True})
                    await self.save()
                    await self._heartbeat()
                    return
                record = self.get(domain)
                if record.installed or record.running_version or record.state != "not_installed":
                    raise ManagerError(
                        "Production files or running code prevent absence confirmation"
                    )
                record.absence_confirmed = True
                await self.save()
                await self._heartbeat()
                return
            record = self.get(domain)
            production = await self.client.read_status(self.registry, "production")
            integrations = production.get("integrations", {})
            if production.get("instance_id"):
                raise ManagerError(
                    "Production owns its registry; confirm absence on Production itself"
                )
            prior = integrations.get(domain, {})
            if prior and (
                prior.get("state") != "not_installed"
                or prior.get("owner_confirmed") is not True
                or prior.get("running_version")
                or production.get("instance_id")
            ):
                raise ManagerError(
                    "Production already has a record; do not overwrite it from Sandbox"
                )
            integrations[domain] = {
                "repository": record.repository,
                "state": "not_installed",
                "owner_confirmed": True,
                "updated_at": utcnow(),
                "running_version": None,
                "restart_pending": False,
                "health": "unknown",
            }
            production.update(
                {
                    "schema_version": 1,
                    "environment": "production",
                    "updated_at": utcnow(),
                    "integrations": integrations,
                }
            )
            await self.client.write_status(self.registry, "production", production)
            self.production_snapshot = production
            self.notify()

    async def promotion_eligibility(self, domain: str) -> None:
        record = self.get(domain)
        if self.environment != "sandbox" or not record.installed:
            raise ManagerError("Promotion is available only for installed Sandbox releases")
        raw = await self.client.request(
            "GET", f"/repos/{record.repository}/releases/{record.installed.release_id}"
        )
        release, _ = await self.client.release(record.repository, raw)
        if not release.prerelease:
            raise ManagerError("Release is already Stable")
        sandbox = await self.client.read_status(self.registry, "sandbox")
        production = await self.client.read_status(self.registry, "production")
        validate_promotion(release, sandbox, production, domain)

    async def promote(self, domain: str) -> None:
        async with self.lock:
            await self.verify()
            await self._heartbeat()
            record = self.get(domain)
            await self.promotion_eligibility(domain)
            if record.promotion and record.promotion.get("state") in ("dispatched", "unconfirmed"):
                raise ManagerError("Promotion is already in progress")
            request_id = uuid4().hex
            await self.client.dispatch(
                record.repository,
                "promote.yml",
                {
                    "version": record.installed.version,
                    "domain": domain,
                    "release_id": str(record.installed.release_id),
                    "sha256": record.installed.sha256,
                    "registry": self.registry,
                    "request_id": request_id,
                },
            )
            record.promotion = {
                "state": "dispatched",
                "request_id": request_id,
                "requested_at": utcnow(),
                "release": asdict(record.installed),
                "error": None,
            }
            await self.save()
            self._watch(domain, request_id)

    def _watch(self, domain: str, request_id: str) -> None:
        if domain in self.watched:
            return
        self.watched.add(domain)
        task = self.hass.async_create_background_task(
            self._watch_promotion(domain, request_id), f"IM promotion {domain}"
        )
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        task.add_done_callback(lambda _: self.watched.discard(domain))

    async def _watch_promotion(self, domain: str, request_id: str) -> None:
        try:
            for _ in range(24):
                await asyncio.sleep(5)
                async with self.lock:
                    record = self.get(domain)
                    if not record.promotion or record.promotion.get("request_id") != request_id:
                        return
                    if not record.promotion.get("release"):
                        raise ManagerError(
                            "Promotion request lacks its dispatched release identity"
                        )
                    dispatched = Release(**record.promotion["release"])
                    runs = await self.client.request(
                        "GET",
                        f"/repos/{dispatched.repository}/actions/workflows/"
                        "promote.yml/runs?event=workflow_dispatch&per_page=30",
                    )
                    run = next(
                        (
                            r
                            for r in runs["workflow_runs"]
                            if r["display_title"] == f"promote-{request_id}"
                        ),
                        None,
                    )
                    if not run or run["status"] != "completed":
                        continue
                    record.promotion["url"] = run["html_url"]
                    if run["conclusion"] != "success":
                        raise ManagerError(
                            f"Promotion workflow concluded {run['conclusion']}; inspect audit run"
                        )
                    raw = await self.client.request(
                        "GET", f"/repos/{dispatched.repository}/releases/{dispatched.release_id}"
                    )
                    final, _ = await self.client.release(dispatched.repository, raw)
                    if final.prerelease or final.identity() != dispatched.identity():
                        raise ManagerError(
                            "Workflow succeeded but final release identity/channel "
                            "verification failed"
                        )
                    if record.installed and record.installed.identity() == final.identity():
                        record.installed = final
                    if record.available and record.available.release_id == final.release_id:
                        record.available = None
                    record.offers = [
                        offer for offer in record.offers if offer["release_id"] != final.release_id
                    ]
                    record.promotion["state"] = "succeeded"
                    await self.save()
                    return
            raise ManagerError(
                "Promotion outcome not yet confirmed; inspect workflow run and check again"
            )
        except (ManagerError, KeyError) as err:
            if domain in self.records:
                state = "unconfirmed" if str(err).startswith("Promotion outcome") else "failed"
                self.records[domain].promotion.update({"state": state, "error": str(err)})
                await self.save()

    def get(self, domain: str) -> Managed:
        if domain not in self.records:
            raise ManagerError("Integration is not registered")
        return self.records[domain]

    def failure(self, message: str) -> None:
        self.error = message
        if own := self.records.get(DOMAIN):
            own.health, own.health_at, own.health_release_id = "unhealthy", utcnow(), None
            own.health_boot = BOOT_ID

    async def close(self) -> None:
        for task in tuple(self.tasks):
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
