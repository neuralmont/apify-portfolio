from __future__ import annotations

import asyncio

from .billing import BillingConfigurationError, BillingDeliveryError, push_product
from .core import ExtractionError, extract, validate_input

try:
    from apify import Actor
except ImportError:
    Actor = None


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The Apify SDK is required for Actor execution")
    async with Actor:
        data = validate_input(await Actor.get_input() or {})
        result = await asyncio.to_thread(extract, data)
        delivered_records = []
        delivered = 0
        charged = 0
        billing_limit_reached = False
        delivery_error = None
        billing_error = None
        for record in result["records"]:
            try:
                delivery = await push_product(Actor, record)
            except BillingConfigurationError as exc:
                billing_error = str(exc)
                break
            except BillingDeliveryError as exc:
                delivery_error = str(exc)
                break
            delivered += delivery.delivered_count
            charged += delivery.charged_count
            if delivery.delivered_count:
                delivered_records.append(record)
            if delivery.charge_limit_reached:
                billing_limit_reached = True
                break

        summary = result["summary"]
        for key in ("store_outcomes", "product_outcomes"):
            summary[key] = [{field: value for field, value in outcome.items() if field != "records"} for outcome in summary.get(key, [])]
        extraction_errors = list(summary.get("errors") or [])
        summary["records_delivered"] = delivered
        summary["requested_result_completion"] = "complete" if delivered == len(result["records"]) and not extraction_errors and not delivery_error and not billing_error else "incomplete"
        summary["full_window_coverage"] = bool(summary.get("pagination_complete") and not summary.get("cap_truncated") and summary["requested_result_completion"] == "complete")
        summary["billing"] = {"event_name":"product-record","price_usd":None,"charged_records":charged,"billing_limit_reached":billing_limit_reached,"duplicate_records_charged":0,"diagnostic_records_charged":0}
        if delivery_error:
            summary.setdefault("errors", []).append(delivery_error)
        if billing_error:
            summary.setdefault("errors", []).append(billing_error)
        elif billing_limit_reached:
            message = "customer spending limit reached; delivery stopped"
            if summary["requested_result_completion"] != "complete":
                summary.setdefault("errors", []).append(message)
            else:
                summary.setdefault("warnings", []).append(message)
        await Actor.set_value("RUN_SUMMARY", summary)
        await Actor.set_value("SCHEMA_METADATA", result["schema"])
        fatal = bool(extraction_errors or delivery_error or billing_error)
        if fatal:
            raise ExtractionError("Extraction or delivery failed; see RUN_SUMMARY")
        if billing_limit_reached:
            await Actor.exit(status_message="Customer spending limit reached; delivered products are preserved")
            return
        if summary["requested_result_completion"] != "complete":
            raise ExtractionError("Extraction incomplete; see RUN_SUMMARY")


if __name__ == "__main__":
    asyncio.run(main())
