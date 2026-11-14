"""
Authentication (HS256 + RS256/JWKS JWT, API Key), RBAC Role Hierarchy,
Separation-of-Duties & Approver-Group HITL Governance, and Rate Limiting.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
import time
from collections import deque
from typing import Annotated, Any, ClassVar

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_EPHEMERAL_DEV_SECRET = secrets.token_hex(32)


def is_dev_mode() -> bool:
    """Returns True only when explicit local development mode is opted into."""
    return os.environ.get("ROUTER_DEV_MODE", "").lower() in ("1", "true", "yes")


def validate_security_config() -> None:
    """
    Fail-closed startup check: requires an explicit signing/verification key
    (ROUTER_JWT_SECRET, ROUTER_JWT_PUBLIC_KEY_PEM, or ROUTER_JWKS_JSON)
    unless ROUTER_DEV_MODE=1 is set.
    """
    if is_dev_mode():
        return
    has_key = any(
        bool(os.environ.get(var, "").strip())
        for var in ("ROUTER_JWT_SECRET", "ROUTER_JWT_PUBLIC_KEY_PEM", "ROUTER_JWKS_JSON")
    )
    if not has_key:
        raise RuntimeError(
            "Refusing to start without ROUTER_JWT_SECRET, ROUTER_JWT_PUBLIC_KEY_PEM, "
            "or ROUTER_JWKS_JSON (set ROUTER_DEV_MODE=1 only for local development)."
        )


ROLE_HIERARCHY: dict[str, set[str]] = {
    "super_admin": {
        "super_admin",
        "platform_admin",
        "compliance_officer",
        "data_engineer",
        "analyst",
        "ai_platform_reader",
    },
    "platform_admin": {
        "platform_admin",
        "data_engineer",
        "analyst",
        "ai_platform_reader",
    },
    "compliance_officer": {
        "compliance_officer",
        "analyst",
        "ai_platform_reader",
    },
    "data_engineer": {
        "data_engineer",
        "analyst",
        "ai_platform_reader",
    },
    "analyst": {"analyst", "ai_platform_reader"},
    "ai_platform_reader": {"ai_platform_reader"},
}


def expand_allowed_roles(user_roles: list[str] | None) -> set[str]:
    """Expands a caller's roles across the deterministic RBAC hierarchy."""
    if not user_roles:
        return set()
    allowed: set[str] = set()
    for role in user_roles:
        allowed.add(role)
        allowed.update(ROLE_HIERARCHY.get(role, set()))
    return allowed


def is_role_authorized(required_role: str, user_roles: list[str] | None) -> bool:
    """Checks whether `user_roles` satisfies `required_role` under hierarchy rules."""
    if not user_roles:
        return False
    return required_role in expand_allowed_roles(user_roles)


def _get_jwt_secret(allow_missing: bool = False) -> str | None:
    configured = os.environ.get("ROUTER_JWT_SECRET", "").strip()
    if configured:
        return configured
    if is_dev_mode():
        return _EPHEMERAL_DEV_SECRET
    if allow_missing:
        return None
    raise RuntimeError(
        "ROUTER_JWT_SECRET is required for HS256 signing/verification "
        "(or enable ROUTER_DEV_MODE=1 for local dev)."
    )


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding_str = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding_str).encode("ascii"))


def _int_to_b64url(val: int) -> str:
    byte_len = max(1, (val.bit_length() + 7) // 8)
    return _b64url_encode(val.to_bytes(byte_len, "big"))


def _b64url_to_int(val: str) -> int:
    return int.from_bytes(_b64url_decode(val), "big")


def generate_rsa_keypair_and_jwks(kid: str = "idp-rsa-1") -> dict[str, Any]:
    """Generates an RSA-2048 keypair and corresponding OIDC JWKS document for RS256 verification."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    numbers = public_key.public_numbers()
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": _int_to_b64url(numbers.n),
        "e": _int_to_b64url(numbers.e),
    }
    return {
        "private_pem": private_pem,
        "public_pem": public_pem,
        "jwks": {"keys": [jwk]},
    }


def create_jwt_token(
    username: str,
    roles: list[str],
    expires_in_seconds: int = 3600,
    secret: str | None = None,
    groups: list[str] | None = None,
    issuer: str | None = None,
    audience: str | None = None,
) -> str:
    """Mints an RFC 7519 HS256 JWT bearing subject, RBAC roles, groups, iss, and aud."""
    resolved_secret = secret if secret is not None else _get_jwt_secret()
    if not resolved_secret:
        raise RuntimeError("ROUTER_JWT_SECRET is required")
    signing_secret = resolved_secret.encode("utf-8")
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": username,
        "roles": list(roles),
        "groups": list(groups or []),
        "iat": now,
        "exp": now + expires_in_seconds,
        "iss": issuer or os.environ.get("ROUTER_JWT_ISSUER", "enterprise-mcp-router"),
        "aud": audience or os.environ.get("ROUTER_JWT_AUDIENCE", "enterprise-mcp-gateway"),
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    sig = hmac.new(signing_secret, signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(sig)}"


def create_rs256_jwt_token(
    username: str,
    roles: list[str],
    private_pem: str,
    expires_in_seconds: int = 3600,
    groups: list[str] | None = None,
    kid: str = "idp-rsa-1",
    issuer: str | None = None,
    audience: str | None = None,
) -> str:
    """Mints an RS256 OIDC JWT signed by an RSA private key."""
    private_key = serialization.load_pem_private_key(private_pem.encode("utf-8"), password=None)
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise TypeError("RSA private key required for RS256 token signing.")
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT", "kid": kid}
    payload = {
        "sub": username,
        "roles": list(roles),
        "groups": list(groups or []),
        "iat": now,
        "exp": now + expires_in_seconds,
        "iss": issuer or os.environ.get("ROUTER_JWT_ISSUER", "enterprise-mcp-router"),
        "aud": audience or os.environ.get("ROUTER_JWT_AUDIENCE", "enterprise-mcp-gateway"),
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    sig = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{header_b64}.{payload_b64}.{_b64url_encode(sig)}"


def _load_rsa_public_key_for_token(
    header: dict[str, Any],
    public_key_pem: str | None,
    jwks: dict[str, Any] | None,
) -> Any:
    pem = public_key_pem or os.environ.get("ROUTER_JWT_PUBLIC_KEY_PEM", "").strip()
    if pem:
        return serialization.load_pem_public_key(pem.encode("utf-8"))

    jwks_doc = jwks
    if jwks_doc is None:
        env_jwks = os.environ.get("ROUTER_JWKS_JSON", "").strip()
        if env_jwks:
            jwks_doc = json.loads(env_jwks)

    if isinstance(jwks_doc, dict):
        keys = jwks_doc.get("keys", [])
        kid = header.get("kid")
        matched = [k for k in keys if (not kid or k.get("kid") == kid) and k.get("kty") == "RSA"]
        if matched:
            jwk = matched[0]
            pub_numbers = rsa.RSAPublicNumbers(_b64url_to_int(jwk["e"]), _b64url_to_int(jwk["n"]))
            return pub_numbers.public_key()

    raise ValueError("rs256_public_key_not_configured")


def verify_jwt_token(
    token: str,
    secret: str | None = None,
    public_key_pem: str | None = None,
    jwks: dict[str, Any] | None = None,
    expected_issuer: str | None = None,
    expected_audience: str | None = None,
) -> dict[str, Any]:
    """Verifies an HS256 or RS256/JWKS JWT signature, expiration, subject, iss, and aud."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("malformed_jwt")
    header_b64, payload_b64, sig_b64 = parts

    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        alg = header.get("alg")
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")

        if alg == "HS256":
            hs_secret = secret if secret is not None else _get_jwt_secret(allow_missing=True)
            if not hs_secret:
                raise ValueError("hs256_secret_not_configured")
            expected_sig = _b64url_encode(hmac.new(hs_secret.encode("utf-8"), signing_input, hashlib.sha256).digest())
            if not hmac.compare_digest(expected_sig, sig_b64):
                raise ValueError("invalid_jwt_signature")
        elif alg == "RS256":
            pub_key = _load_rsa_public_key_for_token(header, public_key_pem, jwks)
            try:
                pub_key.verify(_b64url_decode(sig_b64), signing_input, padding.PKCS1v15(), hashes.SHA256())
            except Exception as exc:
                raise ValueError("invalid_jwt_signature") from exc
        else:
            raise ValueError("unsupported_jwt_alg")

        claims = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("invalid_jwt_encoding") from exc

    exp = claims.get("exp")
    if not isinstance(exp, (int, float)) or time.time() > float(exp):
        raise ValueError("expired_jwt")
    if not claims.get("sub"):
        raise ValueError("missing_jwt_subject")

    req_iss = expected_issuer or os.environ.get("ROUTER_JWT_ISSUER", "enterprise-mcp-router")
    if claims.get("iss") != req_iss:
        raise ValueError("invalid_jwt_issuer")

    req_aud = expected_audience or os.environ.get("ROUTER_JWT_AUDIENCE", "enterprise-mcp-gateway")
    aud_claim = claims.get("aud")
    if isinstance(aud_claim, list):
        aud_valid = req_aud in aud_claim
    else:
        aud_valid = aud_claim == req_aud
    if not aud_valid:
        raise ValueError("invalid_jwt_audience")

    return claims


class AuthenticatedPrincipal(BaseModel):
    username: str
    roles: list[str] = Field(default_factory=list)
    groups: list[str] = Field(default_factory=list)
    is_authenticated: bool = True
    auth_scheme: str = "jwt"

    def has_role(self, required_role: str) -> bool:
        return is_role_authorized(required_role, self.roles)


# Development-only demo API keys (disabled by default unless ROUTER_DEV_MODE=1 or ROUTER_ENABLE_DEMO_KEYS=1).
# Notice operators (`ak-admin-demo`) belong to `platform_operators`, while the designated
# peer approver (`ak-superadmin-demo`) belongs strictly to `hitl_approvers`.
DEFAULT_PRINCIPALS: dict[str, AuthenticatedPrincipal] = {
    "ak-analyst-demo": AuthenticatedPrincipal(
        username="analyst_user",
        roles=["analyst"],
        groups=["platform_operators"],
        auth_scheme="api_key",
    ),
    "ak-engineer-demo": AuthenticatedPrincipal(
        username="data_engineer_user",
        roles=["data_engineer", "analyst"],
        groups=["platform_operators"],
        auth_scheme="api_key",
    ),
    "ak-admin-demo": AuthenticatedPrincipal(
        username="platform_admin_user",
        roles=["platform_admin", "analyst", "data_engineer"],
        groups=["platform_operators"],
        auth_scheme="api_key",
    ),
    "ak-superadmin-demo": AuthenticatedPrincipal(
        username="sr_ops_approver@enterprise.io",
        roles=["super_admin", "compliance_officer"],
        groups=["hitl_approvers"],
        auth_scheme="api_key",
    ),
}


def get_configured_principals() -> dict[str, AuthenticatedPrincipal]:
    """Loads API key principals from ROUTER_API_KEYS env; demo keys only in dev mode."""
    principals: dict[str, AuthenticatedPrincipal] = {}
    demo_keys_enabled = is_dev_mode() or os.environ.get("ROUTER_ENABLE_DEMO_KEYS", "").lower() in ("1", "true", "yes")
    if demo_keys_enabled:
        principals.update(DEFAULT_PRINCIPALS)

    env_keys = os.environ.get("ROUTER_API_KEYS")
    if env_keys:
        try:
            custom_map = json.loads(env_keys)
            for k, v in custom_map.items():
                principals[k] = AuthenticatedPrincipal(
                    username=v.get("username", "custom_user"),
                    roles=v.get("roles", ["analyst"]),
                    groups=v.get("groups", []),
                    auth_scheme="api_key",
                )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning("Ignoring malformed ROUTER_API_KEYS JSON: %s", exc)
    return principals


def extract_token_from_headers(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None, alias="Authorization"),
) -> str | None:
    """Extracts bearer token or API key from request headers."""
    if x_api_key:
        return x_api_key.strip()
    if authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() in ("bearer", "apikey", "key"):
            return parts[1].strip()
        return authorization.strip()
    return None


def get_current_principal(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None, alias="Authorization"),
) -> AuthenticatedPrincipal:
    """
    FastAPI dependency verifying caller identity via HS256/RS256 JWT or configured API key.
    Fails closed (401) by default when unauthenticated unless ROUTER_DEV_MODE=1 is set
    and ROUTER_REQUIRE_AUTH is not enabled.
    """
    token = extract_token_from_headers(x_api_key, authorization)
    principals = get_configured_principals()

    if token:
        if token.count(".") == 2:
            try:
                claims = verify_jwt_token(token)
            except ValueError as err:
                raise HTTPException(
                    status_code=401,
                    detail=str(err),
                    headers={"WWW-Authenticate": "Bearer"},
                ) from err
            return AuthenticatedPrincipal(
                username=str(claims["sub"]),
                roles=[str(r) for r in claims.get("roles", ["analyst"])],
                groups=[str(g) for g in claims.get("groups", [])],
                is_authenticated=True,
                auth_scheme="jwt",
            )
        if token in principals:
            return principals[token]
        raise HTTPException(
            status_code=401,
            detail="invalid_credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    require_auth = os.environ.get("ROUTER_REQUIRE_AUTH", "false").lower() in ("true", "1", "yes")
    if not is_dev_mode() or require_auth:
        raise HTTPException(
            status_code=401,
            detail="authentication_required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Unauthenticated local dev callers only receive read-only discovery permissions
    return AuthenticatedPrincipal(
        username="anonymous_reader",
        roles=["analyst", "ai_platform_reader"],
        groups=[],
        is_authenticated=False,
        auth_scheme="anonymous_readonly",
    )


class SlidingWindowRateLimiter:
    """Thread-safe per-principal sliding-window rate limiter."""

    def __init__(self, default_rpm: int = 300):
        self.default_rpm = default_rpm
        self._lock = threading.Lock()
        self._requests: dict[str, deque[float]] = {}

    def check(self, key: str, limit_rpm: int | None = None) -> tuple[bool, int]:
        limit = limit_rpm if limit_rpm is not None else int(os.environ.get("ROUTER_RATE_LIMIT_RPM", str(self.default_rpm)))
        now = time.time()
        window_start = now - 60.0
        with self._lock:
            bucket = self._requests.setdefault(key, deque())
            while bucket and bucket[0] < window_start:
                bucket.popleft()
            if len(bucket) >= limit:
                return False, 0
            bucket.append(now)
            return True, max(0, limit - len(bucket))

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()


DEFAULT_RATE_LIMITER = SlidingWindowRateLimiter()


def enforce_rate_limit(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> AuthenticatedPrincipal:
    """FastAPI dependency enforcing per-principal rate limits."""
    allowed, _ = DEFAULT_RATE_LIMITER.check(f"{principal.auth_scheme}:{principal.username}")
    if not allowed:
        raise HTTPException(status_code=429, detail="rate_limit_exceeded")
    return principal


class HITLGovernanceRules:
    """Security rules governing Human-in-the-Loop approval workflows."""

    ALLOWED_APPROVER_ROLES: ClassVar[set[str]] = {"super_admin", "platform_admin", "compliance_officer", "hitl_approver"}
    REQUIRED_APPROVER_GROUP: str = "hitl_approvers"

    @staticmethod
    def compute_arguments_hash(tool_name: str, arguments: dict[str, Any] | None = None) -> str:
        """Computes a canonical SHA-256 binding hash over tool_name and arguments."""
        canonical_payload = {
            "tool_name": tool_name,
            "arguments": arguments or {},
        }
        serialized = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def validate_resolution(
        cls,
        ticket: dict[str, Any],
        reviewer: str,
        reviewer_roles: list[str] | None = None,
        reviewer_groups: list[str] | None = None,
    ) -> tuple[bool, str | None]:
        """
        Validates whether a reviewer is allowed to approve/reject a ticket.
        Enforces separation of duties (no self-approval), approver role check,
        and mandatory membership in a dedicated approver group (`hitl_approvers`)
        so peer operator sock-puppet accounts cannot approve each other's tickets.
        """
        # 1. Separation of duties check
        requested_by = ticket.get("requested_by")
        if not reviewer or (requested_by and reviewer == requested_by):
            return False, "self_approval_prohibited"

        # 2. Expiration check
        expires_at_epoch = ticket.get("expires_at_epoch")
        if expires_at_epoch and time.time() > expires_at_epoch:
            return False, "hitl_ticket_expired"

        # 3. Status transition check
        if ticket.get("status") != "PENDING_APPROVAL":
            return False, f"ticket_already_resolved:{ticket.get('status')}"

        # 4. Approver role check (fail closed when roles missing)
        if not reviewer_roles or not any(r in cls.ALLOWED_APPROVER_ROLES for r in reviewer_roles):
            return False, "reviewer_not_authorized"

        # 5. Dedicated approver group check (prevents operator/admin sock-puppet approvals)
        if not reviewer_groups or cls.REQUIRED_APPROVER_GROUP not in reviewer_groups:
            return False, "reviewer_missing_approver_group"

        return True, None

    @classmethod
    def validate_consumption(
        cls,
        ticket: dict[str, Any],
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> tuple[bool, str | None]:
        """
        Validates that a ticket can be consumed to authorize tool execution.
        Enforces expiration, single-use replay prevention, tool target matching,
        and canonical argument hash binding.
        """
        # 1. Expiration check
        expires_at_epoch = ticket.get("expires_at_epoch")
        if expires_at_epoch and time.time() > expires_at_epoch:
            return False, "hitl_ticket_expired"

        # 2. Single-use replay check
        if ticket.get("status") == "CONSUMED":
            return False, "hitl_ticket_already_consumed"

        # 3. Approved status check
        if ticket.get("status") != "APPROVED":
            return False, f"hitl_ticket_not_approved:{ticket.get('status')}"

        # 4. Tool target check
        if ticket.get("tool_name") != tool_name:
            return False, "hitl_ticket_tool_mismatch"

        # 5. Canonical argument hash binding check
        expected_hash = ticket.get("arguments_hash")
        if expected_hash:
            actual_hash = cls.compute_arguments_hash(tool_name=tool_name, arguments=arguments)
            if not hmac.compare_digest(expected_hash, actual_hash):
                return False, "hitl_ticket_arguments_hash_mismatch"

        return True, None
