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
            use_llm: Whether to use LLM fallback (requires ANTHROPIC_API_KEY, BOB_API_KEY, or LOCAL_LLM_ENDPOINT)
        """
        self.use_llm = use_llm
        
        # Check for local LLM endpoint first (highest priority)
        self.local_llm_endpoint = os.getenv("LOCAL_LLM_ENDPOINT", "http://127.0.0.1:1234")
        self.use_local_llm = os.getenv("USE_LOCAL_LLM", "true").lower() == "true"
        
        # Confidence threshold for LLM fallback (lower = fewer LLM calls)
        self.llm_confidence_threshold = float(os.getenv("LLM_CONFIDENCE_THRESHOLD", "0.5"))
        
        # Check for API keys - prefer Anthropic, fallback to IBM Bob
        self.api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("BOB_API_KEY")
        self.use_bob_endpoint = bool(os.getenv("BOB_API_KEY")) and not os.getenv("ANTHROPIC_API_KEY")
        self.bob_endpoint = os.getenv("BOB_ENDPOINT", "https://api.us-east.bob.ibm.com")
        
        self.token_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "llm_calls": 0
        }
        
        # Determine which LLM to use
        if self.use_llm:
            if self.use_local_llm:
                logger.info(f"system.classifier: Using local LLM at {self.local_llm_endpoint}")
            elif self.api_key:
                endpoint_type = "IBM Bob" if self.use_bob_endpoint else "Anthropic"
                logger.info(f"system.classifier: Using {endpoint_type} endpoint for LLM fallback")
            else:
                logger.warning(
                    "system.classifier: No LLM endpoint configured, using rules-only mode"
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
        # Threshold can be adjusted via LLM_CONFIDENCE_THRESHOLD env var (default: 0.5)
        if confidence < self.llm_confidence_threshold and self.use_llm:
            logger.info(
                f"system.classifier: Template {template.template_id} has low confidence "
                f"({confidence:.2f} < {self.llm_confidence_threshold}), using LLM fallback"
            )
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
        # Only high confidence if log level is explicitly mapped
        if sample.log_level.upper() in severity_map:
            confidence_factors.append(0.4)
        else:
            confidence_factors.append(0.2)
        
        # Rule 2: Service tags → Category detection
        log_type = "APPLICATION"  # default
        category_confidence = 0.0
        if "compliance" in sample.tags or "audit" in sample.service.lower():
            log_type = "COMPLIANCE"
            category_confidence = 0.5  # High confidence for explicit tags
        elif "security" in sample.tags or "auth" in sample.service.lower():
            log_type = "SECURITY"
            category_confidence = 0.5
        elif "database" in sample.tags or "db" in sample.service.lower():
            log_type = "DATABASE"
            category_confidence = 0.5
        elif any(keyword in template.pattern.lower()
                 for keyword in ["error", "fail", "exception"]):
            log_type = "APPLICATION"
            category_confidence = 0.3  # Medium confidence for pattern matching
        else:
            category_confidence = 0.1  # Low confidence for default
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
        else:  # dev, test, etc.
            signal_quality = "LOW"
            env_confidence = 0.1
        confidence_factors.append(env_confidence)
        
        # Calculate final confidence as average of factors (more conservative)
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
        
        # Route to appropriate LLM endpoint
        if self.use_local_llm:
            return self._llm_classify_local(template, prompt)
        elif self.use_bob_endpoint:
            return self._llm_classify_bob(template, prompt)
        else:
            return self._llm_classify_anthropic(template, prompt)
    
    def _llm_classify_anthropic(
        self, template: Template, prompt: str
    ) -> Classification:
        """Use Anthropic API for classification."""
        try:
            from anthropic import Anthropic
            
            client = Anthropic(api_key=self.api_key)
            
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Track token usage
            usage = getattr(response, "usage", None)
            input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
            output_tokens = getattr(usage, "output_tokens", 0) if usage else 0
            self.token_usage["input_tokens"] += input_tokens
            self.token_usage["output_tokens"] += output_tokens
            self.token_usage["total_tokens"] += input_tokens + output_tokens
            self.token_usage["llm_calls"] += 1

            # Parse response
            response_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    response_text = block.text
                    break
            
            return self._parse_llm_response(template, response_text)
            
        except Exception as e:
            logger.error(f"system.classifier: Anthropic API failed: {e}")
            return self._default_classification(template)
    
    def _llm_classify_local(
        self, template: Template, prompt: str
    ) -> Classification:
        """Use local LLM endpoint for classification."""
        try:
            import requests
            
            response = requests.post(
                f"{self.local_llm_endpoint}/v1/chat/completions",
                headers={
                    "Content-Type": "application/json"
                },
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.7
                },
                timeout=120  # Increased timeout for local LLM (was 30)
            )
            response.raise_for_status()
            
            result_data = response.json()
            
            # Track token usage
            usage = result_data.get("usage", {})
            self.token_usage["input_tokens"] += usage.get("prompt_tokens", 0)
            self.token_usage["output_tokens"] += usage.get("completion_tokens", 0)
            self.token_usage["total_tokens"] += usage.get("total_tokens", 0)
            self.token_usage["llm_calls"] += 1

            # Parse response
            content = result_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            return self._parse_llm_response(template, content)
            
        except Exception as e:
            logger.error(f"system.classifier: Local LLM API failed: {e}")
            return self._default_classification(template)
    
    def _llm_classify_bob(
        self, template: Template, prompt: str
    ) -> Classification:
        """Use IBM Bob API for classification."""
        try:
            import requests
            
            response = requests.post(
                f"{self.bob_endpoint}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-3-5-sonnet-20241022",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200
                },
                timeout=30
            )
            response.raise_for_status()
            
            result_data = response.json()
            
            # Track token usage
            usage = result_data.get("usage", {})
            self.token_usage["input_tokens"] += usage.get("input_tokens", 0)
            self.token_usage["output_tokens"] += usage.get("output_tokens", 0)
            self.token_usage["total_tokens"] += usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
            self.token_usage["llm_calls"] += 1

            # Parse response
            content = result_data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            return self._parse_llm_response(template, content)
            
        except Exception as e:
            logger.error(f"system.classifier: IBM Bob API failed: {e}")
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
                f"system.classifier: LLM classified {template.template_id} as "
                f"{result['type']}/{result['severity']}"
            )
            
            return classification
            
        except Exception as e:
            logger.error(f"system.classifier: Failed to parse LLM response: {e}")
            return self._default_classification(template)
    
    def _default_classification(self, template: Template) -> Classification:
        """Return default classification when LLM fails."""
        return Classification(
            template_id=template.template_id,
            type="APPLICATION",
            severity="LOW",
            signal_quality="LOW",
            confidence=0.3,
            method="default"
        )

# Made with Bob
