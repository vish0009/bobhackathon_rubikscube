# System Architecture — Autonomous Log Cleanup Agent

## High-Level Flow

```mermaid
graph TB
    subgraph Input
        A[Raw Log Lines]
        B[Policy File]
    end
    
    subgraph "Classification Agent"
        C[Drain3 Template Extraction]
        R[Redis Persistence]
        D[Rule-Based Classifier]
        E[LLM Fallback - Low Confidence Only]
        C <--> R
        C --> D
        D -->|Low Confidence| E
    end
    
    subgraph "Value Assessment Agent"
        F[Access Pattern Analysis]
        G[Recency Scoring]
        H[Priority Assignment]
        F --> H
        G --> H
    end
    
    subgraph "Decision/Policy Agent"
        I[Policy Rules Engine]
        J[Compliance Checker]
        K[Final Decision]
        I --> K
        J --> K
    end
    
    subgraph "Execution Agent"
        L[Action Executor]
        M[Audit Logger]
    end
    
    subgraph Storage
        N[Local Filesystem]
        O[S3 Future]
        P[Audit Trail]
    end
    
    A --> C
    B --> I
    D -->|High Confidence| F
    E --> F
    H --> I
    K --> L
    L --> N
    L --> O
    L --> M
    M --> P
```

## Data Flow

```mermaid
sequenceDiagram
    participant Logs as Raw Logs
    participant Class as Classifier
    participant Value as Valuer
    participant Policy as Decider
    participant Exec as Executor
    participant Store as Storage
    
    Logs->>Class: Ingest log lines
    Class->>Class: Extract templates (Drain3)
    Class->>Class: Apply rules
    Class->>Class: LLM fallback if needed
    Class->>Value: Classified templates
    
    Value->>Value: Analyze access patterns
    Value->>Value: Score recency
    Value->>Policy: Priority + recommendation
    
    Policy->>Policy: Load policy rules
    Policy->>Policy: Check compliance
    Policy->>Policy: Apply overrides
    Policy->>Exec: Final decisions
    
    Exec->>Store: Execute actions
    Exec->>Store: Write audit trail
    Store-->>Exec: Confirmation
```

## Data Models

```mermaid
classDiagram
    class LogEntry {
        +str log_id
        +datetime timestamp
        +str service
        +str environment
        +str log_level
        +str message
        +int access_count_last_30_days
    }
    
    class Template {
        +str template_id
        +str pattern
        +int match_count
        +datetime first_seen
        +datetime last_seen
    }
    
    class Classification {
        +str template_id
        +str type
        +str severity
        +str signal_quality
        +float confidence
        +str method
    }
    
    class ValueScore {
        +str template_id
        +str priority
        +str recommended_action
        +str reasoning
        +float score
    }
    
    class Decision {
        +str template_id
        +str action
        +str reasoning
        +bool policy_override
        +str policy_rule_applied
    }
    
    class AuditEntry {
        +str audit_id
        +datetime timestamp
        +str template_id
        +str action
        +int affected_log_count
        +int bytes_freed
        +Tier from_tier
        +Tier to_tier
        +str executor
        +dict metadata
    }
    
    class Policy {
        +dict retention_rules
        +dict compliance_overrides
        +dict storage_costs
        +dict environment_rules
    }
    
    LogEntry --> Template : extracted_from
    Template --> Classification : classified_as
    Classification --> ValueScore : assessed_as
    ValueScore --> Decision : decided_as
    Decision --> AuditEntry : executed_as
    Policy --> Decision : constrains
```

## Classification Agent Detail

```mermaid
flowchart TD
    A[Raw Log Lines] --> B[Drain3 Parser]
    B --> C{Check Cache}
    C -->|Cache Hit| K[Classification Result]
    C -->|Cache Miss| D{Drain3 Change Type}
    
    D -->|cluster_created| E[New Template]
    D -->|cluster_template_changed| F[Template Updated]
    D -->|none| G[Existing Match]
    
    E --> H[Rule Engine]
    F --> H
    G --> H
    
    H --> I{High Confidence?}
    I -->|Yes| J[Rule Classification]
    I -->|No| L{API Key Available?}
    
    L -->|Yes| M[LLM Classification]
    L -->|No| N[Default Classification]
    
    J --> K
    M --> K
    N --> K
    
    K --> O[Update Cache]
    O --> P[Template Mapping]
    P --> Q[Output: Classified Templates]
    
    style J fill:#90EE90
    style M fill:#FFB6C1
    style N fill:#FFD700
```

### Rule-Based Classification Logic

```mermaid
graph LR
    A[Log Entry] --> B{Log Level}
    B -->|ERROR| C[Severity: HIGH]
    B -->|WARN| D[Severity: MEDIUM]
    B -->|INFO| E[Severity: LOW]
    B -->|DEBUG| F[Severity: VERY_LOW]
    
    A --> G{Service Tags}
    G -->|compliance tag| H[Category: COMPLIANCE]
    G -->|security tag| I[Category: SECURITY]
    G -->|database tag| J[Category: DATABASE]
    G -->|application tag| K[Category: APPLICATION]
    
    A --> L{Environment}
    L -->|prod| M[Signal: HIGH]
    L -->|staging| N[Signal: MEDIUM]
    L -->|dev| O[Signal: LOW]
```

## Storage Backend Architecture

```mermaid
classDiagram
    class Tier {
        <<enumeration>>
        HOT
        WARM
        COLD
        ARCHIVE
    }
    
    class StorageBackend {
        <<interface>>
        +write(data: bytes, path: str, tier: Tier) bool
        +read(path: str) bytes
        +delete(path: str) bool
        +set_tier(path: str, tier: Tier) bool
        +get_tier(path: str) Tier
        +list(prefix: str) List~str~
    }
    
    class LocalFilesystemBackend {
        +str base_path
        +dict tier_directories
        +write(data, path, tier) bool
        +read(path) bytes
        +delete(path) bool
        +set_tier(path, tier) bool
        +get_tier(path) Tier
        +list(prefix) List~str~
    }
    
    class S3Backend {
        +str bucket_name
        +str region
        +write(data, path, tier) bool
        +read(path) bytes
        +delete(path) bool
        +set_tier(path, tier) bool
        +get_tier(path) Tier
        +list(prefix) List~str~
    }
    
    StorageBackend <|-- LocalFilesystemBackend
    StorageBackend <|-- S3Backend
    StorageBackend --> Tier
```

## Policy Decision Flow

```mermaid
flowchart TD
    A[Value Score] --> B{Check Compliance Tags}
    B -->|Has compliance tag| C[Apply Compliance Override]
    B -->|No compliance tag| D{Check Environment}
    
    C --> E[RETAIN - Compliance Required]
    
    D -->|Production| F{Check Log Level}
    D -->|Non-Production| G{Check Retention Rules}
    
    F -->|ERROR| H[RETAIN - High Priority]
    F -->|WARN| I{Check Access Pattern}
    F -->|INFO/DEBUG| J{Check Age}
    
    I -->|High Access| H
    I -->|Low Access| K[ARCHIVE]
    
    J -->|Recent| L[RETAIN - Short Term]
    J -->|Old| M[DELETE]
    
    G --> N{Apply Dev Rules}
    N --> O[Shorter Retention]
    
    style E fill:#4ECDC4
    style H fill:#4ECDC4
    style L fill:#4ECDC4
    style K fill:#FFE66D
    style M fill:#FF6B6B
    style O fill:#FFE66D
```

## Agent Interaction Pattern

```mermaid
sequenceDiagram
    participant Main as Main Process
    participant Class as Classifier
    participant Value as Valuer
    participant Policy as Decider
    participant Exec as Executor
    participant Audit as Audit Log
    
    Main->>Class: classify(logs)
    activate Class
    Class->>Class: extract_templates()
    Class->>Class: apply_rules()
    Class->>Class: llm_fallback()
    Class-->>Main: classifications
    deactivate Class
    
    Main->>Value: assess(classifications)
    activate Value
    Value->>Value: analyze_patterns()
    Value->>Value: score_priority()
    Value-->>Main: value_scores
    deactivate Value
    
    Main->>Policy: decide(value_scores, policy)
    activate Policy
    Policy->>Policy: load_policy()
    Policy->>Policy: check_compliance()
    Policy->>Policy: apply_rules()
    Policy-->>Main: decisions
    deactivate Policy
    
    Main->>Exec: execute(decisions)
    activate Exec
    Exec->>Exec: perform_actions()
    Exec->>Audit: log_execution()
    Exec-->>Main: results
    deactivate Exec
```

## Key Design Principles

### 1. Template-Level Processing
- **Why**: Reduces LLM calls from O(n) to O(unique_templates)
- **Impact**: 10x-100x cost reduction for typical log volumes
- **Trade-off**: Assumes logs with same pattern have same value

### 2. Rule-First Classification
- **Why**: Most logs follow predictable patterns
- **Coverage**: 80%+ of templates via rules
- **Fallback**: LLM only for genuinely ambiguous cases

### 3. Policy as Data
- **Why**: Non-engineers can modify retention rules
- **Format**: JSON with clear schema
- **Validation**: Pydantic ensures correctness

### 4. Immutable Audit Trail
- **Why**: Compliance and debugging
- **Storage**: Append-only log
- **Content**: Who, what, when, why for every action

### 5. Storage Abstraction
- **Why**: Easy migration from local to S3
- **Interface**: Common operations (read, write, delete, set_tier)
- **Future**: Add GCS, Azure Blob, etc.

## Performance Considerations

### Drain3 Template Extraction
- **Time Complexity**: O(n log m) where n=logs, m=templates
- **Memory**: O(m) for template storage
- **Optimization**: Batch processing, incremental updates

### LLM Classification
- **Bottleneck**: API latency (100-500ms per call)
- **Mitigation**: Only call for ambiguous templates
- **Caching**: Store classifications for reuse

### Storage Operations
- **Local**: Fast, limited by disk I/O
- **S3**: Network latency, but scalable
- **Optimization**: Batch operations, async writes

## Security & Compliance

### API Key Management
- Environment variable only
- Never logged or stored
- Graceful degradation without key

### Audit Trail
- Immutable append-only log
- Includes all decision context
- Tamper-evident timestamps

### Compliance Overrides
- Tag-based compliance detection (not service-name dependent)
- Flexible tagging system for compliance requirements
- Environment-specific policies
- Always logged in audit trail

## Future Enhancements

### Phase 2
- Real-time log streaming
- Incremental template updates
- Multi-tenant support

### Phase 3
- ML-based value prediction
- Anomaly detection
- Cost optimization dashboard

### Phase 4
- Distributed processing
- Multi-region storage
- Advanced compression strategies