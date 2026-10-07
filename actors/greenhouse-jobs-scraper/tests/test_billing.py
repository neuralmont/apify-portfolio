import asyncio
from types import SimpleNamespace

import pytest

from greenhouse_actor.billing import BillingConfigurationError, push_job


class Actor:
    def __init__(self, result, ppe=True):
        self.result = result
        self.ppe = ppe

    def get_charging_manager(self):
        return SimpleNamespace(get_pricing_info=lambda: SimpleNamespace(is_pay_per_event=self.ppe))

    async def push_data(self, record, **kwargs):
        return self.result


def run(actor):
    return asyncio.run(push_job(actor, {"job_id": "1"}))


def test_sufficient_partial_and_exact_budget_results():
    assert run(Actor(SimpleNamespace(charged_count=1, event_charge_limit_reached=False))).delivered_count == 1
    assert run(Actor(SimpleNamespace(charged_count=0, event_charge_limit_reached=True))).delivered_count == 0
    exact = run(Actor(SimpleNamespace(charged_count=1, event_charge_limit_reached=True)))
    assert (exact.delivered_count, exact.charge_limit_reached) == (1, True)


def test_missing_charge_result_does_not_become_free_delivery():
    with pytest.raises(BillingConfigurationError):
        run(Actor(None))


def test_unmonetized_run_delivers_without_event():
    result = run(Actor(None, ppe=False))
    assert (result.delivered_count, result.charged_count) == (1, 0)
