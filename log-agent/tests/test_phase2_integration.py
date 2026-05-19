"""
Integration tests for Phase 2 - Full pipeline testing.

Tests the complete flow: Classification → Value Assessment → Decision → Execution
"""

import json
from datetime import datetime
from pathlib import Path
import tempfile
import shutil

from log_agent.models import LogEntry, Policy
from log_agent.agents import (
    ClassificationAgent,
    ValueAssessmentAgent,
    DecisionAgent,
    ExecutionAgent,
)
from log_agent.storage import LocalFilesystemBackend


def create_test_log_entries():
    """Create sample log entries for testing."""
    return [
        LogEntry(
            log_id="test_001",
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
            service="api-gateway",
            environment="prod",
            log_level="ERROR",
            message="Database connection failed: timeout after 30s",
            access_count_last_30_days=15,
            tags=["database", "critical"],
        ),
        LogEntry(
            log_id="test_002",
            timestamp=datetime(2024, 1, 15, 10, 31, 0),
            service="auth-service",
            environment="prod",
            log_level="INFO",
            message="User login successful: user_id=12345",
            access_count_last_30_days=3,
            tags=["security", "auth"],
        ),
        LogEntry(
            log_id="test_003",
            timestamp=datetime(2024, 1, 15, 10, 32, 0),
            service="audit-service",
            environment="prod",
            log_level="INFO",
            message="Audit event recorded: action=user_update, user_id=12345",
            access_count_last_30_days=8,
            tags=["compliance", "audit"],
        ),
    ]


def create_test_policy():
    """Create a test policy."""
    return Policy(
        retention_rules={
            "ERROR": {"days": 90, "tier": "hot", "reason": "Critical for debugging"},
            "WARN": {"days": 60, "tier": "warm", "reason": "Important for trends"},
            "INFO": {"days": 30, "tier": "cold", "reason": "General visibility"},
            "DEBUG": {"days": 7, "tier": "cold", "reason": "Development only"},
        },
        compliance_overrides={
            "audit-service": {
                "retention_days": 365,
                "tier": "hot",
                "reason": "Regulatory compliance",
            }
        },
        storage_costs={"hot": 0.023, "warm": 0.01, "cold": 0.004, "archive": 0.001},
        environment_rules={
            "prod": {"min_retention_days": 30, "reason": "Production minimum"},
            "staging": {"min_retention_days": 14, "reason": "Staging minimum"},
            "dev": {"min_retention_days": 7, "reason": "Development minimum"},
        },
    )


def test_full_pipeline():
    """Test the complete pipeline from classification to execution."""
    # Setup
    log_entries = create_test_log_entries()
    policy = create_test_policy()
    
    # Create temporary storage directory
    temp_dir = tempfile.mkdtemp()
    try:
        storage = LocalFilesystemBackend(base_path=temp_dir)
        
        # Initialize agents
        classifier = ClassificationAgent(use_llm=False)  # Use rules-only for testing
        valuer = ValueAssessmentAgent()
        decider = DecisionAgent(policy)
        executor = ExecutionAgent(storage)
        
        # Run pipeline
        # Step 1: Classification
        templates, classifications, line_to_template = classifier.classify(log_entries)
        
        assert len(templates) > 0, "Should extract at least one template"
        assert len(classifications) == len(templates), "Should have one classification per template"
        assert len(line_to_template) == len(log_entries), "Should map all log entries"
        
        # Step 2: Value Assessment
        value_scores = valuer.assess(templates, classifications, log_entries, line_to_template)
        
        assert len(value_scores) == len(templates), "Should have one value score per template"
        assert all(0 <= v.score <= 1 for v in value_scores), "Scores should be between 0 and 1"
        assert all(v.priority in ["HIGH", "MEDIUM", "LOW"] for v in value_scores), "Valid priorities"
        
        # Step 3: Decision Making
        decisions = decider.decide(value_scores, log_entries, templates, line_to_template)
        
        assert len(decisions) == len(templates), "Should have one decision per template"
        assert all(d.action in ["RETAIN", "ARCHIVE", "DELETE", "COMPRESS"] for d in decisions), "Valid actions"
        
        # Check for compliance override on audit-service logs
        audit_decisions = [
            d for d in decisions
            if any(
                log.service == "audit-service"
                for log in log_entries
                if line_to_template.get(log.log_id) == d.template_id
            )
        ]
        if audit_decisions:
            assert any(d.policy_override for d in audit_decisions), "Audit logs should have policy override"
        
        # Step 4: Execution
        audit_entries = executor.execute(decisions, log_entries, templates, line_to_template)
        
        assert len(audit_entries) == len(decisions), "Should have one audit entry per decision"
        assert all(a.affected_log_count >= 0 for a in audit_entries), "Valid affected counts"
        assert all(a.bytes_freed >= 0 for a in audit_entries), "Valid bytes freed"
        
        print("[PASS] Full pipeline test passed")
        return True
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_value_assessment_scoring():
    """Test that value assessment produces reasonable scores."""
    log_entries = create_test_log_entries()
    
    classifier = ClassificationAgent(use_llm=False)
    valuer = ValueAssessmentAgent()
    
    templates, classifications, line_to_template = classifier.classify(log_entries)
    value_scores = valuer.assess(templates, classifications, log_entries, line_to_template)
    
    # ERROR logs should have higher scores than INFO logs
    error_scores = [
        v.score for v, c in zip(value_scores, classifications)
        if c.severity in ["HIGH", "CRITICAL"]
    ]
    info_scores = [
        v.score for v, c in zip(value_scores, classifications)
        if c.severity == "LOW"
    ]
    
    if error_scores and info_scores:
        avg_error = sum(error_scores) / len(error_scores)
        avg_info = sum(info_scores) / len(info_scores)
        assert avg_error > avg_info, "ERROR logs should score higher than INFO logs"
    
    print("[PASS] Value assessment scoring test passed")
    return True


def test_policy_overrides():
    """Test that policy overrides work correctly."""
    log_entries = create_test_log_entries()
    policy = create_test_policy()
    
    classifier = ClassificationAgent(use_llm=False)
    valuer = ValueAssessmentAgent()
    decider = DecisionAgent(policy)
    
    templates, classifications, line_to_template = classifier.classify(log_entries)
    value_scores = valuer.assess(templates, classifications, log_entries, line_to_template)
    decisions = decider.decide(value_scores, log_entries, templates, line_to_template)
    
    # Check that compliance override is applied
    override_count = sum(1 for d in decisions if d.policy_override)
    assert override_count > 0, "Should have at least one policy override"
    
    # Check that ERROR logs are retained
    error_decisions = [
        d for d in decisions
        if any(
            log.log_level == "ERROR"
            for log in log_entries
            if line_to_template.get(log.log_id) == d.template_id
        )
    ]
    if error_decisions:
        assert all(d.action == "RETAIN" for d in error_decisions), "ERROR logs should be retained"
    
    print("[PASS] Policy overrides test passed")
    return True


if __name__ == "__main__":
    print("Running Phase 2 Integration Tests...")
    print()
    
    try:
        test_full_pipeline()
        test_value_assessment_scoring()
        test_policy_overrides()
        
        print()
        print("="*60)
        print("All Phase 2 integration tests passed! [SUCCESS]")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        raise

# Made with Bob
