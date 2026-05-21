# Maintenance Guide

## Overview
This guide provides procedures for maintaining the Autonomous Log Cleanup & Archival Agent in production.

## Table of Contents
1. [Routine Maintenance](#routine-maintenance)
2. [Monitoring](#monitoring)
3. [Updates and Patches](#updates-and-patches)
4. [Database Maintenance](#database-maintenance)
5. [Log Management](#log-management)
6. [Performance Tuning](#performance-tuning)
7. [Backup Procedures](#backup-procedures)
8. [Emergency Procedures](#emergency-procedures)

## 1. Routine Maintenance

### Daily Tasks
- [ ] Check API health endpoint: `GET /health`
- [ ] Review system statistics: `GET /stats`
- [ ] Monitor error logs for anomalies
- [ ] Verify dashboard accessibility
- [ ] Check storage tier distribution

### Weekly Tasks
- [ ] Review audit trail for unusual patterns
- [ ] Analyze LLM token usage and costs
- [ ] Check storage capacity and growth trends
- [ ] Review classification accuracy
- [ ] Update policy rules if needed

### Monthly Tasks
- [ ] Review and update retention policies
- [ ] Analyze template growth patterns
- [ ] Performance benchmarking
- [ ] Security audit
- [ ] Documentation updates

### Quarterly Tasks
- [ ] Comprehensive system review
- [ ] Capacity planning
- [ ] Disaster recovery testing
- [ ] Dependency updates
- [ ] User feedback review

## 2. Monitoring

### Key Metrics to Monitor

#### System Health
```bash
# Check API health
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "phase": "3",
  "storage_backend": "LocalFilesystem",
  "policy_loaded": true
}
```

#### Performance Metrics
- API response times (target: < 200ms)
- Log processing throughput
- LLM call frequency and latency
- Storage I/O operations
- Memory usage
- CPU utilization

#### Business Metrics
- Total logs processed
- Unique templates extracted
- Classification accuracy
- Policy override rate
- Storage tier distribution
- Bytes freed by archival

### Monitoring Tools

#### Built-in Monitoring
```bash
# Get system statistics
curl http://localhost:8000/stats

# Monitor audit trail
curl http://localhost:8000/audit?limit=100
```

#### Dashboard Monitoring
- Access dashboard at `http://localhost:8501`
- Review Overview page for key metrics
- Check Classification Statistics for accuracy
- Monitor Decision History for policy effectiveness

#### Log Monitoring
```bash
# View application logs
tail -f logs/system.log

# Filter for errors
grep "ERROR" logs/system.log

# Filter for warnings
grep "WARNING" logs/system.log
```

### Alerting Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| API Response Time | > 500ms | > 1000ms |
| Error Rate | > 1% | > 5% |
| Storage Usage | > 80% | > 95% |
| LLM Failures | > 5% | > 20% |
| Memory Usage | > 80% | > 95% |

## 3. Updates and Patches

### Update Process

#### 1. Pre-Update Checklist
- [ ] Review changelog for breaking changes
- [ ] Backup current configuration
- [ ] Backup policy files
- [ ] Backup audit trail
- [ ] Schedule maintenance window
- [ ] Notify users

#### 2. Update Procedure
```bash
# 1. Stop services
systemctl stop log-agent-api
systemctl stop log-agent-dashboard

# 2. Backup current version
cp -r log-agent log-agent-backup-$(date +%Y%m%d)

# 3. Pull latest changes
cd log-agent
git pull origin main

# 4. Update dependencies
pip install -e . --upgrade

# 5. Run tests
pytest tests/

# 6. Start services
systemctl start log-agent-api
systemctl start log-agent-dashboard

# 7. Verify health
curl http://localhost:8000/health
```

#### 3. Post-Update Verification
- [ ] API health check passes
- [ ] Dashboard loads correctly
- [ ] Log ingestion works
- [ ] Classification functioning
- [ ] Policy rules applied correctly
- [ ] Audit trail accessible

#### 4. Rollback Procedure
```bash
# If update fails, rollback:
systemctl stop log-agent-api log-agent-dashboard
rm -rf log-agent
mv log-agent-backup-YYYYMMDD log-agent
systemctl start log-agent-api log-agent-dashboard
```

### Dependency Updates

#### Check for Updates
```bash
# List outdated packages
pip list --outdated

# Check security vulnerabilities
pip-audit
```

#### Update Dependencies
```bash
# Update specific package
pip install --upgrade package-name

# Update all dependencies (use with caution)
pip install -e . --upgrade

# Test after updates
pytest tests/
```

## 4. Database Maintenance

### Cache Management

#### Template Cache
```python
# Clear template cache (via API)
# Note: This will trigger re-classification on next ingestion
# Implement cache clear endpoint if needed
```

#### Classification Cache
- Automatically managed by application
- Cleared on service restart
- Monitor cache size in memory

### Audit Trail Management

#### Archive Old Audit Entries
```bash
# Export audit trail older than 90 days
curl "http://localhost:8000/audit?limit=10000" > audit_archive_$(date +%Y%m%d).json

# Implement audit trail cleanup if needed
```

## 5. Log Management

### Application Logs

#### Log Rotation
```bash
# Configure logrotate
cat > /etc/logrotate.d/log-agent << EOF
/var/log/log-agent/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 log-agent log-agent
    sharedscripts
    postrotate
        systemctl reload log-agent-api
    endscript
}
EOF
```

#### Log Analysis
```bash
# Count errors by type
grep "ERROR" logs/system.log | cut -d: -f4 | sort | uniq -c

# Find slow operations
grep "processing_time" logs/system.log | awk '{print $NF}' | sort -n | tail -20

# Monitor LLM usage
grep "llm_calls" logs/system.log
```

### Storage Logs

#### Monitor Storage Growth
```bash
# Check storage tier sizes
du -sh log_storage/hot
du -sh log_storage/warm
du -sh log_storage/cold
du -sh log_storage/archive

# Count files per tier
find log_storage/hot/logs -name "*.json" | wc -l
find log_storage/cold/logs -name "*.json" | wc -l
```

#### Cleanup Old Logs
```bash
# Archive logs older than retention period
# (Handled automatically by execution agent)

# Manual cleanup if needed
find log_storage/archive -name "*.json" -mtime +365 -delete
```

## 6. Performance Tuning

### API Performance

#### Optimize Response Times
```python
# Enable caching for frequently accessed data
# Implement pagination for large result sets
# Use background tasks for heavy operations
```

#### Connection Pooling
```python
# Configure connection limits
# Adjust timeout settings
# Monitor concurrent requests
```

### LLM Performance

#### Reduce LLM Calls
```python
# Adjust confidence threshold (default: 0.7)
# Higher threshold = fewer LLM calls
# Lower threshold = more LLM calls

# Set via environment variable
export LLM_CONFIDENCE_THRESHOLD=0.8
```

#### Batch Processing
```python
# Process logs in batches
# Optimize template extraction
# Cache LLM responses
```

### Storage Performance

#### Optimize File Operations
```bash
# Use SSD for hot tier
# Use HDD for cold/archive tiers
# Implement compression for archive tier
```

## 7. Backup Procedures

### What to Backup

#### Critical Data
- Policy configuration (`data/sample_policy.json`)
- Audit trail (via API export)
- Template cache (if using Redis)
- Application configuration
- Storage tier data

#### Backup Schedule
- **Hourly**: Audit trail incremental
- **Daily**: Policy configuration
- **Weekly**: Full storage backup
- **Monthly**: Complete system backup

### Backup Commands

```bash
# Backup policy
cp data/sample_policy.json backups/policy_$(date +%Y%m%d_%H%M%S).json

# Backup audit trail
curl http://localhost:8000/audit?limit=100000 > backups/audit_$(date +%Y%m%d).json

# Backup storage (hot tier only for daily)
tar -czf backups/storage_hot_$(date +%Y%m%d).tar.gz log_storage/hot/

# Full backup (weekly)
tar -czf backups/full_backup_$(date +%Y%m%d).tar.gz \
    log-agent/ \
    log_storage/ \
    data/
```

### Restore Procedures

```bash
# Restore policy
cp backups/policy_YYYYMMDD_HHMMSS.json data/sample_policy.json
systemctl restart log-agent-api

# Restore storage
tar -xzf backups/storage_hot_YYYYMMDD.tar.gz

# Full restore
tar -xzf backups/full_backup_YYYYMMDD.tar.gz
```

## 8. Emergency Procedures

### Service Down

#### Quick Diagnosis
```bash
# Check service status
systemctl status log-agent-api
systemctl status log-agent-dashboard

# Check logs
journalctl -u log-agent-api -n 100
tail -100 logs/system.log

# Check port availability
netstat -tulpn | grep 8000
netstat -tulpn | grep 8501
```

#### Recovery Steps
```bash
# 1. Stop services
systemctl stop log-agent-api log-agent-dashboard

# 2. Check for port conflicts
lsof -i :8000
lsof -i :8501

# 3. Clear any locks
rm -f /tmp/log-agent-*.lock

# 4. Restart services
systemctl start log-agent-api
systemctl start log-agent-dashboard

# 5. Verify
curl http://localhost:8000/health
```

### High Error Rate

#### Investigation
```bash
# Check recent errors
grep "ERROR" logs/system.log | tail -50

# Check LLM connectivity
curl -X POST http://localhost:11434/api/generate \
  -d '{"model": "llama3.2:3b", "prompt": "test"}'

# Check storage space
df -h
```

#### Mitigation
```bash
# Switch to rules-only mode
unset ANTHROPIC_API_KEY
systemctl restart log-agent-api

# Increase log level for debugging
export LOG_LEVEL=DEBUG
systemctl restart log-agent-api
```

### Storage Full

#### Immediate Actions
```bash
# Check storage usage
df -h

# Find largest directories
du -sh log_storage/* | sort -h

# Emergency cleanup (archive tier)
find log_storage/archive -name "*.json" -mtime +180 -delete

# Compress old logs
find log_storage/cold -name "*.json" -mtime +30 -exec gzip {} \;
```

### Data Corruption

#### Detection
```bash
# Verify JSON files
find log_storage -name "*.json" -exec python -m json.tool {} \; > /dev/null

# Check audit trail integrity
curl http://localhost:8000/audit | python -m json.tool
```

#### Recovery
```bash
# Restore from backup
cp backups/policy_latest.json data/sample_policy.json

# Rebuild template cache
# (Will happen automatically on next ingestion)

# Verify system
pytest tests/
```

## Contact Information

### Support Escalation
1. **Level 1**: Check this guide and troubleshooting docs
2. **Level 2**: Contact DevOps team
3. **Level 3**: Contact development team
4. **Level 4**: Emergency hotline

### Key Contacts
- **DevOps Lead**: [Email/Phone]
- **Technical Lead**: [Email/Phone]
- **On-Call Engineer**: [Rotation Schedule]

## Maintenance Log

Keep a log of all maintenance activities:

| Date | Activity | Performed By | Result | Notes |
|------|----------|--------------|--------|-------|
| 2026-05-21 | Bug fix deployment | Bob | Success | Fixed tier distribution |
| | | | | |

## Additional Resources

- [Troubleshooting Guide](TROUBLESHOOTING.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [API Documentation](API_DOCUMENTATION.md)
- [Security Guide](SECURITY.md)

---

**Last Updated**: 2026-05-21  
**Version**: 1.0.0  
**Maintained By**: DevOps Team