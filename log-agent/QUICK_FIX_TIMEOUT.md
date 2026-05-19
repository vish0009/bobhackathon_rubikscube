# Quick Fix for Timeout Issues

If you're getting timeout errors like:
```
API Error: HTTPConnectionPool(host='localhost', port=8000): Read timed out. (read timeout=30)
```

## Solution 1: Reduce LLM Calls (RECOMMENDED)

The timeout happens because too many templates are being sent to the LLM. Reduce the number of LLM calls:

```bash
# Set a lower confidence threshold (fewer LLM calls)
export LLM_CONFIDENCE_THRESHOLD=0.3

# Run your application
python -m log_agent data/sample_logs.json data/sample_policy.json
```

**What this does**: Only templates with very low confidence (< 0.3) will use the LLM. Most templates will use fast rule-based classification.

## Solution 2: Use Rules-Only Mode

Disable LLM completely for fastest processing:

```bash
# Disable LLM
export USE_LOCAL_LLM=false

# Run your application
python -m log_agent data/sample_logs.json data/sample_policy.json
```

## Solution 3: Use a Faster Model

If you need LLM classification, use a smaller/faster model:

1. In LM Studio, load a smaller model:
   - **Llama 3.1 8B Q4** (fastest)
   - **Mistral 7B Q4** (very fast)
   - **Phi-3 Medium Q4** (compact)

2. Enable GPU acceleration in LM Studio settings

3. Run with default settings:
   ```bash
   python -m log_agent data/sample_logs.json data/sample_policy.json
   ```

## Understanding the Confidence Threshold

The `LLM_CONFIDENCE_THRESHOLD` controls when to use LLM:

| Threshold | LLM Calls | Speed | Accuracy |
|-----------|-----------|-------|----------|
| 0.3 | Very Few | ⚡⚡⚡ Fast | Good |
| 0.5 | Some (default) | ⚡⚡ Moderate | Better |
| 0.7 | Many | ⚡ Slow | Best |

**Recommendation**: Start with `0.3` and increase only if needed.

## Current Settings

The application now has these optimizations:

✅ **Timeout increased**: 120 seconds (was 30)  
✅ **Default threshold**: 0.5 (balanced)  
✅ **Configurable**: Use `LLM_CONFIDENCE_THRESHOLD` env var  

## Testing Your Configuration

```bash
# Test with minimal LLM calls
export LLM_CONFIDENCE_THRESHOLD=0.3
python test_local_llm.py

# Check the output for:
# - Number of LLM calls (should be low)
# - Classification method breakdown
```

## Quick Commands

```bash
# Fastest (no LLM)
export USE_LOCAL_LLM=false
python -m log_agent data/sample_logs.json data/sample_policy.json

# Fast (minimal LLM)
export LLM_CONFIDENCE_THRESHOLD=0.3
python -m log_agent data/sample_logs.json data/sample_policy.json

# Balanced (default)
python -m log_agent data/sample_logs.json data/sample_policy.json

# Accurate (more LLM)
export LLM_CONFIDENCE_THRESHOLD=0.7
python -m log_agent data/sample_logs.json data/sample_policy.json
```

## Still Having Issues?

1. **Check your LLM server is running**:
   ```bash
   curl http://127.0.0.1:1234/v1/models
   ```

2. **Test response time**:
   ```bash
   time curl -X POST http://127.0.0.1:1234/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"messages":[{"role":"user","content":"Test"}],"max_tokens":10}'
   ```
   Should complete in < 5 seconds

3. **Use a smaller model** in LM Studio

4. **Enable GPU acceleration** in LM Studio settings