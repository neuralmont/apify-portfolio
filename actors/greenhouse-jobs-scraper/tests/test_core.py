from types import SimpleNamespace

import pytest

from greenhouse_actor.core import ExtractionError, InputError, extract, html_to_text, normalize_board, validate_input


def job(job_id, title="Senior Engineer", location="Remote", internal=900, content="<p>Build &amp; ship.</p>", departments=None):
    return {"id": job_id, "internal_job_id": internal, "title": title, "updated_at": "2026-10-07T00:00:00Z", "location": {"name": location}, "absolute_url": f"https://boards.greenhouse.io/acme/jobs/{job_id}", "content": content, "departments": departments or [{"id": 1, "name": "Engineering"}], "offices": [{"id": 2, "name": "Remote", "location": "Worldwide"}]}


class FakeClient:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []
        self.stats = SimpleNamespace(requests=0, retries=0, bytes_received=0)

    def get_board(self, token):
        self.calls.append(token)
        self.stats.requests += 1
        value = self.payloads[token]
        if isinstance(value, Exception):
            raise value
        return value


def data(**overrides):
    value = {"boards": ["acme"], "maxJobs": 100}
    value.update(overrides)
    return validate_input(value)


def test_board_token_url_normalization_and_duplicate_boards():
    assert normalize_board(" https://job-boards.greenhouse.io/acme/ ") == "acme"
    assert validate_input({"boards": ["acme", "https://boards.greenhouse.io/acme"], "maxJobs": 2})["boards"] == ["acme"]
    with pytest.raises(InputError, match="individual"):
        normalize_board("https://boards.greenhouse.io/acme/jobs/12")


def test_filters_are_or_within_group_and_and_between_groups():
    client = FakeClient({"acme": {"jobs": [job(1, "Senior Engineer", "New York"), job(2, "Designer", "Remote", departments=[{"name": "Design"}]), job(3, "Data Engineer", "Remote")]}})
    result = extract(data(titleKeywords=["engineer", "designer"], locationKeywords=["remote"]), client)
    assert [row["job_id"] for row in result["records"]] == ["2", "3"]


def test_html_entities_and_markup_become_readable_text():
    assert html_to_text("<p>Build &amp; ship.</p><ul><li>Fast</li><li>Safe</li></ul>") == "Build & ship.\nFast\nSafe"


def test_job_id_is_identity_and_internal_id_is_nullable():
    client = FakeClient({"acme": {"jobs": [job(1, internal=99), job(2, internal=99), job(1, internal=100)]}})
    result = extract(data(), client)
    assert [row["job_id"] for row in result["records"]] == ["1", "2"]
    assert result["summary"]["duplicates"] == 1
    assert result["records"][0]["internal_job_id"] == "99"


def test_global_cap_counts_source_rows_and_skips_later_boards():
    client = FakeClient({"acme": {"jobs": [job(i) for i in range(4)]}, "beta": {"jobs": [job(9)]}})
    result = extract(data(boards=["acme", "beta"], maxJobs=3), client)
    assert len(result["records"]) == 3
    assert result["summary"]["records_fetched"] == 4
    assert result["summary"]["cap_truncated"] is True
    assert result["summary"]["skipped_boards"] == ["beta"]
    assert client.calls == ["acme"]


def test_empty_board_is_successful_not_failure():
    result = extract(data(), FakeClient({"acme": {"jobs": []}}))
    assert result["records"] == []
    assert result["summary"]["errors"] == []
    assert result["summary"]["requested_result_completion"] == "complete"


def test_failed_board_preserves_other_records_and_marks_incomplete():
    client = FakeClient({"acme": {"jobs": [job(1)]}, "bad": ExtractionError("invalid board")})
    result = extract(data(boards=["acme", "bad"]), client)
    assert len(result["records"]) == 1
    assert result["summary"]["boards_failed"] == 1
    assert result["summary"]["requested_result_completion"] == "incomplete"
    assert result["summary"]["errors"] == ["invalid board"]


def test_malformed_later_board_preserves_first_board_records():
    client = FakeClient({"acme": {"jobs": [job(1)]}, "bad": {"jobs": [None]}})
    result = extract(data(boards=["acme", "bad"]), client)
    assert [row["job_id"] for row in result["records"]] == ["1"]
    assert result["summary"]["boards_failed"] == 1
    assert result["summary"]["requested_result_completion"] == "incomplete"
    assert "non-object job" in result["summary"]["errors"][0]


def test_malformed_location_is_a_board_failure():
    malformed = job(1)
    malformed["location"] = ["not", "an", "object"]
    result = extract(data(), FakeClient({"acme": {"jobs": [malformed]}}))
    assert result["records"] == []
    assert result["summary"]["boards_failed"] == 1
    assert "location" in result["summary"]["errors"][0]


def test_exact_single_board_cap_is_requested_complete_but_not_full_matching_coverage():
    result = extract(data(maxJobs=2), FakeClient({"acme": {"jobs": [job(1), job(2)]}}))
    assert result["summary"]["requested_result_completion"] == "complete"
    assert result["summary"]["full_input_coverage"] is True
    assert result["summary"]["all_matching_jobs_delivered"] is True


def test_summary_has_no_job_payloads():
    result = extract(data(), FakeClient({"acme": {"jobs": [job(1)]}}))
    assert "records" not in result["summary"]
    assert "content" not in str(result["summary"])
