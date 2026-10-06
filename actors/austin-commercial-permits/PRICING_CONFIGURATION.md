# Pricing configuration — review only

This document prepares the private Actor for a future paid beta. It does not enable charging.

## Proposed Apify Console setup

1. Open the private Actor's monetization setup in Apify Console.
2. Select **Pay per event** and define the custom primary event `permit-record`.
3. Set the event title to **Delivered permit record**, describe it as one permit record written to the default dataset, and set the price to `$0.003`.
4. Remove the synthetic `apify-default-dataset-item` event, or set its price to zero, so the same default-dataset row is not billed a second time.
5. Keep **Pay per event + usage OFF**. Platform usage is included in the proposed `$0.003` event price; turning this option on would pass usage charges through to customers and would not match this beta configuration.
6. Remove or disable any `apify-actor-start` event for this initial beta; there is no additional start fee in the proposal.
7. Set the minimum customer run limit to cover one `permit-record` event (`$0.003`) and confirm the Console's `minimalMaxTotalChargeUsd` value before activation.
8. Leave the Actor private and charging disabled until the checklist in `LAUNCH_READINESS.md` is signed off.

The Actor code calls the official Python SDK shortcut:

```python
charge_result = await Actor.push_data(record, charged_event_name="permit-record")
if charge_result.event_charge_limit_reached:
    # RUN_SUMMARY is written, then the Actor exits cleanly.
    await Actor.exit(status_message="Customer spending limit reached")
```

The SDK handles event charging, API errors, and idempotency. The Actor does not retry an ambiguous dataset push in application code. It charges only after the SDK has accepted the visible permit delivery; summary artifacts use `set_value` and are never charged. `charged_count` and `event_charge_limit_reached` are recorded in `RUN_SUMMARY`.

## Local monetization test

Apify's documented local switch logs test charges without billing:

```bash
cd actors/austin-commercial-permits
ACTOR_TEST_PAY_PER_EVENT=true python3.11 -m austin_actor.main
```

Inspect the local `charging-log` dataset and `RUN_SUMMARY`; do not use production credentials. The current repository tests also exercise successful charging, spending-limit partial delivery, and an ambiguous push failure without a blind retry.

For the fixture-backed real-SDK reconciliation used for this release, run `scripts/verify_billing_sdk.py` with `apify==4.0.2` in Python 3.11+; see `evidence/billing_sdk_integration_20261006.json` for the three recorded cases.

References: [Apify Python SDK pay-per-event](https://docs.apify.com/sdk/python/docs/concepts/pay-per-event) and [Apify pay-per-event pricing](https://docs.apify.com/actors/publishing/monetize/pay-per-event).
