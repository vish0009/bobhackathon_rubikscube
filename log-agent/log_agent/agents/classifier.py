"""
Classification Agent - Classifies log templates using rules and LLM fallback.

This agent implements template-level processing to dramatically reduce costs:
- Extracts templates using Drain3
- Applies rule-based classification first (80%+ coverage)
- Falls back to LLM only for ambiguous templates
- Maintains line-to-template mapping for final output
"""

import os
import json
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

from ..models import LogEntry, Template, Classification
from ..config import get_logger

logger = get_logger("system.classifier")


class ClassificationAgent:
    """
    Agent responsible for classifying log templates.
    
    Uses a three-tier approach:
    1. Drain3 for template extraction
    2. Rule-based classification for common patterns
    3. LLM fallback for ambiguous cases
    """
    
    def __init__(self, use_llm: bool = True):
        """
        Initialize the classification agent.
        
        Args:
            use_llm: Whether to use LLM fallback (requires ANTHROPIC_API_KEY)
        """
        self.use_llm = use_llm
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        
        if self.use_llm and not self.api_key:
            logger.warning(
                "system.classifier: No ANTHROPIC_API_KEY found, using rules-only mode"
            )
            self.use_llm = False
        
        # Initialize Drain3 with default config
        config = TemplateMinerConfig()
        config.load({
            "drain": {
                "depth": 4,
                "sim_th": 0.4,
                "max_children": 100,
                "max_clusters": 1024
            }
        })
        self.template_miner = TemplateMiner(config=config)
        
        # Cache for classifications to avoid re-processing
        self.classification_cache: Dict[str, Classification] = {}
        
        logger.info(
            f"system.classifier: Initialized (LLM={'enabled' if self.use_llm else 'disabled'})"
        )
    
    def classify(self, log_entries: List[LogEntry]) -> Tuple[
        List[Template],
        List[Classification],
        Dict[str, str]
    ]:
        """
        Classify a batch of log entries.
        
        Returns templates, classifications, and line-to-template mapping.
        
        Args:
            log_entries: List of log entries to classify
            
        Returns:
            Tuple of (templates, classifications, line_to_template_map)
            where line_to_template_map is {log_id: template_id}
        """
        logger.info(f"system.classifier: Processing {len(log_entries)} log entries")
        
        # Step 1: Extract templates using Drain3
        templates, line_to_template = self._extract_templates(log_entries)
        logger.info(f"system.classifier: Extracted {len(templates)} unique templates")
        
        # Step 2: Classify each template
        classifications = []
        for template in templates:
            classification = self._classify_template(template, log_entries)
            classifications.append(classification)
        
        # Log statistics
        rule_count = sum(1 for c in classifications if c.method == "rule")
        llm_count = sum(1 for c in classifications if c.method == "llm")
        default_count = sum(1 for c in classifications if c.method == "default")
        
        logger.info(
            f"system.classifier: Classification complete - "
            f"Rule: {rule_count}, LLM: {llm_count}, Default: {default_count}"
        )
        
        return templates, classifications, line_to_template
    
    def _extract_templates(
        self, log_entries: List[LogEntry]
    ) -> Tuple[List[Template], Dict[str, str]]:
        """
        Extract templates from log entries using Drain3.
        
        Returns:
            Tuple of (templates, line_to_template_map)
        """
        templates_dict: Dict[str, Template] = {}
        line_to_template: Dict[str, str] = {}
        
        for entry in log_entries:
            # Add log message to Drain3
            result = self.template_miner.add_log_message(entry.message)
            
            template_id = f"template_{result['cluster_id']}"
            
            # Create or update template
            if template_id not in templates_dict:
                templates_dict[template_id] = Template(
                    template_id=template_id,
                    pattern=result["template_mined"],
                    match_count=1,
                    first_seen=entry.timestamp,
                    last_seen=entry.timestamp
                )
            else:
                # Update existing template
                template = templates_dict[template_id]
                template.match_count += 1
                template.last_seen = max(template.last_seen, entry.timestamp)
            
            # Map log entry to template
            line_to_template[entry.log_id] = template_id
        
        return list(templates_dict.values()), line_to_template
    
    def _classify_template(
        self, template: Template, log_entries: List[LogEntry]
    ) -> Classification:
        """
        Classify a single template using rules first, then LLM fallback.
        
        Args:
            template: Template to classify
            log_entries: All log entries (for context)
            
        Returns:
            Classification result
        """
        # Check cache first
        if template.template_id in self.classification_cache:
            return self.classification_cache[template.template_id]
        
        # Get sample log entries for this template
        template_cluster_id = int(template.template_id.split("_")[1])
        sample_entries = []
        for e in log_entries:
            match_result = self.template_miner.match(e.message)
            if match_result and match_result.cluster_id == template_cluster_id:
                sample_entries.append(e)
                if len(sample_entries) >= 3:  # Take up to 3 samples
                    break
        
        # Try rule-based classification first
        classification, confidence = self._rule_based_classify(template, sample_entries)
        
        # If confidence is low and LLM is available, use LLM fallback
        if confidence < 0.7 and self.use_llm:
            classification = self._llm_classify(template, sample_entries)
        
        # Cache the result
        self.classification_cache[template.template_id] = classification
        
        return classification
    
    def _rule_based_classify(
        self, template: Template, sample_entries: List[LogEntry]
    ) -> Tuple[Classification, float]:
        """
        Apply rule-based classification logic.
        
        Returns:
            Tuple of (classification, confidence_score)
        """
        if not sample_entries:
            # Default classification
            return Classification(
                template_id=template.template_id,
                type="APPLICATION",
                severity="LOW",
                signal_quality="LOW",
                confidence=0.3,
                method="default"
            ), 0.3
        
        # Use first sample for classification
        sample = sample_entries[0]
        confidence = 0.0
        
        # Rule 1: Log level → Severity mapping
        severity_map = {
            "CRITICAL": "CRITICAL",
            "FATAL": "CRITICAL",
            "ERROR": "HIGH",
            "WARN": "MEDIUM",
            "WARNING": "MEDIUM",
            "INFO": "LOW",
            "DEBUG": "VERY_LOW",
            "TRACE": "VERY_LOW"
        }
        severity = severity_map.get(sample.log_level.upper(), "LOW")
        confidence += 0.3
        
        # Rule 2: Service tags → Category detection
        log_type = "APPLICATION"  # default
        if "compliance" in sample.tags or "audit" in sample.service.lower():
            log_type = "COMPLIANCE"
            confidence += 0.4
        elif "security" in sample.tags or "auth" in sample.service.lower():
            log_type = "SECURITY"
            confidence += 0.4
        elif "database" in sample.tags or "db" in sample.service.lower():
            log_type = "DATABASE"
            confidence += 0.4
        elif any(keyword in template.pattern.lower() 
                 for keyword in ["error", "fail", "exception"]):
            log_type = "APPLICATION"
            confidence += 0.2
        else:
            confidence += 0.1
        
        # Rule 3: Environment → Signal quality
        signal_quality = "MEDIUM"  # default
        if sample.environment.lower() == "prod":
            signal_quality = "HIGH"
            confidence += 0.3
        elif sample.environment.lower() in ["staging", "stage"]:
            signal_quality = "MEDIUM"
            confidence += 0.2
        else:  # dev, test, etc.
            signal_quality = "LOW"
            confidence += 0.1
        
        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)
        
        classification = Classification(
            template_id=template.template_id,
            type=log_type,
            severity=severity,
            signal_quality=signal_quality,
            confidence=confidence,
            method="rule"
        )
        
        return classification, confidence
    
    def _llm_classify(
        self, template: Template, sample_entries: List[LogEntry]
    ) -> Classification:
        """
        Use LLM to classify ambiguous templates.
        
        Args:
            template: Template to classify
            sample_entries: Sample log entries for context
            
        Returns:
            Classification result
        """
        try:
            from anthropic import Anthropic
            
            client = Anthropic(api_key=self.api_key)
            
            # Prepare context
            samples_text = "\n".join([
                f"- [{e.log_level}] {e.service} ({e.environment}): {e.message}"
                for e in sample_entries[:3]
            ])
            
            prompt = f"""Classify this log template for retention management.

Template Pattern: {template.pattern}

Sample Log Entries:
{samples_text}

Provide classification in JSON format:
{{
  "type": "APPLICATION|DATABASE|SECURITY|COMPLIANCE|INFRASTRUCTURE",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW|VERY_LOW",
  "signal_quality": "HIGH|MEDIUM|LOW"
}}

Consider:
- Type: What system component does this relate to?
- Severity: How critical is this log for debugging/monitoring?
- Signal Quality: How valuable is this for observability?"""
            
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse LLM response
            result = json.loads(response.content[0].text)
            
            classification = Classification(
                template_id=template.template_id,
                type=result["type"],
                severity=result["severity"],
                signal_quality=result["signal_quality"],
                confidence=0.9,  # High confidence for LLM results
                method="llm"
            )
            
            logger.debug(
                f"system.classifier: LLM classified {template.template_id} as "
                f"{result['type']}/{result['severity']}"
            )
            
            return classification
            
        except Exception as e:
            logger.error(f"system.classifier: LLM classification failed: {e}")
            # Fall back to default
            return Classification(
                template_id=template.template_id,
                type="APPLICATION",
                severity="LOW",
                signal_quality="LOW",
                confidence=0.3,
                method="default"
            )

# Made with Bob
