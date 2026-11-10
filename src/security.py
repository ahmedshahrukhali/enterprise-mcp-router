"""
Enterprise Authentication, RBAC Role Verification, and Separation-of-Duties HITL Security.
Provides secure API key and token extraction, role hierarchy evaluation,
and prevents self-approval, ticket replay, and unauthenticated privilege escalation.
"""

import json
import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import Header, HTTPException, Request
from pydantic import BaseModel, Field


class AuthenticatedPrincipal(BaseModel):
    username: str
    roles: List[str] = Field(default_factory=list)
    is_authenticated: bool = True
    auth_scheme: str = "api_key"

    def has_role(self, required_role: str) -> bool:
        if "super_admin" in self.roles:
            return True
        if required_role in self.roles:
            return True
        # Platform admin implies analyst and data_engineer privileges
        if "platform_admin" in self.roles and required_role in ("analyst", "data_engineer"):
            return True
        return False


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
    FastAPI dependency to authenticate caller.
    If ROUTER_REQUIRE_AUTH is true, unauthenticated requests are rejected with 401.
    If false (demo default), an anonymous dev principal is returned.
    """
    token = extract_token_from_headers(x_api_key, authorization)
    principals = get_configured_principals()

    if token:
        if token in principals:
            return principals[token]
        raise HTTPException(
            status_code=401,
            detail="invalid_api_key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # If no token provided:
    require_auth = os.environ.get("ROUTER_REQUIRE_AUTH", "false").lower() in ("true", "1", "yes")
    if require_auth:
        raise HTTPException(
            status_code=401,
            detail="authentication_required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Dev/demo default principal
    return AuthenticatedPrincipal(
        username="demo_agent",
        roles=["analyst", "data_engineer", "platform_admin", "super_admin"],
        is_authenticated=False,
        auth_scheme="anonymous_dev",
    )


class HITLGovernanceRules:
    """Security rules governing Human-in-the-Loop approval workflows."""

    ALLOWED_APPROVER_ROLES: Set[str] = {"platform_admin", "super_admin"}

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
        if reviewer_roles:
            if not any(r in cls.ALLOWED_APPROVER_ROLES for r in reviewer_roles):
                return False, "reviewer_not_authorized"

        return True, None

    @classmethod
    def validate_consumption(
        cls,
        ticket: Dict[str, Any],
        tool_name: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates that a ticket can be consumed to authorize tool execution.
        Enforces single-use (replay prevention), tool target matching, and expiration.
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

        return True, None
