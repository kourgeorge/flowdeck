# Polymarket Integration Architecture

## System Architecture Diagram

```mermaid
graph TB
    subgraph "External Services"
        PM[Polymarket API<br/>gamma-api.polymarket.com]
        CLOB[CLOB API<br/>clob.polymarket.com]
    end

    subgraph "Data Layer"
        PD[polymarket.py<br/>Dataflow Module]
        CACHE[Redis Cache<br/>5min TTL]
    end

    subgraph "Integration Layer"
        INT[interface.py<br/>Vendor Router]
        TOOLS[prediction_market_tools.py<br/>LangChain Tools]
    end

    subgraph "AI Agents"
        MA[Market Analyst]
        SA[Sentiment Analyst]
        NA[News Analyst]
    end

    subgraph "Backend Services"
        PS[polymarket_service.py<br/>Business Logic]
        API[REST API<br/>polymarket.py router]
    end

    subgraph "Frontend"
        PMW[PredictionMarketWidget]
        MSC[MarketSentimentChart]
        SDP[StockDetailPanel]
    end

    PM --> PD
    CLOB --> PD
    PD --> CACHE
    CACHE --> INT
    INT --> TOOLS
    TOOLS --> MA
    TOOLS --> SA
    TOOLS --> NA
    PD --> PS
    PS --> API
    API --> PMW
    API --> MSC
    PMW --> SDP
    MSC --> SDP

    style PM fill:#e1f5ff
    style CLOB fill:#e1f5ff
    style PD fill:#fff4e1
    style TOOLS fill:#fff4e1
    style MA fill:#e8f5e9
    style SA fill:#e8f5e9
    style NA fill:#e8f5e9
    style PMW fill:#f3e5f5
    style MSC fill:#f3e5f5
```

## Data Flow Sequence

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Backend
    participant PolymarketService
    participant DataflowModule
    participant PolymarketAPI
    participant AIAgent

    User->>Frontend: View Stock Page (AAPL)
    Frontend->>Backend: GET /api/polymarket/ticker/AAPL
    Backend->>PolymarketService: get_ticker_predictions(AAPL)
    PolymarketService->>DataflowModule: get_related_markets(AAPL)
    
    alt Cache Hit
        DataflowModule-->>PolymarketService: Return cached data
    else Cache Miss
        DataflowModule->>PolymarketAPI: Search markets for AAPL
        PolymarketAPI-->>DataflowModule: Market data
        DataflowModule->>DataflowModule: Cache for 5min
        DataflowModule-->>PolymarketService: Market data
    end
    
    PolymarketService-->>Backend: Formatted predictions
    Backend-->>Frontend: JSON response
    Frontend->>Frontend: Render PredictionMarketWidget
    
    User->>Frontend: Request AI Analysis
    Frontend->>Backend: POST /api/analysis/generate
    Backend->>AIAgent: Analyze AAPL
    AIAgent->>DataflowModule: get_prediction_market_sentiment(AAPL)
    DataflowModule-->>AIAgent: Sentiment data
    AIAgent->>AIAgent: Incorporate into analysis
    AIAgent-->>Backend: Complete report
    Backend-->>Frontend: Analysis with predictions
```

## Component Integration Points

```mermaid
graph LR
    subgraph "Existing Components"
        MA1[Market Analyst]
        SA1[Sentiment Analyst]
        SDP1[StockDetailPanel]
        DB1[Dashboard]
    end

    subgraph "New Polymarket Components"
        PMT[Prediction Market Tools]
        PMW1[PredictionMarketWidget]
        MSC1[MarketSentimentChart]
        PS1[PolymarketService]
    end

    MA1 -.->|Add tool| PMT
    SA1 -.->|Add tool| PMT
    SDP1 -.->|Add widget| PMW1
    SDP1 -.->|Add chart| MSC1
    DB1 -.->|Add section| PMW1
    PMT --> PS1
    PMW1 --> PS1
    MSC1 --> PS1

    style PMT fill:#ffeb3b
    style PMW1 fill:#ffeb3b
    style MSC1 fill:#ffeb3b
    style PS1 fill:#ffeb3b
```

## Configuration Flow

```mermaid
graph TD
    ENV[.env file<br/>POLYMARKET_API_BASE_URL]
    DC[default_config.py<br/>prediction_markets: polymarket]
    INT[interface.py<br/>VENDOR_METHODS]
    API[vendor domain API]
    PM[polymarket.py functions]

    ENV --> DC
    DC --> INT
    INT --> API
    API --> PM

    style ENV fill:#e3f2fd
    style DC fill:#fff3e0
    style INT fill:#f3e5f5
    style PM fill:#e8f5e9
```

## Agent Tool Integration

```mermaid
graph TB
    subgraph "Market Analyst Tools"
        T1[get_stock_data]
        T2[get_stock_quote]
        T3[get_indicators]
        T4[get_prediction_market_sentiment]
        T5[get_market_implied_probabilities]
    end

    subgraph "Tool Implementation"
        T4 --> PMF1[get_market_sentiment]
        T5 --> PMF2[get_related_markets]
        T5 --> PMF3[search_markets]
    end

    subgraph "Polymarket API"
        PMF1 --> API1[/markets/search]
        PMF2 --> API2[/markets]
        PMF3 --> API3[/markets/search]
    end

    style T4 fill:#ffeb3b
    style T5 fill:#ffeb3b
    style PMF1 fill:#fff4e1
    style PMF2 fill:#fff4e1
    style PMF3 fill:#fff4e1
```

## Frontend Component Hierarchy

```mermaid
graph TD
    APP[App.tsx]
    SP[StockPage.tsx]
    SDP[StockDetailPanel.tsx]
    
    subgraph "Existing Tabs"
        MT[MarketTab]
        NT[NewsTab]
        FT[FundamentalsTab]
    end
    
    subgraph "New Components"
        PMT[PredictionMarketsTab]
        PMW[PredictionMarketWidget]
        MSC[MarketSentimentChart]
        PML[PredictionMarketList]
    end

    APP --> SP
    SP --> SDP
    SDP --> MT
    SDP --> NT
    SDP --> FT
    SDP --> PMT
    PMT --> PMW
    PMT --> MSC
    PMT --> PML

    style PMT fill:#ffeb3b
    style PMW fill:#ffeb3b
    style MSC fill:#ffeb3b
    style PML fill:#ffeb3b
```

## Error Handling Flow

```mermaid
graph TD
    REQ[API Request]
    CACHE{Cache<br/>Available?}
    API{API<br/>Available?}
    RETRY{Retry<br/>Count < 3?}
    FALLBACK[Use Cached/Default]
    SUCCESS[Return Data]
    ERROR[Log Error & Degrade]

    REQ --> CACHE
    CACHE -->|Yes| SUCCESS
    CACHE -->|No| API
    API -->|Yes| SUCCESS
    API -->|No| RETRY
    RETRY -->|Yes| API
    RETRY -->|No| FALLBACK
    FALLBACK --> ERROR

    style SUCCESS fill:#4caf50
    style ERROR fill:#f44336
    style FALLBACK fill:#ff9800
```

## Caching Strategy

```mermaid
graph LR
    subgraph "Cache Layers"
        L1[In-Memory<br/>1min TTL]
        L2[Redis<br/>5min TTL]
        L3[Database<br/>24hr TTL]
    end

    subgraph "Data Types"
        D1[Market Prices<br/>High Frequency]
        D2[Market List<br/>Medium Frequency]
        D3[Historical Data<br/>Low Frequency]
    end

    D1 --> L1
    D2 --> L2
    D3 --> L3

    style L1 fill:#ffcdd2
    style L2 fill:#fff9c4
    style L3 fill:#c8e6c9
```

## Deployment Architecture

```mermaid
graph TB
    subgraph "Production Environment"
        LB[Load Balancer]
        
        subgraph "Backend Cluster"
            B1[Backend Instance 1]
            B2[Backend Instance 2]
        end
        
        subgraph "Cache Layer"
            RC[Redis Cluster]
        end
        
        subgraph "Database"
            DB[(PostgreSQL)]
        end
        
        subgraph "External"
            PM[Polymarket API]
        end
    end

    LB --> B1
    LB --> B2
    B1 --> RC
    B2 --> RC
    B1 --> DB
    B2 --> DB
    B1 --> PM
    B2 --> PM

    style LB fill:#e1f5ff
    style RC fill:#fff4e1
    style DB fill:#e8f5e9
    style PM fill:#f3e5f5
```

## Key Design Principles

### 1. Modularity
- Polymarket integration is a separate module
- Can be enabled/disabled via configuration
- No breaking changes to existing functionality

### 2. Performance
- Multi-layer caching strategy
- Async API calls
- Batch requests where possible
- Lazy loading in frontend

### 3. Reliability
- Graceful degradation if API unavailable
- Fallback to cached data
- Comprehensive error handling
- Rate limiting and backoff

### 4. Extensibility
- Easy to add new prediction market sources
- Pluggable architecture
- Clear interfaces between components

### 5. User Experience
- Clear data presentation
- Tooltips and explanations
- Visual indicators for data freshness
- Responsive design

## Technology Stack

### Backend
- **Python 3.11+**: Core language
- **FastAPI**: REST API framework
- **aiohttp**: Async HTTP client
- **Redis**: Caching layer
- **SQLAlchemy**: Database ORM

### AI/ML
- **LangChain**: Agent framework
- **LangGraph**: Multi-agent orchestration
- **OpenAI/Anthropic**: LLM providers

### Frontend
- **React 18**: UI framework
- **TypeScript**: Type safety
- **Vite**: Build tool
- **Recharts**: Data visualization

### Infrastructure
- **Docker**: Containerization
- **Nginx**: Reverse proxy
- **systemd**: Process management

## Security Considerations

1. **API Key Management**: No keys required for public Polymarket API
2. **Rate Limiting**: Implement client-side rate limiting
3. **Data Validation**: Validate all API responses
4. **Error Sanitization**: Don't expose internal errors to users
5. **CORS**: Proper CORS configuration for API endpoints

## Monitoring & Observability

```mermaid
graph LR
    subgraph "Metrics"
        M1[API Response Time]
        M2[Cache Hit Rate]
        M3[Error Rate]
        M4[Request Volume]
    end

    subgraph "Logging"
        L1[API Calls]
        L2[Cache Operations]
        L3[Errors]
        L4[User Actions]
    end

    subgraph "Alerts"
        A1[High Error Rate]
        A2[API Unavailable]
        A3[Cache Failures]
    end

    M3 --> A1
    L3 --> A2
    L2 --> A3

    style A1 fill:#f44336
    style A2 fill:#f44336
    style A3 fill:#f44336
```

## Next Steps

1. Review and approve this architecture
2. Set up development environment
3. Begin Phase 1 implementation (Core Infrastructure)
4. Iterate based on feedback and testing
