# Changelog

All notable changes to the Autonomous Log Cleanup & Archival Agent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- S3 storage backend implementation
- Redis template persistence
- Advanced analytics dashboard
- Real-time log streaming
- Custom policy DSL

## [1.0.1] - 2026-05-21

### Fixed
- **Storage Tier Distribution Bug**: Fixed dashboard displaying static data instead of dynamic real-time statistics
  - Root cause: API `/stats` endpoint returned lowercase tier names ("hot", "warm", "cold", "archive") but dashboard expected uppercase ("HOT", "WARM", "COLD", "ARCHIVE")
  - Solution: Added `.upper()` conversion in `log_agent/api/main.py` line 612
  - Impact: Dashboard now shows accurate, real-time file counts for each storage tier
  - Tested with 865 log files (825 HOT, 40 COLD)
  - Commit: 4d87b38

### Added
- Test script `test_tier_fix.py` to verify tier distribution functionality
- Comprehensive SDLC documentation folder with maintenance guides

## [1.0.0] - 2026-05-20

### Added - Phase 4: Dashboard
- Streamlit-based web dashboard for monitoring and management
- Overview page with system statistics and health checks
- Template explorer with pagination and filtering
- Classification statistics with interactive visualizations
- Decision history viewer with policy override tracking
- Audit trail browser with detailed execution records
- Policy management interface with JSON editor
- Log ingestion interface with LLM configuration controls
- Real-time data refresh capabilities

### Added - Phase 3: REST API
- FastAPI-based REST API with 13 endpoints
- Log ingestion endpoint with immediate/background processing
- Template query endpoints with pagination
- Classification listing with filters
- Decision history tracking
- Audit trail access
- Policy management (GET/PUT)
- System statistics endpoint
- Health check and status endpoints
- API key authentication (optional)
- Auto-generated OpenAPI/Swagger documentation
- S3 storage backend stub

### Added - Phase 2: Core Agents
- Value Assessment Agent with multi-factor scoring
  - Severity scoring (40% weight)
  - Access pattern analysis (25% weight)
  - Recency scoring (20% weight)
  - Signal quality assessment (10% weight)
  - Environment factor (5% weight)
- Decision/Policy Agent with rule engine
  - Compliance override system (tag-based)
  - Retention rules by log level
  - Environment-specific rules
  - Policy override tracking
- Execution Agent with storage operations
  - Action execution (RETAIN, ARCHIVE, DELETE, COMPRESS)
  - Storage tier management
  - Metrics tracking
  - Immutable audit trail
- Full pipeline integration in `__main__.py`

### Added - Phase 1: Classification
- Classification Agent with Drain3 integration
  - Template extraction (depth=4, similarity=0.4)
  - Rule-based classification (80%+ coverage)
  - LLM fallback for ambiguous templates
  - Confidence scoring system
  - Line-to-template mapping
  - Graceful degradation without API key
- Pydantic data models for all entities
  - LogEntry, Template, Classification
  - ValueScore, Decision, AuditEntry
  - Policy, Tier enum
- Local filesystem storage backend
  - Tier-based directory structure
  - File operations (read, write, delete)
  - Tier transitions
- Configuration and logging setup
- Sample data and test files

### Infrastructure
- Project structure and package setup
- Dependencies management (pyproject.toml)
- Comprehensive README documentation
- API and dashboard stubs
- Test framework setup

## [0.1.0] - 2026-05-15

### Added
- Initial project setup
- Project architecture design
- Technology stack selection
- Development environment configuration

## Version History Summary

| Version | Date | Phase | Key Features |
|---------|------|-------|--------------|
| 1.0.1 | 2026-05-21 | Maintenance | Bug fixes, SDLC docs |
| 1.0.0 | 2026-05-20 | Phase 4 | Dashboard complete |
| 0.4.0 | 2026-05-19 | Phase 4 | Dashboard development |
| 0.3.0 | 2026-05-18 | Phase 3 | REST API complete |
| 0.2.0 | 2026-05-17 | Phase 2 | Core agents complete |
| 0.1.0 | 2026-05-16 | Phase 1 | Classification complete |
| 0.0.1 | 2026-05-15 | Setup | Initial setup |

## Breaking Changes

### Version 1.0.0
- None (first stable release)

## Migration Guide

### Upgrading to 1.0.1
No migration required. This is a bug fix release with no breaking changes.

### Upgrading to 1.0.0
If upgrading from pre-release versions:
1. Update dependencies: `pip install -e .`
2. Review policy configuration format
3. Update API client code to use new endpoints
4. Test dashboard connectivity

## Known Issues

### Current
- None

### Resolved
- ✅ Storage tier distribution showing static data (Fixed in 1.0.1)

## Security Updates

### Version 1.0.0
- Added API key authentication support
- Input validation on all endpoints
- Secure configuration handling

## Performance Improvements

### Version 1.0.0
- Template-level processing reduces LLM calls by 10x-100x
- Efficient file counting for storage statistics
- Pagination support for large datasets
- Background processing for log ingestion

## Contributors

- Bob (AI Assistant) - Initial development and bug fixes
- [Your Team] - Requirements and testing

## Links

- [GitHub Repository](https://github.com/vish0009/bobhackathon_rubikscube)
- [Documentation](../README.md)
- [API Documentation](../log_agent/api/main.py)
- [Dashboard](../log_agent/dashboard/app.py)

---

**Note**: This changelog follows the [Keep a Changelog](https://keepachangelog.com/) format.
Categories: Added, Changed, Deprecated, Removed, Fixed, Security