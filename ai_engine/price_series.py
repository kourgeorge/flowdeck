"""Parse the backend's annotated vendor CSV into validated daily closes."""
import csv
import io
import math
from datetime import date


def parse_daily_closes(raw: str):
    body = '\n'.join(line for line in raw.splitlines() if line.strip() and not line.lstrip().startswith('#'))
    prices = {}
    for row in csv.DictReader(io.StringIO(body)):
        try:
            day = str(row.get('Date', row.get('date', '')))[:10]
            date.fromisoformat(day)
            close = float(row.get('Close', row.get('close', '')))
            if math.isfinite(close) and close > 0:
                prices[day] = close
        except (TypeError, ValueError):
            continue
    return [{'Date': day, 'Close': prices[day]} for day in sorted(prices)]
