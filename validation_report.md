# Validation report

Observation date: 2026-10-06 (America/Chicago). The newest manual macOS Terminal run saved `outputs/snapshots/20261006T204519Z/`. Codex’s ordinary execution environment remains unable to resolve the hosts; the local observation is the live evidence used below.

## Saved live observation

The newest manifest reports Chicago `success` with 100 issued rows and a full-window count of 3,032; Seattle `success` with 100 issued rows (count 451) plus 100 `application_date_sample` rows (count 453); and Austin `success` with 100 issued rows (count 4,770). All requested cohorts succeeded, so the aggregate is complete. The run used 11 requests, 0 retries, and 992,594 bytes. The saved manifest did not record wall-clock elapsed time, so none is inferred.

The raw saved records confirm the mappings: Chicago has `contact_1_type/name` through `contact_9_type/name`, Seattle has `contractorcompanyname`, and Austin uses `permittype`, `permit_class_mapped`, `permit_location`, `total_job_valuation`, `status_current`, `contractor_trade`, and `contractor_company_name`. The Austin and Chicago/Seattle metadata references are recorded in [source_inventory.md](source_inventory.md).

Reproducible statistics are calculated by `python3 audit_saved.py outputs/snapshots/20261006T204519Z`. The sanitized results and Austin 10-record audit are in [evidence/live_quality_20261006T204519Z.json](evidence/live_quality_20261006T204519Z.json); selected source-shaped, contact-redacted records are in [raw_audit_records_20261006T204519Z.json](evidence/raw_audit_records_20261006T204519Z.json). Counts are full-window API counts; completeness and classification counts are only deterministic 100-record samples:

| Sample | Classification | Address | Description | Valuation | Contractor | Other |
|---|---:|---:|---:|---:|---:|---|
| Chicago issued n=100 | commercial 6, residential 27, unknown 67 | 100% | 100% | 96% | 99% overall / 100% commercial | postal 0%, status 74%, coordinates 99% |
| Seattle issued n=100 | commercial 27, residential 73, unknown 0 | 100% | 100% | 100% | 8% overall / 4% commercial | postal 88%, status/coordinates 100% |
| Seattle application-date n=100 | commercial 22, residential 78, unknown 0 | 100% | 100% | 100% | 0% overall / 0% commercial | postal 77%, status/coordinates 100% |
| Austin issued n=100 | commercial 36, residential 64, unknown 0 | 100% | 100% | 8% | 88% overall / 78% commercial | postal 0%, status/coordinates 70% |

Chicago classification is heuristic work-description evidence because the source does not provide an explicit commercial/residential category in the mapped fields. Five records with conflicting commercial/residential cues (`3342274`, `3433168`, `3439955`, `3443901`, `N2983385`) are now `unknown` with ambiguity evidence. Seattle and Austin classifications are source-provided category fields. Contractor completeness is shown both overall and within commercial-classified records; contact names are retained only for source-supported contractor roles/company fields, not owners or unrelated roles. These samples are not representative yield estimates and do not establish lead quality, purchase intent, or equipment need.

## City recommendations

- Chicago: retain as a secondary source. It has 99% contractor-field completeness overall and 100% among the six commercial-classified sample rows, but no postal values, no source classification field in this mapping, and five ambiguous mixed-use/conflict records.
- Seattle: retain issued permits as a useful classification source, but contractor availability is weak (1/27 commercial issued rows). The application-date sample is useful as a separate cohort, not evidence of unissued/in-progress status.
- Austin: strongest contractor coverage in this observation (28/36 commercial rows), but valuation completeness is only 8%, postal is 0%, and coordinates are 70%. Keep for future repeated observations, with those limitations explicit.

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

- The saved Chicago, Seattle, and Austin samples have ten-record mapping/classification audits in the evidence artifact; they are checks against source-shaped raw fields, not independent permit adjudication.
- Compare counts by application date, issue date, and status where fields support it.
- Count contractor names and distinguish business names from individual names.
- Inspect repeated addresses and source project/related-permit fields; do not merge on address alone.
- Seattle’s official catalog explicitly includes issued or in-progress permits. The other sources’ status fields must be inspected live before making the same claim.
- Updated timestamps may support a cursor, but only repeated observations can establish whether changes are reliably captured. One observation cannot establish publication latency or freshness.

## Economics / product fit

Measured local probe resource usage is recorded in `run_metrics.json`; it is not measured Apify cost. Per-territory daily request model, assuming one shared scan per city per day: 10 territories = 3 city scans/day plus 10 local filter reads; 100 territories = the same 3 shared city scans/day plus 100 local filter reads. Without shared caching, those become 30 and 300 city scans/day respectively. These are request-volume scenarios, not cost claims. Storage and retries are represented by the measured bytes and retry counters once live.

No current Apify pricing was verified in this offline run, so no dollar estimate is fabricated. Shared caching is an architectural possibility only; it is not implemented here.

## Recommendation

**Narrow.** Chicago, Seattle, and Austin all produced bounded issued cohorts in the newest observation. Seattle’s issued sample has low contractor availability (8% overall; 1/27 commercial), while Austin has stronger contractor availability (88% overall; 28/36 commercial) but only 8% valuation completeness and 70% coordinate completeness. Chicago has high contractor availability but substantial classification ambiguity. Keep all three as probe sources, with Austin/Seattle preferred for the next data-quality iteration; do not proceed to an Actor until repeated observations and demand validation are completed. This is not a demand claim or a longitudinal-freshness claim.
