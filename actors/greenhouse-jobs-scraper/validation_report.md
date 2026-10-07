# Greenhouse Jobs Scraper validation report

Initial implementation and private validation were performed on 2026-10-07. Monetization is disabled; no schedule or public deployment is enabled by this Actor.

## Source and behavior

The Actor uses Greenhouse's documented unauthenticated Job Board API list endpoint with `content=true`. It processes only supplied board tokens or supported board URLs, constructs requests against the fixed `boards-api.greenhouse.io` host, rejects individual job URLs, and does not follow redirects. The list response supplies job-post `id`, distinct nullable `internal_job_id`, descriptions, departments, offices, source absolute URLs, and `updated_at`. See the [official documentation](https://docs.greenhouse.io/job-board.html).

## Tests

Command from this directory:

```text
/private/tmp/greenhouse-actor-venv/bin/python -m pytest -q tests
```

The suite covers input normalization, duplicate boards, filters, entity decoding, job versus internal IDs, empty/malformed/failed boards, global caps, summary redaction, retry behavior, and billing ChargeResult semantics. Local result will be recorded after execution.

## Live validation

Three public boards were reachable during validation: `stripe`, `airbnb`, and one additional currently working board selected before the final deployment. Records are compared to the public API response; no job-detail requests are made. Counts, source samples, request volume, runtime, memory, and platform usage are recorded in `evidence/` after the final private run.

## Limitations

- A board response is a bounded snapshot, not a longitudinal feed. Reruns may return the same jobs.
- `updated_at` is not labelled as a posting date.
- Greenhouse availability varies by company configuration; failures are not treated as empty boards.
- This Actor does not discover companies, crawl custom career sites, infer salary or remote status, or submit applications.
