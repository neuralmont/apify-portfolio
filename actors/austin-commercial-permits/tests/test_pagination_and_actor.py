import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from austin_actor import core  # noqa: E402
from austin_actor import main as actor_main  # noqa: E402


FIELDS = [
    "permit_number", "issue_date", "permittype", "permit_class_mapped", "description",
    "status_current", "permit_location", "total_job_valuation", "contractor_trade",
    "contractor_company_name",
]


def row(number):
    return {
        "permit_number": f"A-{number}", "issue_date": "2026-10-06T00:00:00.000",
        "permittype": "BP", "permit_class_mapped": "Commercial", "description": "Office buildout",
        "status_current": "Issued", "permit_location": f"{number} Congress Ave",
        "total_job_valuation": "1000", "contractor_trade": "General Contractor",
        "contractor_company_name": "Acme Builders LLC",
    }


class OffsetSource:
    def __init__(self, pages=None, count=0, metadata_error=None, count_error=None, page_error=None):
        self.pages = pages or {}
        self.count = count
        self.metadata_error = metadata_error
        self.count_error = count_error
        self.page_error = page_error
        self.calls = []
        self.requests = self.retries_used = self.bytes = 0

    def get_json(self, url, params):
        self.calls.append((url, dict(params)))
        if "api/views" in url:
            if self.metadata_error:
                raise core.ExtractionError(self.metadata_error)
            return {"columns": [{"fieldName": field} for field in FIELDS]}
        if params.get("$select"):
            if self.count_error:
                raise core.ExtractionError(self.count_error)
            return [{"n": str(self.count)}]
        offset = int(params["$offset"])
        if self.page_error and offset == self.page_error[0]:
            raise core.ExtractionError(self.page_error[1])
        return self.pages.get(offset, [])


def data(max_results=100):
    return core.validate_input({"startDate": "2026-10-01", "endDate": "2026-10-06", "maxResults": max_results})


class PaginationTests(unittest.TestCase):
    def test_successful_capped_extraction_is_complete_but_truncated(self):
        source = OffsetSource({0: [row(i) for i in range(100)]}, count=250)
        result = core.run_extraction(data(100), source, "t")
        self.assertEqual(result["summary"]["completion"], "complete")
        self.assertTrue(result["summary"]["cap_truncated"])
        self.assertEqual(result["summary"]["cap_truncation_reason"], "maxResults_cap")
        self.assertEqual(result["summary"]["records_fetched"], 100)
        self.assertFalse(result["summary"]["errors"])

    def test_two_pages_and_final_limit_are_requested(self):
        source = OffsetSource({0: [row(i) for i in range(1000)], 1000: [row(i) for i in range(1000, 1500)]}, count=1500)
        result = core.run_extraction(data(1500), source, "t")
        page_calls = [params for url, params in source.calls if params.get("$offset") is not None]
        self.assertEqual([int(call["$limit"]) for call in page_calls], [1000, 500])
        self.assertEqual(result["summary"]["records_fetched"], 1500)
        self.assertEqual(result["summary"]["records_delivered"], 1500)
        self.assertEqual(result["summary"]["completion"], "complete")

    def test_failure_after_first_page_preserves_partial_results_and_error(self):
        source = OffsetSource({0: [row(i) for i in range(1000)]}, count=1500, page_error=(1000, "page two unavailable"))
        result = core.run_extraction(data(1500), source, "t")
        self.assertEqual(result["summary"]["completion"], "incomplete")
        self.assertEqual(result["summary"]["records_delivered"], 1000)
        self.assertIn("page two unavailable", result["summary"]["errors"][0])

    def test_metadata_and_count_failures_are_diagnostic(self):
        metadata = core.run_extraction(data(), OffsetSource(metadata_error="HTTP 503 metadata"), "t")
        self.assertIn("metadata request/validation failed", metadata["summary"]["errors"][0])
        counted = core.run_extraction(data(), OffsetSource(count=1, count_error="HTTP 500 count"), "t")
        self.assertIn("count request failed", counted["summary"]["errors"][0])

    def test_repeated_page_is_bounded_and_visible(self):
        repeated = [row(i) for i in range(1000)]
        source = OffsetSource({0: repeated, 1000: repeated}, count=2000)
        result = core.run_extraction(data(1500), source, "t")
        self.assertEqual(result["summary"]["completion"], "incomplete")
        self.assertTrue(any("repeated page" in error for error in result["summary"]["errors"]))
        self.assertLessEqual(len(source.calls), 4)

    def test_inconsistent_count_is_an_error(self):
        source = OffsetSource({0: [row(1), row(2)]}, count=1)
        result = core.run_extraction(data(100), source, "t")
        self.assertEqual(result["summary"]["completion"], "incomplete")
        self.assertTrue(any("delivered rows exceed source count" in error for error in result["summary"]["errors"]))


class ActorOutputTests(unittest.TestCase):
    def test_contractor_summary_is_a_run_local_key_value_artifact(self):
        pushed = []
        values = {}

        class FakeActor:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def get_input(self): return {"startDate":"2026-10-01", "endDate":"2026-10-06"}
            class Manager:
                class Pricing: is_pay_per_event = False
                def get_pricing_info(self): return self.Pricing()
            def get_charging_manager(self): return self.Manager()
            async def push_data(self, item): pushed.append(item)
            async def set_value(self, key, value): values[key] = value

        original_actor = actor_main.Actor
        original_run = actor_main.run_extraction
        actor_main.Actor = FakeActor()
        actor_main.run_extraction = lambda data: {
            "records": [{"source_record_id":"A-1"}],
            "contractor_summary": [{"contractor_name_original":"Acme Builders LLC", "delivered_permit_count":1, "count_is_not_project_count":True}],
            "summary": {"completion":"complete"}, "schema": {"verified_fields": []},
        }
        try:
            asyncio.run(actor_main.main())
        finally:
            actor_main.Actor = original_actor
            actor_main.run_extraction = original_run
        self.assertIn("CONTRACTOR_SUMMARY", values)
        self.assertNotIn("contractor-summary", values)
        self.assertEqual(len(pushed), 1)

    def _run_billing_actor(self, fake_actor, records, summary_errors=None):
        original_actor = actor_main.Actor
        original_run = actor_main.run_extraction
        actor_main.Actor = fake_actor
        actor_main.run_extraction = lambda data: {
            "records": records,
            "contractor_summary": [{"contractor_name_original": "Acme Builders LLC", "delivered_permit_count": 1}],
            "summary": {"completion": "complete", "errors": list(summary_errors or []), "pagination_complete": True, "cap_truncated": False},
            "schema": {"verified_fields": []},
        }
        try:
            asyncio.run(actor_main.main())
        finally:
            actor_main.Actor = original_actor
            actor_main.run_extraction = original_run

    def test_ppe_charges_only_delivered_permit_records(self):
        class ChargeResult:
            charged_count = 1
            event_charge_limit_reached = False

        class Pricing:
            is_pay_per_event = True

        class Manager:
            def get_pricing_info(self): return Pricing()

        class FakeActor:
            def __init__(self): self.pushes = []; self.values = {}
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def get_input(self): return {"startDate":"2026-10-01", "endDate":"2026-10-06"}
            def get_charging_manager(self): return Manager()
            async def push_data(self, item, **kwargs): self.pushes.append((item, kwargs)); return ChargeResult()
            async def set_value(self, key, value): self.values[key] = value

        fake = FakeActor()
        self._run_billing_actor(fake, [
            {"source_record_id": "A-1", "contractor_name": "Delivered Co", "contractor_trade": "General Contractor", "issue_date": "2026-10-01"},
            {"source_record_id": "A-2", "contractor_name": "Not Delivered Co", "contractor_trade": "General Contractor", "issue_date": "2026-10-02"},
        ])
        self.assertEqual(len(fake.pushes), 2)
        self.assertEqual([call[1]["charged_event_name"] for call in fake.pushes], ["permit-record", "permit-record"])
        self.assertEqual(fake.values["RUN_SUMMARY"]["billing"]["charged_records"], 2)
        self.assertEqual(fake.values["RUN_SUMMARY"]["billing"]["summary_rows_charged"], 0)
        self.assertEqual(sum(item["delivered_permit_count"] for item in fake.values["CONTRACTOR_SUMMARY"]), 2)

    def test_customer_limit_preserves_partial_delivery_and_stops_cleanly(self):
        class ChargeResult:
            def __init__(self, charged_count, limited):
                self.charged_count = charged_count
                self.event_charge_limit_reached = limited

        class Pricing: is_pay_per_event = True
        class Manager:
            def get_pricing_info(self): return Pricing()

        class FakeActor:
            def __init__(self): self.calls = 0; self.values = {}; self.exit_called = False
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def get_input(self): return {"startDate":"2026-10-01", "endDate":"2026-10-06"}
            def get_charging_manager(self): return Manager()
            async def push_data(self, item, **kwargs):
                self.calls += 1
                return ChargeResult(1, self.calls == 1)
            async def set_value(self, key, value): self.values[key] = value
            async def exit(self, **kwargs): self.exit_called = True

        fake = FakeActor()
        self._run_billing_actor(fake, [
            {"source_record_id": "A-1", "contractor_name": "Delivered Co", "contractor_trade": "General Contractor", "issue_date": "2026-10-01"},
            {"source_record_id": "A-2", "contractor_name": "Not Delivered Co", "contractor_trade": "General Contractor", "issue_date": "2026-10-02"},
        ])
        summary = fake.values["RUN_SUMMARY"]
        self.assertEqual(fake.calls, 1)
        self.assertTrue(fake.exit_called)
        self.assertEqual(summary["records_delivered"], 1)
        self.assertTrue(summary["billing"]["billing_limit_reached"])
        self.assertIn("spending limit", summary["errors"][0])
        self.assertEqual(summary["billing"]["summary_rows_charged"], 0)
        self.assertEqual(fake.values["CONTRACTOR_SUMMARY"][0]["contractor_name_original"], "Delivered Co")

    def test_exact_budget_delivery_remains_requested_result_complete(self):
        class ChargeResult:
            charged_count = 1
            event_charge_limit_reached = True
        class Pricing: is_pay_per_event = True
        class Manager:
            def get_pricing_info(self): return Pricing()
        class FakeActor:
            def __init__(self): self.values = {}; self.exit_called = False
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def get_input(self): return {"startDate":"2026-10-01", "endDate":"2026-10-06"}
            def get_charging_manager(self): return Manager()
            async def push_data(self, item, **kwargs): return ChargeResult()
            async def set_value(self, key, value): self.values[key] = value
            async def exit(self, **kwargs): self.exit_called = True
        fake = FakeActor()
        self._run_billing_actor(fake, [{"source_record_id": "A-1", "contractor_name": "Exact Budget Co", "contractor_trade": "General Contractor", "issue_date": "2026-10-01"}])
        summary = fake.values["RUN_SUMMARY"]
        self.assertTrue(fake.exit_called)
        self.assertEqual(summary["completion"], "complete")
        self.assertEqual(summary["requested_result_completion"], "complete")
        self.assertTrue(summary["full_window_coverage"])
        self.assertEqual(summary["errors"], [])
        self.assertIn("warnings", summary)

    def test_spending_limit_does_not_hide_extraction_failure(self):
        class ChargeResult:
            charged_count = 1
            event_charge_limit_reached = True
        class Pricing: is_pay_per_event = True
        class Manager:
            def get_pricing_info(self): return Pricing()
        class FakeActor:
            def __init__(self): self.values = {}; self.exit_called = False
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def get_input(self): return {"startDate":"2026-10-01", "endDate":"2026-10-06"}
            def get_charging_manager(self): return Manager()
            async def push_data(self, item, **kwargs): return ChargeResult()
            async def set_value(self, key, value): self.values[key] = value
            async def exit(self, **kwargs): self.exit_called = True
        fake = FakeActor()
        with self.assertRaises(Exception):
            self._run_billing_actor(fake, [{"source_record_id": "A-1"}], ["source page failed after delivered row"])
        summary = fake.values["RUN_SUMMARY"]
        self.assertFalse(fake.exit_called)
        self.assertEqual(summary["completion"], "incomplete")
        self.assertIn("source page failed", summary["errors"][0])

    def test_pricing_manager_failure_is_diagnostic_and_fails(self):
        class FakeActor:
            def __init__(self): self.values = {}; self.pushes = 0
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def get_input(self): return {"startDate":"2026-10-01", "endDate":"2026-10-06"}
            def get_charging_manager(self): raise RuntimeError("manager unavailable")
            async def push_data(self, item, **kwargs): self.pushes += 1
            async def set_value(self, key, value): self.values[key] = value
        fake = FakeActor()
        with self.assertRaises(Exception):
            self._run_billing_actor(fake, [{"source_record_id": "A-1"}])
        self.assertEqual(fake.pushes, 0)
        self.assertIn("pricing mode unavailable", fake.values["RUN_SUMMARY"]["errors"][0])

    def test_missing_ppe_charge_result_is_diagnostic_and_fails(self):
        class Pricing: is_pay_per_event = True
        class Manager:
            def get_pricing_info(self): return Pricing()
        class FakeActor:
            def __init__(self): self.values = {}
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def get_input(self): return {"startDate":"2026-10-01", "endDate":"2026-10-06"}
            def get_charging_manager(self): return Manager()
            async def push_data(self, item, **kwargs): return None
            async def set_value(self, key, value): self.values[key] = value
        fake = FakeActor()
        with self.assertRaises(Exception):
            self._run_billing_actor(fake, [{"source_record_id": "A-1"}])
        self.assertIn("incomplete ChargeResult", fake.values["RUN_SUMMARY"]["errors"][0])

    def test_transport_failure_is_not_blindly_retried_or_double_charged(self):
        class Pricing: is_pay_per_event = True
        class Manager:
            def get_pricing_info(self): return Pricing()

        class FakeActor:
            def __init__(self): self.calls = 0; self.values = {}
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return False
            async def get_input(self): return {"startDate":"2026-10-01", "endDate":"2026-10-06"}
            def get_charging_manager(self): return Manager()
            async def push_data(self, item, **kwargs):
                self.calls += 1
                raise RuntimeError("ambiguous transport failure")
            async def set_value(self, key, value): self.values[key] = value

        fake = FakeActor()
        with self.assertRaises(Exception):
            self._run_billing_actor(fake, [{"source_record_id": "A-1"}])
        self.assertEqual(fake.calls, 1)
        self.assertIn("ambiguous transport failure", fake.values["RUN_SUMMARY"]["errors"][0])
