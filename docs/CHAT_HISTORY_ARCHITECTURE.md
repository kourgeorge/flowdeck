# Chat History Architecture

## System Architecture Overview

```mermaid
graph TB
    subgraph "Frontend"
        UI[Chat UI]
        History[History Sidebar]
        Export[Export Feature]
    end
    
    subgraph "API Layer"
        ChatRouter[Chat Router<br/>/api/chat]
        HistoryRouter[History Router<br/>/api/chat/sessions]
    end
    
    subgraph "Service Layer"
        ChatService[Chat Service]
        SessionMgr[Session Manager]
        ToolLogger[Tool Call Logger]
    end
    
    subgraph "AI Engine"
        Agent[FlowDeck Agent]
        Tools[17 Tools]
        ToolNode[Tool Node]
    end
    
    subgraph "Database"
        Sessions[(chat_sessions)]
        Messages[(chat_messages)]
        ToolCalls[(chat_tool_calls)]
        Users[(users)]
    end
    
    UI --> ChatRouter
    History --> HistoryRouter
    Export --> HistoryRouter
    
    ChatRouter --> ChatService
    HistoryRouter --> SessionMgr
    
    ChatService --> Agent
    ChatService --> SessionMgr
    Agent --> ToolNode
    ToolNode --> Tools
    ToolNode --> ToolLogger
    
    SessionMgr --> Sessions
    SessionMgr --> Messages
    ToolLogger --> ToolCalls
    
    Sessions --> Users
    Messages --> Sessions
    ToolCalls --> Messages
```

## Data Flow: Chat Message with Persistence

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant ChatRouter
    participant ChatService
    participant SessionMgr
    participant Agent
    participant ToolNode
    participant ToolLogger
    participant DB
    
    User->>Frontend: Send message
    Frontend->>ChatRouter: POST /api/chat/stream
    ChatRouter->>ChatService: chat_stream(messages, user_id)
    
    ChatService->>SessionMgr: get_or_create_session()
    SessionMgr->>DB: INSERT/SELECT chat_sessions
    DB-->>SessionMgr: session_id
    
    ChatService->>SessionMgr: save_message(user, content)
    SessionMgr->>DB: INSERT chat_messages
    
    ChatService->>Agent: stream(messages)
    
    loop Tool Execution
        Agent->>ToolNode: invoke_tool(name, input)
        ToolNode->>ToolLogger: log_start(tool_name, input)
        ToolNode->>ToolNode: execute_tool()
        ToolNode->>ToolLogger: log_complete(output, status)
        ToolLogger->>DB: INSERT chat_tool_calls
        ToolNode-->>Agent: tool_result
    end
    
    Agent-->>ChatService: response_stream
    
    ChatService->>SessionMgr: save_message(assistant, content)
    SessionMgr->>DB: INSERT chat_messages
    
    ChatService->>SessionMgr: update_session_stats()
    SessionMgr->>DB: UPDATE chat_sessions
    
    ChatService-->>Frontend: SSE stream
    Frontend-->>User: Display response
```

## Database Schema Relationships

```mermaid
erDiagram
    users ||--o{ chat_sessions : "owns"
    chat_sessions ||--o{ chat_messages : "contains"
    chat_messages ||--o{ chat_tool_calls : "triggers"
    
    users {
        int id PK
        string email UK
        string name
        int token_balance
        datetime created_at
    }
    
    chat_sessions {
        int id PK
        int user_id FK
        string session_id UK "UUID"
        string title "Auto-generated"
        text context_json "Watchlist, page"
        datetime created_at
        datetime updated_at
        datetime last_message_at
        int message_count "Denormalized"
        int total_tokens_used "Cumulative"
        bool is_archived "Soft delete"
    }
    
    chat_messages {
        int id PK
        int session_id FK
        string role "user|assistant|system"
        text content "Message text"
        int tokens_used "For assistant"
        int tool_calls_count "Denormalized"
        datetime created_at
        text metadata_json "Charts, timing"
    }
    
    chat_tool_calls {
        int id PK
        int message_id FK
        int session_id FK "For queries"
        string tool_name "get_stock_quote"
        text tool_input "JSON params"
        text tool_output "JSON result"
        int execution_time_ms "Performance"
        string status "success|error"
        text error_message "If failed"
        datetime created_at
        int sequence_number "Order"
    }
```

## Component Interaction: Session Management

```mermaid
graph LR
    subgraph "Session Lifecycle"
        Create[Create Session]
        Active[Active Session]
        Archive[Archived]
        Delete[Deleted]
    end
    
    Create -->|First message| Active
    Active -->|User archives| Archive
    Active -->|90 days inactive| Archive
    Archive -->|User restores| Active
    Archive -->|180 days| Delete
    Active -->|User deletes| Delete
    
    subgraph "Operations"
        List[List Sessions]
        Load[Load History]
        Update[Update Title]
        Export[Export Data]
    end
    
    Active --> List
    Active --> Load
    Active --> Update
    Active --> Export
    Archive --> List
    Archive --> Load
    Archive --> Export
```

## Tool Call Logging Architecture

```mermaid
graph TB
    subgraph "Tool Execution Flow"
        Start[Tool Invoked]
        Capture[Capture Input]
        Execute[Execute Tool]
        Result[Capture Output]
        Log[Log to DB]
        Return[Return Result]
    end
    
    Start --> Capture
    Capture --> Execute
    Execute --> Result
    Result --> Log
    Log --> Return
    
    subgraph "Logged Data"
        Name[Tool Name]
        Input[Input Params]
        Output[Output Data]
        Time[Execution Time]
        Status[Success/Error]
        Seq[Sequence Number]
    end
    
    Capture --> Name
    Capture --> Input
    Capture --> Seq
    Result --> Output
    Result --> Time
    Result --> Status
    
    Name --> Log
    Input --> Log
    Output --> Log
    Time --> Log
    Status --> Log
    Seq --> Log
```

## API Endpoints Structure

```mermaid
graph TB
    subgraph "Chat Endpoints"
        Chat[POST /api/chat]
        Stream[POST /api/chat/stream]
    end
    
    subgraph "History Endpoints"
        ListSessions[GET /api/chat/sessions]
        GetSession[GET /api/chat/sessions/:id]
        CreateSession[POST /api/chat/sessions]
        UpdateSession[PUT /api/chat/sessions/:id]
        DeleteSession[DELETE /api/chat/sessions/:id]
        ExportSession[GET /api/chat/sessions/:id/export]
    end
    
    subgraph "Response Models"
        SessionList[SessionListResponse]
        SessionDetail[SessionDetailResponse]
        MessageList[MessageListResponse]
        ToolCallList[ToolCallListResponse]
    end
    
    ListSessions --> SessionList
    GetSession --> SessionDetail
    GetSession --> MessageList
    MessageList --> ToolCallList
```

## Frontend State Management

```mermaid
stateDiagram-v2
    [*] --> NoSession: User opens chat
    NoSession --> CreatingSession: First message sent
    CreatingSession --> ActiveSession: Session created
    ActiveSession --> LoadingHistory: User selects history
    LoadingHistory --> ActiveSession: History loaded
    ActiveSession --> SendingMessage: User sends message
    SendingMessage --> ActiveSession: Response received
    ActiveSession --> [*]: User closes chat
    
    note right of ActiveSession
        State includes:
        - session_id
        - messages[]
        - tool_calls[]
        - is_streaming
    end note
```

## Performance Optimization Strategy

```mermaid
graph TB
    subgraph "Write Optimization"
        Batch[Batch Tool Calls]
        Async[Async Writes]
        Index[Indexed Columns]
    end
    
    subgraph "Read Optimization"
        Paginate[Paginate Messages]
        LazyLoad[Lazy Load Tools]
        Cache[Cache Sessions]
    end
    
    subgraph "Storage Optimization"
        Truncate[Truncate Large Outputs]
        Compress[Compress Old Data]
        Archive[Archive Inactive]
    end
    
    Batch --> FastWrite[Fast Writes]
    Async --> FastWrite
    Index --> FastWrite
    
    Paginate --> FastRead[Fast Reads]
    LazyLoad --> FastRead
    Cache --> FastRead
    
    Truncate --> SmallDB[Smaller DB]
    Compress --> SmallDB
    Archive --> SmallDB
```

## Security & Privacy Model

```mermaid
graph TB
    subgraph "Access Control"
        Auth[Authentication]
        UserOnly[User-Only Access]
        AdminView[Admin Support View]
    end
    
    subgraph "Data Protection"
        Sanitize[Sanitize Inputs]
        Redact[Redact PII]
        Encrypt[Encrypt Sensitive]
    end
    
    subgraph "Data Lifecycle"
        Retention[Retention Policy]
        SoftDelete[Soft Delete]
        HardDelete[Hard Delete]
    end
    
    Auth --> UserOnly
    Auth --> AdminView
    
    UserOnly --> Sanitize
    AdminView --> Redact
    
    Sanitize --> Retention
    Redact --> Retention
    Retention --> SoftDelete
    SoftDelete --> HardDelete
```

## Implementation Phases

```mermaid
gantt
    title Chat History Implementation Timeline
    dateFormat YYYY-MM-DD
    section Phase 1: Database
    Design Schema           :done, 2026-03-03, 1d
    Create Models          :active, 2026-03-04, 1d
    Migration Script       :2026-03-05, 1d
    section Phase 2: Backend
    Update Chat Service    :2026-03-06, 2d
    Tool Call Logging      :2026-03-08, 2d
    section Phase 3: API
    History Endpoints      :2026-03-10, 2d
    Session Management     :2026-03-12, 1d
    section Phase 4: Frontend
    UI Components          :2026-03-13, 3d
    API Integration        :2026-03-16, 2d
    section Phase 5: Polish
    Data Retention         :2026-03-18, 1d
    Testing & Docs         :2026-03-19, 2d
```

## Key Design Decisions

### 1. Session-Based Architecture
- **Decision**: Use session-based model rather than flat message list
- **Rationale**: Enables conversation organization, context preservation, and better UX
- **Trade-off**: Slightly more complex schema, but much better user experience

### 2. Denormalized Counters
- **Decision**: Store `message_count` and `total_tokens_used` in sessions table
- **Rationale**: Faster queries for session lists, avoid expensive aggregations
- **Trade-off**: Need to maintain consistency on updates

### 3. Separate Tool Calls Table
- **Decision**: Store tool calls in separate table rather than in message metadata
- **Rationale**: Enables detailed querying, analytics, and debugging
- **Trade-off**: More storage, but much more valuable for analysis

### 4. Dual Foreign Keys in Tool Calls
- **Decision**: Reference both `message_id` and `session_id` in tool calls
- **Rationale**: Faster session-level queries without joining through messages
- **Trade-off**: Slight redundancy, but significant query performance gain

### 5. Soft Delete with Archive Flag
- **Decision**: Use `is_archived` flag rather than immediate deletion
- **Rationale**: Users can restore conversations, gradual cleanup
- **Trade-off**: Need cleanup job, but better user experience

## Monitoring & Observability

```mermaid
graph TB
    subgraph "Metrics"
        WriteLatency[Write Latency]
        ReadLatency[Read Latency]
        StorageSize[Storage Size]
        ErrorRate[Error Rate]
    end
    
    subgraph "Alerts"
        HighLatency[High Latency Alert]
        FailedWrites[Failed Writes Alert]
        StorageFull[Storage Full Alert]
    end
    
    subgraph "Dashboards"
        Usage[Usage Dashboard]
        Performance[Performance Dashboard]
        Errors[Error Dashboard]
    end
    
    WriteLatency --> HighLatency
    ReadLatency --> HighLatency
    ErrorRate --> FailedWrites
    StorageSize --> StorageFull
    
    WriteLatency --> Performance
    ReadLatency --> Performance
    StorageSize --> Usage
    ErrorRate --> Errors