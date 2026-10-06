#!/usr/bin/env python3
"""Print reproducible completeness and contractor statistics for permits.jsonl."""
import json
import sys
from collections import Counter
from pathlib import Path

FIELDS = ("issue_date", "status_raw", "source_permit_type", "source_class", "work_description", "project_address", "latitude", "longitude", "contractor_name", "contractor_trade", "project_valuation")

path = Path(sys.argv[1])
rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
classified = [row for row in rows if row.get("source_class") in ("Commercial", "Residential")]
print(json.dumps({
    "records": len(rows),
    "classification_counts": Counter(row.get("source_class") or "unknown" for row in rows),
    "field_completeness": {field: sum(row.get(field) not in (None, "") for row in rows) for field in FIELDS},
    "contractor_completeness_overall": sum(row.get("contractor_name") not in (None, "") for row in rows),
    "contractor_completeness_commercial": sum(row.get("contractor_name") not in (None, "") for row in rows if row.get("source_class") == "Commercial"),
    "commercial_records": sum(row.get("source_class") == "Commercial" for row in rows),
    "classified_records": len(classified),
}, indent=2, default=dict))
