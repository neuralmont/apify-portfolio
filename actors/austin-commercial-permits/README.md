# Austin Commercial Permits — local Actor beta

This is a bounded, local Apify Actor beta for Austin’s official [Issued Construction Permits](https://data.austintexas.gov/d/3syk-w9eu) dataset. It is intentionally limited to issued permits and does not enrich records, infer commercial use, or claim demand, market share, publication latency, or longitudinal reliability.

The Actor verifies the dataset schema before querying, applies filters in Socrata SoQL, paginates deterministically by `issue_date DESC, permit_number ASC`, preserves source values, and emits a machine-readable `RUN_SUMMARY`. A contractor summary is a separate dataset artifact and describes activity within the delivered permit records only; its counts are not project counts.

## Inputs

The input schema is in `.actor/input_schema.json`. Defaults are the most recent seven calendar dates in `America/Chicago`, inclusive, `Commercial`, and at most 100 records. `issue_date` is a source date-only field: the Actor sends the selected dates as inclusive source boundaries and does not label them UTC timestamps.

Supported source filters are the verified Austin values `BP`, `EP`, `MP`, `PP`, `DS` and the source contractor trades `General Contractor`, `Electrical Contractor`, `Plumbing Contractor`, and `Mechanical Contractor`. `permitClass` may be `Commercial`, `Residential`, or `All`. `descriptionKeywords`, `requireContractor`, `maxResults` (1–5000), and `includeContractorSummary` are optional.

## Local run

From this directory, with Python 3.9+:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python run_local.py --input input.json --output-dir local_output
```

The dependency-free core can also be tested without installing the SDK. An incomplete retrieval exits with status 2 after preserving delivered records and the run summary. The Actor runtime raises after pushing delivered records when `RUN_SUMMARY.completion` is `incomplete`.

## Actor run

The Dockerfile uses the current Apify Python base image and installs the pinned major-version SDK range. Build and run locally with the Apify CLI or Docker after installing the project dependencies. The Actor writes permit records to the default dataset, a separate `contractor-summary` dataset when requested, and `RUN_SUMMARY` plus `SCHEMA_METADATA` key-value records. It does not publish, schedule, configure billing, or deploy anything.

## Interpretation limits

The source class is preserved as `source_class`; no fallback text inference is performed by the Actor. Missing source values remain null. The issued-only source cannot identify unissued or in-progress applications. A `maxResults` cap makes the run incomplete by design, even though the returned rows are valid. Repeated runs are observations, not a guarantee of freshness or complete territory coverage.
