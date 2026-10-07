# Greenhouse Jobs Scraper — Search Tracked Companies

Search jobs across our tracked Greenhouse company boards. The default experience accepts job-title and/or location text and returns the first matching records found in a stable directory order. It does not discover companies or claim internet-wide coverage.

## Input modes

The Console form exposes two modes:

- **Search tracked companies** (default): enter at least one of `titleKeywords`, `locationKeywords`, or `departmentKeywords`. The Actor searches the maintained directory of 36 verified public boards as of 2026-10-07.
- **Specific companies**: select tracked company tokens and/or provide `additionalBoards`. The legacy `boards` input remains supported; an input containing `boards` without an explicit `mode` is treated as Specific companies mode.

The current Apify form supports these selections as string-list fields. It is not presented as a searchable dropdown. Directory tokens include `stripe`, `airbnb`, and `coinbase`; custom boards can be tokens or standard `https://boards.greenhouse.io/{token}` / `https://job-boards.greenhouse.io/{token}` URLs. Individual job URLs are rejected.

`maxJobs` defaults to 100 and is capped at 5,000 delivered records across the run. Boards are fetched once in stable directory/input order. The run stops requesting later boards after the result cap or a spending limit. A capped result is the first matching results in that order, not every match or the best matches.

Filters are literal, case-insensitive text matching: OR within each filter group and AND between nonempty groups. Location matching uses employer-provided location text; there is no radius search, geocoding, or inferred remote eligibility. Directory mode rejects an empty filter set so it cannot silently scrape every job.

The public source is Greenhouse's unauthenticated Job Board API: `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true`. Greenhouse documents the endpoint and the `content=true` behavior in the [official Job Board API documentation](https://docs.greenhouse.io/job-board.html). A board failure is distinct from a valid empty board and leaves other delivered records available.

## Output

Each default-dataset row includes `company_name` when the board is verified in the directory, otherwise `null`, plus the board token, job ID, nullable internal job ID, title, source location, departments, offices, HTML and plain-text description, source URL, source `updated_at`, and observation timestamp. HTML is preserved as data and is not executed. Missing values remain `null` or empty arrays.

`RUN_SUMMARY` contains search mode, directory version, available/attempted/succeeded/failed/skipped board counts, source jobs examined, matches, selected/delivered counts, cap and budget coverage, request metrics, and diagnostics only. It never contains job payloads. `SCHEMA_METADATA` records source and normalization notes.

Example input:

```json
{
  "mode": "directory",
  "titleKeywords": ["engineer", "analyst"],
  "locationKeywords": ["remote", "new york"],
  "maxJobs": 100
}
```

Example output:

```json
{
  "source": "greenhouse",
  "company_name": "Stripe",
  "board_token": "stripe",
  "job_id": "8172487",
  "title": "Abuse Investigator",
  "location": "Dublin",
  "departments": [{"name": "8611 Security Analytics"}],
  "description_text": "Who we are...",
  "job_url": "https://stripe.com/jobs/search?gh_jid=8172487",
  "updated_at": "2026-09-25T16:45:00-04:00"
}
```

This is a bounded snapshot. It does not track changes, infer posting dates, provide applicant data, crawl custom career sites, or guarantee freshness. The directory is a maintained sample, not every Greenhouse company; failed or skipped boards mean coverage is incomplete and are reported in `RUN_SUMMARY`.

## Pricing status

The provisional proposal is `$0.001` per delivered job record (`$1.00 per 1,000`), including descriptions and nested department/office data. Duplicate, filtered, failed, empty-board, summary, and diagnostic work is not charged. This price is not enabled while the Actor remains private. No new charging event was introduced for directory search.

## Directory maintenance

`greenhouse_actor/directory.json` contains 36 distinct verified mappings, source board URLs, and the verification date. Run the bounded validation check from this directory before proposing reviewed changes:

```text
python3 scripts/refresh_directory.py
```

It checks each committed token against the official public API and reports source URLs; it does not discover or rewrite entries.

See [validation_report.md](validation_report.md) for measured observations, tests, private build/run evidence, and remaining launch decisions.
