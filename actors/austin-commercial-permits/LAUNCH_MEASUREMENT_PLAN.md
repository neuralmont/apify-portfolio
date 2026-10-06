# 30-day paid-beta measurement plan

This plan starts only after an approved private paid-beta activation. Current customer charging is disabled, so all metrics below are presently unavailable. The four existing benchmark runs and any owner/test runs are excluded from customer metrics.

Capture a daily export of Actor run metadata, usage, PPE event charges, and acquisition attribution. Use the Apify run ID and customer/account identifier for deduplication; do not count retries as new users or runs. Review a daily dashboard and a day-7, day-14, and day-30 summary.

| Metric | Definition | Current status |
| --- | --- | --- |
| External users | Unique non-owner accounts with at least one completed beta run | Unavailable; no customer charging is active |
| Paying users | Unique non-owner accounts with at least one billed `permit-record` event | Unavailable |
| Repeat paying users | Paying users with billed runs on two or more separate days | Unavailable |
| Revenue | Customer-billed `permit-record` events × $0.003, reconciled to Apify billing | Unavailable |
| Platform costs | Apify run usage and any usage passed through under PPE; build costs tracked separately | Unavailable for customers; prior benchmark costs are excluded |
| Failures | Runs with failed status or incomplete `RUN_SUMMARY`; track source, billing-limit, validation, and timeout causes separately | Available after activation from run metadata and summaries |
| Acquisition source | Tagged referral/source on the first customer run or checkout/referral record | Unavailable until attribution is configured |

## 30-day review

- Days 1–7: verify billing reconciliation, customer spending-limit behavior, output links, and failure diagnostics with the first external users. Do not count internal tests.
- Days 8–14: measure unique external and paying users, first-to-second-run conversion, billed rows per run, revenue, platform cost, and failure rate by input shape.
- Days 15–21: compare repeat-paying behavior and acquisition sources; review whether customers use the contractor summary without interpreting it as project count.
- Days 22–30: decide whether to continue, narrow the audience/use case, or stop. Report gross event revenue, platform costs, net contribution after Apify's applicable share/costs, failure rate, and any unresolved data-quality limitation.

Do not infer demand, freshness, project volume, or market opportunity from the existing benchmark runs. They are excluded operational tests, not customer evidence.
