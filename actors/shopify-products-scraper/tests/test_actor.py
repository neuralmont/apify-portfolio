import asyncio
from types import SimpleNamespace

import pytest

from shopify_actor import main as actor_main
from shopify_actor.core import ExtractionError


class FakeActor:
    def __init__(self, results):
        self.results = iter(results)
        self.values = {}
        self.pushed = []
        self.exit_called = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get_input(self):
        return {"productUrls": ["https://shop.example/products/item"], "maxProducts": 3}

    def get_charging_manager(self):
        return SimpleNamespace(get_pricing_info=lambda: SimpleNamespace(is_pay_per_event=True))

    async def push_data(self, record, **kwargs):
        self.pushed.append(record)
        return next(self.results)

    async def set_value(self, key, value):
        self.values[key] = value

    async def exit(self, **kwargs):
        self.exit_called = True


def _result(errors=None, records=None):
    delivered_records = records or [{"product_id": "1"}, {"product_id": "2"}, {"product_id": "3"}]
    return {
        "records": delivered_records,
        "summary": {"errors": errors or [], "pagination_complete": True, "cap_truncated": False, "store_outcomes": [{"status": "partial", "records": delivered_records}]},
        "schema": {"fixture": True},
    }


def test_spending_limit_only_exits_successfully_after_partial_delivery(monkeypatch):
    actor = FakeActor([
        SimpleNamespace(charged_count=1, event_charge_limit_reached=False),
        SimpleNamespace(charged_count=0, event_charge_limit_reached=True),
    ])
    monkeypatch.setattr(actor_main, "Actor", actor)
    monkeypatch.setattr(actor_main, "extract", lambda data: _result())

    asyncio.run(actor_main.main())

    assert actor.exit_called
    assert len(actor.pushed) == 2
    assert actor.values["RUN_SUMMARY"]["records_delivered"] == 1
    assert actor.values["RUN_SUMMARY"]["requested_result_completion"] == "incomplete"
    assert all("records" not in outcome for outcome in actor.values["RUN_SUMMARY"].get("store_outcomes", []))


def test_spending_limit_does_not_hide_extraction_failure(monkeypatch):
    actor = FakeActor([SimpleNamespace(charged_count=1, event_charge_limit_reached=True)])
    monkeypatch.setattr(actor_main, "Actor", actor)
    monkeypatch.setattr(actor_main, "extract", lambda data: _result(["source failed"]))

    with pytest.raises(ExtractionError):
        asyncio.run(actor_main.main())

    assert not actor.exit_called
    assert actor.pushed
    assert "source failed" in actor.values["RUN_SUMMARY"]["errors"]


def test_exact_budget_delivery_is_successful(monkeypatch):
    actor = FakeActor([
        SimpleNamespace(charged_count=1, event_charge_limit_reached=False),
        SimpleNamespace(charged_count=1, event_charge_limit_reached=True),
    ])
    monkeypatch.setattr(actor_main, "Actor", actor)
    monkeypatch.setattr(actor_main, "extract", lambda data: _result(records=[{"product_id": "1"}, {"product_id": "2"}]))

    asyncio.run(actor_main.main())

    assert actor.exit_called
    assert actor.values["RUN_SUMMARY"]["records_delivered"] == 2
    assert actor.values["RUN_SUMMARY"]["requested_result_completion"] == "complete"
