"""
Streamlit dashboard for log management visualization.

Provides:
- Overview metrics and statistics
- Template visualization and exploration
- Classification statistics
- Decision history
- Audit trail viewer
- Policy management UI
- Real-time monitoring
"""

import streamlit as st
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from log_agent.config import get_logger
    logger = get_logger("system.dashboard")
except ImportError:
    # Fallback to basic logging if import fails
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("system.dashboard")

# Configuration
API_BASE_URL = "http://localhost:8000"
DEFAULT_API_KEY = "bob_prod_bob-user_37ju5HfjRZr3o4sbjbXQKvHuoFRD3w3qS6x5xScRLZ5spXQSRaQ37V4yjmp1AXnPe787sDzS7Wr3mPyw1qP76rv_3XsQ3mHDXbyu3JWxmCBVQjLz2ZchgbmdNHnRXGeewp3Y"


# Helper Functions for API Calls
def get_api_headers() -> Dict[str, str]:
    """Get headers for API requests including API key if configured."""
    headers = {"Content-Type": "application/json"}
    api_key = st.session_state.get("api_key", DEFAULT_API_KEY)
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def api_get(endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
    """Make GET request to API."""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        response = requests.get(url, params=params, headers=get_api_headers(), timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        logger.error(f"system.dashboard: API GET error for {endpoint}: {e}")
        return None


def api_post(endpoint: str, data: Dict) -> Optional[Dict]:
    """Make POST request to API."""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        response = requests.post(url, json=data, headers=get_api_headers(), timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        logger.error(f"system.dashboard: API POST error for {endpoint}: {e}")
        return None


def api_put(endpoint: str, data: Dict) -> Optional[Dict]:
    """Make PUT request to API."""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        response = requests.put(url, json=data, headers=get_api_headers(), timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API Error: {str(e)}")
        logger.error(f"system.dashboard: API PUT error for {endpoint}: {e}")
        return None


# Page Functions

def show_overview():
    """Display overview page with key metrics and statistics."""
    st.header("📊 Overview")
    
    # Check API health
    health = api_get("/health")
    if not health:
        st.error("⚠️ Cannot connect to API server. Please ensure it's running on http://localhost:8000")
        st.code("python -m uvicorn log_agent.api.main:app --reload", language="bash")
        return
    
    # Display health status
    col1, col2, col3 = st.columns(3)
    with col1:
        status_color = "🟢" if health.get("status") == "healthy" else "🔴"
        st.metric("API Status", f"{status_color} {health.get('status', 'unknown').title()}")
    with col2:
        st.metric("Phase", health.get("phase", "N/A"))
    with col3:
        st.metric("Storage Backend", health.get("storage_backend", "N/A"))
    
    st.divider()
    
    # Get system statistics
    stats = api_get("/stats")
    if stats:
        st.subheader("📈 System Statistics")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Logs Processed", f"{stats.get('total_logs_processed', 0):,}")
        with col2:
            st.metric("Unique Templates", f"{stats.get('total_templates', 0):,}")
        with col3:
            st.metric("Total Decisions", f"{stats.get('total_decisions', 0):,}")
        with col4:
            st.metric("Audit Entries", f"{stats.get('total_audit_entries', 0):,}")
        
        st.divider()

        # BOB API token usage
        st.subheader("🤖 BOB API Token Usage")
        token_usage = stats.get("token_usage", {})
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Input Tokens", f"{token_usage.get('input_tokens', 0):,}")
        with col2:
            st.metric("Output Tokens", f"{token_usage.get('output_tokens', 0):,}")
        with col3:
            st.metric("Total Tokens", f"{token_usage.get('total_tokens', 0):,}")
        with col4:
            st.metric("LLM Calls", f"{token_usage.get('llm_calls', 0):,}")
        
        st.divider()
        
        # Storage tier distribution
        st.subheader("💾 Storage Tier Distribution")
        storage_tiers = stats.get("storage_tiers", {})
        
        if any(storage_tiers.values()):
            # Create pie chart
            tier_df = pd.DataFrame([
                {"Tier": tier, "Count": count}
                for tier, count in storage_tiers.items()
                if count > 0
            ])
            
            fig = px.pie(
                tier_df,
                values="Count",
                names="Tier",
                title="Logs by Storage Tier",
                color="Tier",
                color_discrete_map={
                    "HOT": "#FF6B6B",
                    "WARM": "#FFE66D",
                    "COLD": "#4ECDC4",
                    "ARCHIVE": "#95E1D3"
                }
            )
            st.plotly_chart(fig, width='stretch')
            
            # Show tier details
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🔥 HOT", storage_tiers.get("HOT", 0))
            with col2:
                st.metric("🌡️ WARM", storage_tiers.get("WARM", 0))
            with col3:
                st.metric("❄️ COLD", storage_tiers.get("COLD", 0))
            with col4:
                st.metric("📦 ARCHIVE", storage_tiers.get("ARCHIVE", 0))
        else:
            st.info("No logs in storage yet. Ingest some logs to see distribution.")
    
    st.divider()
    
    # Quick actions
    st.subheader("⚡ Quick Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Refresh Data", width='stretch'):
            st.rerun()
    
    with col2:
        if st.button("📝 View Templates", width='stretch'):
            st.session_state.page = "Templates"
            st.rerun()
    
    with col3:
        if st.button("📋 View Audit Trail", width='stretch'):
            st.session_state.page = "Audit Trail"
            st.rerun()


def show_templates():
    """Display template visualization and exploration."""
    st.header("📝 Template Explorer")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        severity_filter = st.selectbox(
            "Filter by Severity",
            ["All", "HIGH", "MEDIUM", "LOW", "VERY_LOW"],
            key="template_severity_filter"
        )
    with col2:
        limit = st.number_input("Results per page", min_value=10, max_value=100, value=20, step=10)
    with col3:
        offset = st.number_input("Offset", min_value=0, value=0, step=10)
    
    # Fetch templates
    params = {"limit": limit, "offset": offset}
    if severity_filter != "All":
        params["severity"] = severity_filter
    
    templates_data = api_get("/templates", params=params)
    
    if templates_data:
        total = templates_data.get("total", 0)
        classifications = templates_data.get("classifications", [])
        
        st.info(f"Showing {len(classifications)} of {total} templates")
        
        if classifications:
            # Display templates
            for item in classifications:
                template = item.get("template", {})
                classification = item.get("classification", {})
                
                with st.expander(
                    f"🔖 {template.get('template_id', 'N/A')[:8]}... - "
                    f"{classification.get('severity', 'N/A')} - "
                    f"{template.get('match_count', 0)} matches"
                ):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**Template Details**")
                        st.text(f"ID: {template.get('template_id', 'N/A')}")
                        st.text(f"Pattern: {template.get('pattern', 'N/A')}")
                        st.text(f"Matches: {template.get('match_count', 0)}")
                        st.text(f"First Seen: {template.get('first_seen', 'N/A')}")
                        st.text(f"Last Seen: {template.get('last_seen', 'N/A')}")
                    
                    with col2:
                        if classification:
                            st.markdown("**Classification**")
                            st.text(f"Type: {classification.get('type', 'N/A')}")
                            st.text(f"Severity: {classification.get('severity', 'N/A')}")
                            st.text(f"Signal Quality: {classification.get('signal_quality', 'N/A')}")
                            st.text(f"Confidence: {classification.get('confidence', 0):.2f}")
                            st.text(f"Method: {classification.get('method', 'N/A')}")
                    
                    # Get detailed info
                    if st.button(f"View Details", key=f"detail_{template.get('template_id')}"):
                        detail = api_get(f"/templates/{template.get('template_id')}")
                        if detail:
                            st.json(detail)
        else:
            st.warning("No templates found. Ingest some logs first.")


def show_classifications():
    """Display classification statistics and breakdown."""
    st.header("📊 Classification Statistics")
    
    # Fetch all classifications
    classifications_data = api_get("/classifications", params={"limit": 1000})
    
    if classifications_data:
        classifications = classifications_data.get("classifications", [])
        
        if classifications:
            df = pd.DataFrame(classifications)
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Classifications", len(classifications))
            with col2:
                rule_based = len([c for c in classifications if c.get("method") == "rule"])
                st.metric("Rule-Based", f"{rule_based} ({rule_based/len(classifications)*100:.1f}%)")
            with col3:
                llm_based = len([c for c in classifications if c.get("method") == "llm"])
                st.metric("LLM-Based", f"{llm_based} ({llm_based/len(classifications)*100:.1f}%)")
            with col4:
                avg_confidence = df["confidence"].mean() if "confidence" in df else 0
                st.metric("Avg Confidence", f"{avg_confidence:.2f}")
            
            st.divider()
            
            # Charts
            col1, col2 = st.columns(2)
            
            with col1:
                # Severity distribution
                st.subheader("Severity Distribution")
                severity_counts = df["severity"].value_counts()
                fig = px.bar(
                    x=severity_counts.index,
                    y=severity_counts.values,
                    labels={"x": "Severity", "y": "Count"},
                    color=severity_counts.index,
                    color_discrete_map={
                        "HIGH": "#FF6B6B",
                        "MEDIUM": "#FFE66D",
                        "LOW": "#4ECDC4",
                        "VERY_LOW": "#95E1D3"
                    }
                )
                st.plotly_chart(fig, width='stretch')
            
            with col2:
                # Type distribution
                st.subheader("Type Distribution")
                type_counts = df["type"].value_counts()
                fig = px.pie(
                    values=type_counts.values,
                    names=type_counts.index,
                    title="Classification Types"
                )
                st.plotly_chart(fig, width='stretch')
            
            st.divider()
            
            # Method comparison
            st.subheader("Classification Method Comparison")
            method_counts = df["method"].value_counts()
            fig = px.bar(
                x=method_counts.index,
                y=method_counts.values,
                labels={"x": "Method", "y": "Count"},
                title="Rule-Based vs LLM Classification"
            )
            st.plotly_chart(fig, width='stretch')
            
            # Signal quality distribution
            st.subheader("Signal Quality Distribution")
            signal_counts = df["signal_quality"].value_counts()
            fig = px.bar(
                x=signal_counts.index,
                y=signal_counts.values,
                labels={"x": "Signal Quality", "y": "Count"}
            )
            st.plotly_chart(fig, width='stretch')
        else:
            st.warning("No classifications found.")


def show_decisions():
    """Display decision history and analysis."""
    st.header("⚖️ Decision History")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        action_filter = st.selectbox(
            "Filter by Action",
            ["All", "RETAIN", "ARCHIVE", "DELETE", "COMPRESS"],
            key="decision_action_filter"
        )
    with col2:
        limit = st.number_input("Results per page", min_value=10, max_value=100, value=20, step=10, key="decision_limit")
    with col3:
        offset = st.number_input("Offset", min_value=0, value=0, step=10, key="decision_offset")
    
    # Fetch decisions
    params = {"limit": limit, "offset": offset}
    if action_filter != "All":
        params["action"] = action_filter
    
    decisions_data = api_get("/decisions", params=params)
    
    if decisions_data:
        total = decisions_data.get("total", 0)
        decisions = decisions_data.get("decisions", [])
        
        st.info(f"Showing {len(decisions)} of {total} decisions")
        
        if decisions:
            # Summary
            df = pd.DataFrame(decisions)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Decisions", total)
            with col2:
                policy_overrides = len([d for d in decisions if d.get("policy_override")])
                st.metric("Policy Overrides", f"{policy_overrides} ({policy_overrides/len(decisions)*100:.1f}%)")
            with col3:
                retain_count = len([d for d in decisions if d.get("action") == "RETAIN"])
                st.metric("RETAIN", retain_count)
            with col4:
                archive_count = len([d for d in decisions if d.get("action") == "ARCHIVE"])
                st.metric("ARCHIVE", archive_count)
            
            st.divider()
            
            # Action distribution
            st.subheader("Action Distribution")
            action_counts = df["action"].value_counts()
            fig = px.pie(
                values=action_counts.values,
                names=action_counts.index,
                title="Decision Actions",
                color=action_counts.index,
                color_discrete_map={
                    "RETAIN": "#4ECDC4",
                    "ARCHIVE": "#FFE66D",
                    "DELETE": "#FF6B6B",
                    "COMPRESS": "#95E1D3"
                }
            )
            st.plotly_chart(fig, width='stretch')
            
            st.divider()
            
            # Decision details
            st.subheader("Decision Details")
            for decision in decisions:
                with st.expander(
                    f"🎯 {decision.get('template_id', 'N/A')[:8]}... - "
                    f"{decision.get('action', 'N/A')} "
                    f"{'[POLICY OVERRIDE]' if decision.get('policy_override') else ''}"
                ):
                    st.text(f"Template ID: {decision.get('template_id', 'N/A')}")
                    st.text(f"Action: {decision.get('action', 'N/A')}")
                    st.text(f"Policy Override: {decision.get('policy_override', False)}")
                    if decision.get('policy_rule_applied'):
                        st.text(f"Policy Rule: {decision.get('policy_rule_applied', 'N/A')}")
                    st.markdown("**Reasoning:**")
                    st.write(decision.get('reasoning', 'N/A'))
        else:
            st.warning("No decisions found.")


def show_audit_trail():
    """Display audit trail of all executed actions."""
    st.header("📋 Audit Trail")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        action_filter = st.selectbox(
            "Filter by Action",
            ["All", "RETAIN", "ARCHIVE", "DELETE", "COMPRESS"],
            key="audit_action_filter"
        )
    with col2:
        limit = st.number_input("Results per page", min_value=10, max_value=100, value=20, step=10, key="audit_limit")
    with col3:
        offset = st.number_input("Offset", min_value=0, value=0, step=10, key="audit_offset")
    
    # Fetch audit trail
    params = {"limit": limit, "offset": offset}
    if action_filter != "All":
        params["action"] = action_filter
    
    audit_data = api_get("/audit", params=params)
    
    if audit_data:
        total = audit_data.get("total", 0)
        entries = audit_data.get("entries", [])
        
        st.info(f"Showing {len(entries)} of {total} audit entries")
        
        if entries:
            # Summary metrics
            df = pd.DataFrame(entries)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Entries", total)
            with col2:
                total_logs = sum(e.get("affected_log_count", 0) for e in entries)
                st.metric("Total Logs Affected", f"{total_logs:,}")
            with col3:
                total_bytes = sum(e.get("bytes_freed", 0) for e in entries)
                st.metric("Bytes Freed", f"{total_bytes:,}")
            with col4:
                avg_logs = total_logs / len(entries) if entries else 0
                st.metric("Avg Logs/Entry", f"{avg_logs:.1f}")
            
            st.divider()
            
            # Audit entries
            st.subheader("Audit Entries")
            for entry in entries:
                with st.expander(
                    f"📝 {entry.get('audit_id', 'N/A')[:8]}... - "
                    f"{entry.get('action', 'N/A')} - "
                    f"{entry.get('affected_log_count', 0)} logs"
                ):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.text(f"Audit ID: {entry.get('audit_id', 'N/A')}")
                        st.text(f"Timestamp: {entry.get('timestamp', 'N/A')}")
                        st.text(f"Template ID: {entry.get('template_id', 'N/A')}")
                        st.text(f"Action: {entry.get('action', 'N/A')}")
                        st.text(f"Executor: {entry.get('executor', 'N/A')}")
                    
                    with col2:
                        st.text(f"Affected Logs: {entry.get('affected_log_count', 0)}")
                        st.text(f"Bytes Freed: {entry.get('bytes_freed', 0)}")
                        st.text(f"From Tier: {entry.get('from_tier', 'N/A')}")
                        st.text(f"To Tier: {entry.get('to_tier', 'N/A')}")
                    
                    if entry.get('metadata'):
                        st.markdown("**Metadata:**")
                        st.json(entry.get('metadata'))
        else:
            st.warning("No audit entries found.")


def show_policy_management():
    """Display and manage policy configuration."""
    st.header("⚙️ Policy Management")
    
    # Fetch current policy
    policy_data = api_get("/policy")
    
    if policy_data:
        policy = policy_data.get("policy", {})
        
        st.subheader("Current Policy Configuration")
        
        # Display policy in tabs
        tab1, tab2, tab3, tab4 = st.tabs([
            "Retention Rules",
            "Compliance Overrides",
            "Storage Costs",
            "Environment Rules"
        ])
        
        with tab1:
            st.markdown("**Retention Rules (days by log level)**")
            retention_rules = policy.get("retention_rules", {})
            
            edited_retention = {}
            for level, rule in retention_rules.items():
                if isinstance(rule, dict):
                    current_days = int(rule.get("days", 30))
                    current_tier = rule.get("tier", "cold")
                    current_reason = rule.get("reason", "")
                else:
                    current_days = int(rule)
                    current_tier = "cold"
                    current_reason = ""

                st.markdown(f"**{level}**")
                edited_days = st.number_input(
                    f"{level} retention days",
                    min_value=1,
                    max_value=365,
                    value=current_days,
                    key=f"retention_{level}"
                )
                edited_retention[level] = {
                    "days": edited_days,
                    "tier": current_tier,
                    "reason": current_reason
                }
        
        with tab2:
            st.markdown("**Compliance Overrides (tag → action)**")
            compliance_overrides = policy.get("compliance_overrides", {})
            
            st.json(compliance_overrides)
            st.info("Compliance overrides ensure certain tagged logs are always retained.")
        
        with tab3:
            st.markdown("**Storage Costs ($/GB/month by tier)**")
            storage_costs = policy.get("storage_costs", {})
            
            for tier, cost in storage_costs.items():
                st.metric(tier, f"${cost:.5f}")
        
        with tab4:
            st.markdown("**Environment Rules**")
            environment_rules = policy.get("environment_rules", {})
            
            st.json(environment_rules)
        
        st.divider()
        
        # Update policy
        st.subheader("Update Policy")
        
        if st.button("💾 Save Retention Rules", type="primary"):
            # Build updated policy
            updated_policy = policy.copy()
            updated_policy["retention_rules"] = edited_retention
            
            result = api_put("/policy", updated_policy)
            if result:
                st.success("✅ Policy updated successfully!")
                st.rerun()
        
        st.divider()
        
        # Raw JSON editor
        with st.expander("🔧 Advanced: Edit Raw JSON"):
            st.warning("⚠️ Advanced users only. Invalid JSON will be rejected.")
            
            policy_json = st.text_area(
                "Policy JSON",
                value=json.dumps(policy, indent=2),
                height=400,
                key="policy_json_editor"
            )
            
            if st.button("💾 Update from JSON"):
                try:
                    updated_policy = json.loads(policy_json)
                    result = api_put("/policy", updated_policy)
                    if result:
                        st.success("✅ Policy updated successfully!")
                        st.rerun()
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON: {str(e)}")


def show_log_ingestion():
    """Display log ingestion interface."""
    st.header("📥 Log Ingestion")
    
    st.markdown("""
    Upload and process log entries through the full pipeline:
    1. Classification (template extraction + categorization)
    2. Value assessment (priority scoring)
    3. Decision making (policy application)
    4. Execution (storage operations)
    """)
    
    # Sample log template
    sample_log = {
        "log_id": "log_001",
        "timestamp": datetime.now().isoformat(),
        "service": "api-service",
        "environment": "prod",
        "log_level": "ERROR",
        "message": "Database connection failed",
        "access_count_last_30_days": 10,
        "tags": []
    }
    
    st.subheader("Log Entry Format")
    st.json(sample_log)
    
    st.divider()
    
    # Log input
    st.subheader("Enter Logs (JSON Array)")
    
    logs_json = st.text_area(
        "Logs JSON",
        value=json.dumps([sample_log], indent=2),
        height=300,
        key="logs_input"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        process_immediately = st.checkbox("Process Immediately", value=True)
    
    if st.button("📤 Ingest Logs", type="primary"):
        try:
            logs = json.loads(logs_json)
            
            if not isinstance(logs, list):
                st.error("Logs must be a JSON array")
                return
            
            result = api_post("/logs/ingest", {
                "logs": logs,
                "process_immediately": process_immediately
            })
            
            if result:
                st.success(f"✅ {result.get('message', 'Success')}")
                st.json(result)
                
                # Refresh data
                if st.button("🔄 Refresh Dashboard"):
                    st.rerun()
        
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON: {str(e)}")


# Main Application

def main():
    """Main dashboard application."""
    st.set_page_config(
        page_title="Log Agent Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    if "page" not in st.session_state:
        st.session_state.page = "Overview"
    if "api_key" not in st.session_state:
        st.session_state.api_key = None
    
    # Sidebar
    with st.sidebar:
        st.title("📊 Log Agent")
        st.caption("Autonomous Log Cleanup & Archival")
        
        st.divider()
        
        # Navigation
        st.subheader("Navigation")
        
        pages = {
            "📊 Overview": "Overview",
            "📝 Templates": "Templates",
            "📊 Classifications": "Classifications",
            "⚖️ Decisions": "Decisions",
            "📋 Audit Trail": "Audit Trail",
            "⚙️ Policy": "Policy",
            "📥 Ingest Logs": "Ingest"
        }
        
        for label, page in pages.items():
            if st.button(label, width='stretch', key=f"nav_{page}"):
                st.session_state.page = page
                st.rerun()
        
        st.divider()
        
        # API Configuration
        st.subheader("⚙️ Configuration")
        
        api_url = st.text_input("API URL", value=API_BASE_URL, key="api_url_input")
        
        api_key = st.text_input(
            "API Key (optional)",
            type="password",
            value=st.session_state.api_key or "",
            key="api_key_input"
        )
        
        if st.button("💾 Save Config"):
            st.session_state.api_key = api_key if api_key else None
            st.success("✅ Configuration saved")
        
        st.divider()
        
        # Info
        st.caption("Phase 4: Dashboard")
        st.caption("Version 0.4.0")
    
    # Main content
    st.title("📊 Autonomous Log Cleanup & Archival Agent")
    
    # Route to appropriate page
    page = st.session_state.page
    
    if page == "Overview":
        show_overview()
    elif page == "Templates":
        show_templates()
    elif page == "Classifications":
        show_classifications()
    elif page == "Decisions":
        show_decisions()
    elif page == "Audit Trail":
        show_audit_trail()
    elif page == "Policy":
        show_policy_management()
    elif page == "Ingest":
        show_log_ingestion()
    
    logger.info(f"system.dashboard: Rendered page: {page}")


if __name__ == "__main__":
    main()

# Made with Bob
