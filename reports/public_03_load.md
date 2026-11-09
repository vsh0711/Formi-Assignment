# Grade report — public_03_load

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| arav_cancel_2 | 0.382 | +13.3% | 0.259 | +6.6% | 0.521 | +5.0% | 33% | 407 (409) |
| arav_kyc_1 | 0.467 | +30.2% | 0.271 | +25.8% | 0.596 | -0.7% | 0% | 410 (352) |
| arav_renewal_0 | 0.451 | +11.3% | 0.279 | +5.8% | 0.574 | +4.8% | 26% | 429 (408) |
| kest_cancel_2 | 0.379 | +12.6% | 0.260 | +7.0% | 0.517 | +3.7% | 25% | 435 (418) |
| kest_kyc_1 | 0.467 | +31.5% | 0.269 | +25.7% | 0.597 | -0.0% | 0% | 375 (370) |
| kest_renewal_0 | 0.455 | +13.2% | 0.279 | +5.5% | 0.578 | +6.1% | 28% | 431 (403) |
| nort_cancel_2 | 0.364 | +7.1% | 0.260 | +6.7% | 0.497 | -0.2% | 0% | 412 (368) |
| nort_kyc_1 | 0.468 | +31.4% | 0.271 | +26.1% | 0.594 | -0.2% | 0% | 438 (318) |
| nort_renewal_0 | 0.451 | +11.3% | 0.277 | +4.8% | 0.580 | +5.8% | 31% | 446 (419) |
| tide_cancel_2 | 0.386 | +12.6% | 0.261 | +6.9% | 0.525 | +4.7% | 40% | 419 (401) |
| tide_kyc_1 | 0.421 | +18.1% | 0.248 | +15.6% | 0.593 | -0.8% | 0% | 406 (376) |
| tide_renewal_0 | 0.443 | +9.4% | 0.279 | +5.5% | 0.566 | +3.7% | 21% | 449 (425) |
| ALL | 0.428 | +16.7% | 0.268 | +11.2% | 0.562 | +3.0% | 16% | 5057 (4667) |

## Changes applied by the controller

78 applied — neutral: 37, beneficial: 40, harmful: 1

- nort_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.009 → **neutral**
- nort_cancel_2 v2 (controller_auto) dims=['caller_id', 'schedule'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- kest_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.009 → **neutral**
- kest_cancel_2 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- arav_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.009 → **neutral**
- arav_cancel_2 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- tide_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.009 → **neutral**
- tide_cancel_2 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- tide_renewal_0 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- tide_cancel_2 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- arav_cancel_2 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- arav_kyc_1 v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.209 → **beneficial**
- nort_cancel_2 v3 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.025 → **beneficial**
- tide_renewal_0 v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.027 → **beneficial**
- tide_cancel_2 v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.025 → **beneficial**
- kest_renewal_0 v3 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.036 → **beneficial**
- kest_cancel_2 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- arav_renewal_0 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- nort_cancel_2 v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.007 → **neutral**
- arav_renewal_0 v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.028 → **beneficial**
- tide_cancel_2 v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.007 → **neutral**
- nort_renewal_0 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- nort_renewal_0 v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.041 → **beneficial**
- nort_kyc_1 v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.236 → **beneficial**
- kest_kyc_1 v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.244 → **beneficial**
- tide_cancel_2 v6 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.025 didΔ=+0.000 → **beneficial**
- kest_renewal_0 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.025 didΔ=+0.000 → **beneficial**
- kest_cancel_2 v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.025 didΔ=+0.000 → **beneficial**
- kest_cancel_2 v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.031 → **beneficial**
- arav_renewal_0 v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.024 → **beneficial**
- arav_cancel_2 v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.031 → **beneficial**
- tide_renewal_0 v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.024 → **beneficial**
- tide_cancel_2 v7 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.025 → **beneficial**
- kest_cancel_2 v6 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- arav_cancel_2 v6 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- tide_cancel_2 v8 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.001 → **neutral**
- tide_renewal_0 v6 (controller_auto) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- tide_cancel_2 v9 (controller_approved) dims=['voice'] engageΔ=+0.028 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v7 (controller_auto) dims=['voice', 'caller_id'] engageΔ=+0.017 didΔ=+0.013 → **beneficial**
- kest_cancel_2 v7 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- tide_kyc_1 v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.219 → **beneficial**
- kest_cancel_2 v8 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.023 → **beneficial**
- arav_cancel_2 v8 (controller_auto) dims=['voice', 'caller_id'] engageΔ=+0.011 didΔ=+0.009 → **beneficial**
- nort_renewal_0 v5 (controller_approved) dims=['welcome_message'] engageΔ=+0.023 didΔ=+0.000 → **beneficial**
- kest_renewal_0 v5 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.022 didΔ=+0.000 → **beneficial**
- arav_renewal_0 v6 (controller_approved) dims=['cohorts', 'welcome_message', 'voice'] engageΔ=+0.010 didΔ=+0.000 → **neutral**
- kest_renewal_0 v6 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.014 → **neutral**
- kest_cancel_2 v9 (controller_auto) dims=['voice', 'caller_id'] engageΔ=+0.017 didΔ=+0.000 → **beneficial**
- kest_cancel_2 v10 (controller_auto) dims=['voice', 'caller_id'] engageΔ=+0.011 didΔ=+0.000 → **beneficial**
- tide_cancel_2 v10 (controller_auto) dims=['welcome_message'] engageΔ=+0.006 didΔ=+0.000 → **neutral**
- tide_cancel_2 v11 (controller_auto) dims=['welcome_message'] engageΔ=+0.002 didΔ=+0.000 → **neutral**
- arav_cancel_2 v9 (controller_auto) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nort_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.209 → **beneficial**
- kest_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.209 → **beneficial**
- arav_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.210 → **beneficial**
- tide_cancel_2 v12 (controller_auto) dims=['voice'] engageΔ=+0.016 didΔ=+0.000 → **beneficial**
- tide_cancel_2 v13 (controller_auto) dims=['voice'] engageΔ=+0.004 didΔ=+0.000 → **neutral**
- arav_renewal_0 v7 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nort_renewal_0 v6 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- arav_cancel_2 v10 (controller_auto) dims=['voice'] engageΔ=+0.016 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v11 (controller_auto) dims=['voice'] engageΔ=+0.004 didΔ=+0.000 → **neutral**
- tide_cancel_2 v14 (controller_auto) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- tide_cancel_2 v15 (controller_auto) dims=['welcome_message'] engageΔ=+0.006 didΔ=+0.000 → **neutral**
- tide_cancel_2 v16 (controller_auto) dims=['welcome_message'] engageΔ=+0.002 didΔ=+0.000 → **neutral**
- tide_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.212 → **beneficial**
- arav_renewal_0 v8 (controller_approved) dims=['welcome_message'] engageΔ=+0.029 didΔ=+0.000 → **beneficial**
- nort_renewal_0 v7 (controller_approved) dims=['welcome_message'] engageΔ=+0.034 didΔ=+0.000 → **beneficial**
- kest_renewal_0 v7 (controller_approved) dims=['welcome_message'] engageΔ=+0.034 didΔ=+0.000 → **beneficial**
- arav_renewal_0 v9 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- arav_cancel_2 v12 (controller_auto) dims=['welcome_message'] engageΔ=-0.006 didΔ=+0.000 → **neutral**
- kest_cancel_2 v11 (controller_auto) dims=['welcome_message'] engageΔ=-0.006 didΔ=+0.000 → **neutral**
- arav_cancel_2 v13 (controller_auto) dims=['welcome_message'] engageΔ=-0.002 didΔ=+0.000 → **neutral**
- kest_cancel_2 v12 (controller_auto) dims=['welcome_message'] engageΔ=-0.002 didΔ=+0.000 → **neutral**
- nort_renewal_0 v8 (controller_approved) dims=['cohorts', 'voice'] engageΔ=+0.015 didΔ=+0.000 → **beneficial**
- kest_renewal_0 v8 (controller_approved) dims=['welcome_message'] engageΔ=-0.029 didΔ=+0.000 → **harmful**
- nort_renewal_0 v9 (controller_approved) dims=['welcome_message'] engageΔ=-0.009 didΔ=+0.000 → **neutral**
- tide_cancel_2 v17 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.019 → **neutral**

## Governance

```
{
  "approval_requests": 36,
  "decisions": {
    "approved": 32,
    "rejected": 3,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 3
  },
  "applied_via_approval": 32,
  "auto_applied": 46,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nort_renewal_0": 2,
    "arav_renewal_0": 2,
    "arav_cancel_2": 2,
    "tide_renewal_0": 2,
    "tide_cancel_2": 2,
    "nort_kyc_1": 1,
    "arav_kyc_1": 1,
    "tide_kyc_1": 1,
    "kest_renewal_0": 2,
    "kest_kyc_1": 1,
    "kest_cancel_2": 2
  }
}
```

## Incidents

```
[]
```

## Decaying variants — share of in-population calls still on the variant, by day after onset

```
{
  "nort_renewal_0:welcome_message=W3": {
    "3": 0.755,
    "4": 0.64
  },
  "kest_renewal_0:welcome_message=W3": {
    "3": 0.745,
    "4": 0.454
  },
  "arav_renewal_0:welcome_message=W3": {
    "3": 0.561,
    "4": 0.564
  },
  "tide_renewal_0:welcome_message=W3": {
    "3": 0.248,
    "4": 0.253
  }
}
```

Credits used: 10 · validation runs: 1 · LLM fix calls: 0