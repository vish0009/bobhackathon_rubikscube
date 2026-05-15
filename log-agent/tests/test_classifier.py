"""
Basic tests for the Classification Agent.
"""

import pytest
from datetime import datetime
from log_agent.models import LogEntry
from log_agent.agents import ClassificationAgent


@pytest.fixture
def sample_log_entries():
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
            tags=["database", "critical"]
        ),
        LogEntry(
            log_id="test_002",
            timestamp=datetime(2024, 1, 15, 10, 31, 0),
            service="auth-service",
            environment="prod",
            log_level="INFO",
            message="User login successful: user_id=12345",
            access_count_last_30_days=3,
            tags=["security", "auth"]
        ),
        LogEntry(
            log_id="test_003",
            timestamp=datetime(2024, 1, 15, 10, 32, 0),
            service="api-gateway",
            environment="dev",
            log_level="DEBUG",
            message="Request received: GET /api/v1/users",
            access_count_last_30_days=0,
            tags=["application"]
        ),
    ]


def test_classifier_initialization():
    """Test that classifier initializes correctly."""
    classifier = ClassificationAgent(use_llm=False)
    assert classifier is not None
    assert classifier.use_llm is False


def test_classifier_with_sample_logs(sample_log_entries):
    """Test classification of sample log entries."""
    classifier = ClassificationAgent(use_llm=False)
    
    templates, classifications, line_to_template = classifier.classify(sample_log_entries)
    
    # Check that we got results
    assert len(templates) > 0
    assert len(classifications) > 0
    assert len(line_to_template) == len(sample_log_entries)
    
    # Check that all log entries are mapped to templates
    for entry in sample_log_entries:
        assert entry.log_id in line_to_template


def test_rule_based_classification(sample_log_entries):
    """Test that rule-based classification works."""
    classifier = ClassificationAgent(use_llm=False)
    
    templates, classifications, _ = classifier.classify(sample_log_entries)
    
    # All classifications should be rule-based or default (no LLM)
    for classification in classifications:
        assert classification.method in ["rule", "default"]
        assert classification.confidence >= 0.0
        assert classification.confidence <= 1.0


def test_severity_mapping(sample_log_entries):
    """Test that log levels map to correct severity."""
    classifier = ClassificationAgent(use_llm=False)
    
    templates, classifications, line_to_template = classifier.classify(sample_log_entries)
    
    # Find the ERROR log classification
    error_log = sample_log_entries[0]  # ERROR level
    template_id = line_to_template[error_log.log_id]
    classification = next(c for c in classifications if c.template_id == template_id)
    
    # ERROR should map to HIGH severity
    assert classification.severity == "HIGH"


def test_environment_signal_quality(sample_log_entries):
    """Test that environment affects signal quality."""
    classifier = ClassificationAgent(use_llm=False)
    
    templates, classifications, line_to_template = classifier.classify(sample_log_entries)
    
    # Find prod and dev log classifications
    prod_log = sample_log_entries[0]  # prod environment
    dev_log = sample_log_entries[2]   # dev environment
    
    prod_template_id = line_to_template[prod_log.log_id]
    dev_template_id = line_to_template[dev_log.log_id]
    
    prod_classification = next(c for c in classifications if c.template_id == prod_template_id)
    dev_classification = next(c for c in classifications if c.template_id == dev_template_id)
    
    # Prod should have higher signal quality than dev
    signal_quality_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    assert signal_quality_order[prod_classification.signal_quality] >= signal_quality_order[dev_classification.signal_quality]


def test_template_extraction(sample_log_entries):
    """Test that Drain3 extracts templates correctly."""
    classifier = ClassificationAgent(use_llm=False)
    
    templates, _, _ = classifier.classify(sample_log_entries)
    
    # Check template structure
    for template in templates:
        assert template.template_id.startswith("template_")
        assert len(template.pattern) > 0
        assert template.match_count > 0
        assert template.first_seen is not None
        assert template.last_seen is not None


def test_line_to_template_mapping(sample_log_entries):
    """Test that line-to-template mapping is correct."""
    classifier = ClassificationAgent(use_llm=False)
    
    templates, _, line_to_template = classifier.classify(sample_log_entries)
    
    # Every log entry should be mapped
    assert len(line_to_template) == len(sample_log_entries)
    
    # All mapped template IDs should exist in templates
    template_ids = {t.template_id for t in templates}
    for log_id, template_id in line_to_template.items():
        assert template_id in template_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
