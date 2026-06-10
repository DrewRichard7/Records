"""Password hashing helpers for Records authentication."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sys
import time


ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000
SALT_BYTES = 16
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"{ALGORITHM}${ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations, encoded_salt, encoded_digest = encoded_hash.split("$", 3)
        if algorithm != ALGORITHM:
            return False
        salt = _b64decode(encoded_salt)
        expected = _b64decode(encoded_digest)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def create_session_token(secret: str, max_age: int = SESSION_MAX_AGE_SECONDS) -> str:
    payload = {"authenticated": True, "expires_at": int(time.time()) + max_age}
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded_payload}.{_b64encode(signature)}"


def session_token_is_valid(token: str | None, secret: str) -> bool:
    if not token or "." not in token:
        return False
    encoded_payload, encoded_signature = token.split(".", 1)
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    try:
        actual_signature = _b64decode(encoded_signature)
        payload = json.loads(_b64decode(encoded_payload))
    except (ValueError, TypeError):
        return False
    if not hmac.compare_digest(actual_signature, expected_signature):
        return False
    return bool(payload.get("authenticated")) and int(payload.get("expires_at", 0)) >= int(time.time())


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1]:
        print("Usage: python -m records.auth '<password>'", file=sys.stderr)
        raise SystemExit(2)
    print(hash_password(sys.argv[1]))


if __name__ == "__main__":
    main()
