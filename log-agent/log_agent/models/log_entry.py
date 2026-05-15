"""
LogEntry model representing a single log line with metadata.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class LogEntry(BaseModel):
    """
    Represents a single log entry with associated metadata.
    
    Attributes:
        log_id: Unique identifier for this log entry
        timestamp: When the log was generated
        service: Service that generated the log
        environment: Environment (prod, staging, dev, etc.)
        log_level: Log severity level (ERROR, WARN, INFO, DEBUG, etc.)
        message: The actual log message content
        access_count_last_30_days: Number of times accessed in last 30 days
        tags: Optional list of tags for categorization (e.g., compliance, security)
        template_id: Optional Drain3 template ID after classification
    """
    log_id: str = Field(..., description="Unique identifier for this log entry")
    timestamp: datetime = Field(..., description="When the log was generated")
    service: str = Field(..., description="Service that generated the log")
    environment: str = Field(..., description="Environment (prod, staging, dev)")
    log_level: str = Field(..., description="Log severity level")
    message: str = Field(..., description="The actual log message content")
    access_count_last_30_days: int = Field(
        default=0, 
        ge=0,
        description="Number of times accessed in last 30 days"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorization (compliance, security, etc.)"
    )
    template_id: Optional[str] = Field(
        default=None,
        description="Drain3 template ID after classification"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "log_id": "log_001",
                "timestamp": "2024-01-15T10:30:00Z",
                "service": "api-gateway",
                "environment": "prod",
                "log_level": "ERROR",
                "message": "Database connection failed: timeout after 30s",
                "access_count_last_30_days": 5,
                "tags": ["database", "critical"],
                "template_id": "template_abc123"
            }
        }

# Made with Bob
