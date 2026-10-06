# Pricing configuration — review only

This document prepares the private Actor for a future paid beta. It does not enable charging.

## Proposed Apify Console setup

1. Open the private Actor's monetization setup in Apify Console.
2. Select **Pay per event** and define the custom primary event `permit-record`.
3. Set the event title to **Delivered permit record**, describe it as one permit record written to the default dataset, and set the price to `$0.003`.
4. Remove or set the price of the synthetic `apify-default-dataset-item` event to zero so the same default-dataset row is not billed a second time. Keep the recommended `apify-actor-start` event only if its Console setup is accepted for the beta.
5. Enable **Pay per event + usage** only when the release owner approves passing platform usage through to customers. This is a pricing setting, not an Actor-code setting.
6. Set the minimum customer run limit high enough to cover one `permit-record` event and the intended start-event policy. Confirm the Console's `minimalMaxTotalChargeUsd` value before activation.
7. Leave the Actor private and charging disabled until the checklist in `LAUNCH_READINESS.md` is signed off.

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
ACTOR_TEST_PAY_PER_EVENT=true python -m austin_actor.main
```

Inspect the local `charging-log` dataset and `RUN_SUMMARY`; do not use production credentials. The current repository tests also exercise successful charging, spending-limit partial delivery, and an ambiguous push failure without a blind retry.

References: [Apify Python SDK pay-per-event](https://docs.apify.com/sdk/python/docs/concepts/pay-per-event) and [Apify pay-per-event pricing](https://docs.apify.com/actors/publishing/monetize/pay-per-event).
