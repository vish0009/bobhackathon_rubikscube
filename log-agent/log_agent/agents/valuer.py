"""
Value Assessment Agent - Assesses retention value of log templates.

Analyzes access patterns, recency, and classification to determine
retention priority and recommend actions.
"""

from typing import List, Dict
from datetime import datetime, timedelta
from ..models import Classification, ValueScore, LogEntry, Template
from ..config import get_logger

logger = get_logger("system.valuer")


class ValueAssessmentAgent:
    """
    Agent responsible for assessing the retention value of log templates.
    
    Implements:
    - Access pattern analysis (frequency of access)
    - Recency scoring (how old the logs are)
    - Priority assignment based on classification
    - Cost-benefit analysis for retention decisions
    """
    
    def __init__(self):
        """Initialize the value assessment agent."""
        logger.info("system.valuer: Initialized")
    
    def assess(
        self,
        templates: List[Template],
        classifications: List[Classification],
        log_entries: List[LogEntry],
        line_to_template: Dict[str, str]
    ) -> List[ValueScore]:
        """
        Assess the retention value of classified templates.
        
        Args:
            templates: List of extracted templates
            classifications: List of template classifications
            log_entries: Original log entries for access pattern analysis
            line_to_template: Mapping of log_id to template_id
            
        Returns:
            List of value scores with retention recommendations
        """
        logger.info(f"system.valuer: Assessing {len(classifications)} templates")
        
        # Build template-to-logs mapping for analysis
        template_logs: Dict[str, List[LogEntry]] = {}
        for entry in log_entries:
            template_id = line_to_template.get(entry.log_id)
            if template_id:
                if template_id not in template_logs:
                    template_logs[template_id] = []
                template_logs[template_id].append(entry)
        
        # Assess each template
        value_scores = []
        for template, classification in zip(templates, classifications):
            logs = template_logs.get(template.template_id, [])
            value_score = self._assess_template(template, classification, logs)
            value_scores.append(value_score)
        
        logger.info(f"system.valuer: Assessment complete")
        return value_scores
    
    def _assess_template(
        self,
        template: Template,
        classification: Classification,
        logs: List[LogEntry]
    ) -> ValueScore:
        """
        Assess a single template's retention value.
        
        Args:
            template: Template to assess
            classification: Classification of the template
            logs: Log entries matching this template
            
        Returns:
            ValueScore with priority and recommendation
        """
        # Calculate component scores
        severity_score = self._calculate_severity_score(classification.severity)
        access_score = self._calculate_access_score(logs)
        recency_score = self._calculate_recency_score(template)
        signal_score = self._calculate_signal_score(classification.signal_quality)
        environment_score = self._calculate_environment_score(logs)
        
        # Weighted combination
        # Severity is most important (40%), then access (25%), recency (20%), signal (10%), environment (5%)
        final_score = (
            severity_score * 0.40 +
            access_score * 0.25 +
            recency_score * 0.20 +
            signal_score * 0.10 +
            environment_score * 0.05
        )
        
        # Determine priority and action based on final score
        if final_score >= 0.7:
            priority = "HIGH"
            action = "RETAIN"
        elif final_score >= 0.4:
            priority = "MEDIUM"
            action = "ARCHIVE"
        else:
            priority = "LOW"
            action = "DELETE"
        
        # Build reasoning
        reasoning = self._build_reasoning(
            classification, logs, template,
            severity_score, access_score, recency_score, signal_score, environment_score
        )
        
        return ValueScore(
            template_id=template.template_id,
            priority=priority,
            recommended_action=action,
            reasoning=reasoning,
            score=final_score
        )
    
    def _calculate_severity_score(self, severity: str) -> float:
        """Calculate score based on log severity."""
        severity_map = {
            "CRITICAL": 1.0,
            "HIGH": 0.8,
            "MEDIUM": 0.5,
            "LOW": 0.3,
            "VERY_LOW": 0.1
        }
        return severity_map.get(severity, 0.3)
    
    def _calculate_access_score(self, logs: List[LogEntry]) -> float:
        """Calculate score based on access patterns."""
        if not logs:
            return 0.0
        
        # Average access count across all logs in this template
        total_access = sum(log.access_count_last_30_days for log in logs)
        avg_access = total_access / len(logs)
        
        # Normalize: 0 accesses = 0.0, 20+ accesses = 1.0
        normalized = min(avg_access / 20.0, 1.0)
        return normalized
    
    def _calculate_recency_score(self, template: Template) -> float:
        """Calculate score based on how recent the logs are."""
        now = datetime.utcnow()
        age_days = (now - template.last_seen.replace(tzinfo=None)).days
        
        # Recent logs (< 7 days) = 1.0, old logs (> 90 days) = 0.0
        if age_days <= 7:
            return 1.0
        elif age_days >= 90:
            return 0.0
        else:
            # Linear decay from 1.0 to 0.0 over 7-90 days
            return 1.0 - ((age_days - 7) / 83.0)
    
    def _calculate_signal_score(self, signal_quality: str) -> float:
        """Calculate score based on signal quality."""
        signal_map = {
            "HIGH": 1.0,
            "MEDIUM": 0.6,
            "LOW": 0.3
        }
        return signal_map.get(signal_quality, 0.3)
    
    def _calculate_environment_score(self, logs: List[LogEntry]) -> float:
        """Calculate score based on environment (prod > staging > dev)."""
        if not logs:
            return 0.0
        
        # Check if any logs are from production
        has_prod = any(log.environment == "prod" for log in logs)
        has_staging = any(log.environment == "staging" for log in logs)
        
        if has_prod:
            return 1.0
        elif has_staging:
            return 0.6
        else:
            return 0.3
    
    def _build_reasoning(
        self,
        classification: Classification,
        logs: List[LogEntry],
        template: Template,
        severity_score: float,
        access_score: float,
        recency_score: float,
        signal_score: float,
        environment_score: float
    ) -> str:
        """Build human-readable reasoning for the assessment."""
        reasons = []
        
        # Severity
        reasons.append(f"Severity: {classification.severity} (score: {severity_score:.2f})")
        
        # Access patterns
        if logs:
            avg_access = sum(log.access_count_last_30_days for log in logs) / len(logs)
            reasons.append(f"Avg access: {avg_access:.1f}/30d (score: {access_score:.2f})")
        
        # Recency
        now = datetime.utcnow()
        age_days = (now - template.last_seen.replace(tzinfo=None)).days
        reasons.append(f"Age: {age_days}d (score: {recency_score:.2f})")
        
        # Signal quality
        reasons.append(f"Signal: {classification.signal_quality} (score: {signal_score:.2f})")
        
        # Environment
        if logs:
            envs = set(log.environment for log in logs)
            reasons.append(f"Environments: {', '.join(envs)} (score: {environment_score:.2f})")
        
        return "; ".join(reasons)

# Made with Bob
