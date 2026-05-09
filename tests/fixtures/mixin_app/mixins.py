"""Fixture: mixin classes that contribute DB columns."""
from __future__ import annotations


class TimestampMixin:
    """Adds created_at and updated_at to any model."""
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=True)


class TenantMixin:
    """Adds tenant_id FK to any model."""
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False)
