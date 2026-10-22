"""Public constants; no installation-specific credentials or identifiers."""

from datetime import timedelta
from uuid import uuid4

DOMAIN = "integration_manager"
VERSION = "0.1.0"
BOOT_ID = uuid4().hex
CHECK_INTERVAL = timedelta(hours=24)
HEARTBEAT_INTERVAL = timedelta(hours=1)
STATUS_MAX_AGE = timedelta(hours=2)
HEALTH_MAX_AGE = timedelta(hours=2)
MAX_VARIABLE_BYTES = 48 * 1024
MAX_PACKAGE_BYTES = 32 * 1024 * 1024
MAX_EXTRACTED_BYTES = 64 * 1024 * 1024
MAX_FILES = 2000
PACKAGE_NAME = "integration.zip"
METADATA_NAME = "integration.json"
STORAGE_VERSION = 1
