# Grade report — public_03_load

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| arav_cancel_2 | 0.367 | +9.0% | 0.247 | +1.4% | 0.529 | +6.5% | 38% | 405 (409) |
| arav_kyc_1 | 0.431 | +20.2% | 0.252 | +17.3% | 0.596 | -0.8% | 0% | 421 (352) |
| arav_renewal_0 | 0.430 | +6.0% | 0.265 | +0.4% | 0.578 | +5.5% | 33% | 404 (408) |
| kest_cancel_2 | 0.366 | +8.8% | 0.248 | +2.1% | 0.526 | +5.4% | 37% | 402 (418) |
| kest_kyc_1 | 0.390 | +9.7% | 0.231 | +7.9% | 0.596 | -0.3% | 0% | 383 (370) |
| kest_renewal_0 | 0.429 | +6.7% | 0.265 | +0.1% | 0.572 | +5.1% | 24% | 414 (403) |
| nort_cancel_2 | 0.345 | +1.7% | 0.249 | +1.8% | 0.498 | -0.1% | 0% | 387 (368) |
| nort_kyc_1 | 0.463 | +30.1% | 0.269 | +25.2% | 0.592 | -0.5% | 0% | 435 (318) |
| nort_renewal_0 | 0.434 | +7.2% | 0.265 | +0.3% | 0.584 | +6.6% | 33% | 433 (419) |
| tide_cancel_2 | 0.368 | +7.1% | 0.249 | +1.8% | 0.527 | +5.1% | 37% | 362 (401) |
| tide_kyc_1 | 0.433 | +21.6% | 0.252 | +17.4% | 0.598 | +0.1% | 0% | 394 (376) |
| tide_renewal_0 | 0.433 | +7.1% | 0.265 | +0.3% | 0.581 | +6.5% | 32% | 404 (425) |
| ALL | 0.408 | +11.2% | 0.255 | +5.7% | 0.565 | +3.6% | 19% | 4844 (4667) |

## Changes applied by the controller

56 applied — neutral: 28, beneficial: 27, harmful: 1

- nort_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.009 → **neutral**
- nort_cancel_2 v2 (controller_auto) dims=['caller_id', 'schedule'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- kest_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.009 → **neutral**
- kest_cancel_2 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- arav_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.009 → **neutral**
- arav_cancel_2 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- tide_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.009 → **neutral**
- tide_cancel_2 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- tide_cancel_2 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- kest_cancel_2 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- arav_renewal_0 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- tide_renewal_0 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- nort_renewal_0 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- tide_kyc_1 v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.052 → **beneficial**
- arav_kyc_1 v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.055 → **beneficial**
- tide_cancel_2 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.055 didΔ=+0.000 → **beneficial**
- kest_cancel_2 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.054 didΔ=+0.000 → **beneficial**
- nort_kyc_1 v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.061 → **beneficial**
- arav_cancel_2 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.025 didΔ=+0.000 → **beneficial**
- kest_kyc_1 v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.045 → **beneficial**
- arav_renewal_0 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.022 didΔ=+0.000 → **beneficial**
- nort_renewal_0 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.023 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v5 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- tide_renewal_0 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.023 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v6 (controller_approved) dims=['voice'] engageΔ=+0.028 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v7 (controller_auto) dims=['welcome_message'] engageΔ=+0.006 didΔ=+0.000 → **neutral**
- kest_renewal_0 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v8 (controller_auto) dims=['welcome_message'] engageΔ=+0.002 didΔ=+0.000 → **neutral**
- nort_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.556 → **beneficial**
- tide_cancel_2 v5 (controller_auto) dims=['voice'] engageΔ=+0.016 didΔ=+0.000 → **beneficial**
- kest_cancel_2 v5 (controller_auto) dims=['voice'] engageΔ=+0.016 didΔ=+0.000 → **beneficial**
- tide_cancel_2 v6 (controller_auto) dims=['voice'] engageΔ=+0.004 didΔ=+0.000 → **neutral**
- kest_cancel_2 v6 (controller_auto) dims=['voice'] engageΔ=+0.004 didΔ=+0.000 → **neutral**
- arav_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.411 → **beneficial**
- tide_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.410 → **beneficial**
- nort_renewal_0 v5 (controller_approved) dims=['voice'] engageΔ=-0.001 didΔ=+0.000 → **neutral**
- arav_renewal_0 v5 (controller_approved) dims=['welcome_message'] engageΔ=+0.034 didΔ=+0.000 → **beneficial**
- tide_renewal_0 v5 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nort_renewal_0 v6 (controller_approved) dims=['welcome_message'] engageΔ=+0.034 didΔ=+0.000 → **beneficial**
- kest_renewal_0 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.024 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v9 (controller_auto) dims=['voice'] engageΔ=+0.016 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v10 (controller_auto) dims=['voice'] engageΔ=+0.004 didΔ=+0.000 → **neutral**
- tide_renewal_0 v6 (controller_approved) dims=['welcome_message'] engageΔ=+0.034 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v11 (controller_auto) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- arav_cancel_2 v12 (controller_auto) dims=['welcome_message'] engageΔ=+0.006 didΔ=+0.000 → **neutral**
- arav_cancel_2 v13 (controller_auto) dims=['welcome_message'] engageΔ=+0.002 didΔ=+0.000 → **neutral**
- kest_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.415 → **beneficial**
- kest_renewal_0 v5 (controller_approved) dims=['voice'] engageΔ=-0.001 didΔ=+0.000 → **neutral**
- tide_cancel_2 v7 (controller_auto) dims=['welcome_message'] engageΔ=-0.006 didΔ=+0.000 → **neutral**
- kest_cancel_2 v7 (controller_auto) dims=['welcome_message'] engageΔ=-0.006 didΔ=+0.000 → **neutral**
- tide_cancel_2 v8 (controller_auto) dims=['welcome_message'] engageΔ=-0.002 didΔ=+0.000 → **neutral**
- kest_cancel_2 v8 (controller_auto) dims=['welcome_message'] engageΔ=-0.002 didΔ=+0.000 → **neutral**
- kest_renewal_0 v6 (controller_approved) dims=['welcome_message'] engageΔ=+0.034 didΔ=+0.000 → **beneficial**
- nort_renewal_0 v7 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nort_renewal_0 v8 (controller_approved) dims=['welcome_message'] engageΔ=-0.015 didΔ=+0.000 → **harmful**

## Governance

```
{
  "approval_requests": 36,
  "decisions": {
    "approved": 33,
    "rejected": 2,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 2
  },
  "applied_via_approval": 33,
  "auto_applied": 23,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nort_renewal_0": 2,
    "arav_renewal_0": 1,
    "arav_cancel_2": 3,
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
    "3": 0.75,
    "4": 0.533
  },
  "arav_renewal_0:welcome_message=W3": {
    "3": 0.749,
    "4": 0.749
  },
  "tide_renewal_0:welcome_message=W3": {
    "3": 0.752,
    "4": 0.752
  },
  "kest_renewal_0:welcome_message=W3": {
    "4": 0.749
  }
}
```

Credits used: 0 · validation runs: 0 · LLM fix calls: 0