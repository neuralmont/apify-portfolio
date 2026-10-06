# Find contractors with recently issued commercial permits in Austin

This workflow uses the Actor's existing issued-permit filters. It does not turn permit records into qualified leads.

1. Start a private run and enter:

```json
{
  "startDate": "2026-09-30",
  "endDate": "2026-10-06",
  "permitClass": "Commercial",
  "requireContractor": true,
  "includeContractorSummary": true,
  "maxResults": 100
}
```

2. Wait for the run to finish. Open `RUN_SUMMARY` first. Confirm `completion` is `complete`; if `cap_truncated` is true, the result is successful but covers only the requested cap, not the entire source window.
3. Open the default dataset and use **Export** to download JSON or CSV. The permit rows include the source permit ID, issue date, source class, work description, public address, contractor company/trade when supplied, and valuation when supplied.
4. Open `CONTRACTOR_SUMMARY` in the run's default key-value store. It groups exact source company/trade values and links them to supporting permit IDs.
5. Use the summary to prioritize review of contractor activity in the delivered observation. `delivered_permit_count` means the number of delivered permit records associated with that source company/trade; it is not a count of distinct projects, jobs, or qualified sales leads. Read the descriptions and source IDs before contacting anyone.

If the date window or filters produce more than 100 records, rerun with a larger cap up to 5,000 or narrow the window. Keep each run's dataset and key-value store separate when comparing observations.
