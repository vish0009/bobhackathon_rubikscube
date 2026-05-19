# How to Use - Log Agent Application

## Quick Start Guide

### Prerequisites
- Python 3.8+
- LM Studio running locally
- Required packages installed

### Step-by-Step Instructions

#### 1. Start Local LLM Server
```bash
# Ensure LM Studio is running on:
http://127.0.0.1:1234
```

#### 2. Install Dependencies
```bash
cd bobhackathon_rubikscube/log-agent
pip install -e .
```

#### 3. Start API Server
```bash
# From log-agent directory
python -m log_agent.api.main
```
**API will run on:** `http://localhost:8000`

#### 4. Launch Dashboard
```bash
# Open new terminal in log-agent directory
python -m streamlit run log_agent/dashboard/app.py
```
**Dashboard will open in browser:** `http://localhost:8501`

### What You Can Do

- **Ingest Logs**: Upload log files through the dashboard
- **View Templates**: See extracted log patterns
- **Monitor Classifications**: Track log categorization
- **Review Decisions**: Check retention/archival actions
- **Audit Trail**: View complete operation history

### Troubleshooting

- **LLM Timeout?** Check `QUICK_FIX_TIMEOUT.md`
- **Setup Issues?** See `LOCAL_LLM_SETUP.md`
- **API Docs**: Visit `http://localhost:8000/docs`

### Environment Variables (Optional)
```bash
export LOG_AGENT_API_KEY=your-secret-key  # Enable API authentication
export ANTHROPIC_API_KEY=your-key         # Use Anthropic instead of local LLM