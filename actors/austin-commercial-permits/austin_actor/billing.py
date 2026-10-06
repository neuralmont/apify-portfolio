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


class BillingConfigurationError(RuntimeError):
    """The SDK pricing state or ChargeResult is unusable."""


@dataclass(frozen=True)
class DeliveryResult:
    delivered_count: int
    charged_count: int
    charge_limit_reached: bool = False


def _is_pay_per_event(actor: Any) -> bool:
    """Read pricing state without hiding a broken charging manager."""
    try:
        manager = actor.get_charging_manager()
    except Exception as exc:
        raise BillingConfigurationError(
            "pricing mode unavailable; the Apify charging manager could not be read"
        ) from exc
    try:
        pricing = manager.get_pricing_info()
    except Exception as exc:
        raise BillingConfigurationError(
            "pricing mode unavailable; get_pricing_info failed"
        ) from exc
    if pricing is None or not hasattr(pricing, "is_pay_per_event"):
        raise BillingConfigurationError(
            "pricing mode unavailable; pricing info lacks is_pay_per_event"
        )
    return bool(pricing.is_pay_per_event)


async def push_permit(actor: Any, record: dict[str, Any]) -> DeliveryResult:
    """Persist one permit and, for PPE runs, charge exactly one custom event.

    ``Actor.push_data(..., charged_event_name=...)`` is the SDK-supported
    atomic shortcut: the item is not pushed over the user's spending limit,
    and the returned ChargeResult tells us whether the limit was reached.
    """
    ppe = _is_pay_per_event(actor)
    try:
        if ppe:
            charge_result = await actor.push_data(record, charged_event_name=PERMIT_EVENT_NAME)
            if charge_result is None or not hasattr(charge_result, "charged_count") or not hasattr(charge_result, "event_charge_limit_reached"):
                raise BillingConfigurationError(
                    "PPE push_data returned an incomplete ChargeResult"
                )
            charged_count = charge_result.charged_count
            limit_reached = charge_result.event_charge_limit_reached
            if isinstance(charged_count, bool) or not isinstance(charged_count, int) or charged_count < 0:
                raise BillingConfigurationError("PPE ChargeResult.charged_count is invalid")
            if not isinstance(limit_reached, bool):
                raise BillingConfigurationError("PPE ChargeResult.event_charge_limit_reached is invalid")
            if charged_count > 1:
                raise BillingConfigurationError("one permit push charged more than one event")
            if charged_count <= 0:
                return DeliveryResult(0, 0, limit_reached)
            return DeliveryResult(1, charged_count, limit_reached)
        await actor.push_data(record)
        return DeliveryResult(1, 0, False)
    except BillingConfigurationError:
        raise
    except Exception as exc:  # SDK errors are persisted by the caller.
        raise BillingDeliveryError(f"permit delivery failed: {exc}") from exc
