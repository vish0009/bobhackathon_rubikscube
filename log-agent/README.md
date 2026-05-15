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

#### 1. Rules-Only Mode (No API Key Required)

```bash
python -m log_agent data/sample_logs.json data/sample_policy.json
```

This mode uses only rule-based classification. Perfect for testing and development.

#### 2. LLM-Enhanced Mode (Requires API Key)

```bash
# Set your Anthropic API key
export ANTHROPIC_API_KEY=your_key_here

# Run with LLM fallback
python -m log_agent data/sample_logs.json data/sample_policy.json
```

This mode uses LLM for ambiguous templates that rules can't classify with high confidence.

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
│   └── storage/             # Storage backends
│       ├── backend.py       # Abstract interface
│       ├── local_backend.py # ✓ Local filesystem
│       └── s3_backend.py    # S3 stub (Phase 3)
├── data/
│   ├── sample_logs.json     # Sample log data
│   └── sample_policy.json   # Sample policy rules
├── tests/                   # Test suite
│   ├── test_classifier.py   # Classification tests
│   └── test_phase2_integration.py  # ✓ Phase 2 integration tests
├── pyproject.toml           # Project configuration
└── README.md                # This file
```

## Configuration

### API Key Setup

The system uses Anthropic's Claude API for LLM fallback. Set your API key:

```bash
# Linux/Mac
export ANTHROPIC_API_KEY=your_key_here

# Windows PowerShell
$env:ANTHROPIC_API_KEY="your_key_here"

# Windows CMD
set ANTHROPIC_API_KEY=your_key_here
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

### Phase 3 (Next)
- FastAPI ingestion endpoint
- Query API for template lookup
- S3Backend implementation
- Real-time processing

### Phase 4
- Streamlit dashboard
- Real-time log streaming
- Cost optimization analytics
- Multi-tenant support

## Contributing

This is a hackathon MVP. Contributions welcome!

## License

MIT License

## Contact

For questions or issues, please open a GitHub issue.