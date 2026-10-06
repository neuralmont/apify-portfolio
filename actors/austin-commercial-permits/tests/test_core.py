import json
import sys
import unittest
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parents[1]))

from austin_actor.core import (  # noqa: E402
    ActorInputError,
    ExtractionError,
    build_where,
    contractor_summary,
    default_dates,
    normalize_record,
    run_extraction,
    validate_input,
)


FIELDS = [
    "permit_number", "issue_date", "permittype", "permit_class_mapped", "description",
    "status_current", "permit_location", "total_job_valuation", "contractor_trade",
    "contractor_company_name",
]


def source_row(number, *, description="New commercial shell", permit_class="Commercial", contractor="Acme Builders LLC"):
    return {
        "permit_number": number, "issue_date": "2026-10-06T00:00:00.000",
        "permittype": "BP", "permit_class_mapped": permit_class,
        "description": description, "status_current": "Issued",
        "permit_location": "100 Congress Ave", "total_job_valuation": "12345",
        "contractor_trade": "General Contractor", "contractor_company_name": contractor,
    }


class FakeClient:
    requests = retries_used = bytes = 0

    def __init__(self, pages, count=0):
        self.pages = pages
        self.count = count
        self.calls = []

    def get_json(self, url, params):
        self.calls.append(params)
        if "api/views" in url:
            return {"columns": [{"fieldName": field} for field in FIELDS]}
        if params.get("$select"):
            return [{"n": str(self.count)}]
        offset = int(params.get("$offset", 0))
        return self.pages[offset // 1000] if offset // 1000 < len(self.pages) else []


def test_default_dates_are_seven_inclusive_calendar_dates():
    assert default_dates(date(2026, 10, 6)) == ("2026-09-30", "2026-10-06")


def test_input_and_soql_boundaries_are_explicit_and_escaped():
    data = validate_input({"startDate": "2026-10-01", "endDate": "2026-10-06", "descriptionKeywords": ["O'Reilly"]})
    where = build_where(data)
    assert "issue_date between '2026-10-01T00:00:00' and '2026-10-06T23:59:59'" in where
    assert "o''reilly" in where
    try:
        validate_input({"startDate": "2026-10-07", "endDate": "2026-10-06"})
    except ActorInputError:
        pass
    else:
        raise AssertionError("reversed dates must be rejected")


def test_schema_shaped_record_preserves_raw_values_and_missing_as_null():
    row = normalize_record(source_row("A-1"), "2026-10-06T20:00:00+00:00")
    assert row["source_record_id"] == "A-1"
    assert row["project_valuation"] == "12345"
    assert row["source_class"] == "Commercial"
    assert row["latitude"] is None


def test_contractors_are_grouped_by_original_name_and_trade():
    rows = [normalize_record(source_row("1", contractor="Acme Builders LLC"), "t"), normalize_record(source_row("2", contractor="Acme Builders LLC"), "t")]
    rows[1]["contractor_trade"] = "Electrical Contractor"
    grouped = contractor_summary(rows, False)
    assert {(x["contractor_name_original"], x["contractor_trade"]) for x in grouped} == {("Acme Builders LLC", "General Contractor"), ("Acme Builders LLC", "Electrical Contractor")}
    assert all(x["count_is_not_project_count"] for x in grouped)


def test_pagination_cap_reports_raw_fetch_and_incomplete_status():
    client = FakeClient([[source_row(str(i)) for i in range(3)]], count=10)
    result = run_extraction(validate_input({"startDate": "2026-10-01", "endDate": "2026-10-06", "maxResults": 3}), client, "t")
    assert len(result["records"]) == 3
    assert result["summary"]["records_fetched"] == 3
    assert result["summary"]["records_delivered"] == 3
    assert result["summary"]["records_deduplicated"] == 0
    assert result["summary"]["completion"] == "incomplete"
    assert result["summary"]["cap_truncated"] is True


def test_duplicate_source_ids_are_rejected_and_mark_run_incomplete():
    client = FakeClient([[source_row("same"), source_row("same")]], count=2)
    result = run_extraction(validate_input({"startDate": "2026-10-01", "endDate": "2026-10-06"}), client, "t")
    assert len(result["records"]) == 1
    assert result["summary"]["records_deduplicated"] == 1
    assert result["summary"]["completion"] == "incomplete"
    assert any("duplicate source ID" in error for error in result["summary"]["errors"])


def load_tests(loader, standard_tests, pattern):
    names = [name for name in globals() if name.startswith("test_")]
    return unittest.TestSuite(unittest.FunctionTestCase(globals()[name]) for name in sorted(names))
