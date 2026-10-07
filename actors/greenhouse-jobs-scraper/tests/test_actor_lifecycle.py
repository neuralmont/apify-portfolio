import asyncio
from types import SimpleNamespace

import pytest

from greenhouse_actor import main as actor_main
from greenhouse_actor.core import ExtractionError


def job(job_id):
    return {
        "id": job_id,
        "title": "Engineer",
        "location": {"name": "Remote"},
        "departments": [],
        "offices": [],
        "content": "<p>Build.</p>",
        "absolute_url": f"https://boards.greenhouse.io/acme/jobs/{job_id}",
    }


class FakeClient:
    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []
        self.stats = SimpleNamespace(requests=0, retries=0, bytes_received=0)

    def get_board(self, token):
        self.calls.append(token)
        self.stats.requests += 1
        return self.payloads[token]


class FakeActor:
    def __init__(self, data, client, charge_results=None):
        self.data = data
        self.client = client
        self.charge_results = iter(charge_results or [])
        self.dataset = []
        self.values = {}
        self.exit_called = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get_input(self):
        return self.data

    def get_charging_manager(self):
        return SimpleNamespace(get_pricing_info=lambda: SimpleNamespace(is_pay_per_event=self.ppe))

    async def push_data(self, record, **kwargs):
        self.dataset.append(record)
        if "charged_event_name" in kwargs:
            return next(self.charge_results)
        return None

    async def set_value(self, key, value):
        self.values[key] = value

    async def exit(self, **kwargs):
        self.exit_called = True


def run_actor(monkeypatch, data, payloads, ppe=False, charge_results=None):
    client = FakeClient(payloads)
    fake = FakeActor(data, client, charge_results)
    fake.ppe = ppe
    monkeypatch.setattr(actor_main, "Actor", fake)
    monkeypatch.setattr(actor_main, "GreenhouseClient", lambda *args, **kwargs: client)
    try:
        asyncio.run(actor_main.main())
        error = None
    except Exception as exc:  # lifecycle assertion callers inspect the real failure
        error = exc
    return fake, client, error


def test_spending_limit_stops_before_next_board_and_summary_matches_delivery(monkeypatch):
    fake, client, error = run_actor(
        monkeypatch,
        {"boards": ["acme", "beta"], "maxJobs": 3},
        {"acme": {"jobs": [job(1), job(2), job(3)]}, "beta": {"jobs": [job(4), job(5), job(6)]}},
        ppe=True,
        charge_results=[SimpleNamespace(charged_count=1, event_charge_limit_reached=True)],
    )
    assert error is None
    summary = fake.values["RUN_SUMMARY"]
    assert client.calls == ["acme"]
    assert len(fake.dataset) == 1
    assert summary["records_delivered"] == 1
    assert summary["billing"]["charged_records"] == 1
    assert summary["budget_stop"] is True
    assert summary["board_outcomes"][0]["jobs_selected"] == 3
    assert summary["board_outcomes"][0]["jobs_delivered"] == 1
    assert summary["board_outcomes"][0]["jobs_charged"] == 1
    assert summary["skipped_boards"] == ["beta"]
    assert "records" not in summary
    assert fake.exit_called is True


def test_malformed_later_board_keeps_delivery_and_fails(monkeypatch):
    fake, client, error = run_actor(
        monkeypatch,
        {"boards": ["acme", "bad"], "maxJobs": 3},
        {"acme": {"jobs": [job(1)]}, "bad": {"jobs": [None]}},
    )
    assert isinstance(error, ExtractionError)
    summary = fake.values["RUN_SUMMARY"]
    assert client.calls == ["acme", "bad"]
    assert len(fake.dataset) == 1
    assert summary["records_delivered"] == 1
    assert summary["boards_failed"] == 1
    assert summary["requested_result_completion"] == "incomplete"
    assert summary["full_input_coverage"] is False
    assert "non-object job" in summary["errors"][0]
    assert fake.exit_called is False
