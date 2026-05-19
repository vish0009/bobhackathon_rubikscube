"""
Classification model representing the categorization of a log template.
"""

from pydantic import BaseModel, Field
from typing import Literal


class Classification(BaseModel):
    """
    Represents the classification result for a log template.
    
    Classifications are made at the template level, not individual log lines.
    Each log line inherits the classification from its template.
    
    Attributes:
        template_id: The template this classification applies to
        type: Category of the log (APPLICATION, DATABASE, SECURITY, COMPLIANCE, etc.)
        severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW, VERY_LOW)
        signal_quality: Quality of signal for observability (HIGH, MEDIUM, LOW)
        confidence: Confidence score of the classification (0.0 to 1.0)
        method: How classification was determined (rule, llm, default)
    """
    template_id: str = Field(..., description="The template this classification applies to")
    type: str = Field(
        ...,
        description="Category of the log (APPLICATION, DATABASE, SECURITY, COMPLIANCE, etc.)"
    )
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "VERY_LOW"] = Field(
        ...,
        description="Severity level"
    )
    signal_quality: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        ...,
        description="Quality of signal for observability"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score of the classification (0.0 to 1.0)"
    )
    method: Literal["rule", "llm", "default"] = Field(
        ...,
        description="How classification was determined"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "template_id": "template_abc123",
                "type": "DATABASE",
                "severity": "HIGH",
                "signal_quality": "HIGH",
                "confidence": 0.95,
                "method": "rule"
            }
        }

# Made with Bob
