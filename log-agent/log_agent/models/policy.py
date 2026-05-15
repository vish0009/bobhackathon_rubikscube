"""
Policy model representing retention rules and compliance overrides.
"""

from typing import Dict, Any
from pydantic import BaseModel, Field


class Policy(BaseModel):
    """
    Represents the policy configuration for log retention and management.
    
    Policies are loaded from JSON files and provide guardrails for
    the Decision Agent, including compliance overrides and cost considerations.
    
    Attributes:
        retention_rules: Rules for retention by log level, environment, etc.
        compliance_overrides: Service/tag-based compliance requirements
        storage_costs: Cost per GB for different storage tiers
        environment_rules: Environment-specific retention policies
    """
    retention_rules: Dict[str, Any] = Field(
        ...,
        description="Rules for retention by log level, environment, etc."
    )
    compliance_overrides: Dict[str, Any] = Field(
        default_factory=dict,
        description="Service/tag-based compliance requirements"
    )
    storage_costs: Dict[str, float] = Field(
        default_factory=dict,
        description="Cost per GB for different storage tiers"
    )
    environment_rules: Dict[str, Any] = Field(
        default_factory=dict,
        description="Environment-specific retention policies"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "retention_rules": {
                    "ERROR": {"days": 90, "tier": "hot"},
                    "WARN": {"days": 60, "tier": "warm"},
                    "INFO": {"days": 30, "tier": "cold"},
                    "DEBUG": {"days": 7, "tier": "cold"}
                },
                "compliance_overrides": {
                    "audit-service": {
                        "retention_days": 365,
                        "tier": "hot",
                        "reason": "Regulatory compliance requirement"
                    }
                },
                "storage_costs": {
                    "hot": 0.023,
                    "warm": 0.01,
                    "cold": 0.004,
                    "archive": 0.001
                },
                "environment_rules": {
                    "prod": {"min_retention_days": 30},
                    "staging": {"min_retention_days": 14},
                    "dev": {"min_retention_days": 7}
                }
            }
        }

# Made with Bob
