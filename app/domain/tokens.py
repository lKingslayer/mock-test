from __future__ import annotations

import base64
import hashlib
import json
import os

from pydantic import BaseModel, Field, ValidationError

from .paths import normalize_resource_path

__all__ = [
    "TOKEN_VERSION",
    "TokenPayload",
    "TokenError",
    "UnsupportedTokenVersionError",
    "MalformedTokenError",
    "derive_salt",
    "get_seed_from_env",
    "encode_resource_token",
    "decode_resource_token",
]

# Version your tokens so you can change their layout later without breaking old ones.
TOKEN_VERSION = 1
_UINT64_MAX = (1 << 64) - 1


# ------------------------
# Errors
# ------------------------
class TokenError(ValueError):
    """Base class for token-related errors.

    The `code` attribute lets the API map errors to stable machine codes later.
    """

    code: str = "invalid_token"


class UnsupportedTokenVersionError(TokenError):
    code = "unsupported_token_version"


class MalformedTokenError(TokenError):
    code = "malformed_token"


# ------------------------
# Schema
# ------------------------
class TokenPayload(BaseModel):
    """Opaque-but-decodable token payload for a single uploaded resource.

    Fields are deliberately short to keep tokens compact when base64-encoded.
    """

    ver: int = Field(..., ge=1, le=1)  # token schema version
    kb_id: str  # owning knowledge-base id
    rp: str  # normalized resource path
    ca_ms: int  # created_at epoch milliseconds
    salt: int = Field(..., ge=0, le=_UINT64_MAX)  # 64-bit RNG salt


# ------------------------
# Internals
# ------------------------

def _hash64(data: bytes) -> int:
    """Return a 64-bit integer derived from a BLAKE2b hash.

    We take a 16-byte digest and use its lower 8 bytes as an unsigned 64-bit int.
    This is stable across processes and platforms.
    """

    h = hashlib.blake2b(data, digest_size=16).digest()
    # Take the *last* 8 bytes (little-endian) to mix bits from the digest
    return int.from_bytes(h[8:], "little", signed=False)


def derive_salt(seed: int, kb_id: str, resource_path: str) -> int:
    """Derive a deterministic 64-bit salt from seed, kb_id, and resource path."""
    payload = f"{seed}|{kb_id}|{resource_path}".encode()
    return _hash64(payload) & _UINT64_MAX


def get_seed_from_env() -> int:
    """Read CI_RUN_SEED from environment.

    Returns 0 if unset to keep behavior predictable in local dev.
    """

    val = os.getenv("CI_RUN_SEED")
    if val is None:
        return 0
    try:
        return int(val, 10)
    except ValueError as e:  # pragma: no cover
        raise ValueError("CI_RUN_SEED must be an integer") from e


# ------------------------
# Public encode/decode
# ------------------------

def encode_resource_token(*, kb_id: str, resource_path: str, created_at_ms: int, seed: int) -> str:
    """Create a compact, URL-safe token representing a resource instance.

    The token encodes: version, kb_id, normalized path, created_at (ms), and a salt.
    """
    rp = normalize_resource_path(resource_path)
    salt = derive_salt(seed, kb_id, rp)
    payload = TokenPayload(ver=TOKEN_VERSION, kb_id=kb_id, rp=rp, ca_ms=created_at_ms, salt=salt)
    as_json = json.dumps(payload.model_dump(), separators=(",", ":"), ensure_ascii=False)
    raw = as_json.encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_resource_token(token: str) -> TokenPayload:
    """Decode and validate a token back into a `TokenPayload`.

    Raises a specific `TokenError` subclass if parsing/validation fails.
    """
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
    except Exception as e:  # pragma: no cover
        raise MalformedTokenError("Token is not valid base64url") from e

    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:  # pragma: no cover
        raise MalformedTokenError("Token JSON is malformed") from e

    try:
        payload = TokenPayload(**data)
    except ValidationError as e:
        raise MalformedTokenError(f"Token schema invalid: {e}") from e

    if payload.ver != TOKEN_VERSION:
        raise UnsupportedTokenVersionError(f"Unsupported token version: {payload.ver}")

    # Ensure resource path was (and still is) normalized
    if payload.rp != normalize_resource_path(payload.rp):
        raise MalformedTokenError("Token resource path is not normalized")

    return payload