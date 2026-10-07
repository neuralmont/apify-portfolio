# 30-day paid-beta measurement plan

This plan starts on the public paid-beta launch date, 2026-10-07. The Actor is public and configured for `$0.003` per delivered permit record; the first launch-day metrics below are not yet available. The four existing benchmark runs and all owner/test runs are excluded from customer metrics.

Capture a daily export of Actor run metadata, usage, PPE event charges, and acquisition attribution. Use the Apify run ID and customer/account identifier for deduplication; do not count retries as new users or runs. Review a daily dashboard and a day-7, day-14, and day-30 summary.

| Metric | Definition | Current status |
| --- | --- | --- |
| External users | Unique non-owner accounts with at least one completed beta run; report free-plan and paid-plan users separately | Unavailable at launch; collect from public run metadata |
| Paying users | Unique non-owner accounts with at least one billed `permit-record` event; free-plan activity excluded | Unavailable at launch |
| Repeat paying users | Paying users with billed runs on two or more separate days; free-plan activity excluded | Unavailable |
| Revenue | Apify's actual customer earnings/payout metric for this Actor, reconciled to billed `permit-record` events; do not substitute gross test usage | Unavailable at launch |
| Platform costs | Apify run usage for customer runs; build costs tracked separately and free-plan usage reported separately from revenue-generating customers | Unavailable for customers at launch; prior benchmark/build costs are excluded |
| Failures | Runs with failed status or incomplete `RUN_SUMMARY`; track source, billing-limit, validation, and timeout causes separately | Available after activation from run metadata and summaries |
| Acquisition source | Tagged referral/source on the first customer run or checkout/referral record | Unavailable until attribution is configured |

## 30-day review

- Days 1–7 after public availability: verify billing reconciliation, customer spending-limit behavior, output links, and failure diagnostics with the first external users. Do not count internal tests or free-plan activity as revenue.
- Days 8–14: measure unique external and paying users, first-to-second-run conversion, billed rows per run, revenue, platform cost, and failure rate by input shape.
- Days 15–21: compare repeat-paying behavior and acquisition sources; review whether customers use the contractor summary without interpreting it as project count.
- Days 22–30: decide whether to continue, narrow the audience/use case, or stop. Report gross event revenue, platform costs, net contribution after Apify's applicable share/costs, failure rate, and any unresolved data-quality limitation.

Reconcile gross event charges, Apify's actual earnings/payout metrics, platform costs, and free-plan usage separately. Do not infer demand, freshness, project volume, or market opportunity from the existing benchmark runs. They are excluded operational tests, not customer evidence.
