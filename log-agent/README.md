# Autonomous Log Cleanup & Archival Agent

An intelligent log management system using agentic AI to classify, assess, and manage log retention with cost optimization and compliance awareness.

## Overview

This system uses a multi-agent architecture to intelligently manage log data:

1. **Classification Agent**: Extracts templates using Drain3, applies rule-based classification, with LLM fallback for ambiguous cases ✓
2. **Value Assessment Agent**: Analyzes access patterns, recency, and assigns retention priority ✓ (Phase 2)
3. **Decision/Policy Agent**: Applies compliance rules and policy constraints ✓ (Phase 2)
4. **Execution Agent**: Performs retention actions and maintains audit trail ✓ (Phase 2)

### Key Features

- **Template-Level Processing**: Reduces LLM calls from O(n) to O(unique_templates) - typically 10x-100x cost reduction
- **Rule-First Approach**: 80%+ of logs classified by rules, LLM only for ambiguous cases
- **Graceful Degradation**: Works without API key using rules-only mode
- **Compliance-Aware**: Tag-based compliance detection with policy overrides
- **Storage Abstraction**: Easy migration from local filesystem to S3

## Architecture

```
Raw Logs → Classification Agent → Value Agent → Decision Agent → Execution Agent → Storage
                                                                                    ↓
                                                                              Audit Trail
```

### Template-Level Processing

The system's core innovation is processing at the template level, not individual log lines:

1. Drain3 extracts unique patterns from logs
2. Each template is classified once
3. All matching log lines inherit the template's classification
4. This dramatically reduces processing time and LLM API costs

## Quick Start

### Prerequisites

- Python 3.10 or higher
- `uv` package manager (recommended) or `pip`

### Installation

```bash
# Clone the repository
cd bobhackathon_rubikscube/log-agent

# Install dependencies
uv pip install -e .

# Or with pip
pip install -e .
```

### Running the Demo

The system now runs the complete pipeline from classification to execution.

#### 1. Local LLM Mode (DEFAULT - RECOMMENDED)

```bash
# Start your local LLM server (e.g., LM Studio on port 1234)
# Then run the application - it will automatically use the local LLM
python -m log_agent data/sample_logs.json data/sample_policy.json
```

**This is the default mode!** The system automatically connects to `http://127.0.0.1:1234` for local LLM inference. No API keys, no costs, no external calls!

**Supported Local LLM Servers:**
- LM Studio (port 1234 by default)
- Ollama (port 11434)
- llama.cpp server
- text-generation-webui

See [LOCAL_LLM_SETUP.md](LOCAL_LLM_SETUP.md) for detailed setup instructions.

#### 2. Rules-Only Mode (No LLM)

```bash
# Disable LLM completely
export USE_LOCAL_LLM=false

python -m log_agent data/sample_logs.json data/sample_policy.json
```

This mode uses only rule-based classification. Perfect for testing without any LLM.

#### 3. Cloud API Mode (Requires API Key)

```bash
# Disable local LLM first
export USE_LOCAL_LLM=false

# Option A: Use Anthropic API
export ANTHROPIC_API_KEY=sk-ant-your_key_here

# Option B: Use IBM Bob API
export BOB_API_KEY=your_bob_api_key

# Run with cloud API LLM fallback
python -m log_agent data/sample_logs.json data/sample_policy.json
```

This mode uses external APIs for LLM fallback. Requires valid API credentials and incurs API costs.

### Expected Output (Phase 2)

```
================================================================================
LOG MANAGEMENT PIPELINE - PHASE 2 COMPLETE
================================================================================

                              OVERALL STATISTICS
--------------------------------------------------------------------------------
Total log lines processed: 8
Unique templates extracted: 6
Total logs affected: 8
Total bytes freed: 2,450

                          CLASSIFICATION STATISTICS
--------------------------------------------------------------------------------
Rule-based: 5 (83.3%)
LLM-based:  1 (16.7%)
Default:    0 (0.0%)

                         VALUE ASSESSMENT STATISTICS
--------------------------------------------------------------------------------
High priority:   3 (50.0%)
Medium priority: 2 (33.3%)
Low priority:    1 (16.7%)

                            DECISION STATISTICS
--------------------------------------------------------------------------------
RETAIN:  4 (66.7%)
ARCHIVE: 1 (16.7%)
DELETE:  1 (16.7%)
Policy overrides: 2 (33.3%)

                        DETAILED TEMPLATE BREAKDOWN
--------------------------------------------------------------------------------

Template: template_1
  Pattern: Database connection failed: timeout after <*> s...
  Matches: 2 log lines
  Classification: HIGH / DATABASE / HIGH
  Value Score: 0.85 (HIGH priority)
  Decision: RETAIN [POLICY OVERRIDE]
  Execution: 2 logs, 450 bytes freed
  Policy Rule: retention_rule:ERROR

...
```

## Project Structure

```
log-agent/
├── log_agent/
│   ├── __init__.py
│   ├── __main__.py          # CLI entrypoint (full pipeline)
│   ├── config.py            # Logging configuration
│   ├── agents/              # Agent implementations
│   │   ├── classifier.py    # ✓ Classification Agent
│   │   ├── valuer.py        # ✓ Value Assessment Agent (Phase 2)
│   │   ├── decider.py       # ✓ Decision/Policy Agent (Phase 2)
│   │   └── executor.py      # ✓ Execution Agent (Phase 2)
│   ├── models/              # Pydantic data models
│   │   ├── tier.py          # Storage tier enum
│   │   ├── log_entry.py     # Log entry model
│   │   ├── template.py      # Drain3 template
│   │   ├── classification.py
│   │   ├── value_score.py
│   │   ├── decision.py
│   │   ├── audit_entry.py
│   │   └── policy.py
│   ├── storage/             # Storage backends
│   │   ├── backend.py       # Abstract interface
│   │   ├── local_backend.py # ✓ Local filesystem
│   │   └── s3_backend.py    # ✓ S3 implementation (Phase 3)
│   └── api/                 # REST API (Phase 3)
│       ├── __init__.py
│       └── main.py          # ✓ FastAPI application
├── data/
│   ├── sample_logs.json     # Sample log data
│   └── sample_policy.json   # Sample policy rules
├── tests/                   # Test suite
│   ├── test_classifier.py   # Classification tests
│   ├── test_phase2_integration.py  # ✓ Phase 2 integration tests
│   └── test_api.py          # ✓ API tests (Phase 3)
├── pyproject.toml           # Project configuration
└── README.md                # This file
```

## Configuration

### API Key Setup

The system uses the configured LLM fallback with `BOB_API_KEY`. Set your API key:

```bash
# Linux/Mac
export BOB_API_KEY=your_key_here

# Windows PowerShell
$env:BOB_API_KEY="your_key_here"

# Windows CMD
set BOB_API_KEY=your_key_here
```

**Important**: The system gracefully degrades to rules-only mode if no API key is provided.

### Drain3 Configuration

Default configuration (in `classifier.py`):
- `depth`: 4
- `sim_th`: 0.4 (similarity threshold)
- `max_children`: 100
- `max_clusters`: 1024

These can be tuned for your specific log patterns.

## Classification Rules

The rule-based classifier uses these heuristics:

### Severity Mapping (Log Level → Severity)
- `CRITICAL`/`FATAL` → `CRITICAL`
- `ERROR` → `HIGH`
- `WARN`/`WARNING` → `MEDIUM`
- `INFO` → `LOW`
- `DEBUG`/`TRACE` → `VERY_LOW`

### Category Detection (Tags/Service → Type)
- `compliance` tag or `audit` in service → `COMPLIANCE`
- `security` tag or `auth` in service → `SECURITY`
- `database` tag or `db` in service → `DATABASE`
- Error keywords in pattern → `APPLICATION`

### Signal Quality (Environment → Quality)
- `prod` → `HIGH`
- `staging`/`stage` → `MEDIUM`
- `dev`/`test` → `LOW`

## Sample Data

### sample_logs.json

Contains 8 diverse log entries covering:
- Different log levels (ERROR, WARN, INFO, DEBUG)
- Multiple environments (prod, staging, dev)
- Various services (api-gateway, auth-service, audit-service, etc.)
- Different access patterns
- Compliance-sensitive logs (audit-service)

### sample_policy.json

Defines retention policies:
- Retention rules by log level
- Compliance overrides for specific services
- Storage tier costs
- Environment-specific rules

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

The project uses:
- Type hints on all public functions
- Pydantic models for all data structures
- Docstrings on all public functions
- `logging` module (not `print`)
- System logs prefixed with `system.`

### Adding New Classification Rules

Edit `log_agent/agents/classifier.py` in the `_rule_based_classify` method:

```python
# Add your custom rule
if "your_keyword" in template.pattern.lower():
    log_type = "YOUR_TYPE"
    confidence += 0.4
```

## Phase 2 Features (NEW!)

### Value Assessment Agent
- **Access Pattern Analysis**: Evaluates `access_count_last_30_days` to determine log importance
- **Recency Scoring**: Recent logs (< 7 days) score higher than old logs (> 90 days)
- **Multi-Factor Scoring**: Combines severity (40%), access (25%), recency (20%), signal quality (10%), environment (5%)
- **Priority Assignment**: HIGH (score ≥ 0.7), MEDIUM (0.4-0.7), LOW (< 0.4)
- **Action Recommendations**: RETAIN, ARCHIVE, or DELETE based on priority

### Decision/Policy Agent
- **Compliance Overrides**: Tag-based detection (e.g., `compliance`, `audit` tags) → Always RETAIN
- **Retention Rules**: Log level-based policies (ERROR: 90 days, WARN: 60 days, INFO: 30 days, DEBUG: 7 days)
- **Environment Rules**: Production logs have minimum 30-day retention
- **Policy Override Tracking**: All policy-driven decisions are flagged and logged

### Execution Agent
- **Action Execution**: Performs RETAIN, ARCHIVE, DELETE, and COMPRESS operations
- **Storage Operations**: Manages tier transitions (HOT → WARM → COLD → ARCHIVE)
- **Audit Trail**: Creates immutable audit entries for every action
- **Metrics Tracking**: Calculates affected log counts and bytes freed

### Full Pipeline Integration
The system now runs end-to-end:
1. **Classification**: Extract templates and classify
2. **Value Assessment**: Score each template's retention value
3. **Decision Making**: Apply policy rules and compliance overrides
4. **Execution**: Perform actions and log to audit trail

## Phase 3 Features (NEW!)

### FastAPI REST API
A complete REST API for log ingestion and querying:

#### Starting the API Server

```bash
# Install API dependencies
pip install -e ".[api]"

# Start the server
python -m log_agent.api.main

# Or with uvicorn directly
uvicorn log_agent.api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

#### API Authentication

The API supports optional API key authentication:

```bash
# Set API key (optional - if not set, authentication is disabled)
export LOG_AGENT_API_KEY=your-secret-key-here

# Start server with authentication enabled
python -m log_agent.api.main
```

Protected endpoints (POST/PUT operations) require the `X-API-Key` header when authentication is enabled.

#### API Endpoints

**General Endpoints:**
- `GET /` - API status and version
- `GET /health` - Health check
- `GET /stats` - System statistics

**Log Ingestion:**
- `POST /logs/ingest` - Ingest and process logs (requires API key if configured)

**Template Queries:**
- `GET /templates` - List all templates with pagination and filtering
- `GET /templates/{template_id}` - Get specific template details

**Classification Queries:**
- `GET /classifications` - List classifications with filtering

**Decision History:**
- `GET /decisions` - List all decisions with filtering

**Audit Trail:**
- `GET /audit` - Get audit trail with pagination

**Policy Management:**
- `GET /policy` - Get current policy
- `PUT /policy` - Update policy (requires API key if configured)

#### API Usage Examples

**1. Ingest Logs**

```bash
# Without authentication (dev mode)
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "logs": [
      {
        "log_id": "log_001",
        "timestamp": "2024-01-15T10:30:00Z",
        "service": "api-gateway",
        "environment": "prod",
        "log_level": "ERROR",
        "message": "Database connection failed: timeout after 30s",
        "access_count_last_30_days": 150,
        "tags": []
      }
    ],
    "process_immediately": true
  }'

# With authentication
curl -X POST http://localhost:8000/logs/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key-here" \
  -d '{"logs": [...], "process_immediately": true}'
```

**2. List Templates**

```bash
# Get all templates
curl http://localhost:8000/templates

# With pagination
curl "http://localhost:8000/templates?limit=10&offset=0"

# Filter by severity
curl "http://localhost:8000/templates?severity=HIGH"
```

**3. Get Template Details**

```bash
curl http://localhost:8000/templates/template_1
```

**4. List Classifications**

```bash
# All classifications
curl http://localhost:8000/classifications

# Filter by type and severity
curl "http://localhost:8000/classifications?type=DATABASE&severity=HIGH"
```

**5. Get Decisions**

```bash
# All decisions
curl http://localhost:8000/decisions

# Filter by action
curl "http://localhost:8000/decisions?action=RETAIN"
```

**6. Get Audit Trail**

```bash
curl http://localhost:8000/audit
```

**7. Get System Stats**

```bash
curl http://localhost:8000/stats
```

**8. Update Policy**

```bash
curl -X PUT http://localhost:8000/policy \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secret-key-here" \
  -d '{
    "retention_rules": {
      "ERROR": 90,
      "WARN": 60,
      "INFO": 30,
      "DEBUG": 7
    },
    "compliance_overrides": {
      "compliance": "RETAIN",
      "audit": "RETAIN"
    },
    "storage_costs": {
      "HOT": 0.023,
      "WARM": 0.0125,
      "COLD": 0.004,
      "ARCHIVE": 0.00099
    },
    "environment_rules": {
      "prod": {"min_retention_days": 30},
      "staging": {"min_retention_days": 14},
      "dev": {"min_retention_days": 7}
    }
  }'
```

#### Python Client Example

```python
import requests
import json

# API configuration
API_URL = "http://localhost:8000"
API_KEY = "your-secret-key-here"  # Optional

headers = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY  # Include if authentication is enabled
}

# Ingest logs
logs_data = {
    "logs": [
        {
            "log_id": "log_001",
            "timestamp": "2024-01-15T10:30:00Z",
            "service": "api-gateway",
            "environment": "prod",
            "log_level": "ERROR",
            "message": "Database connection failed",
            "access_count_last_30_days": 150,
            "tags": []
        }
    ],
    "process_immediately": True
}

response = requests.post(
    f"{API_URL}/logs/ingest",
    headers=headers,
    json=logs_data
)
print(f"Ingestion result: {response.json()}")

# Query templates
response = requests.get(f"{API_URL}/templates")
templates = response.json()
print(f"Total templates: {templates['total']}")

# Get system stats
response = requests.get(f"{API_URL}/stats")
stats = response.json()
print(f"Stats: {json.dumps(stats, indent=2)}")
```

### S3 Storage Backend

Full S3 backend implementation with storage class management:

```python
from log_agent.storage import S3Backend
from log_agent.models import Tier

# Initialize S3 backend
storage = S3Backend(
    bucket_name="my-log-bucket",
    region="us-east-1",
    prefix="logs/"
)

# Write to S3 with storage class
data = b"log data"
storage.write(data, "logs/log_001.json", Tier.HOT)  # Uses S3 Standard

# Change storage tier
storage.set_tier("logs/log_001.json", Tier.COLD)  # Moves to Glacier Instant Retrieval

# Read from S3
data = storage.read("logs/log_001.json")

# List objects
files = storage.list("logs/")
```

**Storage Class Mapping:**
- `HOT` → S3 Standard
- `WARM` → S3 Standard-IA (Infrequent Access)
- `COLD` → S3 Glacier Instant Retrieval
- `ARCHIVE` → S3 Glacier Deep Archive

### Running API Tests

```bash
# Install test dependencies
pip install -e ".[dev,api]"

# Run API tests
pytest tests/test_api.py -v

# Run all tests
pytest tests/ -v
```
## Phase 4 Features (NEW!)

### Streamlit Dashboard

A comprehensive web-based dashboard for visualizing and managing log data:

#### Starting the Dashboard

```bash
# Install dashboard dependencies
pip install -e ".[dashboard]"

# Start the dashboard (requires API server to be running)
streamlit run log_agent/dashboard/app.py

# Or with custom port
streamlit run log_agent/dashboard/app.py --server.port 8501
```

The dashboard will be available at `http://localhost:8501`

**Prerequisites**: The FastAPI server must be running on `http://localhost:8000` for the dashboard to function.

#### Dashboard Features

**1. Overview Page**
- System health status and API connectivity
- Key metrics: total logs processed, unique templates, decisions, audit entries
- Storage tier distribution with interactive pie chart
- Quick action buttons for common tasks

**2. Template Explorer**
- Browse all extracted log templates
- Filter by severity level
- Pagination support for large datasets
- Detailed view showing:
  - Template pattern and ID
  - Match count and timestamps
  - Classification details (type, severity, signal quality)
  - Confidence scores and classification method

**3. Classification Statistics**
- Summary metrics: total classifications, rule-based vs LLM percentages
- Interactive charts:
  - Severity distribution bar chart
  - Type distribution pie chart
  - Classification method comparison
  - Signal quality distribution
- Average confidence score tracking

**4. Decision History**
- View all policy decisions with filtering
- Filter by action type (RETAIN, ARCHIVE, DELETE, COMPRESS)
- Policy override tracking and visualization
- Action distribution pie chart
- Detailed reasoning for each decision

**5. Audit Trail Viewer**
- Complete audit log of all executed actions
- Filter by action type
- Pagination for large audit trails
- Metrics: total logs affected, bytes freed
- Detailed metadata for each audit entry

**6. Policy Management UI**
- View and edit current policy configuration
- Tabs for different policy sections:
  - Retention rules (editable with validation)
  - Compliance overrides
  - Storage costs by tier
  - Environment-specific rules
- Save changes with immediate effect
- Advanced JSON editor for power users

**7. Log Ingestion Interface**
- Upload and process logs directly from the UI
- Sample log template provided
- JSON validation
- Immediate or background processing options
- Real-time feedback on ingestion results

#### Dashboard Configuration

The dashboard supports API key authentication and custom API URLs:

1. **API URL Configuration**: Set the API base URL in the sidebar (default: `http://localhost:8000`)
2. **API Key**: Optionally provide an API key for protected endpoints
3. **Navigation**: Use the sidebar to switch between different pages
4. **Auto-refresh**: Use the refresh button to update data

#### Dashboard Usage Examples

**Starting Both Services:**

```bash
# Terminal 1: Start API server
python -m log_agent.api.main

# Terminal 2: Start dashboard
streamlit run log_agent/dashboard/app.py
```

**Accessing the Dashboard:**

1. Open browser to `http://localhost:8501`
2. Check API connectivity on Overview page
3. Navigate using sidebar buttons
4. Use filters and pagination to explore data
5. Ingest logs using the Log Ingestion page
6. Monitor changes in real-time

**Dashboard Screenshots:**

The dashboard provides:
- 📊 **Overview**: System health and key metrics
- 📝 **Templates**: Browse and filter log templates
- 📊 **Classifications**: Statistical analysis with charts
- ⚖️ **Decisions**: Policy decision history
- 📋 **Audit Trail**: Complete action log
- ⚙️ **Policy**: Configuration management
- 📥 **Ingest Logs**: Upload interface


## Roadmap

### Phase 1 ✓ COMPLETE
- Classification Agent with Drain3
- Rule-based classification
- LLM fallback
- Sample data and CLI

### Phase 2 ✓ COMPLETE
- Value Assessment Agent with multi-factor scoring
- Decision/Policy Agent with compliance overrides
- Execution Agent with audit trail
- Integration tests and full pipeline

### Phase 3 ✓ COMPLETE
- FastAPI REST API with all endpoints
- API key authentication
- S3Backend implementation with storage classes
- Comprehensive API tests
- API documentation and examples

### Phase 4 ✓ COMPLETE
- Streamlit dashboard with comprehensive visualization
- Template explorer with filtering
- Classification statistics and charts
- Decision history viewer
- Audit trail browser
- Policy management UI
- Log ingestion interface
- Real-time data refresh

## Contributing

This is a hackathon MVP. Contributions welcome!

## License

MIT License

## Contact

For questions or issues, please open a GitHub issue.