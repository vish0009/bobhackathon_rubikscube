# Troubleshooting Guide

## Overview
This guide provides solutions to common issues encountered with the Autonomous Log Cleanup & Archival Agent.

## Table of Contents
1. [API Issues](#api-issues)
2. [Dashboard Issues](#dashboard-issues)
3. [Classification Issues](#classification-issues)
4. [Storage Issues](#storage-issues)
5. [LLM Issues](#llm-issues)
6. [Performance Issues](#performance-issues)
7. [Data Issues](#data-issues)

## 1. API Issues

### Issue: API Server Won't Start

**Symptoms:**
- `systemctl start log-agent-api` fails
- Port 8000 already in use error

**Diagnosis:**
```bash
# Check if port is in use
netstat -tulpn | grep 8000
lsof -i :8000

# Check service status
systemctl status log-agent-api

# Check logs
journalctl -u log-agent-api -n 50
```

**Solutions:**

1. **Port Conflict:**
```bash
# Kill process using port 8000
kill -9 $(lsof -t -i:8000)

# Or change port in startup
uvicorn log_agent.api.main:app --port 8001
```

2. **Permission Issues:**
```bash
# Check file permissions
ls -la log-agent/

# Fix permissions
chmod +x log-agent/log_agent/api/main.py
```

3. **Missing Dependencies:**
```bash
# Reinstall dependencies
pip install -e . --force-reinstall
```

### Issue: API Returns 500 Errors

**Symptoms:**
- All endpoints return Internal Server Error
- Logs show Python exceptions

**Diagnosis:**
```bash
# Check detailed error logs
tail -100 logs/system.log | grep ERROR

# Test API health
curl -v http://localhost:8000/health
```

**Solutions:**

1. **Storage Backend Not Initialized:**
```bash
# Check if storage directory exists
ls -la log_storage/

# Create if missing
mkdir -p log_storage/{hot,warm,cold,archive}/logs
```

2. **Policy File Missing:**
```bash
# Check policy file
cat data/sample_policy.json

# Restore from backup if corrupted
cp backups/policy_latest.json data/sample_policy.json
```

3. **Python Path Issues:**
```bash
# Verify Python path
python -c "import log_agent; print(log_agent.__file__)"

# Reinstall package
pip uninstall log-agent
pip install -e .
```

### Issue: API Authentication Fails

**Symptoms:**
- 401 Unauthorized errors
- Valid API key rejected

**Diagnosis:**
```bash
# Check if API key is set
echo $LOG_AGENT_API_KEY

# Test without authentication
curl http://localhost:8000/health
```

**Solutions:**

1. **API Key Not Set:**
```bash
# Set API key
export LOG_AGENT_API_KEY="your-api-key"

# Restart service
systemctl restart log-agent-api
```

2. **Wrong API Key:**
```bash
# Use correct header
curl -H "X-API-Key: your-api-key" http://localhost:8000/logs/ingest
```

3. **Disable Authentication (Dev Only):**
```bash
# Unset API key
unset LOG_AGENT_API_KEY

# Restart service
systemctl restart log-agent-api
```

## 2. Dashboard Issues

### Issue: Dashboard Won't Load

**Symptoms:**
- Browser shows "Connection refused"
- Dashboard page blank or error

**Diagnosis:**
```bash
# Check if dashboard is running
netstat -tulpn | grep 8501

# Check Streamlit process
ps aux | grep streamlit

# Check logs
tail -50 logs/dashboard.log
```

**Solutions:**

1. **Dashboard Not Started:**
```bash
# Start dashboard
streamlit run log_agent/dashboard/app.py

# Or use systemd
systemctl start log-agent-dashboard
```

2. **Port Conflict:**
```bash
# Use different port
streamlit run log_agent/dashboard/app.py --server.port 8502
```

3. **API Not Accessible:**
```bash
# Check API connectivity from dashboard
curl http://localhost:8000/health

# Update API_BASE_URL in dashboard/app.py if needed
```

### Issue: Dashboard Shows "Cannot Connect to API"

**Symptoms:**
- Red error message on dashboard
- API health check fails

**Diagnosis:**
```bash
# Test API from dashboard server
curl http://localhost:8000/health

# Check network connectivity
ping localhost
```

**Solutions:**

1. **API Not Running:**
```bash
# Start API server
systemctl start log-agent-api
```

2. **Wrong API URL:**
```python
# Update in dashboard/app.py
API_BASE_URL = "http://localhost:8000"  # Correct URL
```

3. **Firewall Blocking:**
```bash
# Check firewall rules
sudo iptables -L

# Allow port 8000
sudo ufw allow 8000
```

### Issue: Storage Tier Distribution Shows Static Data

**Status:** ✅ FIXED in v1.0.1

**Symptoms:**
- Pie chart doesn't update
- File counts remain constant

**Solution:**
- Upgrade to v1.0.1 or later
- The bug was fixed by converting tier names to uppercase in the API

**Verification:**
```bash
# Test the fix
python test_tier_fix.py

# Should show uppercase tier names: HOT, WARM, COLD, ARCHIVE
```

## 3. Classification Issues

### Issue: All Logs Classified as "UNKNOWN"

**Symptoms:**
- Classification confidence very low
- No rule-based matches

**Diagnosis:**
```bash
# Check log format
cat data/sample_logs.json | python -m json.tool

# Test classification
python -m log_agent data/sample_logs.json data/sample_policy.json
```

**Solutions:**

1. **Invalid Log Format:**
```json
// Ensure logs have required fields
{
  "log_id": "log_001",
  "timestamp": "2024-01-01T00:00:00Z",
  "service": "api-service",
  "environment": "prod",
  "log_level": "ERROR",
  "message": "Error message",
  "access_count_last_30_days": 10,
  "tags": []
}
```

2. **Missing log_level Field:**
```python
# Add default log_level if missing
log_entry["log_level"] = log_entry.get("log_level", "INFO")
```

3. **Drain3 Configuration:**
```python
# Adjust Drain3 parameters in classifier.py
depth = 4  # Increase for more specific templates
sim_th = 0.4  # Decrease for more lenient matching
```

### Issue: LLM Classification Not Working

**Symptoms:**
- All classifications use rules
- No LLM calls in logs

**Diagnosis:**
```bash
# Check if LLM is enabled
grep "llm_calls" logs/system.log

# Test LLM connectivity
curl -X POST http://localhost:11434/api/generate \
  -d '{"model": "llama3.2:3b", "prompt": "test"}'
```

**Solutions:**

1. **LLM Not Configured:**
```bash
# For Ollama (local)
ollama pull llama3.2:3b
ollama serve

# For Anthropic (cloud)
export ANTHROPIC_API_KEY="your-key"
```

2. **Confidence Threshold Too High:**
```python
# Lower threshold in classifier.py
if classification.confidence < 0.5:  # Was 0.7
    # Use LLM fallback
```

3. **LLM Timeout:**
```python
# Increase timeout in classifier.py
response = requests.post(url, json=payload, timeout=300)  # 5 minutes
```

## 4. Storage Issues

### Issue: Storage Full

**Symptoms:**
- "No space left on device" errors
- Write operations fail

**Diagnosis:**
```bash
# Check disk space
df -h

# Check storage usage by tier
du -sh log_storage/*
```

**Solutions:**

1. **Emergency Cleanup:**
```bash
# Archive old logs
find log_storage/hot -name "*.json" -mtime +30 -exec mv {} log_storage/cold/ \;

# Delete very old logs
find log_storage/archive -name "*.json" -mtime +365 -delete
```

2. **Compress Logs:**
```bash
# Compress cold tier
find log_storage/cold -name "*.json" -exec gzip {} \;
```

3. **Adjust Retention Policy:**
```json
// Reduce retention periods in policy
{
  "retention_rules": {
    "ERROR": {"days": 30},  // Was 90
    "INFO": {"days": 7}     // Was 30
  }
}
```

### Issue: Files Not Moving Between Tiers

**Symptoms:**
- All logs stay in HOT tier
- Execution agent not working

**Diagnosis:**
```bash
# Check audit trail
curl http://localhost:8000/audit | python -m json.tool

# Check execution logs
grep "executor" logs/system.log
```

**Solutions:**

1. **Policy Not Applied:**
```bash
# Verify policy loaded
curl http://localhost:8000/policy

# Reload policy
systemctl restart log-agent-api
```

2. **Permissions Issue:**
```bash
# Check directory permissions
ls -la log_storage/

# Fix permissions
chmod -R 755 log_storage/
```

3. **Decision Logic:**
```python
# Check decision agent logic
# Ensure decisions are being made correctly
```

## 5. LLM Issues

### Issue: LLM Calls Timing Out

**Symptoms:**
- Log processing very slow
- Timeout errors in logs

**Diagnosis:**
```bash
# Check LLM response time
time curl -X POST http://localhost:11434/api/generate \
  -d '{"model": "llama3.2:3b", "prompt": "test"}'

# Check system resources
top
nvidia-smi  # If using GPU
```

**Solutions:**

1. **Increase Timeout:**
```python
# In classifier.py
response = requests.post(url, json=payload, timeout=300)  # 5 minutes
```

2. **Use Smaller Model:**
```bash
# Switch to faster model
ollama pull llama3.2:1b  # Smaller, faster
```

3. **Reduce LLM Usage:**
```python
# Increase confidence threshold
if classification.confidence < 0.8:  # Was 0.7
    # Fewer LLM calls
```

### Issue: High LLM Costs

**Symptoms:**
- Unexpected API bills
- Too many LLM calls

**Diagnosis:**
```bash
# Check token usage
curl http://localhost:8000/stats | jq '.token_usage'

# Count LLM calls
grep "llm_calls" logs/system.log | wc -l
```

**Solutions:**

1. **Optimize Classification:**
```python
# Improve rule-based classification
# Add more rules to reduce LLM fallback
```

2. **Batch Processing:**
```python
# Process multiple templates in one LLM call
# (Requires code modification)
```

3. **Use Local LLM:**
```bash
# Switch to Ollama instead of Anthropic
ollama serve
# Remove ANTHROPIC_API_KEY
```

## 6. Performance Issues

### Issue: Slow Log Processing

**Symptoms:**
- Processing 1000 logs takes > 10 minutes
- High CPU usage

**Diagnosis:**
```bash
# Profile processing time
time python -m log_agent data/sample_logs.json data/sample_policy.json

# Check resource usage
top
htop
```

**Solutions:**

1. **Disable LLM:**
```bash
# Use rules-only mode
unset ANTHROPIC_API_KEY
# Should process 1000 logs in < 30 seconds
```

2. **Optimize Drain3:**
```python
# Use Redis persistence instead of in-memory
# Reduces template extraction time
```

3. **Batch Processing:**
```python
# Process logs in smaller batches
# Reduces memory usage
```

### Issue: High Memory Usage

**Symptoms:**
- System running out of memory
- OOM killer terminating processes

**Diagnosis:**
```bash
# Check memory usage
free -h
ps aux --sort=-%mem | head -10
```

**Solutions:**

1. **Clear Caches:**
```python
# Implement cache size limits
# Clear old templates periodically
```

2. **Process in Batches:**
```python
# Reduce batch size
# Process 100 logs at a time instead of 1000
```

3. **Increase System Memory:**
```bash
# Add swap space
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

## 7. Data Issues

### Issue: Corrupted JSON Files

**Symptoms:**
- JSON parse errors
- Invalid log entries

**Diagnosis:**
```bash
# Find corrupted files
find log_storage -name "*.json" -exec python -m json.tool {} \; 2>&1 | grep -B1 "Expecting"

# Validate specific file
python -m json.tool log_storage/hot/logs/log_001.json
```

**Solutions:**

1. **Restore from Backup:**
```bash
# Restore corrupted files
cp backups/log_storage_YYYYMMDD.tar.gz .
tar -xzf log_storage_YYYYMMDD.tar.gz
```

2. **Remove Corrupted Files:**
```bash
# Remove invalid JSON files
find log_storage -name "*.json" -exec sh -c 'python -m json.tool {} > /dev/null 2>&1 || rm {}' \;
```

3. **Fix JSON Format:**
```python
# Use JSON repair tool
pip install jsonrepair
python -c "from jsonrepair import repair_json; print(repair_json(open('file.json').read()))"
```

### Issue: Audit Trail Inconsistencies

**Symptoms:**
- Missing audit entries
- Incorrect metrics

**Diagnosis:**
```bash
# Check audit trail
curl http://localhost:8000/audit | python -m json.tool

# Verify audit entry count
curl http://localhost:8000/stats | jq '.total_audit_entries'
```

**Solutions:**

1. **Rebuild Audit Trail:**
```bash
# Export current audit trail
curl http://localhost:8000/audit?limit=100000 > audit_backup.json

# Restart service (clears in-memory audit)
systemctl restart log-agent-api

# Re-process logs to rebuild audit
```

2. **Verify Data Integrity:**
```python
# Check for duplicate audit IDs
# Verify timestamps are sequential
# Ensure all required fields present
```

## Quick Reference

### Common Commands

```bash
# Restart all services
systemctl restart log-agent-api log-agent-dashboard

# Check all logs
tail -f logs/system.log

# Test API
curl http://localhost:8000/health

# Test dashboard
curl http://localhost:8501

# Clear caches
rm -rf __pycache__/ *.pyc

# Run tests
pytest tests/

# Check storage
du -sh log_storage/*
```

### Emergency Contacts

- **DevOps Team**: [Contact Info]
- **Development Team**: [Contact Info]
- **On-Call Engineer**: [Contact Info]

### Additional Resources

- [Maintenance Guide](MAINTENANCE_GUIDE.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [API Documentation](../README.md)
- [GitHub Issues](https://github.com/vish0009/bobhackathon_rubikscube/issues)

---

**Last Updated**: 2026-05-21  
**Version**: 1.0.0  
**Maintained By**: DevOps Team