# Commercial Construction Permit Intelligence — bounded feasibility probe

This is a reproducible, bounded probe—not an Actor, lead qualifier, dashboard, or customer-demand test. It uses public Socrata endpoints, the Python 3 standard library, deterministic ordering, stable source IDs, and two bounded data requests per city (sample + full-window count), with two retries.

## Run

```bash
python3 -m unittest discover -s tests -v
python3 probe.py live --cities chicago seattle austin --limit 100 --out outputs/live.csv
python3 probe.py compare outputs/previous.jsonl outputs/live.jsonl --out outputs/events.jsonl
python3 probe.py compare fixtures/before.jsonl fixtures/after.jsonl --out /tmp/permit-fixture-events.jsonl
```

`live` uses the most recent 30 calendar days at execution time and each city’s documented issue-date field. It writes CSV and JSONL siblings plus `outputs/run_metrics.json`. A live network failure is recorded per city; it does not create a plausible-looking empty baseline. `compare` is safe to run against a failed extraction only if the caller retains the last good JSONL as the baseline; the comparator itself never emits removals.

## Sources and mappings

See [source_inventory.md](source_inventory.md) and [field_mapping.csv](field_mapping.csv). Canonical landing pages: Chicago `ydr8-5enu`, Seattle `76t5-zqzr`, and Austin `3syk-w9eu`.

## Caveats

`observed_at` is our observation time, while `source_updated_at` is copied from a source row when present. Neither proves publication latency. Commercial classification is `commercial`, `residential`, or `unknown`; heuristic matches include their supporting text. No row is a qualified lead, confirmed purchase, or equipment-need claim. Project grouping is always null in this probe until a source relationship or defensible evidence is supplied.

The checked-in normalized sample is a clearly labeled fixture, not live city data. See `samples/` and `validation_report.md`.
