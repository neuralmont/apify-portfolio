# Private release report — 2026-10-07

## Reviewed source

- Requested source SHA: `82e09acc09bbfe38e4d177b6713db4a4b741b9d1`.
- This exact reviewed source was pushed to the existing Actor `g32YlfG1SeYV9ctKK`.
- The Actor remains private; no publication or schedule was created.

## Deployment and pricing readback

The private deployment succeeded:

- Build `0.2.1`, ID `aHA3Ib9CQYkNM4pcu`, status `SUCCEEDED`.
- Finished `2026-10-07T13:13:34.733Z`; build duration 12.101 seconds.
- Apify did not expose a Git SHA in build readback; the source SHA above is the exact local commit supplied to `apify actors push`.

The saved pricing configuration is PPE with one event:

| Setting | Required value | Readback |
| --- | --- | --- |
| `permit-record` | `$0.003` per delivered permit | Saved; primary event |
| Pay per event + usage | OFF | Saved PPE event configuration; the public Actor API has no separate readback boolean |
| `apify-default-dataset-item` | Removed or `$0` | Absent from configured events |
| `apify-actor-start` | Disabled | Absent from configured events |
| Contractor summary event | None | Absent; summary is included KVS output |

Apify did not require publication to save this private configuration. Sanitized evidence is in `evidence/private_platform_release_20261007.json`; credentials and raw API responses are excluded.

## Small private platform billing checks

These checks ran remotely against the private deployed Actor and are distinct from the earlier local SDK tests. They used the 2026-01-01 through 2026-10-06 Commercial window and bounded result caps. They are owner/test accounting only, not customer billing. Apify reports platform usage separately from event charges.

| Check | Run ID | Dataset rows | `permit-record` events | Final status | Summary |
| --- | --- | ---: | ---: | --- | --- |
| Sufficient budget, request 3 | `hCwm7C3r2Bs3sBV4X` | 3 | 3 | Exit 0; complete | Contractor summary count 3; no limit reached; usage `$0.0013323346` |
| Budget for 2, request 3 | `WCa6XMJKlEUqsPBeo` | 2 | 2 | Exit 0; incomplete | Spending-limit-only stop; contractor summary count 2; usage `$0.0011423905` |
| Exact budget for 2, request 2 | `LuFJzVJ4VIi6yvg9D` | 2 | 2 | Exit 0; complete | Exact-budget final delivery; contractor summary count 2; usage `$0.0012026044` |

Each run used a distinct default key-value store, and its `CONTRACTOR_SUMMARY` row count matched that run's delivered rows. The documented Apify charge endpoint is an Actor-internal POST operation, not a post-run listing endpoint; consequently, the available reconciliation is `RUN_SUMMARY.charged_records` plus the saved pricing event set. No synthetic event or contractor-summary charge was present in readback.

The exact real-SDK local evidence remains `evidence/billing_sdk_integration_20261006.json`; it was not rerun here. Local test events use simulated `$1` pricing and do not verify the proposed Console price.

## Remaining platform requirement

No publication is required for this saved private configuration. Before any customer launch, complete the separate release review and any Console payout/KYC requirements. This pass did not publish, enable schedules, or run customer billing.
