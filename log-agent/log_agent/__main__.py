"""
CLI entrypoint for the log agent system.

Usage:
    python -m log_agent data/sample_logs.json [data/sample_policy.json]
    
Environment Variables:
    USE_BOB_SHELL=true    - Use Bob Shell for LLM fallback (local inference)
    BOB_SHELL_PATH=path   - Path to bob executable (default: "bob")
    ANTHROPIC_API_KEY=key - Use Anthropic API for LLM fallback
    BOB_API_KEY=key       - Use IBM Bob API for LLM fallback
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime

from .config import setup_logging, get_logger
from .models import LogEntry, Policy
from .agents import ValueAssessmentAgent, DecisionAgent, ExecutionAgent
from .storage import LocalFilesystemBackend

# Import appropriate classifier based on environment
if os.getenv("USE_BOB_SHELL", "false").lower() == "true":
    from .agents.classifier_bob_shell import ClassificationAgentBobShell as ClassificationAgent
    CLASSIFIER_TYPE = "Bob Shell"
else:
    from .agents import ClassificationAgent
    CLASSIFIER_TYPE = "API"

# Setup logging
setup_logging(level="INFO")
logger = get_logger("system.main")


def load_log_entries(file_path: str) -> list[LogEntry]:
    """
    Load log entries from a JSON file.
    
    Args:
        file_path: Path to JSON file containing log entries
        
    Returns:
        List of LogEntry objects
    """
    logger.info(f"system.main: Loading log entries from {file_path}")
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    entries = []
    for item in data:
        # Parse timestamp
        item['timestamp'] = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
        entries.append(LogEntry(**item))
    
    logger.info(f"system.main: Loaded {len(entries)} log entries")
    return entries


def load_policy(file_path: str) -> Policy:
    """
    Load policy from a JSON file.
    
    Args:
        file_path: Path to JSON file containing policy
        
    Returns:
        Policy object
    """
    logger.info(f"system.main: Loading policy from {file_path}")
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    policy = Policy(**data)
    logger.info(f"system.main: Policy loaded")
    return policy


def print_pipeline_summary(
    templates, classifications, value_scores, decisions, audit_entries, line_to_template
):
    """Print a comprehensive summary of the entire pipeline."""
    print("\n" + "="*80)
    print("LOG MANAGEMENT PIPELINE - PHASE 2 COMPLETE")
    print("="*80)
    
    # Overall statistics
    print(f"\n{'OVERALL STATISTICS':^80}")
    print("-"*80)
    print(f"Total log lines processed: {len(line_to_template)}")
    print(f"Unique templates extracted: {len(templates)}")
    print(f"Total logs affected: {sum(a.affected_log_count for a in audit_entries)}")
    print(f"Total bytes freed: {sum(a.bytes_freed for a in audit_entries):,}")
    
    # Classification statistics
    print(f"\n{'CLASSIFICATION STATISTICS':^80}")
    print("-"*80)
    rule_count = sum(1 for c in classifications if c.method == "rule")
    llm_count = sum(1 for c in classifications if c.method == "llm")
    default_count = sum(1 for c in classifications if c.method == "default")
    
    print(f"Rule-based: {rule_count} ({rule_count/len(classifications)*100:.1f}%)")
    print(f"LLM-based:  {llm_count} ({llm_count/len(classifications)*100:.1f}%)")
    print(f"Default:    {default_count} ({default_count/len(classifications)*100:.1f}%)")
    
    # Value assessment statistics
    print(f"\n{'VALUE ASSESSMENT STATISTICS':^80}")
    print("-"*80)
    high_priority = sum(1 for v in value_scores if v.priority == "HIGH")
    medium_priority = sum(1 for v in value_scores if v.priority == "MEDIUM")
    low_priority = sum(1 for v in value_scores if v.priority == "LOW")
    
    print(f"High priority:   {high_priority} ({high_priority/len(value_scores)*100:.1f}%)")
    print(f"Medium priority: {medium_priority} ({medium_priority/len(value_scores)*100:.1f}%)")
    print(f"Low priority:    {low_priority} ({low_priority/len(value_scores)*100:.1f}%)")
    
    # Decision statistics
    print(f"\n{'DECISION STATISTICS':^80}")
    print("-"*80)
    retain_count = sum(1 for d in decisions if d.action == "RETAIN")
    archive_count = sum(1 for d in decisions if d.action == "ARCHIVE")
    delete_count = sum(1 for d in decisions if d.action == "DELETE")
    override_count = sum(1 for d in decisions if d.policy_override)
    
    print(f"RETAIN:  {retain_count} ({retain_count/len(decisions)*100:.1f}%)")
    print(f"ARCHIVE: {archive_count} ({archive_count/len(decisions)*100:.1f}%)")
    print(f"DELETE:  {delete_count} ({delete_count/len(decisions)*100:.1f}%)")
    print(f"Policy overrides: {override_count} ({override_count/len(decisions)*100:.1f}%)")
    
    # Detailed template breakdown
    print(f"\n{'DETAILED TEMPLATE BREAKDOWN':^80}")
    print("-"*80)
    
    for template, classification, value_score, decision, audit in zip(
        templates, classifications, value_scores, decisions, audit_entries
    ):
        print(f"\nTemplate: {template.template_id}")
        print(f"  Pattern: {template.pattern[:65]}...")
        print(f"  Matches: {template.match_count} log lines")
        print(f"  Classification: {classification.severity} / {classification.type} / {classification.signal_quality}")
        print(f"  Value Score: {value_score.score:.2f} ({value_score.priority} priority)")
        print(f"  Decision: {decision.action}" +
              (f" [POLICY OVERRIDE]" if decision.policy_override else ""))
        print(f"  Execution: {audit.affected_log_count} logs, {audit.bytes_freed} bytes freed")
        if decision.policy_override:
            print(f"  Policy Rule: {decision.policy_rule_applied}")
    
    print("\n" + "="*80)


def main():
    """Main CLI entrypoint."""
    if len(sys.argv) < 2:
        print("Usage: python -m log_agent <log_file.json> [policy_file.json]")
        print("\nExample:")
        print("  python -m log_agent data/sample_logs.json data/sample_policy.json")
        print("  python -m log_agent data/sample_logs.json  # Uses default policy")
        sys.exit(1)
    
    log_file = sys.argv[1]
    policy_file = sys.argv[2] if len(sys.argv) > 2 else "data/sample_policy.json"
    
    if not Path(log_file).exists():
        logger.error(f"system.main: File not found: {log_file}")
        sys.exit(1)
    
    if not Path(policy_file).exists():
        logger.error(f"system.main: Policy file not found: {policy_file}")
        sys.exit(1)
    
    try:
        # Load data
        log_entries = load_log_entries(log_file)
        policy = load_policy(policy_file)
        
        # Initialize storage backend
        storage = LocalFilesystemBackend(base_path="./log_storage")
        
        # Initialize agents
        logger.info(f"system.main: Initializing agents (Classifier: {CLASSIFIER_TYPE})")
        
        # Initialize classifier with Bob Shell path if specified
        if CLASSIFIER_TYPE == "Bob Shell":
            bob_shell_path = os.getenv("BOB_SHELL_PATH", "bob")
            classifier = ClassificationAgent(use_llm=True, bob_shell_path=bob_shell_path)
            logger.info(f"system.main: Using Bob Shell at: {bob_shell_path}")
        else:
            classifier = ClassificationAgent(use_llm=True)
        
        valuer = ValueAssessmentAgent()
        decider = DecisionAgent(policy)
        executor = ExecutionAgent(storage)
        
        # Run pipeline
        logger.info("system.main: Starting pipeline")
        
        # Step 1: Classification
        logger.info("system.main: Step 1 - Classification")
        templates, classifications, line_to_template = classifier.classify(log_entries)
        
        # Step 2: Value Assessment
        logger.info("system.main: Step 2 - Value Assessment")
        value_scores = valuer.assess(templates, classifications, log_entries, line_to_template)
        
        # Step 3: Decision Making
        logger.info("system.main: Step 3 - Decision Making")
        decisions = decider.decide(value_scores, log_entries, templates, line_to_template)
        
        # Step 4: Execution
        logger.info("system.main: Step 4 - Execution")
        audit_entries = executor.execute(decisions, log_entries, templates, line_to_template)
        
        logger.info("system.main: Pipeline complete")
        
        # Print comprehensive summary
        print_pipeline_summary(
            templates, classifications, value_scores, decisions, audit_entries, line_to_template
        )
        
        # Print classifier info
        if CLASSIFIER_TYPE == "Bob Shell":
            print(f"\n{'CLASSIFIER INFORMATION':^80}")
            print("-"*80)
            print(f"Classifier Type: Bob Shell (Local AI Inference)")
            print(f"LLM Enabled: {classifier.use_llm}")
            if hasattr(classifier, 'token_usage'):
                print(f"Bob Shell Calls: {classifier.token_usage['llm_calls']}")
                print(f"Approximate Tokens: {classifier.token_usage['total_tokens']}")
        else:
            print(f"\n{'CLASSIFIER INFORMATION':^80}")
            print("-"*80)
            print(f"Classifier Type: API-based")
            if hasattr(classifier, 'use_bob_endpoint') and classifier.use_bob_endpoint:
                print(f"API Endpoint: IBM Bob API")
            elif hasattr(classifier, 'api_key') and classifier.api_key:
                print(f"API Endpoint: Anthropic")
            else:
                print(f"API Endpoint: None (Rules-only mode)")
            if hasattr(classifier, 'token_usage'):
                print(f"LLM Calls: {classifier.token_usage['llm_calls']}")
                print(f"Total Tokens: {classifier.token_usage['total_tokens']}")
        
        logger.info("system.main: Demo complete")
        
    except Exception as e:
        logger.error(f"system.main: Error during pipeline execution: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

# Made with Bob
