# Greenhouse Jobs Scraper — Company Boards & Full Descriptions

Extract public job postings from Greenhouse company boards that you supply. The Actor uses Greenhouse's public Job Board API and returns one default-dataset row per unique job post within each board.

This is a bounded snapshot. Reruns can return the same jobs again; it does not track new, changed, or removed postings. `updated_at` is Greenhouse's source-updated timestamp, not a guaranteed publication date.

## Input

Supply `boards` as board tokens or standard board URLs such as `stripe`, `https://boards.greenhouse.io/stripe`, or `https://job-boards.greenhouse.io/stripe`. To find a token, open a company's Greenhouse board URL and use the path segment after the host. Individual job URLs are rejected rather than interpreted as requests for the whole board.

`maxJobs` defaults to 100 and is capped at 5,000 across all boards. `titleKeywords`, `locationKeywords`, and `departmentKeywords` are optional case-insensitive OR filters within each group; nonempty groups are combined with AND. Boards are processed in input order, duplicate boards are removed, and later boards are skipped after the global cap or a spending-limit stop.

The public source is `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true`. Greenhouse documents this endpoint as public and says `content=true` includes descriptions, departments, and offices. No login, applicant data, application submission, company discovery, proxy, browser, salary extraction, or custom career-site crawling is supported. A board can be unavailable or can expose no jobs; failures are reported distinctly from a valid empty response.

## Example input

```json
{
  "boards": ["stripe", "https://boards.greenhouse.io/airbnb"],
  "maxJobs": 100,
  "titleKeywords": ["engineer", "analyst"],
  "locationKeywords": ["remote", "new york"],
  "departmentKeywords": ["engineering"]
}
```

## Output

Each dataset record includes the source, board token, string job-post ID, nullable internal job ID, title, source location, department and office structures, source HTML description, entity-decoded plain-text description, source absolute URL, `updated_at`, and `retrieved_at`. HTML is stored as data; it is not executed. Missing values remain `null` or empty arrays. The Actor does not infer salary, remote status, or posted dates.

Sanitized example:

```json
{
  "source": "greenhouse",
  "board_token": "example",
  "job_id": "127817",
  "internal_job_id": "144381",
  "title": "Vault Designer",
  "location": "NYC",
  "departments": [{"id": 13583, "name": "Design"}],
  "offices": [{"id": 8304, "name": "New York", "location": "New York, NY, United States"}],
  "description_html": "<p>Build thoughtful products.</p>",
  "description_text": "Build thoughtful products.",
  "job_url": "https://boards.greenhouse.io/example/jobs/127817",
  "updated_at": "2016-01-14T10:55:28-05:00",
  "retrieved_at": "2026-10-07T00:00:00Z"
}
```

`RUN_SUMMARY` contains counts, coverage, cap/budget stop reasons, request metrics, and diagnostics only. It never contains job records or descriptions. `SCHEMA_METADATA` records source and normalization notes.

## Pricing proposal

Proposed beta price: `$0.001` per delivered job record (`$1.00 per 1,000`), including the full description and department/office structure. Duplicate, filtered, failed, empty-board, summary, and diagnostic work is not charged. No start fee, synthetic dataset-item fee, or platform-usage pass-through is proposed. Monetization is disabled for this initial private deployment.

## Official documentation

- [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html)
- [List jobs](https://docs.greenhouse.io/job-board.html#list-jobs)

See [validation_report.md](validation_report.md) for live observations, tests, and limitations.
