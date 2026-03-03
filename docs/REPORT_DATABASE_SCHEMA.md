# Report Database Schema

## Overview

Reports are stored in the `reports` table in SQLite. Each report is uniquely identified by the combination of `(ticker, run_id, report_type)`.

## Database Table: `reports`

**Location**: [`backend/models/db_models.py`](../backend/models/db_models.py) lines 25-40

### Schema Definition

```python
class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(32), nullable=False, index=True)
    run_id = Column(String(64), nullable=False)
    report_type = Column(String(64), nullable=False)
    content = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("ticker", "run_id", "report_type", name="uq_report_ticker_run_type"),
        Index("idx_reports_ticker_run", "ticker", "run_id"),
        Index("idx_reports_run_date", "run_id"),
    )
```

### Fields

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | Integer | No | Primary key, auto-increment |
| `ticker` | String(32) | No | Stock ticker symbol (e.g., "AAPL"), stored uppercase, indexed |
| `run_id` | String(64) | No | Analysis run identifier (format: `YYYY-MM-DD` or `YYYY-MM-DD_HH-MM-SS`) |
| `report_type` | String(64) | No | Type of report (see Report Types below) |
| `content` | Text | Yes | Markdown content of the report |
| `metadata_json` | Text | Yes | JSON string containing metadata (see Metadata Fields below) |
| `created_at` | DateTime | No | Timestamp when report was created (UTC) |

### Constraints & Indexes

1. **Unique Constraint**: `(ticker, run_id, report_type)` - Prevents duplicate reports
2. **Index**: `(ticker, run_id)` - Fast lookups by ticker and run
3. **Index**: `run_id` - Fast lookups by date
4. **Index**: `ticker` - Fast lookups by ticker

## Report Types

The following report types are generated during analysis:

### Analyst Reports
- `market_report` - Market Analyst's analysis
- `sentiment_report` - Social Media Analyst's sentiment analysis
- `news_report` - News Analyst's news analysis
- `fundamentals_report` - Fundamentals Analyst's financial analysis
- `technical_report` - Technical Analyst's chart analysis
- `sec_report` - SEC Analyst's regulatory filings analysis (US stocks only)

### Decision Reports
- `investment_plan` - Combined bull/bear research and recommendation
- `trader_investment_plan` - Trader's execution plan
- `final_trade_decision` - Portfolio Manager's final decision with risk analysis

## Metadata Fields

The `metadata_json` field stores a JSON object with the following possible fields:

### Common Fields (All Reports)
```json
{
  "score": 7.5,                    // Numeric score (0-10)
  "score_label": "Market Score",   // Label for the score
  "analysis_date": "2024-01-15",   // Date of analysis
  "generated_at": "2024-01-15T10:30:00Z",  // ISO timestamp
  "key_takeaways": [               // Array of key points (max 5)
    "Key point 1",
    "Key point 2"
  ],
  "models_used": {                 // LLM models used
    "provider": "azure",
    "deep_think": "gpt-4",
    "quick_think": "gpt-3.5-turbo"
  }
}
```

### Investment Plan Specific
```json
{
  "recommendation_score": 8.0,     // Conviction score (0-10)
  "expected_return_pct": 15.5,     // Expected return percentage
  "bull_case_return_pct": 25.0,    // Bull case return
  "bear_case_return_pct": -5.0,    // Bear case return
  "bull_viewpoint": [              // Bull researcher's arguments
    "Argument 1",
    "Argument 2"
  ],
  "bear_viewpoint": [              // Bear researcher's arguments
    "Argument 1",
    "Argument 2"
  ]
}
```

### Trader Plan Specific
```json
{
  "recommendation": "BUY",         // BUY, SELL, or HOLD
  "tps_plan": "..."               // TPS (Take Profit/Stop Loss) YAML plan
}
```

### Final Decision Specific
```json
{
  "recommendation": "BUY",         // Final recommendation
  "confidence": 0.85,              // Confidence level (0-1)
  "risk_score": 8.5,              // Risk score (0-10)
  "risky_viewpoint": [            // Aggressive analyst's view
    "Point 1"
  ],
  "safe_viewpoint": [             // Conservative analyst's view
    "Point 1"
  ],
  "neutral_viewpoint": [          // Neutral analyst's view
    "Point 1"
  ]
}
```

## Data Flow

### Writing Reports

**Location**: [`backend/services/report_service.py`](../backend/services/report_service.py) lines 96-143

```python
save_report(
    ticker="AAPL",
    run_id="2024-01-15_10-30-00",
    report_type="market_report",
    content="# Market Analysis\n...",
    metadata={
        "score": 7.5,
        "score_label": "Market Score",
        "key_takeaways": ["Point 1", "Point 2"],
        # ... other metadata
    }
)
```

The function:
1. Checks if report exists (by ticker, run_id, report_type)
2. If exists: Updates content and metadata
3. If not: Inserts new report
4. Commits to database

### Reading Reports

**Location**: [`backend/services/report_service.py`](../backend/services/report_service.py) lines 307-328

```python
# Get all reports for a specific run
reports = report_service.get_reports_with_scores("AAPL", "2024-01-15")

# Returns:
{
    "market_report": {
        "content": "...",
        "score": 7.5,
        "score_label": "Market Score",
        "key_takeaways": [...],
        "analysis_date": "2024-01-15",
        "generated_at": "2024-01-15T10:30:00Z",
        "days_ago": 0,
        # ... other fields
    },
    "news_report": { ... },
    # ... other reports
}
```

## Related Tables

### `analysis_runs` Table

Links reports to their creators for the token economy:

```python
class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String(32), nullable=False)
    run_id = Column(String(64), nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id"))
    earned_tokens = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### `report_views` Table

Tracks unique views per report for rewarding creators:

```python
class ReportView(Base):
    __tablename__ = "report_views"
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String(32), nullable=False)
    run_id = Column(String(64), nullable=False)
    viewer_id = Column(Integer, ForeignKey("users.id"))
    viewed_at = Column(DateTime, default=datetime.utcnow)
```

## Example Query Patterns

### Get Latest Report for Ticker
```python
latest_date = report_service.get_latest_report_date("AAPL")
reports = report_service.get_reports_with_scores("AAPL", latest_date)
```

### Check if Report Exists
```python
has_report = report_service.has_report_for_date("AAPL", "2024-01-15")
```

### Get All Tickers with Reports for Date
```python
tickers = report_service.get_tickers_with_reports_for_date("2024-01-15")
```

### Get Historical Analyses
```python
history = report_service.get_historical_analyses("AAPL")
# Returns: [
#   {"date": "2024-01-15_10-30-00", "available_reports": ["market_report", "news_report", ...]},
#   {"date": "2024-01-14_09-15-00", "available_reports": [...]},
# ]
```

## Multi-Worker Considerations

⚠️ **Important**: With multiple uvicorn workers, the unique constraint on `(ticker, run_id, report_type)` provides database-level protection against duplicate reports.

However, this does NOT prevent multiple workers from starting duplicate analyses - it only prevents them from writing duplicate reports. See [`docs/MULTI_WORKER_ISSUE.md`](./MULTI_WORKER_ISSUE.md) for details on the concurrency issue.

### What Happens with Duplicate Writes

If two workers try to write the same report:

1. **First worker**: Successfully inserts report
2. **Second worker**: Unique constraint violation → Updates existing report instead

The `save_report()` function handles this gracefully by checking for existing reports first (lines 108-116).

## Performance Considerations

### Indexes
- `ticker` index: Fast lookups by stock symbol
- `(ticker, run_id)` composite index: Fast lookups for specific analyses
- `run_id` index: Fast date-based queries

### Query Optimization
- Use `run_id.like(f"{date}%")` for date-based queries (leverages index)
- Paginated queries for large result sets
- Distinct queries for unique ticker lists

## Related Documentation

- Database Models: [`backend/models/db_models.py`](../backend/models/db_models.py)
- Report Service: [`backend/services/report_service.py`](../backend/services/report_service.py)
- Analysis Service: [`backend/services/analysis_service.py`](../backend/services/analysis_service.py)
- Multi-Worker Issue: [`docs/MULTI_WORKER_ISSUE.md`](./MULTI_WORKER_ISSUE.md)