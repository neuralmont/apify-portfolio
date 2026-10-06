# Austin Actor beta readiness

Status: local beta implementation only. No publication, schedule, billing, or paid enrichment is configured.

The implementation has a source-specific schema check, inclusive date-only input semantics, server-side SoQL filters, deterministic pagination, bounded retries, bounded HTTP 400 diagnostics, atomic local outputs, and explicit incomplete summaries. The summary separates source matches, raw rows fetched, delivered rows, duplicate rows rejected, request metrics, and field completeness.

Before any production decision, run a small default observation and a paginated commercial observation against the official Austin dataset. Review the saved `RUN_SUMMARY`, `SCHEMA_METADATA`, and raw source-shaped records. Treat the results as feasibility evidence only: they do not establish demand, market share, publication latency, or longitudinal reliability.
