"""Exercise the real Apify 4.0.2 SDK in local PPE test mode.

This uses fixture product records, real SDK storage and charging behavior, and
does not mock the charging manager. Local PPE events use the SDK's simulated
$1 default and therefore do not verify the proposed $0.003 Console price.
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


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--records", type=int, required=True)
    p.add_argument("--max-total-charge-usd", type=float, required=True)
    return p.parse_args()


def read_items(directory: Path) -> list[dict]:
    return [json.loads(path.read_text()) for path in sorted(directory.glob("*.json")) if path.name != "__metadata__.json"]


async def run(ns: argparse.Namespace) -> int:
    kv = ns.output_dir / "key_value_stores" / "default"
    kv.mkdir(parents=True, exist_ok=True)
    (kv / "INPUT.json").write_text(json.dumps({"storeUrls": ["https://fixture.example"], "maxProducts": ns.records}))
    os.environ.update({
        "APIFY_LOCAL_STORAGE_DIR": str(ns.output_dir),
        "APIFY_DEFAULT_DATASET_ID": "default",
        "APIFY_DEFAULT_KEY_VALUE_STORE_ID": "default",
        "ACTOR_TEST_PAY_PER_EVENT": "true",
        "ACTOR_MAX_TOTAL_CHARGE_USD": str(ns.max_total_charge_usd),
    })
    import apify
    from apify import Actor as SDKActor
    from shopify_actor import main as actor_main

    actor_main.Actor = SDKActor(exit_process=False)
    records = [{"store_url":"https://fixture.example","product_id":str(i),"handle":f"p-{i}","title":f"Fixture {i}","variants":[],"observed_at":"2026-10-07T00:00:00Z","source_endpoint":"https://fixture.example/products.json"} for i in range(ns.records)]
    actor_main.extract = lambda data: {"records": records, "summary": {"errors": [], "pagination_complete": True, "cap_truncated": False}, "schema": {"fixture": True}}
    exit_status = 0
    error = None
    try:
        await actor_main.main()
    except BaseException as exc:
        exit_status = 1
        error = f"{type(exc).__name__}: {exc}"
    dataset = read_items(ns.output_dir / "datasets" / "default")
    charges = read_items(ns.output_dir / "datasets" / "charging-log")
    summary_path = kv / "RUN_SUMMARY"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else None
    report = {"sdk_versions":{"apify":apify.__version__,"python":"%d.%d.%d" % sys.version_info[:3]},"configured_max_total_charge_usd":ns.max_total_charge_usd,"process_exit_status":exit_status,"error":error,"dataset_rows":len(dataset),"charge_event_counts":dict(Counter(item.get("event_name") for item in charges)),"run_summary":summary,"local_event_price_note":"SDK local PPE test events default to simulated $1; this does not verify the proposed $0.003 Console price"}
    print(json.dumps(report, indent=2, sort_keys=True))
    return exit_status


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(args())))
