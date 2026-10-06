"""Run the Actor with the real Apify SDK in local PPE test mode.

This uses fixture extraction data but never mocks Actor charging, storage, or
the charging manager. Local PPE events are simulated at the SDK's default $1
price; they do not verify the proposed Console price.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--records", type=int, required=True)
    parser.add_argument("--max-total-charge-usd", type=float, required=True)
    return parser.parse_args()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_items(directory: Path) -> list[dict]:
    return [
        read_json(path)
        for path in sorted(directory.glob("*.json"))
        if path.name != "__metadata__.json"
    ]


async def run(args: argparse.Namespace) -> int:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    kv_dir = args.output_dir / "key_value_stores" / "default"
    kv_dir.mkdir(parents=True, exist_ok=True)
    (kv_dir / "INPUT.json").write_text(
        json.dumps({"startDate": "2026-10-01", "endDate": "2026-10-06", "maxResults": args.records}),
        encoding="utf-8",
    )
    os.environ.update(
        {
            "APIFY_LOCAL_STORAGE_DIR": str(args.output_dir),
            "APIFY_DEFAULT_DATASET_ID": "default",
            "APIFY_DEFAULT_KEY_VALUE_STORE_ID": "default",
            "ACTOR_TEST_PAY_PER_EVENT": "true",
            "ACTOR_MAX_TOTAL_CHARGE_USD": str(args.max_total_charge_usd),
        }
    )

    import apify
    from apify import Actor as SDKActor

    from austin_actor import main as actor_main

    actor_main.Actor = SDKActor(exit_process=False)
    records = [
        {
            "source_record_id": f"SDK-PPE-{index}",
            "contractor_name": "SDK Fixture Builders LLC",
            "contractor_trade": "General Contractor",
            "issue_date": f"2026-10-{index + 1:02d}",
        }
        for index in range(args.records)
    ]
    actor_main.run_extraction = lambda data: {
        "records": records,
        "contractor_summary": [],
        "summary": {
            "completion": "complete",
            "errors": [],
            "pagination_complete": True,
            "cap_truncated": False,
        },
        "schema": {"verified_fields": []},
    }

    exit_status = 0
    error = None
    try:
        await actor_main.main()
    except BaseException as exc:  # Preserve artifacts for failed scenarios.
        exit_status = 1
        error = f"{type(exc).__name__}: {exc}"

    dataset = read_items(args.output_dir / "datasets" / "default")
    charge_events = read_items(args.output_dir / "datasets" / "charging-log")
    summary_path = kv_dir / "RUN_SUMMARY"
    contractor_path = kv_dir / "CONTRACTOR_SUMMARY"
    summary = read_json(summary_path) if summary_path.exists() else None
    contractor = read_json(contractor_path) if contractor_path.exists() else []
    report = {
        "sdk_versions": {
            "apify": apify.__version__,
            "python": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
        },
        "configured_max_total_charge_usd": args.max_total_charge_usd,
        "process_exit_status": exit_status,
        "error": error,
        "dataset_rows": len(dataset),
        "dataset_source_ids": [item.get("source_record_id") for item in dataset],
        "charge_event_counts": dict(Counter(item.get("event_name") for item in charge_events)),
        "charge_events": charge_events,
        "run_summary": summary,
        "contractor_summary_rows": len(contractor),
        "contractor_summary_permit_count_sum": sum(item.get("delivered_permit_count", 0) for item in contractor),
        "local_event_price_note": "SDK local PPE test events default to simulated $1; this does not verify the proposed $0.003 Console price",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return exit_status


if __name__ == "__main__":
    arguments = parse_args()
    raise SystemExit(asyncio.run(run(arguments)))
