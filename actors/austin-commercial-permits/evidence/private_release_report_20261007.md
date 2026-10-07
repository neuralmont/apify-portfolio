# Private release report — 2026-10-07

## Reviewed source

- Requested source SHA: `3f1d9713bb9a7eecdc61c10e88100eb05426205a`
- Local repository matched that SHA before release edits.
- No public publication or schedule was created.

## Deployment and platform configuration

Deployment/build and pricing readback were not completed because this environment has no authenticated Apify Console session, no `APIFY_TOKEN`, and no Apify CLI credentials. The browser reaches the Apify sign-in page. No credentials were entered or recorded, and no platform configuration was guessed.

Whether Apify requires publication before activating these pricing settings could not be assessed without that authenticated Console readback.

The configuration to apply and read back is:

| Setting | Required value | Readback |
| --- | --- | --- |
| Custom event `permit-record` | `$0.003` per delivered permit | unavailable without authentication |
| Pay per event + usage | OFF | unavailable without authentication |
| `apify-default-dataset-item` | removed or `$0` | unavailable without authentication |
| `apify-actor-start` | disabled | unavailable without authentication |
| Contractor summary event | none | implemented as included KVS output |

## Small billing checks

The three checks were exercised against the real Apify Python SDK locally with fixture extraction data, local storage, and `ACTOR_TEST_PAY_PER_EVENT=true`. They are owner/test accounting only. Local PPE events use simulated `$1` pricing and do not verify the proposed Console price. Because the local test configuration still emits the synthetic default-dataset event, the local total-charge budgets were 10 for the sufficient case and 4 for the two-record budget cases; the custom `permit-record` counts are the relevant result billing counts.

| Check | Dataset rows | `permit-record` events | Final status | Summary |
| --- | ---: | ---: | --- | --- |
| Sufficient budget, request 3 | 3 | 3 | Exit 0; complete | Contractor summary count 3; no limit reached |
| Budget for 2, request 3 | 2 | 2 | Exit 0; incomplete | Spending-limit-only stop; contractor summary count 2; default synthetic events 2 |
| Exact budget for 2, request 2 | 2 | 2 | Exit 0; complete | Exact-budget final delivery; contractor summary count 2; default synthetic events 2 |

The exact real-SDK evidence is `evidence/billing_sdk_integration_20261006.json`; no customer billing is represented. The 2026-10-07 command outputs used the committed `scripts/verify_billing_sdk.py` and SDK versions recorded in that evidence.

## Release constraint

An authenticated Apify owner must deploy the reviewed source, record the resulting private build ID/source SHA, apply the pricing settings above, and read back the saved configuration. If Apify requires publication before activating pricing, keep the Actor private and record that constraint instead of publishing.
