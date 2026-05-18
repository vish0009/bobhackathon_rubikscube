"""
Classification Agent with Bob Shell Integration - Uses local Bob Shell for LLM fallback.

This version uses Bob Shell (the AI assistant) as a subprocess for classification,
avoiding API authentication issues and providing immediate LLM capabilities.
"""

import os
import json
import subprocess
import tempfile
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

from ..models import LogEntry, Template, Classification
from ..config import get_logger

logger = get_logger("system.classifier")


class ClassificationAgentBobShell:
    """
    Agent responsible for classifying log templates using Bob Shell.
    
    Uses a three-tier approach:
    1. Drain3 for template extraction
    2. Rule-based classification for common patterns
    3. Bob Shell fallback for ambiguous cases (via subprocess)
    """
    
    def __init__(self, use_llm: bool = True, bob_shell_path: str = "bob"):
        """
        Initialize the classification agent with Bob Shell integration.
        
        Args:
            use_llm: Whether to use Bob Shell fallback
            bob_shell_path: Path to bob executable (default: "bob" assumes it's in PATH)
        """
        self.use_llm = use_llm
        self.bob_shell_path = bob_shell_path
        
        self.token_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "llm_calls": 0
        }
        
        # Test if Bob Shell is available
        if self.use_llm:
            try:
                result = subprocess.run(
                    [self.bob_shell_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    logger.info(f"system.classifier: Bob Shell available at {self.bob_shell_path}")
                else:
                    logger.warning("system.classifier: Bob Shell not found, using rules-only mode")
                    self.use_llm = False
            except Exception as e:
                logger.warning(f"system.classifier: Bob Shell not available ({e}), using rules-only mode")
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
            f"system.classifier: Initialized (LLM={'Bob Shell' if self.use_llm else 'disabled'})"
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
            f"Rule: {rule_count}, Bob Shell: {llm_count}, Default: {default_count}"
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
        Classify a single template using rules first, then Bob Shell fallback.
        
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
        
        # If confidence is low and Bob Shell is available, use Bob Shell fallback
        if confidence < 0.7 and self.use_llm:
            classification = self._bob_shell_classify(template, sample_entries)
        
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
        confidence_factors = []
        
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
        if sample.log_level.upper() in severity_map:
            confidence_factors.append(0.4)
        else:
            confidence_factors.append(0.2)
        
        # Rule 2: Service tags → Category detection
        log_type = "APPLICATION"  # default
        category_confidence = 0.0
        if "compliance" in sample.tags or "audit" in sample.service.lower():
            log_type = "COMPLIANCE"
            category_confidence = 0.5
        elif "security" in sample.tags or "auth" in sample.service.lower():
            log_type = "SECURITY"
            category_confidence = 0.5
        elif "database" in sample.tags or "db" in sample.service.lower():
            log_type = "DATABASE"
            category_confidence = 0.5
        elif any(keyword in template.pattern.lower()
                 for keyword in ["error", "fail", "exception"]):
            log_type = "APPLICATION"
            category_confidence = 0.3
        else:
            category_confidence = 0.1
        confidence_factors.append(category_confidence)
        
        # Rule 3: Environment → Signal quality
        signal_quality = "MEDIUM"  # default
        env_confidence = 0.0
        if sample.environment.lower() == "prod":
            signal_quality = "HIGH"
            env_confidence = 0.3
        elif sample.environment.lower() in ["staging", "stage"]:
            signal_quality = "MEDIUM"
            env_confidence = 0.2
        else:
            signal_quality = "LOW"
            env_confidence = 0.1
        confidence_factors.append(env_confidence)
        
        # Calculate final confidence as average
        confidence = sum(confidence_factors) / len(confidence_factors)
        
        classification = Classification(
            template_id=template.template_id,
            type=log_type,
            severity=severity,
            signal_quality=signal_quality,
            confidence=confidence,
            method="rule"
        )
        
        return classification, confidence
    
    def _bob_shell_classify(
        self, template: Template, sample_entries: List[LogEntry]
    ) -> Classification:
        """
        Use Bob Shell to classify ambiguous templates.
        
        Args:
            template: Template to classify
            sample_entries: Sample log entries for context
            
        Returns:
            Classification result
        """
        # Prepare context
        samples_text = "\n".join([
            f"- [{e.log_level}] {e.service} ({e.environment}): {e.message}"
            for e in sample_entries[:3]
        ])
        
        prompt = f"""Classify this log template for retention management.

Template Pattern: {template.pattern}

Sample Log Entries:
{samples_text}

Provide classification in JSON format ONLY (no markdown, no explanation):
{{
  "type": "APPLICATION|DATABASE|SECURITY|COMPLIANCE|INFRASTRUCTURE",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW|VERY_LOW",
  "signal_quality": "HIGH|MEDIUM|LOW"
}}

Consider:
- Type: What system component does this relate to?
- Severity: How critical is this log for debugging/monitoring?
- Signal Quality: How valuable is this for observability?

Respond with ONLY the JSON object, nothing else."""
        
        try:
            # Create temporary file for prompt
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(prompt)
                prompt_file = f.name
            
            try:
                # Call Bob Shell with the prompt
                result = subprocess.run(
                    [self.bob_shell_path, "ask", prompt],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    response_text = result.stdout.strip()
                    
                    # Track usage (approximate)
                    self.token_usage["llm_calls"] += 1
                    self.token_usage["input_tokens"] += len(prompt.split())
                    self.token_usage["output_tokens"] += len(response_text.split())
                    self.token_usage["total_tokens"] += len(prompt.split()) + len(response_text.split())
                    
                    return self._parse_llm_response(template, response_text)
                else:
                    logger.error(f"system.classifier: Bob Shell failed: {result.stderr}")
                    return self._default_classification(template)
                    
            finally:
                # Clean up temp file
                try:
                    os.unlink(prompt_file)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"system.classifier: Bob Shell execution failed: {e}")
            return self._default_classification(template)
    
    def _parse_llm_response(
        self, template: Template, response_text: str
    ) -> Classification:
        """Parse LLM response and create classification."""
        try:
            # Extract JSON from response (may have markdown code blocks)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Find JSON object in response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                response_text = response_text[start_idx:end_idx]
            
            result = json.loads(response_text)
            
            classification = Classification(
                template_id=template.template_id,
                type=result["type"],
                severity=result["severity"],
                signal_quality=result["signal_quality"],
                confidence=0.9,  # High confidence for LLM results
                method="llm"
            )
            
            logger.debug(
                f"system.classifier: Bob Shell classified {template.template_id} as "
                f"{result['type']}/{result['severity']}"
            )
            
            return classification
            
        except Exception as e:
            logger.error(f"system.classifier: Failed to parse Bob Shell response: {e}")
            logger.debug(f"system.classifier: Response was: {response_text[:200]}")
            return self._default_classification(template)
    
    def _default_classification(self, template: Template) -> Classification:
        """Return default classification when Bob Shell fails."""
        return Classification(
            template_id=template.template_id,
            type="APPLICATION",
            severity="LOW",
            signal_quality="LOW",
            confidence=0.3,
            method="default"
        )

# Made with Bob Shell
