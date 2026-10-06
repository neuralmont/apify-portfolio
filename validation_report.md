# Validation report

Observation date: 2026-10-06 (America/Chicago). A normal permitted HTTPS check and the corrected probe could not resolve `data.cityofchicago.org`, `data.seattle.gov`, or `data.austintexas.gov`; Python returned `nodename nor servname provided`. The probe exited 2 after 9 requests, 6 bounded retries, and 0 bytes. No live rows, counts, schema confirmations, contractor audit, classification audit, or 10-record source audits were claimed. This is an unresolved connectivity blocker, not evidence that the sources are empty.

Exact macOS Terminal rerun commands:

```bash
cd /Users/johnmcmanus/Documents/ChatGPT/apify-portfolio
mkdir -p outputs
END=$(date -u +%F); START=$(date -u -v-30d +%F)
LOG="outputs/live-$(date -u +%Y%m%dT%H%M%SZ).stdout.json"
python3 probe.py live --cities chicago seattle austin --limit 100 --since "$START" --until "$END" --seattle-in-progress --out outputs/live.csv > "$LOG"; rc=$?
echo "exit=$rc"
python3 -c 'import json; d=json.load(open("outputs/run_metrics.json")); print(" ".join(f"{city}={v.get(\"errors\") or \"ok\"}" for city,v in d["cities"].items()))'
exit "$rc"
```

The command intentionally returns exit code 2 when one or more requested cities fail. It still saves timestamped raw/normalized observations and diagnostics, and preserves each previously successful city baseline. The manifest contains immutable `previous_baseline` and `current_snapshot` paths for a safe comparison.

## What is implemented

The live command fetches official schema metadata before using explicit city mappings, bounds each cohort to 100 rows, uses deterministic date-descending/ID-ascending order, and a count query for each cohort. Seattle’s second cohort is deliberately named `application_date_sample`; it is not asserted to be in progress or unissued. Issued/application overlap is retained as separate cohort identity. It records request count, retries, bytes, elapsed time, and errors. Raw sampled records are saved beside normalized records. Per-city baselines are timestamped and advanced only after that city succeeds, including a verified empty result; failed cities retain their prior baseline. Atomic writes prevent partially written files.

The comparator emits deterministic `new` and `changed` events for status, valuation, description, and contractor fields. Event IDs hash the transition payload, so two successive changes differ while replaying the same snapshot pair deduplicates to the same ID. It never emits removals and does not overwrite a baseline. When both manifest paths are supplied it rejects different date windows or cohort configurations. Fixtures demonstrate one changed and one new record; fixture results are not live observations.

## Quality questions to answer after live run

- Inspect at least 10 rows per accessible city against the official landing page/source record URL; record mapping errors, missingness, and classification decisions.
- Compare counts by application date, issue date, and status where fields support it.
- Count contractor names and distinguish business names from individual names.
- Inspect repeated addresses and source project/related-permit fields; do not merge on address alone.
- Seattle’s official catalog explicitly includes issued or in-progress permits. The other sources’ status fields must be inspected live before making the same claim.
- Updated timestamps may support a cursor, but only repeated observations can establish whether changes are reliably captured. One observation cannot establish publication latency or freshness.

## Economics / product fit

Measured local probe resource usage is recorded in `run_metrics.json`; it is not measured Apify cost. Per-territory daily request model, assuming one shared scan per city per day: 10 territories = 3 city scans/day plus 10 local filter reads; 100 territories = the same 3 shared city scans/day plus 100 local filter reads. Without shared caching, those become 30 and 300 city scans/day respectively. These are request-volume scenarios, not cost claims. Storage and retries are represented by the measured bytes and retry counters once live.

No current Apify pricing was verified in this offline run, so no dollar estimate is fabricated. Shared caching is an architectural possibility only; it is not implemented here.

## Recommendation

**Narrow.** The official datasets are plausible inputs and the extraction/comparison mechanics are technically feasible, but this run cannot establish current yield, completeness, contractor usefulness, freshness, or customer demand. A next probe should restore network access, complete the 10-row audits, and run repeated observations before a full Actor is considered. This is not a technical go and is not proof of demand.
