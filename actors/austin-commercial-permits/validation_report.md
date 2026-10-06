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

Local extraction is verified by the dependency-free runner and unit tests. The current repository has Apify CLI 1.2.1, while the current npm CLI 1.10.0 was used for schema validation. Docker and Podman are not installed in this environment, so container verification could not be performed. Apify cloud verification was completed privately on build `rgIovT5VBdeaVQ8cv`; the live HTTPS observation above is a local process observation, distinct from those cloud runs.

The current CLI schema commands and results were:

```bash
cd actors/austin-commercial-permits
apify validate-schema                         # local 1.2.1: input only, passed
npx --yes apify-cli@latest validate-schema    # CLI 1.10.0: input, dataset, output passed
```

The nested manifest uses `dockerContextDir: ".."` because that path is relative to `.actor/actor.json`; the Dockerfile and README paths resolve at the Actor root, while the schema paths resolve under `.actor`. This matches the current Actor definition and monorepo documentation.

Container commands to run when Docker is available:

```bash
cd actors/austin-commercial-permits
docker build -t austin-commercial-permits-beta .
storage_dir=$(mktemp -d /tmp/austin-actor-storage.XXXXXX)
mkdir -p "$storage_dir/key_value_stores/default"
cp input.example.json "$storage_dir/key_value_stores/default/INPUT.json"
docker run --rm \
  -e APIFY_LOCAL_STORAGE_DIR=/apify_storage \
  -e APIFY_DEFAULT_DATASET_ID=default \
  -e APIFY_DEFAULT_KEY_VALUE_STORE_ID=default \
  -v "$storage_dir:/apify_storage" \
  austin-commercial-permits-beta
find "$storage_dir" -type f -print
```

Expected successful smoke-test evidence is exit status 0, permit items under the default dataset storage, and `RUN_SUMMARY.json` plus `CONTRACTOR_SUMMARY.json` under the default key-value store. To verify a genuine extraction failure preserves diagnostics and fails, repeat with `--network none`; metadata retrieval should be recorded in `RUN_SUMMARY` and the container should exit nonzero. This tests failure handling without changing source mappings.

For a private benchmark, build from this nested directory and run the same date window at `maxResults` 100, 1,500, and 5,000. Record runtime and peak memory from the Apify run details, billed usage and usage charges from the run/build usage panels or API response, delivered rows and `matching_source_count` from `RUN_SUMMARY`, final status, build ID, run ID, and the dataset, `RUN_SUMMARY`, and `CONTRACTOR_SUMMARY` links. Keep build costs separate from run costs; do not infer cloud cost from local timing. Do not publish, enable charging, or schedule runs.

```bash
cd actors/austin-commercial-permits
docker build -t austin-commercial-permits-beta .
docker run --rm austin-commercial-permits-beta
```

The run’s default dataset contains permit records. `RUN_SUMMARY` and `CONTRACTOR_SUMMARY` are JSON artifacts in the run’s default key-value store; the latter is isolated by run and counts activity within delivered records, not distinct construction projects.

## Private Apify cloud verification

This pass created a private Actor and completed a remote build and benchmark runs. No public publishing, schedule, or separate charging configuration was enabled.

| Item | ID/status | Runtime | Peak memory | Usage |
| --- | --- | ---: | ---: | ---: |
| Build 0.1.1 | `rgIovT5VBdeaVQ8cv` / SUCCEEDED | 15.235 s | n/a | $0.0033731111 build usage |
| maxResults 100 | `pScqzuF4TcT9eA0Mi` / SUCCEEDED | 15.568 s | 59.20 MiB | $0.0041817487 |
| maxResults 1,500 | `uYHhmQ76cdU9647Yk` / SUCCEEDED | 37.145 s | 77.27 MiB | $0.0161507564 |
| maxResults 5,000 | `pHdBKntPTSvKxy69m` / SUCCEEDED | 114.023 s | 100.75 MiB | $0.0511634989 |

All three runs used the `2026-01-01` through `2026-10-06` Commercial window. They reported 12,008 matching source records, no errors or duplicates, and delivered 100, 1,500, and 5,000 records respectively. Each was a successful capped run with `cap_truncated: true`. The 1,500 run requested pages of 1,000 and 500; the 5,000 run requested five pages of 1,000. Default dataset item counts matched delivered records. `RUN_SUMMARY` and `CONTRACTOR_SUMMARY` were readable from each run’s default key-value store.

Representative authenticated Console run links and storage IDs:

- [100-record run](https://console.apify.com/actors/g32YlfG1SeYV9ctKK/runs/pScqzuF4TcT9eA0Mi): dataset `5qgeA1x0bReM3tUSM`, key-value store `viDIJ5d2UB8afra1I`
- [1,500-record run](https://console.apify.com/actors/g32YlfG1SeYV9ctKK/runs/uYHhmQ76cdU9647Yk): dataset `mKd7MC8tP7hkWVGhC`, key-value store `bhgmrlikqDVMglbjx`
- [5,000-record run](https://console.apify.com/actors/g32YlfG1SeYV9ctKK/runs/pHdBKntPTSvKxy69m): dataset `ZgHG4XIZmxYkG1NEd`, key-value store `jqZaCP7AaXfFs5ocl`

The run output tab exposes the signed dataset, `RUN_SUMMARY`, and `CONTRACTOR_SUMMARY` links; signed URLs are intentionally not committed to Git.

## Review of all four existing private runs

No runs were started for this review. The four existing runs used the same inclusive date window and Commercial filter. Dataset retrieval and unique `source_record_id` counting were performed through authenticated CLI reads; all rows had non-missing unique permit IDs.

| Run ID | maxResults | Status | Dataset rows / unique IDs | Completion / truncation / pagination | Errors | Runtime | Peak memory | Run usage |
| --- | ---: | --- | ---: | --- | --- | ---: | ---: | ---: |
| `eZtJR2CJztRVEVC5P` | 100 | SUCCEEDED | 100 / 100 | complete / yes / false | none | 8.037 s | 64.35 MiB | $0.0025058093 |
| `uYHhmQ76cdU9647Yk` | 1,500 | SUCCEEDED | 1,500 / 1,500 | complete / yes / false | none | 37.145 s | 77.27 MiB | $0.0161507564 |
| `pHdBKntPTSvKxy69m` | 5,000 | SUCCEEDED | 5,000 / 5,000 | complete / yes / false | none | 114.023 s | 100.75 MiB | $0.0511634989 |
| `pScqzuF4TcT9eA0Mi` | 100 | SUCCEEDED | 100 / 100 | complete / yes / false | none | 15.568 s | 59.20 MiB | $0.0041817487 |

Each run’s key-value store contained `RUN_SUMMARY` and `CONTRACTOR_SUMMARY`. Contractor summary group/count checks were respectively 60 groups/87 delivered permits, 613/1,347, 1,457/4,598, and 60/87; all summaries had `extraction_incomplete: false`. The distinct store IDs and matching per-run counts verify isolation. Build cost was $0.0033731111 and is separate from run usage. The sanitized machine-readable evidence is `evidence/private_run_comparison_20261006.json`.

## Paid-beta preparation

The proposed price is `$0.003` per delivered permit record. The implementation uses the official Python SDK's `push_data(..., charged_event_name="permit-record")` shortcut only when the run is in PPE mode. It records `charged_count` and `event_charge_limit_reached`, preserves partial delivery in `RUN_SUMMARY`, and exits cleanly at a customer spending limit. The SDK owns idempotency and transport retries; the Actor does not blindly retry an ambiguous push. Summary artifacts, source counts, and rejected duplicates are not charged. Charging is not configured or enabled on the private Actor.

The proposed Console setup, listing metadata, tutorial, and 30-day measurement plan are in `PRICING_CONFIGURATION.md`, `LISTING_METADATA.md`, `TUTORIAL.md`, and `LAUNCH_MEASUREMENT_PLAN.md`. The four prior benchmark runs remain operational tests and are excluded from customer metrics.

## Remaining limitations

This beta covers only issued permits in Austin’s dataset. It does not identify unissued applications or guarantee current publication timing. The Actor preserves source classification and does not infer it from addresses or descriptions. Missing valuations and coordinates remain missing. Contractor summaries group exact source company/trade values and count delivered permit records, not distinct projects. Customer billing, publishing, and scheduling remain disabled; no enrichment was added.
