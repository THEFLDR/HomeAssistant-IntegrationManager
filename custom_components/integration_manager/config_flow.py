"""Native setup and key rotation. PEM files never enter config entries or diagnostics."""

import os
from pathlib import Path
from uuid import uuid4

import voluptuous as vol
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, VERSION
from .github import GitHubClient
from .models import ManagerError, repository, version

KEY_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD, multiline=True)
)


def write_key(path: Path, key: str) -> str:
    """Verify key material and write atomically with owner-only permissions."""
    parsed = serialization.load_pem_private_key(key.encode(), password=None)
    if not isinstance(parsed, rsa.RSAPrivateKey) or parsed.key_size < 2048:
        raise ManagerError("GitHub App requires an RSA private key of at least 2048 bits")
    if path.is_symlink() or path.parent.is_symlink() or path.parent.parent.is_symlink():
        raise ManagerError("Key path must not be a symlink")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".key-{uuid4().hex}")
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(key)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return str(path)


def connection_schema(defaults: dict, *, optional_key=False) -> vol.Schema:
    key = vol.Optional("private_key") if optional_key else vol.Required("private_key")
    return vol.Schema(
        {
            vol.Required("app_id", default=defaults.get("app_id", "")): str,
            vol.Required("client_id", default=defaults.get("client_id", "")): str,
            vol.Required("installation_id", default=defaults.get("installation_id", "")): str,
            key: KEY_SELECTOR,
        }
    )


async def validate_connection(hass, data: dict, key: str) -> None:
    if not str(data["app_id"]).isdigit() or not str(data["installation_id"]).isdigit():
        raise ManagerError("App ID and Installation ID must be numeric")
    client = GitHubClient(
        async_get_clientsession(hass), str(data["app_id"]), str(data["installation_id"]), key
    )
    await client.validate(repository(data["registry_repository"]))


class IntegrationManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        errors = {}
        if user_input is not None:
            try:
                if user_input["environment"] == "production" and version(VERSION) < (1, 0, 0):
                    return self.async_abort(reason="production_before_one")
                key = user_input["private_key"]
                await validate_connection(self.hass, user_input, key)
                instance = uuid4().hex
                path = Path(
                    self.hass.config.path(".storage", "integration_manager_keys", f"{instance}.pem")
                )
                key_path = await self.hass.async_add_executor_job(write_key, path, key)
                data = {k: v for k, v in user_input.items() if k != "private_key"}
                data.update({"key_path": key_path, "instance_id": instance})
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Integration Manager ({data['environment'].title()})", data=data
                )
            except ManagerError, ValueError, OSError, TypeError:
                errors["base"] = "cannot_connect"
        schema = connection_schema(user_input or {}).extend(
            {
                vol.Required("environment", default="sandbox"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=["sandbox", "production"])
                ),
                vol.Required(
                    "registry_repository", default="THEFLDR/HomeAssistant-IntegrationManager"
                ): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return IntegrationManagerOptionsFlow()


class IntegrationManagerOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        config = {**self.config_entry.data, **self.config_entry.options}
        errors = {}
        if user_input is not None:
            try:
                key = user_input.get("private_key") or await self.hass.async_add_executor_job(
                    Path(config["key_path"]).read_text
                )
                merged = {**config, **user_input}
                await validate_connection(self.hass, merged, key)
                if user_input.get("private_key"):
                    await self.hass.async_add_executor_job(write_key, Path(config["key_path"]), key)
                return self.async_create_entry(
                    title="", data={k: v for k, v in user_input.items() if k != "private_key"}
                )
            except ManagerError, ValueError, OSError, TypeError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="init", data_schema=connection_schema(config, optional_key=True), errors=errors
        )
