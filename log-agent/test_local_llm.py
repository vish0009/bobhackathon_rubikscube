#!/usr/bin/env python3
"""
Test script to verify local LLM integration at http://127.0.0.1:1234
"""

import os
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from log_agent.agents.classifier import ClassificationAgent
from log_agent.models import LogEntry

def test_local_llm():
    """Test classification with local LLM endpoint."""
    
    # Set environment to use local LLM
    os.environ["USE_LOCAL_LLM"] = "true"
    os.environ["LOCAL_LLM_ENDPOINT"] = "http://127.0.0.1:1234"
    
    # Remove API keys to ensure we use local LLM
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("BOB_API_KEY", None)
    
    print("=" * 80)
    print("Testing Local LLM Integration")
    print("=" * 80)
    print(f"Local LLM Endpoint: {os.environ['LOCAL_LLM_ENDPOINT']}")
    print()
    
    # Create sample log entries
    sample_logs = [
        LogEntry(
            log_id="test_001",
            timestamp="2024-01-15T10:30:00Z",
            log_level="ERROR",
            service="payment-service",
            environment="production",
            message="Payment processing failed for transaction TX-12345",
            tags=["payment", "error"],
            metadata={"transaction_id": "TX-12345"}
        ),
        LogEntry(
            log_id="test_002",
            timestamp="2024-01-15T10:31:00Z",
            log_level="INFO",
            service="user-service",
            environment="production",
            message="User login successful for user@example.com",
            tags=["auth", "login"],
            metadata={"user": "user@example.com"}
        ),
        LogEntry(
            log_id="test_003",
            timestamp="2024-01-15T10:32:00Z",
            log_level="DEBUG",
            service="cache-service",
            environment="development",
            message="Cache hit for key: user_profile_12345",
            tags=["cache", "performance"],
            metadata={"key": "user_profile_12345"}
        )
    ]
    
    # Initialize classifier
    print("Initializing ClassificationAgent with local LLM...")
    classifier = ClassificationAgent(use_llm=True)
    print()
    
    # Classify logs
    print("Classifying log entries...")
    templates, classifications, line_to_template = classifier.classify(sample_logs)
    print()
    
    # Display results
    print("=" * 80)
    print("CLASSIFICATION RESULTS")
    print("=" * 80)
    print()
    
    print(f"Total Templates Extracted: {len(templates)}")
    print(f"Total Classifications: {len(classifications)}")
    print()
    
    for i, (template, classification) in enumerate(zip(templates, classifications), 1):
        print(f"Template {i}:")
        print(f"  Pattern: {template.pattern}")
        print(f"  Classification:")
        print(f"    Type: {classification.type}")
        print(f"    Severity: {classification.severity}")
        print(f"    Signal Quality: {classification.signal_quality}")
        print(f"    Confidence: {classification.confidence:.2f}")
        print(f"    Method: {classification.method}")
        print()
    
    # Display token usage
    print("=" * 80)
    print("TOKEN USAGE STATISTICS")
    print("=" * 80)
    print(f"LLM Calls: {classifier.token_usage['llm_calls']}")
    print(f"Input Tokens: {classifier.token_usage['input_tokens']}")
    print(f"Output Tokens: {classifier.token_usage['output_tokens']}")
    print(f"Total Tokens: {classifier.token_usage['total_tokens']}")
    print()
    
    # Calculate percentages
    rule_based = sum(1 for c in classifications if c.method == "rule")
    llm_based = sum(1 for c in classifications if c.method == "llm")
    
    print("=" * 80)
    print("CLASSIFICATION METHOD BREAKDOWN")
    print("=" * 80)
    print(f"Rule-based: {rule_based} ({rule_based/len(classifications)*100:.1f}%)")
    print(f"LLM-based: {llm_based} ({llm_based/len(classifications)*100:.1f}%)")
    print()
    
    if llm_based > 0:
        print("✅ SUCCESS: Local LLM is being used for classification!")
    else:
        print("⚠️  WARNING: No templates were classified using LLM")
        print("   This might be expected if all templates had high confidence from rules.")
    
    return classifier.token_usage['llm_calls'] > 0

if __name__ == "__main__":
    try:
        success = test_local_llm()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# Made with Bob
