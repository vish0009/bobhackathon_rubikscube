"""
Decision/Policy Agent - Makes final retention decisions based on policy.

Applies policy rules and compliance overrides to value assessments.
"""

from typing import List, Dict, Optional
from ..models import ValueScore, Decision, Policy, LogEntry, Template
from ..config import get_logger

logger = get_logger("system.decider")


class DecisionAgent:
    """
    Agent responsible for making final retention decisions.
    
    Implements:
    - Policy rules engine (retention by log level)
    - Compliance checking (tag-based overrides)
    - Environment-specific rules
    - Cost optimization logic
    """
    
    def __init__(self, policy: Policy):
        """
        Initialize the decision agent.
        
        Args:
            policy: Policy configuration
        """
        self.policy = policy
        logger.info("system.decider: Initialized")
    
    def decide(
        self,
        value_scores: List[ValueScore],
        log_entries: List[LogEntry],
        templates: List[Template],
        line_to_template: Dict[str, str]
    ) -> List[Decision]:
        """
        Make final retention decisions based on policy.
        
        Args:
            value_scores: List of value assessments
            log_entries: Original log entries for policy context
            templates: List of templates
            line_to_template: Mapping of log_id to template_id
            
        Returns:
            List of final decisions
        """
        logger.info(f"system.decider: Processing {len(value_scores)} value scores")
        
        # Build template-to-logs mapping
        template_logs: Dict[str, List[LogEntry]] = {}
        for entry in log_entries:
            template_id = line_to_template.get(entry.log_id)
            if template_id:
                if template_id not in template_logs:
                    template_logs[template_id] = []
                template_logs[template_id].append(entry)
        
        # Make decisions for each value score
        decisions = []
        for value_score in value_scores:
            logs = template_logs.get(value_score.template_id, [])
            decision = self._make_decision(value_score, logs)
            decisions.append(decision)
        
        # Log statistics
        override_count = sum(1 for d in decisions if d.policy_override)
        logger.info(
            f"system.decider: Decisions complete - "
            f"{override_count} policy overrides applied"
        )
        
        return decisions
    
    def _make_decision(
        self,
        value_score: ValueScore,
        logs: List[LogEntry]
    ) -> Decision:
        """
        Make a decision for a single template.
        
        Args:
            value_score: Value assessment for the template
            logs: Log entries matching this template
            
        Returns:
            Final decision
        """
        # Check for compliance overrides first (highest priority)
        compliance_decision = self._check_compliance_override(logs)
        if compliance_decision:
            return compliance_decision
        
        # Check environment-specific rules
        environment_decision = self._check_environment_rules(value_score, logs)
        if environment_decision:
            return environment_decision
        
        # Check retention rules by log level
        retention_decision = self._check_retention_rules(value_score, logs)
        if retention_decision:
            return retention_decision
        
        # Default: accept value assessment recommendation
        return Decision(
            template_id=value_score.template_id,
            action=value_score.recommended_action,
            reasoning=f"Value assessment accepted: {value_score.reasoning}",
            policy_override=False,
            policy_rule_applied=None
        )
    
    def _check_compliance_override(
        self,
        logs: List[LogEntry]
    ) -> Optional[Decision]:
        """
        Check if any logs have compliance tags requiring override.
        
        Args:
            logs: Log entries to check
            
        Returns:
            Decision if compliance override applies, None otherwise
        """
        if not logs:
            return None
        
        # Check if any log has compliance tags
        for log in logs:
            if hasattr(log, 'tags') and log.tags:
                has_compliance_tag = any(tag in {"compliance", "audit"} for tag in log.tags)
                if not has_compliance_tag:
                    continue

                service = log.service
                if service in self.policy.compliance_overrides:
                    override = self.policy.compliance_overrides[service]
                    reason = override.get("reason", "Compliance retention policy")
                    retention_days = override.get("retention_days", "unknown")
                    tier = override.get("tier", "hot")
                    return Decision(
                        template_id="unknown",  # overwritten by caller when needed
                        action="RETAIN",
                        reasoning=(
                            f"Compliance override: {reason} "
                            f"(retain {retention_days} days in {tier} tier)"
                        ),
                        policy_override=True,
                        policy_rule_applied=f"compliance_override:{service}"
                    )
        
        return None
    
    def _check_environment_rules(
        self,
        value_score: ValueScore,
        logs: List[LogEntry]
    ) -> Optional[Decision]:
        """
        Check environment-specific retention rules.
        
        Args:
            value_score: Value assessment
            logs: Log entries to check
            
        Returns:
            Decision if environment rule applies, None otherwise
        """
        if not logs:
            return None
        
        # Get the most restrictive environment (prod > staging > dev)
        environments = set(log.environment for log in logs)
        
        if "prod" in environments:
            env = "prod"
        elif "staging" in environments:
            env = "staging"
        elif "dev" in environments:
            env = "dev"
        else:
            return None
        
        # Check if environment has specific rules
        if env in self.policy.environment_rules:
            env_rule = self.policy.environment_rules[env]
            min_retention = env_rule.get("min_retention_days", 0)
            reason = env_rule.get("reason", f"{env} environment minimum retention policy")
            
            # If value assessment recommends DELETE but environment requires retention
            if value_score.recommended_action == "DELETE" and min_retention > 0:
                return Decision(
                    template_id=value_score.template_id,
                    action="ARCHIVE",
                    reasoning=(
                        f"Environment rule override: {reason} "
                        f"(min {min_retention} days). Changed DELETE to ARCHIVE."
                    ),
                    policy_override=True,
                    policy_rule_applied=f"environment_rule:{env}"
                )
        
        return None
    
    def _check_retention_rules(
        self,
        value_score: ValueScore,
        logs: List[LogEntry]
    ) -> Optional[Decision]:
        """
        Check retention rules by log level.
        
        Args:
            value_score: Value assessment
            logs: Log entries to check
            
        Returns:
            Decision if retention rule applies, None otherwise
        """
        if not logs:
            return None
        
        # Get the most severe log level
        log_levels = [log.log_level for log in logs]
        
        # Priority: ERROR > WARN > INFO > DEBUG
        if "ERROR" in log_levels:
            level = "ERROR"
        elif "WARN" in log_levels:
            level = "WARN"
        elif "INFO" in log_levels:
            level = "INFO"
        elif "DEBUG" in log_levels:
            level = "DEBUG"
        else:
            return None
        
        # Check if log level has retention rules
        if level in self.policy.retention_rules:
            rule = self.policy.retention_rules[level]
            if not isinstance(rule, dict):
                return None

            reason = rule.get("reason", f"{level} retention rule")
            days = rule.get("days", "unknown")
            tier = rule.get("tier", "hot")
            
            # For ERROR logs, always RETAIN (override if value assessment says otherwise)
            if level == "ERROR" and value_score.recommended_action != "RETAIN":
                return Decision(
                    template_id=value_score.template_id,
                    action="RETAIN",
                    reasoning=(
                        f"Retention rule override: {reason} "
                        f"(retain {days} days in {tier} tier). "
                        f"Changed {value_score.recommended_action} to RETAIN."
                    ),
                    policy_override=True,
                    policy_rule_applied=f"retention_rule:{level}"
                )
            
            # For WARN logs, at least ARCHIVE
            if level == "WARN" and value_score.recommended_action == "DELETE":
                return Decision(
                    template_id=value_score.template_id,
                    action="ARCHIVE",
                    reasoning=(
                        f"Retention rule override: {reason} "
                        f"(retain {days} days in {tier} tier). "
                        f"Changed DELETE to ARCHIVE."
                    ),
                    policy_override=True,
                    policy_rule_applied=f"retention_rule:{level}"
                )
        
        return None

# Made with Bob
