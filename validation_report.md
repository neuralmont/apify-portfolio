# Validation report

Observation date: 2026-10-06 (America/Chicago). The execution environment could not resolve the three official hosts (`curl` returned `Could not resolve host`), so no live rows, counts, or 10-record source audits were claimed. This is an unresolved blocker, not evidence that the sources are empty. Run the exact command in the README from a network-enabled environment to populate live outputs and metrics.

## What is implemented

The live command bounds each city to at most 100 rows, one 30-day window, deterministic date-descending/ID-ascending order, and a count query for the full window. It records request count, retries, bytes, elapsed time, and errors. Sample completeness is calculated only over returned rows; the full-window count is kept separate. Source timestamps and `observed_at` are not conflated.

The comparator emits deterministic `new` and `changed` events for status, valuation, description, and contractor fields. It never emits removals and does not overwrite a baseline. Fixtures demonstrate one changed and one new record; fixture results are not live observations.

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
