from __future__ import annotations

import asyncio

from .billing import BillingConfigurationError, BillingDeliveryError, push_job
from .core import ExtractionError, GreenhouseClient, extract_board, validate_input

try:
    from apify import Actor
except ImportError:
    Actor = None


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The Apify SDK is required for Actor execution")
    async with Actor:
        data = validate_input(await Actor.get_input() or {})
        client = GreenhouseClient(data["requestTimeoutSecs"], data["retries"])
        retrieved_at = None
        identities: set[tuple[str, str]] = set()
        outcomes = []
        errors = []
        skipped = []
        delivered = 0
        charged = 0
        limit_reached = False
        delivery_error = None
        billing_error = None
        cap_truncated = False
        for index, spec in enumerate(data["board_specs"]):
            token = spec["board_token"]
            if delivered >= data["maxJobs"]:
                skipped.extend(data["boards"][index:])
                cap_truncated = True
                break
            board_result = await asyncio.to_thread(
                extract_board,
                data,
                token,
                client,
                data["maxJobs"] - delivered,
                identities,
                retrieved_at,
                spec.get("company_name"),
            )
            outcome = board_result["outcome"]
            outcomes.append(outcome)
            if outcome["errors"]:
                errors.extend(outcome["errors"])
            if outcome["coverage"] == "truncated_at_global_cap":
                cap_truncated = True
            for record in board_result["records"]:
                if delivery_error or billing_error or limit_reached:
                    break
                try:
                    delivery = await push_job(Actor, record)
                except BillingConfigurationError as exc:
                    billing_error = str(exc)
                    break
                except BillingDeliveryError as exc:
                    delivery_error = str(exc)
                    break
                delivered += delivery.delivered_count
                charged += delivery.charged_count
                outcome["jobs_delivered"] += delivery.delivered_count
                outcome["jobs_charged"] += delivery.charged_count
                if delivery.charge_limit_reached:
                    limit_reached = True
                    break
            if delivery_error or billing_error:
                skipped.extend(data["boards"][index + 1:])
                break
            if limit_reached:
                skipped.extend(data["boards"][index + 1:])
                break
            if delivered >= data["maxJobs"]:
                cap_truncated = cap_truncated or outcome["jobs_matched"] > outcome["jobs_selected"]
                skipped.extend(data["boards"][index + 1:])
                break
        records_matched = sum(outcome["jobs_matched"] for outcome in outcomes)
        records_selected = sum(outcome["jobs_selected"] for outcome in outcomes)
        extraction_errors = list(errors)
        all_matching_delivered = not extraction_errors and not skipped and not cap_truncated and delivered >= records_matched
        requested_complete = not extraction_errors and not delivery_error and not billing_error and (
            delivered >= data["maxJobs"] or (not limit_reached and all_matching_delivered)
        )
        summary = {
            "search_mode": data["mode"],
            "directory_version": data["directory_version"],
            "directory_size": data["directory_size"],
            "boards_requested": len(data["boards"]),
            "boards_available": data["directory_size"] if data["mode"] == "directory" else len(data["board_specs"]),
            "boards_processed": len(outcomes),
            "boards_attempted": len(outcomes),
            "boards_succeeded": sum(outcome["status"] == "success" for outcome in outcomes),
            "boards_skipped": len(skipped),
            "boards_failed": sum(outcome["status"] == "failed" for outcome in outcomes),
            "records_fetched": sum(outcome["jobs_fetched"] for outcome in outcomes),
            "records_examined": sum(outcome["jobs_fetched"] for outcome in outcomes),
            "records_matched": records_matched,
            "records_selected": records_selected,
            "records_delivered": delivered,
            "duplicates": sum(outcome["duplicates"] for outcome in outcomes),
            "cap_truncated": cap_truncated,
            "budget_stop": limit_reached,
            "skipped_boards": skipped,
            "requested_result_completion": "complete" if requested_complete else "incomplete",
            "full_input_coverage": not skipped and not extraction_errors and not delivery_error and not billing_error,
            "all_selected_boards_searched": not skipped and not extraction_errors and not delivery_error and not billing_error,
            "all_matching_jobs_delivered": all_matching_delivered,
            "coverage": "bounded_global_cap" if cap_truncated else ("partial_with_errors" if extraction_errors or delivery_error or billing_error else "all_requested_boards"),
            "board_outcomes": outcomes,
            "errors": extraction_errors,
            "resource": {"requests": client.stats.requests, "retries": client.stats.retries, "bytes_received": client.stats.bytes_received},
        }
        if delivery_error:
            summary["errors"].append(delivery_error)
        if billing_error:
            summary["errors"].append(billing_error)
        elif limit_reached:
            message = "customer spending limit reached; delivery stopped"
            summary.setdefault("warnings", []).append(message)
        summary["billing"] = {"event_name": "job-record", "price_usd": None, "charged_records": charged, "billing_limit_reached": limit_reached, "duplicate_records_charged": 0, "diagnostic_records_charged": 0}
        schema = {"api": "Greenhouse Job Board API", "endpoint": "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true", "content": "Descriptions are source data; HTML is preserved and plain text is derived with entity decoding."}
        await Actor.set_value("RUN_SUMMARY", summary)
        await Actor.set_value("SCHEMA_METADATA", schema)
        if extraction_errors or delivery_error or billing_error:
            raise ExtractionError("Extraction or delivery failed; see RUN_SUMMARY")
        if limit_reached:
            await Actor.exit(status_message="Customer spending limit reached; delivered jobs are preserved")
            return
        if not requested_complete:
            raise ExtractionError("Extraction incomplete; see RUN_SUMMARY")


if __name__ == "__main__":
    asyncio.run(main())
