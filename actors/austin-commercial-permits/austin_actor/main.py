from __future__ import annotations
import asyncio
from .core import ActorInputError, ExtractionError, run_extraction

try:
    from apify import Actor, Dataset
except ImportError:  # Local core tests do not require the SDK; Docker installs it.
    Actor = Dataset = None


async def main() -> None:
    if Actor is None:
        raise RuntimeError("The Apify SDK is required for Actor execution; use run_local.py for dependency-free local runs.")
    async with Actor:
        actor_input = await Actor.get_input() or {}
        from .core import validate_input
        data = validate_input(actor_input)
        result = run_extraction(data)
        for record in result["records"]:
            await Actor.push_data(record)
        if data["includeContractorSummary"]:
            summary_dataset = await Dataset.open(name="contractor-summary")
            for row in result["contractor_summary"]:
                await summary_dataset.push_data(row)
        await Actor.set_value("RUN_SUMMARY", result["summary"])
        await Actor.set_value("SCHEMA_METADATA", result["schema"])
        if result["summary"]["completion"] != "complete":
            raise ExtractionError("Extraction incomplete; see RUN_SUMMARY")


if __name__ == "__main__":
    asyncio.run(main())
