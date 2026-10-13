"""Credential-scoped partitions, not a user-account/IAM implementation."""
from contextvars import ContextVar

tenant_context: ContextVar[str] = ContextVar("axiom_tenant", default="local")


def current_tenant() -> str:
    return tenant_context.get()