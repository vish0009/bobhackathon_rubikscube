"""
Tests for the FastAPI application.

Tests all API endpoints including authentication, log ingestion, and queries.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from log_agent.api.main import app, _templates_cache, _classifications_cache, _decisions_cache, _audit_trail
from log_agent.models import LogEntry


@pytest.fixture
def client():
    """Create a test client for the API."""
    # TestClient with raise_server_exceptions=False to see actual errors
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_logs():
    """Load sample logs for testing."""
    sample_path = Path(__file__).parent.parent / "data" / "sample_logs.json"
    with open(sample_path, 'r') as f:
        return json.load(f)


@pytest.fixture
def api_key():
    """Set up API key for testing."""
    test_key = "test-api-key-12345"
    os.environ["LOG_AGENT_API_KEY"] = test_key
    yield test_key
    # Cleanup
    if "LOG_AGENT_API_KEY" in os.environ:
        del os.environ["LOG_AGENT_API_KEY"]


@pytest.fixture
def clear_caches():
    """Clear global caches before each test."""
    _templates_cache.clear()
    _classifications_cache.clear()
    _decisions_cache.clear()
    _audit_trail.clear()
    yield
    # Cleanup after test
    _templates_cache.clear()
    _classifications_cache.clear()
    _decisions_cache.clear()
    _audit_trail.clear()


class TestGeneralEndpoints:
    """Test general API endpoints."""
    
    def test_root_endpoint(self, client):
        """Test the root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Log Agent API"
        assert data["version"] == "0.3.0"
        assert data["status"] == "operational"
    
    def test_health_endpoint(self, client):
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["phase"] == "3"


class TestAuthentication:
    """Test API authentication."""
    
    def test_ingest_without_api_key_when_not_required(self, client, sample_logs, clear_caches):
        """Test ingestion works without API key when not configured."""
        # Ensure no API key is set
        if "LOG_AGENT_API_KEY" in os.environ:
            del os.environ["LOG_AGENT_API_KEY"]
        
        response = client.post(
            "/logs/ingest",
            json={"logs": sample_logs[:2], "process_immediately": True}
        )
        assert response.status_code == 200
    
    def test_ingest_with_valid_api_key(self, client, sample_logs, api_key, clear_caches):
        """Test ingestion with valid API key."""
        response = client.post(
            "/logs/ingest",
            json={"logs": sample_logs[:2], "process_immediately": True},
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
    
    def test_ingest_with_invalid_api_key(self, client, sample_logs, api_key, clear_caches):
        """Test ingestion fails with invalid API key."""
        response = client.post(
            "/logs/ingest",
            json={"logs": sample_logs[:2], "process_immediately": True},
            headers={"X-API-Key": "wrong-key"}
        )
        assert response.status_code == 401
        assert "Invalid or missing API key" in response.json()["detail"]
    
    def test_ingest_without_api_key_when_required(self, client, sample_logs, api_key, clear_caches):
        """Test ingestion fails without API key when required."""
        response = client.post(
            "/logs/ingest",
            json={"logs": sample_logs[:2], "process_immediately": True}
        )
        assert response.status_code == 401


class TestLogIngestion:
    """Test log ingestion endpoints."""
    
    def test_ingest_logs_immediate_processing(self, client, sample_logs, clear_caches):
        """Test immediate log processing."""
        # Disable API key for this test
        if "LOG_AGENT_API_KEY" in os.environ:
            del os.environ["LOG_AGENT_API_KEY"]
        
        response = client.post(
            "/logs/ingest",
            json={"logs": sample_logs[:3], "process_immediately": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["logs_received"] == 3
        assert data["templates_extracted"] > 0
        assert data["processing_time_ms"] > 0
    
    def test_ingest_logs_background_processing(self, client, sample_logs, clear_caches):
        """Test background log processing."""
        # Disable API key for this test
        if "LOG_AGENT_API_KEY" in os.environ:
            del os.environ["LOG_AGENT_API_KEY"]
        
        response = client.post(
            "/logs/ingest",
            json={"logs": sample_logs[:2], "process_immediately": False}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["logs_received"] == 2
    
    def test_ingest_invalid_logs(self, client, clear_caches):
        """Test ingestion with invalid log data."""
        # Disable API key for this test
        if "LOG_AGENT_API_KEY" in os.environ:
            del os.environ["LOG_AGENT_API_KEY"]
        
        invalid_logs = [{"invalid": "data"}]
        response = client.post(
            "/logs/ingest",
            json={"logs": invalid_logs, "process_immediately": True}
        )
        
        assert response.status_code == 500


class TestTemplateEndpoints:
    """Test template-related endpoints."""
    
    def test_list_templates_empty(self, client, clear_caches):
        """Test listing templates when none exist."""
        response = client.get("/templates")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["classifications"] == []
    
    def test_list_templates_after_ingestion(self, client, sample_logs, clear_caches):
        """Test listing templates after ingesting logs."""
        # Disable API key for this test
        if "LOG_AGENT_API_KEY" in os.environ:
            del os.environ["LOG_AGENT_API_KEY"]
        
        # Ingest logs first
        client.post(
            "/logs/ingest",
            json={"logs": sample_logs[:4], "process_immediately": True}
        )
        
        # List templates
        response = client.get("/templates")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0
        assert len(data["classifications"]) > 0
    
    def test_list_templates_with_pagination(self, client, sample_logs, clear_caches):
        """Test template pagination."""
        # Disable API key for this test
        if "LOG_AGENT_API_KEY" in os.environ:
            del os.environ["LOG_AGENT_API_KEY"]
        
        # Ingest logs
        client.post(
            "/logs/ingest",
            json={"logs": sample_logs, "process_immediately": True}
        )
        
        # Test pagination
        response = client.get("/templates?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["classifications"]) <= 2
    
    def test_get_template_not_found(self, client, clear_caches):
        """Test getting a non-existent template."""
        response = client.get("/templates/nonexistent-id")
        assert response.status_code == 404
    
    def test_get_template_success(self, client, sample_logs, clear_caches):
        """Test getting a specific template."""
        # Disable API key for this test
        if "LOG_AGENT_API_KEY" in os.environ:
            del os.environ["LOG_AGENT_API_KEY"]
        
        # Ingest logs
        ingest_response = client.post(
            "/logs/ingest",
            json={"logs": sample_logs[:2], "process_immediately": True}
        )
        
        # Get list of templates
        list_response = client.get("/templates")
        templates = list_response.json()["classifications"]
        
        if templates:
            template_id = templates[0]["template"]["template_id"]
            
            # Get specific template
            response = client.get(f"/templates/{template_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["template"]["template_id"] == template_id


class TestClassificationEndpoints:
    """Test classification endpoints."""
    
    def test_list_classifications_empty(self, client, clear_caches):
        """Test listing classifications when none exist."""
        response = client.get("/classifications")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
    
    def test_list_classifications_with_filters(self, client, sample_logs, clear_caches):
        """Test filtering classifications."""
        # Disable API key for this test
        if "LOG_AGENT_API_KEY" in os.environ:
            del os.environ["LOG_AGENT_API_KEY"]
        
        # Ingest logs
        client.post(
            "/logs/ingest",
            json={"logs": sample_logs, "process_immediately": True}
        )
        
        # Test severity filter
        response = client.get("/classifications?severity=HIGH")
        assert response.status_code == 200


class TestDecisionEndpoints:
    """Test decision endpoints."""
    
    def test_list_decisions_empty(self, client, clear_caches):
        """Test listing decisions when none exist."""
        response = client.get("/decisions")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
    
    def test_list_decisions_after_ingestion(self, client, sample_logs, clear_caches):
        """Test listing decisions after processing logs."""
        # Disable API key for this test
        if "LOG_AGENT_API_KEY" in os.environ:
            del os.environ["LOG_AGENT_API_KEY"]
        
        # Ingest logs
        client.post(
            "/logs/ingest",
            json={"logs": sample_logs[:3], "process_immediately": True}
        )
        
        # List decisions
        response = client.get("/decisions")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0


class TestAuditEndpoints:
    """Test audit trail endpoints."""
    
    def test_get_audit_trail_empty(self, client, clear_caches):
        """Test getting audit trail when empty."""
        response = client.get("/audit")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
    
    def test_get_audit_trail_after_execution(self, client, sample_logs, clear_caches):
        """Test audit trail after log processing."""
        # Disable API key for this test
        if "LOG_AGENT_API_KEY" in os.environ:
            del os.environ["LOG_AGENT_API_KEY"]
        
        # Ingest logs
        client.post(
            "/logs/ingest",
            json={"logs": sample_logs[:2], "process_immediately": True}
        )
        
        # Get audit trail
        response = client.get("/audit")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0
        assert len(data["entries"]) > 0


class TestPolicyEndpoints:
    """Test policy management endpoints."""
    
    def test_get_policy(self, client):
        """Test getting current policy."""
        response = client.get("/policy")
        assert response.status_code == 200
        data = response.json()
        assert "policy" in data
    
    def test_update_policy_without_auth(self, client, api_key):
        """Test updating policy without authentication."""
        new_policy = {
            "retention_rules": {"ERROR": 90},
            "compliance_overrides": {},
            "storage_costs": {},
            "environment_rules": {}
        }
        
        response = client.put("/policy", json=new_policy)
        assert response.status_code == 401
    
    def test_update_policy_with_auth(self, client, api_key):
        """Test updating policy with authentication."""
        new_policy = {
            "retention_rules": {"ERROR": 90},
            "compliance_overrides": {},
            "storage_costs": {},
            "environment_rules": {}
        }
        
        response = client.put(
            "/policy",
            json=new_policy,
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["policy"]["retention_rules"]["ERROR"] == 90
    
    def test_update_policy_invalid_data(self, client, api_key):
        """Test updating policy with invalid data."""
        invalid_policy = {"invalid": "data"}
        
        response = client.put(
            "/policy",
            json=invalid_policy,
            headers={"X-API-Key": api_key}
        )
        assert response.status_code == 400


class TestStatsEndpoint:
    """Test statistics endpoint."""
    
    def test_get_stats_initial(self, client, clear_caches):
        """Test getting stats with no data."""
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_logs_processed"] == 0
        assert data["total_templates"] == 0
        assert data["total_decisions"] == 0
    
    def test_get_stats_after_processing(self, client, sample_logs, clear_caches):
        """Test getting stats after processing logs."""
        # Disable API key for this test
        if "LOG_AGENT_API_KEY" in os.environ:
            del os.environ["LOG_AGENT_API_KEY"]
        
        # Ingest logs
        client.post(
            "/logs/ingest",
            json={"logs": sample_logs[:3], "process_immediately": True}
        )
        
        # Get stats
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_logs_processed"] > 0
        assert data["total_templates"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob