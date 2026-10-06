from __future__ import annotations
import asyncio
from .billing import BillingDeliveryError, push_permit
from .core import ExtractionError, contractor_summary, run_extraction

try:
    from apify import Actor
except ImportError:  # Local core tests do not require the SDK; Docker installs it.
    Actor = None


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The Apify SDK is required for Actor execution; use run_local.py for dependency-free local runs.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        from .core import validate_input
        data = validate_input(actor_input)
        result = run_extraction(data)
        delivered = 0
        charged = 0
        delivered_records = []
        billing_limit_reached = False
        delivery_error = None
        for record in result["records"]:
            try:
                delivery = await push_permit(Actor, record)
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
        summary["records_delivered"] = delivered
        summary["billing"] = {
            "event_name": "permit-record",
            "price_usd": 0.003,
            "charged_records": charged,
            "billing_limit_reached": billing_limit_reached,
            "summary_rows_charged": 0,
            "source_counts_charged": 0,
            "discarded_duplicates_charged": 0,
        }
        if delivery_error:
            summary["completion"] = "incomplete"
            summary.setdefault("errors", []).append(delivery_error)
        elif billing_limit_reached:
            summary["completion"] = "incomplete"
            summary.setdefault("errors", []).append("customer spending limit reached; delivery stopped")
        if data["includeContractorSummary"]:
            await Actor.set_value(
                "CONTRACTOR_SUMMARY",
                contractor_summary(delivered_records, summary["completion"] != "complete"),
            )
        await Actor.set_value("RUN_SUMMARY", summary)
        await Actor.set_value("SCHEMA_METADATA", result["schema"])
        if billing_limit_reached and hasattr(Actor, "exit"):
            await Actor.exit(status_message="Customer spending limit reached; delivered records are preserved")
            return
        if summary["completion"] != "complete":
            raise ExtractionError("Extraction incomplete; see RUN_SUMMARY")


if __name__ == "__main__":
    asyncio.run(main())
