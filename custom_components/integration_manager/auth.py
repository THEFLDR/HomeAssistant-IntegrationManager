"""Shared App JWT construction; no OAuth or credential persistence."""

import time

import jwt

from .models import ManagerError


def assertion(app_id: str, private_key: str) -> str:
    now = int(time.time())
    try:
        return jwt.encode(
            {"iat": now - 60, "exp": now + 540, "iss": app_id}, private_key, algorithm="RS256"
        )
    except (ValueError, jwt.PyJWTError) as err:
        raise ManagerError("Invalid GitHub App RSA private key") from err
