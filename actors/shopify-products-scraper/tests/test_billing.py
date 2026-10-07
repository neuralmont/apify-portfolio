import asyncio
from types import SimpleNamespace

import pytest

from shopify_actor.billing import BillingConfigurationError, push_product


class Actor:
    def __init__(self, result=None, error=None, ppe=True):
        self.result = result
        self.error = error
        self.ppe = ppe
        self.pushes = []

    def get_charging_manager(self):
        return SimpleNamespace(get_pricing_info=lambda: SimpleNamespace(is_pay_per_event=self.ppe))

    async def push_data(self, record, **kwargs):
        self.pushes.append((record, kwargs))
        if self.error:
            raise self.error
        return self.result


def run(actor):
    return asyncio.run(push_product(actor, {"product_id": "1"}))


def test_sufficient_budget_delivers_and_charges_one_product():
    result = run(Actor(SimpleNamespace(charged_count=1, event_charge_limit_reached=False)))
    assert (result.delivered_count, result.charged_count, result.charge_limit_reached) == (1, 1, False)


def test_partial_and_exact_budget_preserve_limit_signal():
    partial = run(Actor(SimpleNamespace(charged_count=0, event_charge_limit_reached=True)))
    exact = run(Actor(SimpleNamespace(charged_count=1, event_charge_limit_reached=True)))
    assert (partial.delivered_count, partial.charge_limit_reached) == (0, True)
    assert (exact.delivered_count, exact.charge_limit_reached) == (1, True)


def test_missing_charge_result_fails_instead_of_free_delivery():
    with pytest.raises(BillingConfigurationError):
        run(Actor(None))
