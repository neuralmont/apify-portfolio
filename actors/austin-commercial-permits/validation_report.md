# Austin commercial permits beta validation

Date: 2026-10-06. Source: official Austin Socrata dataset `3syk-w9eu` and its metadata endpoint. This is a bounded feasibility observation, not a demand, market-share, publication-latency, or longitudinal-reliability claim.

## Live observation

The execution environment reached the official HTTPS endpoint with normal TLS verification after the sandboxed DNS check was unavailable. The default seven-calendar-date run used `2026-09-30` through `2026-10-06` in `America/Chicago`; the source field is date-only and was not represented as UTC.

| Run | Source matches | Fetched | Delivered | Completion | Requests | Retries | Bytes | Elapsed |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| Commercial, max 100 | 194 | 100 | 100 | complete; full window truncated | 3 | 0 | 304,703 | 1.187 s |
| Commercial, max 5000 | 194 | 194 | 194 | complete | 3 | 0 | 472,404 | 1.612 s |
| Commercial, Jan 1–Oct 6, max 1500 | 12,008 | 1,500 | 1,500 | complete; full window truncated | 4 | 0 | 2,616,443 | 5.033 s |

The first run intentionally truncated the full window at its cap; under the corrected semantics it should be a successful run with `completion: complete`, `cap_truncated: true`, and no errors. The paginated run delivered the full 194 matching source rows for this window. No duplicates or request errors were reported.

The larger live pagination run made two page requests after metadata and count: offset 0 with limit 1,000 returning 1,000 rows, then offset 1,000 with limit 500 returning 500 rows. This verifies the remaining-allowance bound and records the full source count separately from delivered rows.

For the complete run, all 194 rows had issue date, status, source permit type, source class, description, and address. Latitude and longitude were present on 127/194 (65.5%) each. Contractor name was present on 176/194 (90.7%) overall and on 176/194 commercial-classified rows (90.7%); contractor trade was present on 181/194 (93.3%). Project valuation was present on 13/194 (6.7%). All 194 rows had source class `Commercial`; this is a sample statistic for the requested source filter, not a population estimate.

The three-record audit sample in `evidence/austin_live_sample_20261006.jsonl` retains source identifiers, source class/type, descriptions, public permit addresses, contractor company/trade fields, and raw valuation nulls. It omits coordinates and other unnecessary fields. The descriptions provide direct supporting text for grocery-store ramp work, a business service center, and warehouse food-service renovation. They are examples only, not a commercial-yield estimate.

Reproduce the statistics with:

```bash
python3 scripts/audit_output.py /tmp/austin-actor-live-20261006-paginated/permits.jsonl
```

Reproduce the bounded runs with:

```bash
python3 run_local.py --input input.example.json --output-dir /tmp/austin-actor-live-20261006
python3 run_local.py --input input.paginated.example.json --output-dir /tmp/austin-actor-live-20261006-paginated
```

The output directory contains `permits.jsonl`, `contractor_summary.jsonl`, and `run_summary.json`; writes are atomic. A future run should use a new output directory so observations remain separate.

## Verification layers and private benchmark

Local extraction is verified by the dependency-free runner and unit tests. Container verification and Apify cloud verification are separate gates and were not completed in this pass unless explicitly reported by the caller; the live HTTPS observation above is a local process observation, not an Apify cloud run. For a private benchmark, build from this nested directory and run the same input window at `maxResults` 100, 1,500, and 5,000. Record runtime, peak memory, billed usage, delivered rows, `matching_source_count`, `cap_truncated`, and final run status. Do not publish, enable charging, or schedule runs.

```bash
cd actors/austin-commercial-permits
docker build -t austin-commercial-permits-beta .
docker run --rm austin-commercial-permits-beta
```

The run’s default dataset contains permit records. `RUN_SUMMARY` and `CONTRACTOR_SUMMARY` are JSON artifacts in the run’s default key-value store; the latter is isolated by run and counts activity within delivered records, not distinct construction projects.

## Remaining limitations

This beta covers only issued permits in Austin’s dataset. It does not identify unissued applications or guarantee current publication timing. The Actor preserves source classification and does not infer it from addresses or descriptions. Missing valuations and coordinates remain missing. Contractor summaries group exact source company/trade values and count delivered permit records, not distinct projects. No billing, publishing, scheduling, enrichment, or Apify deployment was performed.
