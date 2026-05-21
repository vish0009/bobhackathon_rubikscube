"""
FastAPI application for log ingestion and querying.

Provides REST endpoints for:
- Log ingestion and processing
- Template lookup
- Classification queries
- Decision history
- Policy management
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import json
import os

from fastapi import FastAPI, HTTPException, BackgroundTasks, status, Security, Depends
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..config import get_logger, setup_logging
from ..models import LogEntry, Template, Classification, ValueScore, Decision, AuditEntry, Policy
from ..agents import ClassificationAgent, ValueAssessmentAgent, DecisionAgent, ExecutionAgent
from ..storage import LocalFilesystemBackend

# Setup logging
setup_logging(level="INFO")
logger = get_logger("system.api")

# Initialize FastAPI app
app = FastAPI(
    title="Log Agent API",
    description="Autonomous Log Cleanup & Archival Agent API",
    version="0.3.0"
)

# API Key Authentication
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key() -> Optional[str]:
    """Get API key from environment variable."""
    return os.getenv("LOG_AGENT_API_KEY")

async def verify_api_key(api_key: str = Security(api_key_header)):
    """
    Verify API key for protected endpoints.
    
    If LOG_AGENT_API_KEY is not set, authentication is disabled (dev mode).
    """
    expected_key = get_api_key()
    
    # If no API key is configured, allow all requests (dev mode)
    if not expected_key:
        logger.warning("system.api: API key authentication disabled (no LOG_AGENT_API_KEY set)")
        return None
    
    # If API key is configured, require it
    if not api_key or api_key != expected_key:
        logger.warning("system.api: Invalid or missing API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )
    
    return api_key

# Global state (in production, use proper state management/database)
_storage_backend = None
_policy = None
_templates_cache: Dict[str, Template] = {}
_classifications_cache: Dict[str, Classification] = {}
_decisions_cache: Dict[str, Decision] = {}
_audit_trail: List[AuditEntry] = []
_token_usage: Dict[str, int] = {
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0,
    "llm_calls": 0
}


# Request/Response Models
class LogIngestRequest(BaseModel):
    """Request model for log ingestion."""
    logs: List[Dict[str, Any]] = Field(..., description="List of log entries to ingest")
    process_immediately: bool = Field(True, description="Process logs immediately or queue")


class LogIngestResponse(BaseModel):
    """Response model for log ingestion."""
    status: str
    logs_received: int
    templates_extracted: int
    processing_time_ms: float
    message: str


class TemplateResponse(BaseModel):
    """Response model for template details."""
    template: Dict[str, Any]
    classification: Optional[Dict[str, Any]] = None
    value_score: Optional[Dict[str, Any]] = None
    decision: Optional[Dict[str, Any]] = None


class ClassificationListResponse(BaseModel):
    """Response model for classification list."""
    total: int
    classifications: List[Dict[str, Any]]


class DecisionHistoryResponse(BaseModel):
    """Response model for decision history."""
    total: int
    decisions: List[Dict[str, Any]]


class AuditTrailResponse(BaseModel):
    """Response model for audit trail."""
    total: int
    entries: List[Dict[str, Any]]


class PolicyResponse(BaseModel):
    """Response model for policy."""
    policy: Dict[str, Any]


class StatsResponse(BaseModel):
    """Response model for system statistics."""
    total_logs_processed: int
    total_templates: int
    total_decisions: int
    total_audit_entries: int
    storage_tiers: Dict[str, int]
    token_usage: Dict[str, int]


# Startup/Shutdown Events
@app.on_event("startup")
async def startup_event():
    """Initialize the API on startup."""
    global _storage_backend, _policy
    
    logger.info("system.api: Starting API server")
    
    # Initialize storage backend
    storage_path = Path("./log_storage")
    _storage_backend = LocalFilesystemBackend(base_path=str(storage_path))
    logger.info(f"system.api: Storage backend initialized at {storage_path}")
    
    # Load default policy - try multiple locations
    policy_paths = [
        Path("data/sample_policy.json"),
        Path("bobhackathon_rubikscube/log-agent/data/sample_policy.json"),
        Path("log-agent/data/sample_policy.json")
    ]
    
    policy_loaded = False
    for policy_path in policy_paths:
        if policy_path.exists():
            try:
                with open(policy_path, 'r') as f:
                    policy_data = json.load(f)
                _policy = Policy(**policy_data)
                logger.info(f"system.api: Default policy loaded from {policy_path}")
                policy_loaded = True
                break
            except Exception as e:
                logger.warning(f"system.api: Failed to load policy from {policy_path}: {e}")
    
    if not policy_loaded:
        logger.warning("system.api: No default policy found, using minimal policy")
        _policy = Policy(
            retention_rules={
                "ERROR": 90,
                "WARN": 60,
                "INFO": 30,
                "DEBUG": 7
            },
            compliance_overrides={
                "compliance": "RETAIN",
                "audit": "RETAIN"
            },
            storage_costs={
                "HOT": 0.023,
                "WARM": 0.0125,
                "COLD": 0.004,
                "ARCHIVE": 0.00099
            },
            environment_rules={
                "prod": {"min_retention_days": 30},
                "staging": {"min_retention_days": 14},
                "dev": {"min_retention_days": 7}
            }
        )
        logger.info("system.api: Minimal policy created")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("system.api: Shutting down API server")


# Helper Functions
def _process_logs_pipeline(log_entries: List[LogEntry]) -> tuple:
    """
    Run the full log processing pipeline.
    
    Returns:
        Tuple of (templates, classifications, value_scores, decisions, audit_entries, line_to_template)
    """
    logger.info(f"system.api: Processing {len(log_entries)} log entries")
    
    # Ensure policy and storage are initialized
    if _policy is None:
        raise RuntimeError("Policy not initialized. Server startup may have failed.")
    if _storage_backend is None:
        raise RuntimeError("Storage backend not initialized. Server startup may have failed.")
    
    # Initialize agents
    classifier = ClassificationAgent(use_llm=True)
    valuer = ValueAssessmentAgent()
    decider = DecisionAgent(_policy)
    executor = ExecutionAgent(_storage_backend)
    
    # Run pipeline
    templates, classifications, line_to_template = classifier.classify(log_entries)
    value_scores = valuer.assess(templates, classifications, log_entries, line_to_template)
    decisions = decider.decide(value_scores, log_entries, templates, line_to_template)
    audit_entries = executor.execute(decisions, log_entries, templates, line_to_template)

    # Update cumulative token usage
    classifier_token_usage = getattr(classifier, "token_usage", {})
    _token_usage["input_tokens"] += int(classifier_token_usage.get("input_tokens", 0))
    _token_usage["output_tokens"] += int(classifier_token_usage.get("output_tokens", 0))
    _token_usage["total_tokens"] += int(classifier_token_usage.get("total_tokens", 0))
    _token_usage["llm_calls"] += int(classifier_token_usage.get("llm_calls", 0))
    
    # Update caches
    for template in templates:
        _templates_cache[template.template_id] = template
    for classification in classifications:
        _classifications_cache[classification.template_id] = classification
    for decision in decisions:
        _decisions_cache[decision.template_id] = decision
    _audit_trail.extend(audit_entries)
    
    logger.info(f"system.api: Pipeline complete - {len(templates)} templates, {len(decisions)} decisions")
    
    return templates, classifications, value_scores, decisions, audit_entries, line_to_template


# API Endpoints

@app.get("/", tags=["General"])
async def root():
    """Root endpoint - API status."""
    return {
        "name": "Log Agent API",
        "version": "0.3.0",
        "status": "operational",
        "message": "Autonomous Log Cleanup & Archival Agent API - Phase 3"
    }


@app.get("/health", tags=["General"])
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "phase": "3",
        "storage_backend": "LocalFilesystem" if _storage_backend else "Not initialized",
        "policy_loaded": _policy is not None
    }


@app.post("/logs/ingest", response_model=LogIngestResponse, tags=["Logs"])
async def ingest_logs(
    request: LogIngestRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """
    Ingest log entries for processing.
    
    Accepts a batch of log entries and processes them through the full pipeline:
    1. Classification (template extraction + categorization)
    2. Value assessment (priority scoring)
    3. Decision making (policy application)
    4. Execution (storage operations)
    """
    start_time = datetime.now()
    
    try:
        # Parse log entries
        log_entries = []
        for log_data in request.logs:
            # Parse timestamp if string
            if isinstance(log_data.get('timestamp'), str):
                log_data['timestamp'] = datetime.fromisoformat(
                    log_data['timestamp'].replace('Z', '+00:00')
                )
            log_entries.append(LogEntry(**log_data))
        
        logger.info(f"system.api: Received {len(log_entries)} logs for ingestion")
        
        if request.process_immediately:
            # Process synchronously
            templates, _, _, _, _, _ = _process_logs_pipeline(log_entries)
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return LogIngestResponse(
                status="processed",
                logs_received=len(log_entries),
                templates_extracted=len(templates),
                processing_time_ms=processing_time,
                message=f"Successfully processed {len(log_entries)} logs"
            )
        else:
            # Queue for background processing
            background_tasks.add_task(_process_logs_pipeline, log_entries)
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return LogIngestResponse(
                status="queued",
                logs_received=len(log_entries),
                templates_extracted=0,
                processing_time_ms=processing_time,
                message=f"Queued {len(log_entries)} logs for background processing"
            )
    
    except Exception as e:
        logger.error(f"system.api: Error ingesting logs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing logs: {str(e)}"
        )


@app.get("/templates", response_model=ClassificationListResponse, tags=["Templates"])
async def list_templates(
    limit: int = 100,
    offset: int = 0,
    severity: Optional[str] = None
):
    """
    List all extracted templates with their classifications.
    
    Supports pagination and filtering by severity.
    """
    try:
        templates_list = list(_templates_cache.values())
        
        # Filter by severity if specified
        if severity:
            filtered = []
            for template in templates_list:
                classification = _classifications_cache.get(template.template_id)
                if classification and classification.severity.upper() == severity.upper():
                    filtered.append(template)
            templates_list = filtered
        
        # Pagination
        total = len(templates_list)
        paginated = templates_list[offset:offset + limit]
        
        # Build response
        result = []
        for template in paginated:
            classification = _classifications_cache.get(template.template_id)
            result.append({
                "template": template.model_dump(),
                "classification": classification.model_dump() if classification else None
            })
        
        return ClassificationListResponse(
            total=total,
            classifications=result
        )
    
    except Exception as e:
        logger.error(f"system.api: Error listing templates: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing templates: {str(e)}"
        )


@app.get("/templates/{template_id}", response_model=TemplateResponse, tags=["Templates"])
async def get_template(template_id: str):
    """
    Get detailed information about a specific template.
    
    Includes template, classification, value score, and decision.
    """
    try:
        template = _templates_cache.get(template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template {template_id} not found"
            )
        
        classification = _classifications_cache.get(template_id)
        value_score = None  # Would need to cache value scores
        decision = _decisions_cache.get(template_id)
        
        return TemplateResponse(
            template=template.model_dump(),
            classification=classification.model_dump() if classification else None,
            value_score=value_score,
            decision=decision.model_dump() if decision else None
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"system.api: Error getting template: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting template: {str(e)}"
        )


@app.get("/classifications", response_model=ClassificationListResponse, tags=["Classifications"])
async def list_classifications(
    limit: int = 100,
    offset: int = 0,
    type: Optional[str] = None,
    severity: Optional[str] = None
):
    """
    List all template classifications.
    
    Supports pagination and filtering by type and severity.
    """
    try:
        classifications_list = list(_classifications_cache.values())
        
        # Apply filters
        if type:
            classifications_list = [c for c in classifications_list if c.type.upper() == type.upper()]
        if severity:
            classifications_list = [c for c in classifications_list if c.severity.upper() == severity.upper()]
        
        # Pagination
        total = len(classifications_list)
        paginated = classifications_list[offset:offset + limit]
        
        result = [c.model_dump() for c in paginated]
        
        return ClassificationListResponse(
            total=total,
            classifications=result
        )
    
    except Exception as e:
        logger.error(f"system.api: Error listing classifications: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing classifications: {str(e)}"
        )


@app.get("/decisions", response_model=DecisionHistoryResponse, tags=["Decisions"])
async def list_decisions(
    limit: int = 100,
    offset: int = 0,
    action: Optional[str] = None
):
    """
    List all decisions made by the policy agent.
    
    Supports pagination and filtering by action type.
    """
    try:
        decisions_list = list(_decisions_cache.values())
        
        # Filter by action if specified
        if action:
            decisions_list = [d for d in decisions_list if d.action.upper() == action.upper()]
        
        # Pagination
        total = len(decisions_list)
        paginated = decisions_list[offset:offset + limit]
        
        result = [d.model_dump() for d in paginated]
        
        return DecisionHistoryResponse(
            total=total,
            decisions=result
        )
    
    except Exception as e:
        logger.error(f"system.api: Error listing decisions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing decisions: {str(e)}"
        )


@app.get("/audit", response_model=AuditTrailResponse, tags=["Audit"])
async def get_audit_trail(
    limit: int = 100,
    offset: int = 0,
    action: Optional[str] = None
):
    """
    Get the audit trail of all executed actions.
    
    Supports pagination and filtering by action type.
    """
    try:
        audit_list = _audit_trail.copy()
        
        # Filter by action if specified
        if action:
            audit_list = [a for a in audit_list if a.action.upper() == action.upper()]
        
        # Pagination
        total = len(audit_list)
        paginated = audit_list[offset:offset + limit]
        
        result = [a.model_dump() for a in paginated]
        
        return AuditTrailResponse(
            total=total,
            entries=result
        )
    
    except Exception as e:
        logger.error(f"system.api: Error getting audit trail: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting audit trail: {str(e)}"
        )


@app.get("/policy", response_model=PolicyResponse, tags=["Policy"])
async def get_policy():
    """Get the current policy configuration."""
    try:
        if not _policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No policy loaded"
            )
        
        return PolicyResponse(policy=_policy.model_dump())
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"system.api: Error getting policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting policy: {str(e)}"
        )


@app.put("/policy", response_model=PolicyResponse, tags=["Policy"])
async def update_policy(
    policy_data: Dict[str, Any],
    api_key: str = Depends(verify_api_key)
):
    """
    Update the policy configuration.
    
    This will affect all future log processing decisions.
    """
    global _policy
    
    try:
        # Validate and create new policy
        new_policy = Policy(**policy_data)
        _policy = new_policy
        
        logger.info("system.api: Policy updated successfully")
        
        return PolicyResponse(policy=_policy.model_dump())
    
    except Exception as e:
        logger.error(f"system.api: Error updating policy: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid policy data: {str(e)}"
        )


@app.get("/stats", response_model=StatsResponse, tags=["Statistics"])
async def get_stats():
    """Get system statistics."""
    try:
        # Count logs by tier - initialize with uppercase keys as expected by dashboard
        storage_tiers = {"HOT": 0, "WARM": 0, "COLD": 0, "ARCHIVE": 0}
        
        if _storage_backend:
            try:
                import os
                for tier_enum, tier_dir in _storage_backend.tier_directories.items():
                    logs_dir = tier_dir / "logs"
                    
                    if logs_dir.exists() and logs_dir.is_dir():
                        # tier_enum is a Tier enum, get its value (string) and convert to uppercase
                        # The Tier enum values are lowercase ("hot", "warm", "cold", "archive")
                        # but the dashboard expects uppercase keys ("HOT", "WARM", "COLD", "ARCHIVE")
                        tier_name = tier_enum.value.upper() if hasattr(tier_enum, 'value') else str(tier_enum).upper()
                        
                        # Use os.listdir for better performance with large directories
                        try:
                            files = os.listdir(logs_dir)
                            file_count = sum(1 for f in files if f.endswith('.json'))
                            storage_tiers[tier_name] = file_count
                            logger.debug(f"system.api: Found {file_count} files in {tier_name} tier")
                        except Exception as e:
                            logger.warning(f"system.api: Error counting files in {tier_name}: {e}")
                            storage_tiers[tier_name] = 0
            except Exception as e:
                logger.error(f"system.api: Failed to calculate storage tier distribution: {e}", exc_info=True)
        
        return StatsResponse(
            total_logs_processed=sum(a.affected_log_count for a in _audit_trail),
            total_templates=len(_templates_cache),
            total_decisions=len(_decisions_cache),
            total_audit_entries=len(_audit_trail),
            storage_tiers=storage_tiers,
            token_usage=_token_usage
        )
    
    except Exception as e:
        logger.error(f"system.api: Error getting stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting stats: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    logger.info("system.api: Starting API server")
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Made with Bob
