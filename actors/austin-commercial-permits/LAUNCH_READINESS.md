# Austin Actor beta readiness

Status: local beta implementation only. No publication, schedule, billing, or paid enrichment is configured.

The implementation has a source-specific schema check, inclusive date-only input semantics, server-side SoQL filters, deterministic pagination, bounded retries, bounded HTTP 400 diagnostics, atomic local outputs, and explicit incomplete summaries. A successful cap is distinct from a failure: it reports `completion: complete` plus `cap_truncated: true`; errors remain incomplete. The summary separates source matches, raw rows fetched, delivered rows, duplicate rows rejected, request metrics, and field completeness. Contractor activity is a run-local JSON artifact, not a named dataset.

Verification layers:

- Local extraction: `python3 run_local.py ...` writes atomic JSONL/JSON outputs and records source request metrics.
- Container verification: blocked in the current environment because Docker and Podman are not installed. Run the explicit build/mount/smoke commands in `validation_report.md` when available; inspect the default dataset plus `RUN_SUMMARY` and `CONTRACTOR_SUMMARY`.
- Cloud verification: not performed in this pass. A private benchmark is required before any production decision.

Private benchmark: run privately at `maxResults` 100, 1,500, and 5,000 using the same bounded date window. For each run record elapsed time, peak memory, billed usage, delivered rows, `matching_source_count`, `cap_truncated`, page offsets/limits, and run status from `RUN_SUMMARY`. Use a new run/default storage each time; the contractor artifact is `CONTRACTOR_SUMMARY` in that run’s default key-value store. The current live check verified a 12,008-match window with 1,500 delivered across page limits 1,000 and 500.

Deployment scope is private only: connect the GitHub repository in Apify with the Actor directory set to `actors/austin-commercial-permits`, build the selected commit, and run privately. Capture the build ID/status and build usage separately from each run ID/status, runtime, memory, billed usage, delivered count, and output links. Do not publish, enable charging, or schedule.
