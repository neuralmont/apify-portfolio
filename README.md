# Commercial Construction Permit Intelligence — bounded feasibility probe

This is a reproducible, bounded probe—not an Actor, lead qualifier, dashboard, or customer-demand test. It uses public Socrata endpoints, the Python 3 standard library, deterministic ordering, source-scoped IDs, schema validation, and bounded retries. Every run creates a timestamped snapshot directory and per-city status manifest.

## Run

```bash
python3 -m unittest discover -s tests -v
python3 probe.py live --cities chicago seattle austin --limit 100 --since 2026-09-06 --until 2026-10-06 --seattle-in-progress --out outputs/live.csv
python3 probe.py compare outputs/baselines/chicago.jsonl outputs/snapshots/<timestamp>/chicago/normalized.jsonl --out outputs/events.jsonl
python3 probe.py compare fixtures/before.jsonl fixtures/after.jsonl --out /tmp/permit-fixture-events.jsonl
```

`live` uses explicit inclusive UTC whole-date boundaries (default: the last 30 days), fetches and validates official schema metadata before querying, and writes raw samples, normalized cohorts, a timestamped manifest, and metrics. Chicago and Austin use issued cohorts. Seattle’s optional application/in-progress cohort is separate and must not be interpreted as issue-date coverage. A failed city never advances its baseline; a successful zero-count result is recorded as `verified_empty`. Incomplete extraction exits 2. `compare` keys by `(source_dataset, source_record_id)`, rejects missing/duplicate identities, emits no removals, and creates deterministic transition-specific event IDs.

## Sources and mappings

See [source_inventory.md](source_inventory.md) and [field_mapping.csv](field_mapping.csv). Canonical landing pages: Chicago `ydr8-5enu`, Seattle `76t5-zqzr`, and Austin `3syk-w9eu`.

## Caveats

`observed_at` is our observation time, while `source_updated_at` is copied from a source row when present. Neither proves publication latency. Commercial classification uses explicit source categories when available; only work-description matches are labeled heuristic. Street-address words are never used. Contractor names are retained only when a source contact-role field supports the interpretation. No row is a qualified lead, confirmed purchase, or equipment-need claim. Project grouping is always null in this probe until a source relationship or defensible evidence is supplied.

The checked-in normalized sample is a clearly labeled fixture, not live city data. See `samples/` and `validation_report.md`.
