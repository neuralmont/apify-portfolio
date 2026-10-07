# Greenhouse Jobs Scraper validation report

Initial implementation and private validation were performed on 2026-10-07. Monetization is disabled; no schedule or public deployment is enabled by this Actor. Sanitized measured evidence is in [evidence/validation_20261007.json](evidence/validation_20261007.json).

## Source and behavior

The Actor uses Greenhouse's documented unauthenticated Job Board API list endpoint with `content=true`. It processes only supplied board tokens or supported board URLs, constructs requests against the fixed `boards-api.greenhouse.io` host, rejects individual job URLs, and does not follow redirects. The list response supplies job-post `id`, distinct nullable `internal_job_id`, descriptions, departments, offices, source absolute URLs, and `updated_at`. See the [official documentation](https://docs.greenhouse.io/job-board.html).

## Tests

Command from this directory:

```text
/private/tmp/greenhouse-actor-venv/bin/python -m pytest -q tests
```

The suite covers directory mode, backward-compatible `boards` input, company/custom-board deduplication, filters across boards, zero matches, empty/malformed/failed boards, global caps, summary redaction, retry behavior, packaging manifests, and billing ChargeResult semantics.

Result after the directory-mode change: `22 passed in 0.27s` with Python 3.11.14 and `apify==4.0.2`. Input schema validation succeeded with `apify validate-schema .actor/input_schema.json`.

## Live validation

Three independent public boards were reachable during validation: `stripe`, `airbnb`, and `coinbase`. Each returned HTTP 200 from the documented public list endpoint. Separate bounded observations delivered three records per board: 719/160/223 source rows respectively, one request and zero retries per board. Sanitized source IDs and titles are recorded in the evidence file; no job-detail requests were made.

The maintained directory contains 36 distinct companies, verified on 2026-10-07. It is an intentionally bounded sample, not every Greenhouse company. `python3 scripts/refresh_directory.py` rechecked all 36 entries successfully against the public API; no discovery or external dependency was added. The directory order is the search order, and custom boards without a verified mapping receive `company_name: null`.

The tracked-company private Actor was built from source SHA `b25e687` as build `NLLVwrokOO8p7F2oW` (version `0.1.4`) for Actor `FjuIJU6cw0MqWqwKE`. It remains private and unmonetized.

Two directory-wide benchmarks on that build measured the new search economics. The broad title search (`engineer`) run `raMZMNBlaLa2xX7pC` searched all 36 boards: 7,125 source jobs examined, 2,551 matches and deliveries, 36 requests, zero retries, 87.948 seconds, 173,142,016-byte peak memory, and `$0.02876661167771452` platform usage. The sparse title-plus-location search (`chief executive officer` + `Antarctica`) run `MntUwlwovftD1LQCF` also searched all 36 boards: 7,125 examined, zero matches/deliveries, 36 requests, zero retries, 9.13 seconds, 120,639,488-byte peak memory, and `$0.0021914525950037767` platform usage. Both completed with full selected-board coverage and no errors.

The retained bounded multi-board run `lo3Cov02ME0VoUTMa` requested 300 jobs and succeeded with 300 unique dataset rows in 23.178 seconds, 94,027,776-byte peak memory, and measured platform usage of `$0.0068795481605480125`. It fetched 719 Stripe rows, then skipped Airbnb and Coinbase because the global cap was satisfied; its summary correctly reports `full_input_coverage: false` and `coverage: bounded_global_cap`.

The local real-SDK PPE checks used fixture records only. With `apify==4.0.2`, sufficient (3/3), partial (1 delivered before a limit stop), and exact (2/2) cases reconciled dataset rows, job-record events, summaries, and process status. Local test events simulate `$1` each and also include SDK synthetic dataset-item events, so these checks do not validate the proposed `$0.001` price or represent customer billing.

## Limitations

- A board response is a bounded snapshot, not a longitudinal feed. Reruns may return the same jobs.
- `updated_at` is not labelled as a posting date.
- Greenhouse availability varies by company configuration; failures are not treated as empty boards.
- The current endpoint returns the board list in one response; this Actor bounds delivery but does not claim complete territory coverage when the global cap is reached.
- This Actor does not discover companies, crawl custom career sites, infer salary or remote status, or submit applications.
