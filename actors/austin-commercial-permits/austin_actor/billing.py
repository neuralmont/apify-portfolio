"""Pay-per-event delivery for permit records.

The Apify SDK owns retry and idempotency handling for ``push_data``.  This
module deliberately does not retry an ambiguous push, because doing so in the
Actor could bill a record twice.  Only delivered permit records use the
``permit-record`` event; source counts, rejected duplicates, and key-value
store summaries never pass through this function.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PERMIT_EVENT_NAME = "permit-record"
PERMIT_EVENT_PRICE_USD = 0.003


class BillingDeliveryError(RuntimeError):
    """A dataset push failed; the SDK may have retried it already."""


@dataclass(frozen=True)
class DeliveryResult:
    delivered_count: int
    charged_count: int
    charge_limit_reached: bool = False


def _is_pay_per_event(actor: Any) -> bool:
    """Support PPE and the unmonetized private Actor during the transition."""
    try:
        pricing = actor.get_charging_manager().get_pricing_info()
        return bool(getattr(pricing, "is_pay_per_event", False))
    except (AttributeError, TypeError, RuntimeError):
        return False


def _charge_result_value(result: Any, name: str, default: Any) -> Any:
    if result is None:
        return default
    return getattr(result, name, default)


async def push_permit(actor: Any, record: dict[str, Any]) -> DeliveryResult:
    """Persist one permit and, for PPE runs, charge exactly one custom event.

    ``Actor.push_data(..., charged_event_name=...)`` is the SDK-supported
    atomic shortcut: the item is not pushed over the user's spending limit,
    and the returned ChargeResult tells us whether the limit was reached.
    """
    try:
        if _is_pay_per_event(actor):
            charge_result = await actor.push_data(record, charged_event_name=PERMIT_EVENT_NAME)
            charged_count = int(_charge_result_value(charge_result, "charged_count", 1))
            limit_reached = bool(_charge_result_value(charge_result, "event_charge_limit_reached", False))
            if charged_count <= 0:
                return DeliveryResult(0, 0, limit_reached)
            return DeliveryResult(1, charged_count, limit_reached)
        await actor.push_data(record)
        return DeliveryResult(1, 0, False)
    except Exception as exc:  # SDK errors are persisted by the caller.
        raise BillingDeliveryError(f"permit delivery failed: {exc}") from exc
