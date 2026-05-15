"""
Template model representing a Drain3 extracted log pattern.
"""

from datetime import datetime
from pydantic import BaseModel, Field


class Template(BaseModel):
    """
    Represents a Drain3 extracted log template/pattern.
    
    Templates are the core of template-level processing - all logs matching
    the same template inherit the same classification and decisions.
    
    Attributes:
        template_id: Unique identifier for this template
        pattern: The extracted pattern with wildcards
        match_count: Number of log lines matching this template
        first_seen: When this template was first observed
        last_seen: When this template was last observed
    """
    template_id: str = Field(..., description="Unique identifier for this template")
    pattern: str = Field(..., description="The extracted pattern with wildcards")
    match_count: int = Field(
        default=1,
        ge=1,
        description="Number of log lines matching this template"
    )
    first_seen: datetime = Field(..., description="When this template was first observed")
    last_seen: datetime = Field(..., description="When this template was last observed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "template_id": "template_abc123",
                "pattern": "Database connection failed: timeout after <*> s",
                "match_count": 42,
                "first_seen": "2024-01-15T10:30:00Z",
                "last_seen": "2024-01-15T14:45:00Z"
            }
        }

# Made with Bob
