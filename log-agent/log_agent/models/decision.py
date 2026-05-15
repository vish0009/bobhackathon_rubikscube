"""
Decision model representing the final action to take for a log template.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional


class Decision(BaseModel):
    """
    Represents the final decision for a log template after policy application.
    
    Decisions are made by the Policy/Decision Agent, which may override
    the Value Agent's recommendations based on compliance rules and policies.
    
    Attributes:
        template_id: The template this decision applies to
        action: Final action to take (RETAIN, ARCHIVE, DELETE, COMPRESS)
        reasoning: Human-readable explanation of the decision
        policy_override: Whether policy rules overrode the value assessment
        policy_rule_applied: Name of the policy rule that was applied (if any)
    """
    template_id: str = Field(..., description="The template this decision applies to")
    action: Literal["RETAIN", "ARCHIVE", "DELETE", "COMPRESS"] = Field(
        ...,
        description="Final action to take"
    )
    reasoning: str = Field(
        ...,
        description="Human-readable explanation of the decision"
    )
    policy_override: bool = Field(
        default=False,
        description="Whether policy rules overrode the value assessment"
    )
    policy_rule_applied: Optional[str] = Field(
        default=None,
        description="Name of the policy rule that was applied (if any)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "template_id": "template_abc123",
                "action": "RETAIN",
                "reasoning": "Compliance override: audit-service logs must be retained",
                "policy_override": True,
                "policy_rule_applied": "compliance_audit_retention"
            }
        }

# Made with Bob
