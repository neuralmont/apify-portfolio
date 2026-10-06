# Validation report

Observation date: 2026-10-06 (America/Chicago). A manual macOS Terminal run reached all three official sources and saved `outputs/snapshots/20261006T202655Z/`. Codex’s ordinary execution environment remains unable to resolve the hosts, so no second live run was attempted here. The saved observation is the live evidence used below.

## Saved live observation

The manifest reports Chicago `success` with 100 issued rows and a full-window count of 3,032; Seattle issued `success` with 100 rows and a full-window count of 451; Seattle’s optional `applicationdate` cohort returned HTTP 400; Austin stopped at schema validation because the prior `permit_type` mapping was absent. Chicago saved `issued_raw.jsonl`, `normalized.jsonl`, and `normalized.csv`. Seattle saved only `issued_raw.jsonl`: its issued query completed, but the old all-or-nothing city path did not persist normalized issued output before the optional cohort failure. Austin saved no sample. The corrected code now persists each successful cohort before continuing to an optional cohort and captures bounded HTTP 400 bodies without retrying the same request.

The raw saved records corrected the mappings: Chicago has `contact_1_type/name` through `contact_9_type/name` in the sample, not `contractor_N_*`; Seattle has `contractorcompanyname` on 8 of 100 issued records; Austin’s official schema uses `permittype`, `permit_class_mapped`, `permit_location`, `total_job_valuation`, `status_current`, `contractor_trade`, and `contractor_company_name`. The Austin and Chicago/Seattle metadata references are recorded in [source_inventory.md](source_inventory.md).

Measured sample quality and 10-record audits are in [evidence/live_quality_20261006T202655Z.json](evidence/live_quality_20261006T202655Z.json). Counts are full-window API counts; completeness and classification counts are only the deterministic latest-100 samples:

| Sample | Classification | Address | Description | Valuation | Contractor | Other |
|---|---:|---:|---:|---:|---:|---|
| Chicago issued n=100 | commercial 11, residential 25, unknown 64 | 100% | 100% | 96% | 99% | postal 0%, status 74%, coordinates 99% |
| Seattle issued n=100 | commercial 27, residential 73, unknown 0 | 100% | 100% | 100% | 8% | postal 88%, status/coordinates 100% |

Chicago classification is heuristic work-description evidence because the source does not provide an explicit commercial/residential category in the mapped fields. Seattle classification is source-provided `permitclassmapped`. These samples are not representative yield estimates and do not establish lead quality, purchase intent, or equipment need.

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

The live command fetches official schema metadata before using explicit city mappings, bounds each cohort to 100 rows, uses deterministic date-descending/ID-ascending order, and a count query for each cohort. Seattle’s second cohort is deliberately named `application_date_sample`; it is not asserted to be in progress or unissued. Issued/application overlap is retained as separate cohort identity. It records request count, retries, bytes, elapsed time, and errors. Raw sampled records are saved beside normalized records. Successful cohorts are persisted even if a later optional cohort fails. HTTP 400 responses include a bounded response body and are not retried unchanged. Per-city baselines are timestamped and advanced only after that city succeeds; failed or partial cities retain their prior baseline. Atomic writes prevent partially written files.

The comparator emits deterministic `new` and `changed` events for status, valuation, description, and contractor fields. Event IDs hash the transition payload, so two successive changes differ while replaying the same snapshot pair deduplicates to the same ID. It never emits removals and does not overwrite a baseline. When both manifest paths are supplied it rejects different date windows or cohort configurations. Fixtures demonstrate one changed and one new record; fixture results are not live observations.

## Quality questions to answer after live run

- The saved Chicago and Seattle samples have ten-record mapping/classification audits in the evidence artifact; they are checks against source-shaped raw fields, not independent permit adjudication.
- Compare counts by application date, issue date, and status where fields support it.
- Count contractor names and distinguish business names from individual names.
- Inspect repeated addresses and source project/related-permit fields; do not merge on address alone.
- Seattle’s official catalog explicitly includes issued or in-progress permits. The other sources’ status fields must be inspected live before making the same claim.
- Updated timestamps may support a cursor, but only repeated observations can establish whether changes are reliably captured. One observation cannot establish publication latency or freshness.

## Economics / product fit

Measured local probe resource usage is recorded in `run_metrics.json`; it is not measured Apify cost. Per-territory daily request model, assuming one shared scan per city per day: 10 territories = 3 city scans/day plus 10 local filter reads; 100 territories = the same 3 shared city scans/day plus 100 local filter reads. Without shared caching, those become 30 and 300 city scans/day respectively. These are request-volume scenarios, not cost claims. Storage and retries are represented by the measured bytes and retry counters once live.

No current Apify pricing was verified in this offline run, so no dollar estimate is fabricated. Shared caching is an architectural possibility only; it is not implemented here.

## Recommendation

**Narrow.** Chicago and Seattle provide usable issued-permit inputs in this observation, with materially different contractor completeness and classification evidence. Austin and Seattle’s application cohort still require a corrected live run. The bounded extraction mechanics are technically feasible, but source quality, freshness, repeated-change capture, and customer demand remain unvalidated. This is not a technical go and is not proof of demand.
