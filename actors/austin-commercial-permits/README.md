# Austin Commercial Building Permits & Contractor Activity

Find recently issued commercial building permits in Austin's official public [Issued Construction Permits dataset](https://data.austintexas.gov/d/3syk-w9eu). This private beta is intended first for construction suppliers researching contractor activity.

The Actor returns source permit records; a permit is not a distinct construction project, a qualified lead, or evidence of demand. It does not enrich records, infer commercial use from address text, or claim exclusivity, guaranteed freshness, or complete territory coverage.

## What it does

- Verifies the official Austin Socrata schema before querying.
- Filters by inclusive issue-date calendar window, source commercial/residential classification, permit type, contractor trade, description keywords, and presence of a contractor company name.
- Delivers permit records to the run's default dataset in JSON or CSV export formats.
- Writes `RUN_SUMMARY`, `SCHEMA_METADATA`, and an optional `CONTRACTOR_SUMMARY` to the run's default key-value store.
- Limits a run to 1–5,000 delivered permit records. Reaching the cap is a successful, explicitly truncated result; request, record, duplicate, or pagination errors are reported as incomplete.

The contractor summary groups the exact source company and trade values found in delivered records. Its counts describe activity within those delivered permit records and are not counts of distinct projects or leads. The summary has no separate charge.

## Pricing

Proposed paid-beta pricing is `$0.003` per delivered permit record (`$3 per 1,000`). Only visible permit records use the `permit-record` pay-per-event. Source counts, discarded duplicates, diagnostics, and contractor-summary rows are not charged. Platform usage is included in this proposed price: keep Apify's **Pay per event + usage** option OFF. There is no additional start fee for this initial beta. Customer spending limits can stop a run after a partial delivery; `RUN_SUMMARY` preserves the delivered count and reason.

Pricing is prepared but customer charging remains disabled while this Actor is private. See [PRICING_CONFIGURATION.md](PRICING_CONFIGURATION.md) for the review checklist; do not enable it until the release checklist is approved.

## Example input

```json
{
  "startDate": "2026-09-30",
  "endDate": "2026-10-06",
  "permitClass": "Commercial",
  "permitTypes": ["BP", "MP"],
  "contractorTrades": ["General Contractor"],
  "requireContractor": true,
  "includeContractorSummary": true,
  "maxResults": 100
}
```

`issue_date` is a source date-only value. The dates are inclusive calendar boundaries interpreted in `America/Chicago`; the Actor does not claim UTC timestamp precision. Defaults are the latest seven calendar dates and `Commercial` with a 100-record cap.

## Small real output sample

```json
{
  "source_record_id": "2025-143684 BP",
  "issue_date": "2026-10-05T00:00:00.000",
  "source_permit_type": "BP",
  "source_class": "Commercial",
  "work_description": "Adding a Ramp to Interior Area for Staff Personal for Existing Grocery Store",
  "project_address": "2400 S CONGRESS AVE",
  "contractor_name": "Trusted General Contracting",
  "contractor_trade": "General Contractor",
  "project_valuation": null
}
```

This is a small observation sample, not a promise that every future record has the same completeness. Missing source values remain `null`.

## Exports and interpretation

Open the run's default dataset and choose JSON, CSV, or another Apify-supported export. Open `RUN_SUMMARY` for source counts, delivered rows, truncation, errors, pagination, and resource diagnostics. Open `CONTRACTOR_SUMMARY` for run-local contractor activity. Compare contractor names and supporting permit IDs as activity indicators, not as project counts or qualified leads.

For a step-by-step workflow, see [TUTORIAL.md](TUTORIAL.md). For release status and private verification, see [LAUNCH_READINESS.md](LAUNCH_READINESS.md).
