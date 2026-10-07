"""One PPE event for each successfully delivered Greenhouse job record."""

from dataclasses import dataclass
from typing import Any

JOB_EVENT_NAME = "job-record"


class BillingDeliveryError(RuntimeError):
    pass


class BillingConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class DeliveryResult:
    delivered_count: int
    charged_count: int
    charge_limit_reached: bool = False


def _is_pay_per_event(actor: Any) -> bool:
    try:
        manager = actor.get_charging_manager()
        pricing = manager.get_pricing_info()
    except Exception as exc:
        raise BillingConfigurationError("pricing mode unavailable; charging manager could not be read") from exc
    if pricing is None or not hasattr(pricing, "is_pay_per_event"):
        raise BillingConfigurationError("pricing mode unavailable; pricing info lacks is_pay_per_event")
    return bool(pricing.is_pay_per_event)


async def push_job(actor: Any, record: dict[str, Any]) -> DeliveryResult:
    if not _is_pay_per_event(actor):
        try:
            await actor.push_data(record)
        except Exception as exc:
            raise BillingDeliveryError(f"job delivery failed: {exc}") from exc
        return DeliveryResult(1, 0)
    try:
        result = await actor.push_data(record, charged_event_name=JOB_EVENT_NAME)
    except Exception as exc:
        raise BillingDeliveryError(f"job delivery failed: {exc}") from exc
    if result is None or not hasattr(result, "charged_count") or not hasattr(result, "event_charge_limit_reached"):
        raise BillingConfigurationError("PPE push_data returned an incomplete ChargeResult")
    charged = result.charged_count
    limited = result.event_charge_limit_reached
    if isinstance(charged, bool) or not isinstance(charged, int) or charged not in (0, 1):
        raise BillingConfigurationError("PPE ChargeResult.charged_count is invalid")
    if not isinstance(limited, bool):
        raise BillingConfigurationError("PPE ChargeResult.event_charge_limit_reached is invalid")
    return DeliveryResult(charged, charged, limited)
