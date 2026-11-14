"""
Enterprise Authentication (HS256 JWT + API Key), RBAC Role Hierarchy,
Separation-of-Duties & Argument-Hash-Bound HITL Governance, and Rate Limiting.
"""

import base64
import hashlib
import hmac
import json
import os
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Set, Tuple
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, Field


ROLE_HIERARCHY: Dict[str, Set[str]] = {
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


def expand_allowed_roles(user_roles: Optional[List[str]]) -> Set[str]:
    """Expands a caller's roles across the deterministic RBAC hierarchy."""
    if not user_roles:
        return set()
    allowed: Set[str] = set()
    for role in user_roles:
        allowed.add(role)
        allowed.update(ROLE_HIERARCHY.get(role, set()))
    return allowed


def is_role_authorized(required_role: str, user_roles: Optional[List[str]]) -> bool:
    """Checks whether `user_roles` satisfies `required_role` under hierarchy rules."""
    if not user_roles:
        return False
    return required_role in expand_allowed_roles(user_roles)


def _get_jwt_secret() -> str:
    return os.environ.get("ROUTER_JWT_SECRET", "dev-insecure-change-in-prod-enterprise-mcp-router-key")


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def create_jwt_token(
    username: str,
    roles: List[str],
    expires_in_seconds: int = 3600,
    secret: Optional[str] = None,
) -> str:
    """Mints an RFC 7519 HS256 JWT bearing verified subject and RBAC roles."""
    signing_secret = (secret or _get_jwt_secret()).encode("utf-8")
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": username,
        "roles": list(roles),
        "iat": now,
        "exp": now + expires_in_seconds,
        "iss": "enterprise-mcp-router",
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    sig = hmac.new(signing_secret, signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url_encode(sig)}"


def verify_jwt_token(token: str, secret: Optional[str] = None) -> Dict[str, Any]:
    """Verifies an HS256 JWT signature and expiration claim."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("malformed_jwt")
    header_b64, payload_b64, sig_b64 = parts
    signing_secret = (secret or _get_jwt_secret()).encode("utf-8")

    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        if header.get("alg") != "HS256":
            raise ValueError("unsupported_jwt_alg")
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected_sig = _b64url_encode(hmac.new(signing_secret, signing_input, hashlib.sha256).digest())
        if not hmac.compare_digest(expected_sig, sig_b64):
            raise ValueError("invalid_jwt_signature")
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
    return claims


class AuthenticatedPrincipal(BaseModel):
    username: str
    roles: List[str] = Field(default_factory=list)
    is_authenticated: bool = True
    auth_scheme: str = "jwt"

    def has_role(self, required_role: str) -> bool:
        return is_role_authorized(required_role, self.roles)


# Standard enterprise pre-configured principals
DEFAULT_PRINCIPALS: Dict[str, AuthenticatedPrincipal] = {
    "ak-analyst-demo": AuthenticatedPrincipal(
        username="analyst_user",
        roles=["analyst"],
        auth_scheme="api_key",
    ),
    "ak-engineer-demo": AuthenticatedPrincipal(
        username="data_engineer_user",
        roles=["data_engineer", "analyst"],
        auth_scheme="api_key",
    ),
    "ak-admin-demo": AuthenticatedPrincipal(
        username="platform_admin_user",
        roles=["platform_admin", "analyst", "data_engineer"],
        auth_scheme="api_key",
    ),
    "ak-superadmin-demo": AuthenticatedPrincipal(
        username="super_admin_user",
        roles=["super_admin", "platform_admin", "compliance_officer", "data_engineer", "analyst"],
        auth_scheme="api_key",
    ),
}


def get_configured_principals() -> Dict[str, AuthenticatedPrincipal]:
    """Loads principals from env JSON or default demo table."""
    env_keys = os.environ.get("ROUTER_API_KEYS")
    if env_keys:
        try:
            custom_map = json.loads(env_keys)
            principals = dict(DEFAULT_PRINCIPALS)
            for k, v in custom_map.items():
                principals[k] = AuthenticatedPrincipal(
                    username=v.get("username", "custom_user"),
                    roles=v.get("roles", ["analyst"]),
                    auth_scheme="api_key",
                )
            return principals
        except Exception:
            return DEFAULT_PRINCIPALS
    return DEFAULT_PRINCIPALS


def extract_token_from_headers(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> Optional[str]:
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
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> AuthenticatedPrincipal:
    """
    FastAPI dependency to authenticate caller via signed HS256 JWT or API key.
    Unauthenticated requests are rejected with 401 when ROUTER_REQUIRE_AUTH=true,
    or scoped strictly to read-only guest permissions when demo mode is active.
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
    if require_auth:
        raise HTTPException(
            status_code=401,
            detail="authentication_required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Unauthenticated demo callers never receive privileged or mutating roles
    return AuthenticatedPrincipal(
        username="anonymous_reader",
        roles=["analyst", "ai_platform_reader"],
        is_authenticated=False,
        auth_scheme="anonymous_readonly",
    )


class SlidingWindowRateLimiter:
    """Thread-safe per-principal sliding-window rate limiter."""

    def __init__(self, default_rpm: int = 300):
        self.default_rpm = default_rpm
        self._lock = threading.Lock()
        self._requests: Dict[str, Deque[float]] = {}

    def check(self, key: str, limit_rpm: Optional[int] = None) -> Tuple[bool, int]:
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
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> AuthenticatedPrincipal:
    """FastAPI dependency enforcing per-principal rate limits."""
    allowed, _ = DEFAULT_RATE_LIMITER.check(f"{principal.auth_scheme}:{principal.username}")
    if not allowed:
        raise HTTPException(status_code=429, detail="rate_limit_exceeded")
    return principal


class HITLGovernanceRules:
    """Security rules governing Human-in-the-Loop approval workflows."""

    ALLOWED_APPROVER_ROLES: Set[str] = {"platform_admin", "super_admin"}

    @staticmethod
    def compute_arguments_hash(tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> str:
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
        ticket: Dict[str, Any],
        reviewer: str,
        reviewer_roles: Optional[List[str]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates whether a reviewer is allowed to approve/reject a ticket.
        Enforces separation of duties (no self-approval) and approver role hierarchy.
        """
        # 1. Separation of duties check
        requested_by = ticket.get("requested_by")
        if requested_by and reviewer == requested_by:
            return False, "self_approval_prohibited"

        # 2. Expiration check
        expires_at_epoch = ticket.get("expires_at_epoch")
        if expires_at_epoch and time.time() > expires_at_epoch:
            return False, "hitl_ticket_expired"

        # 3. Status transition check
        if ticket.get("status") != "PENDING_APPROVAL":
            return False, f"ticket_already_resolved:{ticket.get('status')}"

        # 4. Approver role check (if reviewer_roles provided)
        if reviewer_roles is not None:
            if not any(r in cls.ALLOWED_APPROVER_ROLES for r in reviewer_roles):
                return False, "reviewer_not_authorized"

        return True, None

    @classmethod
    def validate_consumption(
        cls,
        ticket: Dict[str, Any],
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str]]:
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
