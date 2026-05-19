"""
ValueScore model representing the assessed value and retention priority of a log template.
"""

from pydantic import BaseModel, Field
from typing import Literal


class ValueScore(BaseModel):
    """
    Represents the value assessment for a log template.
    
    Value assessments consider access patterns, recency, and classification
    to determine retention priority and recommended actions.
    
    Attributes:
        template_id: The template this value score applies to
        priority: Retention priority (HIGH, MEDIUM, LOW)
        recommended_action: Suggested action (RETAIN, ARCHIVE, DELETE, COMPRESS)
        reasoning: Human-readable explanation of the assessment
        score: Numeric value score (0.0 to 1.0, higher = more valuable)
    """
    template_id: str = Field(..., description="The template this value score applies to")
    priority: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        ...,
        description="Retention priority"
    )
    recommended_action: Literal["RETAIN", "ARCHIVE", "DELETE", "COMPRESS"] = Field(
        ...,
        description="Suggested action"
    )
    reasoning: str = Field(
        ...,
        description="Human-readable explanation of the assessment"
    )
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Numeric value score (0.0 to 1.0, higher = more valuable)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "template_id": "template_abc123",
                "priority": "HIGH",
                "recommended_action": "RETAIN",
                "reasoning": "High severity error with recent access pattern",
                "score": 0.85
            }
        }

# Made with Bob
