"""One PPE event for each product record delivered to the default dataset."""

from dataclasses import dataclass
from typing import Any

PRODUCT_EVENT_NAME = "product-record"


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
    except Exception as exc:
        raise BillingConfigurationError("pricing mode unavailable; charging manager could not be read") from exc
    try:
        pricing = manager.get_pricing_info()
    except Exception as exc:
        raise BillingConfigurationError("pricing mode unavailable; get_pricing_info failed") from exc
    if pricing is None or not hasattr(pricing, "is_pay_per_event"):
        raise BillingConfigurationError("pricing mode unavailable; pricing info lacks is_pay_per_event")
    return bool(pricing.is_pay_per_event)


async def push_product(actor: Any, record: dict[str, Any]) -> DeliveryResult:
    ppe = _is_pay_per_event(actor)
    try:
        if not ppe:
            await actor.push_data(record)
            return DeliveryResult(1, 0, False)
        charge_result = await actor.push_data(record, charged_event_name=PRODUCT_EVENT_NAME)
        if charge_result is None or not hasattr(charge_result, "charged_count") or not hasattr(charge_result, "event_charge_limit_reached"):
            raise BillingConfigurationError("PPE push_data returned an incomplete ChargeResult")
        charged = charge_result.charged_count
        limited = charge_result.event_charge_limit_reached
        if isinstance(charged, bool) or not isinstance(charged, int) or charged < 0 or charged > 1:
            raise BillingConfigurationError("PPE ChargeResult.charged_count is invalid")
        if not isinstance(limited, bool):
            raise BillingConfigurationError("PPE ChargeResult.event_charge_limit_reached is invalid")
        return DeliveryResult(1 if charged else 0, charged, limited)
    except BillingConfigurationError:
        raise
    except Exception as exc:
        raise BillingDeliveryError(f"product delivery failed: {exc}") from exc
