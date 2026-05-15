"""
AuditEntry model representing an immutable record of an executed action.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from .tier import Tier


class AuditEntry(BaseModel):
    """
    Represents an immutable audit trail entry for an executed action.
    
    Audit entries provide complete traceability of all actions taken
    by the system, including who, what, when, why, and the impact.
    
    Attributes:
        audit_id: Unique identifier for this audit entry
        timestamp: When the action was executed
        template_id: The template this action was performed on
        action: The action that was executed
        affected_log_count: Number of log lines affected
        bytes_freed: Storage space freed (if applicable)
        from_tier: Original storage tier (if tier change)
        to_tier: New storage tier (if tier change)
        executor: Who/what executed the action (system, user, etc.)
        metadata: Additional context and details
    """
    audit_id: str = Field(..., description="Unique identifier for this audit entry")
    timestamp: datetime = Field(..., description="When the action was executed")
    template_id: str = Field(..., description="The template this action was performed on")
    action: str = Field(..., description="The action that was executed")
    affected_log_count: int = Field(
        ...,
        ge=0,
        description="Number of log lines affected"
    )
    bytes_freed: int = Field(
        default=0,
        ge=0,
        description="Storage space freed (if applicable)"
    )
    from_tier: Optional[Tier] = Field(
        default=None,
        description="Original storage tier (if tier change)"
    )
    to_tier: Optional[Tier] = Field(
        default=None,
        description="New storage tier (if tier change)"
    )
    executor: str = Field(
        default="system",
        description="Who/what executed the action"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context and details"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "audit_id": "audit_001",
                "timestamp": "2024-01-15T14:45:00Z",
                "template_id": "template_abc123",
                "action": "ARCHIVE",
                "affected_log_count": 42,
                "bytes_freed": 1048576,
                "from_tier": "hot",
                "to_tier": "cold",
                "executor": "system",
                "metadata": {
                    "reason": "Low access pattern, age > 30 days",
                    "policy_rule": "default_retention"
                }
            }
        }

# Made with Bob
