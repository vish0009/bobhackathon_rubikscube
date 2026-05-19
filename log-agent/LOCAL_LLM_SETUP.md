# Local LLM Setup Guide

This guide explains how to configure the Log Agent to use a local LLM endpoint instead of cloud-based APIs.

## Overview

The Log Agent now supports three LLM backends (in priority order):
1. **Local LLM** (default) - Running at `http://127.0.0.1:1234`
2. **IBM Bob API** - Cloud-based endpoint
3. **Anthropic API** - Claude API

## Quick Start

### 1. Start Your Local LLM Server

Make sure you have a local LLM server running at `http://127.0.0.1:1234` that supports the OpenAI-compatible API format.

Popular options:
- **LM Studio** - Easy GUI for running local models
- **Ollama** - Command-line tool for local LLMs
- **llama.cpp** - C++ implementation with server mode
- **text-generation-webui** - Web interface for various models

### 2. Configure Environment Variables

The application is pre-configured to use the local LLM by default. No environment variables are required!

**Default Configuration:**
```bash
# These are the defaults (no need to set):
USE_LOCAL_LLM=true
LOCAL_LLM_ENDPOINT=http://127.0.0.1:1234
LLM_CONFIDENCE_THRESHOLD=0.5
```

**Optional: Override the settings:**
```bash
# If your local LLM runs on a different port:
export LOCAL_LLM_ENDPOINT=http://127.0.0.1:8080

# Reduce LLM calls (higher threshold = fewer calls):
export LLM_CONFIDENCE_THRESHOLD=0.3  # Only very ambiguous templates use LLM

# Increase LLM calls (lower threshold = more calls):
export LLM_CONFIDENCE_THRESHOLD=0.7  # More templates use LLM

# Or disable local LLM to use cloud APIs:
export USE_LOCAL_LLM=false
export ANTHROPIC_API_KEY=your_key_here
```

### 3. Run the Application

```bash
# Run the CLI
python -m log_agent data/sample_logs.json data/sample_policy.json

# Run the API server
uvicorn log_agent.api.main:app --reload

# Run the dashboard
streamlit run log_agent/dashboard/app.py
```

### 4. Test Local LLM Integration

```bash
# Run the test script
python test_local_llm.py
```

## How It Works

### Priority Order

The classifier checks for LLM backends in this order:

1. **Local LLM** (if `USE_LOCAL_LLM=true`)
   - Endpoint: `LOCAL_LLM_ENDPOINT` (default: `http://127.0.0.1:1234`)
   - No API key required
   - OpenAI-compatible API format

2. **IBM Bob API** (if `BOB_API_KEY` is set)
   - Endpoint: `BOB_ENDPOINT` (default: `https://api.us-east.bob.ibm.com`)
   - Requires API key

3. **Anthropic API** (if `ANTHROPIC_API_KEY` is set)
   - Official Claude API
   - Requires API key

4. **Rules-only mode** (fallback)
   - No LLM calls
   - Uses only rule-based classification

### API Format

The local LLM endpoint must support the OpenAI chat completions format:

```bash
POST http://127.0.0.1:1234/v1/chat/completions
Content-Type: application/json

{
  "messages": [
    {"role": "user", "content": "Your prompt here"}
  ],
  "max_tokens": 200,
  "temperature": 0.7
}
```

Expected response:
```json
{
  "choices": [
    {
      "message": {
        "content": "LLM response here"
      }
    }
  ],
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150
  }
}
```

## Recommended Models

For log classification, we recommend models with good instruction-following capabilities:

- **Llama 3.1 8B Instruct** - Good balance of speed and quality
- **Mistral 7B Instruct** - Fast and efficient
- **Phi-3 Medium** - Compact but capable
- **Qwen 2.5 7B Instruct** - Strong reasoning abilities

## Configuration Examples

### Example 1: LM Studio (Default)

LM Studio runs on port 1234 by default - no configuration needed!

```bash
# Just start LM Studio and load a model
# The app will automatically connect to http://127.0.0.1:1234
```

### Example 2: Ollama

```bash
# Start Ollama with OpenAI-compatible API
ollama serve

# Set the endpoint (Ollama uses port 11434)
export LOCAL_LLM_ENDPOINT=http://127.0.0.1:11434
```

### Example 3: Custom Port

```bash
# If your LLM server runs on a different port
export LOCAL_LLM_ENDPOINT=http://127.0.0.1:8080
```

### Example 4: Disable Local LLM

```bash
# Use cloud APIs instead
export USE_LOCAL_LLM=false
export ANTHROPIC_API_KEY=sk-ant-...
```

## Troubleshooting

### Connection Refused

**Problem:** `Connection refused` error when trying to connect to local LLM.

**Solution:**
1. Make sure your LLM server is running
2. Check the port number matches your configuration
3. Verify the endpoint URL is correct

```bash
# Test the endpoint manually
curl http://127.0.0.1:1234/v1/models
```

### No LLM Calls

**Problem:** All logs are classified with rules, no LLM calls made.

**Solution:** This is expected behavior! The system uses rules first and only calls the LLM for ambiguous templates (confidence < 0.7). To force LLM usage:

1. Use more diverse log messages
2. Lower the confidence threshold in the code
3. Check the test script output for classification method breakdown

### Slow Performance

**Problem:** Classification is taking too long.

**Solution:**
1. Use a smaller/faster model
2. Reduce `max_tokens` in the prompt
3. Enable GPU acceleration in your LLM server
4. Consider using quantized models (Q4 or Q5)

## Performance Tips

1. **Adjust Confidence Threshold**: Control how many templates trigger LLM calls
   - Default: `0.5` (balanced)
   - Conservative: `0.3` (fewer LLM calls, faster)
   - Aggressive: `0.7` (more LLM calls, better classification)

2. **Model Selection**: Smaller models (7B-8B) are usually sufficient for log classification

3. **Quantization**: Use Q4 or Q5 quantized models for faster inference

4. **GPU Acceleration**: Enable CUDA/Metal for significant speedup

5. **Batch Processing**: The system already batches by template, not by log line

6. **Caching**: Classifications are cached to avoid redundant LLM calls

### Recommended Settings for Different Scenarios

**Fast Processing (Minimal LLM calls)**:
```bash
export LLM_CONFIDENCE_THRESHOLD=0.3
# Use Llama 3.1 8B Q4 model
```

**Balanced (Default)**:
```bash
export LLM_CONFIDENCE_THRESHOLD=0.5
# Use Llama 3.1 8B Q5 model
```

**High Accuracy (More LLM calls)**:
```bash
export LLM_CONFIDENCE_THRESHOLD=0.7
# Use Llama 3.1 70B or Qwen 2.5 14B
```

## Monitoring

The application tracks LLM usage:

```python
# Access token usage statistics
classifier.token_usage
# {
#   "input_tokens": 1234,
#   "output_tokens": 567,
#   "total_tokens": 1801,
#   "llm_calls": 5
# }
```

## Security Notes

- Local LLM requires no API keys or authentication
- All data stays on your machine
- No external API calls when using local LLM
- Suitable for sensitive/compliance-restricted environments

## Support

For issues or questions:
1. Check the logs for error messages
2. Run `test_local_llm.py` to verify configuration
3. Ensure your LLM server supports OpenAI-compatible API
4. Check the LM Studio/Ollama documentation for server setup