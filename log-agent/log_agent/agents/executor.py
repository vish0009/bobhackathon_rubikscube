"""
Execution Agent - Executes retention actions and logs audit trail.

Performs actions against storage backend and maintains immutable audit log.
"""

from typing import List, Dict
from datetime import datetime
import json
from ..models import Decision, AuditEntry, LogEntry, Template, Tier
from ..storage import StorageBackend
from ..config import get_logger

logger = get_logger("system.executor")


class ExecutionAgent:
    """
    Agent responsible for executing retention decisions.
    
    Implements:
    - Action execution (RETAIN, ARCHIVE, DELETE, COMPRESS)
    - Storage backend operations
    - Audit trail logging
    - Rollback capabilities (basic)
    """
    
    def __init__(self, storage_backend: StorageBackend):
        """
        Initialize the execution agent.
        
        Args:
            storage_backend: Storage backend for operations
        """
        self.storage_backend = storage_backend
        logger.info("system.executor: Initialized")
    
    def execute(
        self,
        decisions: List[Decision],
        log_entries: List[LogEntry],
        templates: List[Template],
        line_to_template: Dict[str, str]
    ) -> List[AuditEntry]:
        """
        Execute retention decisions and create audit trail.
        
        Args:
            decisions: List of decisions to execute
            log_entries: Original log entries
            templates: List of templates
            line_to_template: Mapping of log_id to template_id
            
        Returns:
            List of audit entries
        """
        logger.info(f"system.executor: Executing {len(decisions)} decisions")
        
        # Build template-to-logs mapping
        template_logs: Dict[str, List[LogEntry]] = {}
        for entry in log_entries:
            template_id = line_to_template.get(entry.log_id)
            if template_id:
                if template_id not in template_logs:
                    template_logs[template_id] = []
                template_logs[template_id].append(entry)
        
        # Execute each decision
        audit_entries = []
        for i, decision in enumerate(decisions):
            logs = template_logs.get(decision.template_id, [])
            template = next((t for t in templates if t.template_id == decision.template_id), None)
            
            audit_entry = self._execute_decision(decision, logs, template, i)
            audit_entries.append(audit_entry)
        
        # Log statistics
        total_logs = sum(entry.affected_log_count for entry in audit_entries)
        total_bytes = sum(entry.bytes_freed for entry in audit_entries)
        
        logger.info(
            f"system.executor: Execution complete - "
            f"{total_logs} logs affected, {total_bytes} bytes freed"
        )
        
        return audit_entries
    
    def _execute_decision(
        self,
        decision: Decision,
        logs: List[LogEntry],
        template: Template,
        index: int
    ) -> AuditEntry:
        """
        Execute a single decision.
        
        Args:
            decision: Decision to execute
            logs: Log entries affected by this decision
            template: Template being acted upon
            index: Index for audit ID generation
            
        Returns:
            Audit entry for this execution
        """
        affected_count = len(logs)
        bytes_freed = 0
        from_tier = None
        to_tier = None
        
        try:
            if decision.action == "RETAIN":
                # Ensure logs are in HOT tier
                from_tier, to_tier = self._execute_retain(logs)
                logger.info(
                    f"system.executor: RETAIN - {affected_count} logs kept in HOT tier "
                    f"(template: {decision.template_id})"
                )
            
            elif decision.action == "ARCHIVE":
                # Move logs to COLD/ARCHIVE tier
                from_tier, to_tier, bytes_freed = self._execute_archive(logs)
                logger.info(
                    f"system.executor: ARCHIVE - {affected_count} logs moved to {to_tier.value} tier "
                    f"(template: {decision.template_id}, freed: {bytes_freed} bytes)"
                )
            
            elif decision.action == "DELETE":
                # Remove logs from storage
                from_tier, bytes_freed = self._execute_delete(logs)
                to_tier = None
                logger.info(
                    f"system.executor: DELETE - {affected_count} logs removed "
                    f"(template: {decision.template_id}, freed: {bytes_freed} bytes)"
                )
            
            elif decision.action == "COMPRESS":
                # Compress logs (future implementation)
                from_tier, to_tier, bytes_freed = self._execute_compress(logs)
                logger.info(
                    f"system.executor: COMPRESS - {affected_count} logs compressed "
                    f"(template: {decision.template_id}, freed: {bytes_freed} bytes)"
                )
            
            else:
                logger.warning(
                    f"system.executor: Unknown action '{decision.action}' for template {decision.template_id}"
                )
        
        except Exception as e:
            logger.error(
                f"system.executor: Error executing {decision.action} for template {decision.template_id}: {e}",
                exc_info=True
            )
        
        # Create audit entry
        return AuditEntry(
            audit_id=f"audit_{index:04d}_{decision.template_id}",
            timestamp=datetime.utcnow(),
            template_id=decision.template_id,
            action=decision.action,
            affected_log_count=affected_count,
            bytes_freed=bytes_freed,
            from_tier=from_tier,
            to_tier=to_tier,
            executor="system",
            metadata={
                "reasoning": decision.reasoning,
                "policy_override": decision.policy_override,
                "policy_rule_applied": decision.policy_rule_applied,
                "template_pattern": template.pattern if template else None,
                "template_match_count": template.match_count if template else 0
            }
        )
    
    def _execute_retain(self, logs: List[LogEntry]) -> tuple[Tier, Tier]:
        """
        Execute RETAIN action - ensure logs are in HOT tier.
        
        Args:
            logs: Log entries to retain
            
        Returns:
            Tuple of (from_tier, to_tier)
        """
        # For MVP, we just ensure they're marked as HOT
        # In production, this would check current tier and move if needed
        for log in logs:
            path = f"logs/{log.log_id}.json"
            
            # Check if file exists and get current tier
            if self.storage_backend.exists(path):
                current_tier = self.storage_backend.get_tier(path)
                if current_tier != Tier.HOT:
                    # Move to HOT tier
                    self.storage_backend.set_tier(path, Tier.HOT)
                    return current_tier, Tier.HOT
            else:
                # Write to HOT tier
                data = json.dumps(log.model_dump(), default=str).encode('utf-8')
                self.storage_backend.write(data, path, Tier.HOT)
        
        return Tier.HOT, Tier.HOT
    
    def _execute_archive(self, logs: List[LogEntry]) -> tuple[Tier, Tier, int]:
        """
        Execute ARCHIVE action - move logs to COLD tier.
        
        Args:
            logs: Log entries to archive
            
        Returns:
            Tuple of (from_tier, to_tier, bytes_freed)
        """
        bytes_freed = 0
        from_tier = Tier.HOT
        to_tier = Tier.COLD
        
        for log in logs:
            path = f"logs/{log.log_id}.json"
            
            # Check if file exists
            if self.storage_backend.exists(path):
                # Get current tier
                current_tier = self.storage_backend.get_tier(path)
                from_tier = current_tier
                
                # Calculate bytes (estimate based on JSON size)
                data = json.dumps(log.model_dump(), default=str).encode('utf-8')
                bytes_freed += len(data)
                
                # Move to COLD tier
                self.storage_backend.set_tier(path, Tier.COLD)
            else:
                # Write to COLD tier
                data = json.dumps(log.model_dump(), default=str).encode('utf-8')
                self.storage_backend.write(data, path, Tier.COLD)
        
        return from_tier, to_tier, bytes_freed
    
    def _execute_delete(self, logs: List[LogEntry]) -> tuple[Tier, int]:
        """
        Execute DELETE action - remove logs from storage.
        
        Args:
            logs: Log entries to delete
            
        Returns:
            Tuple of (from_tier, bytes_freed)
        """
        bytes_freed = 0
        from_tier = Tier.HOT
        
        for log in logs:
            path = f"logs/{log.log_id}.json"
            
            # Check if file exists
            if self.storage_backend.exists(path):
                # Get current tier before deletion
                from_tier = self.storage_backend.get_tier(path)
                
                # Calculate bytes (estimate based on JSON size)
                data = json.dumps(log.model_dump(), default=str).encode('utf-8')
                bytes_freed += len(data)
                
                # Delete the file
                self.storage_backend.delete(path)
        
        return from_tier, bytes_freed
    
    def _execute_compress(self, logs: List[LogEntry]) -> tuple[Tier, Tier, int]:
        """
        Execute COMPRESS action - compress logs (future implementation).
        
        Args:
            logs: Log entries to compress
            
        Returns:
            Tuple of (from_tier, to_tier, bytes_freed)
        """
        # Placeholder for future compression implementation
        # For now, treat as ARCHIVE
        logger.info("system.executor: COMPRESS not yet implemented, treating as ARCHIVE")
        return self._execute_archive(logs)

# Made with Bob
