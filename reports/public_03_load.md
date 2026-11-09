# Grade report — public_03_load

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| arav_cancel_2 | 0.364 | +8.0% | 0.247 | +1.6% | 0.524 | +5.6% | 32% | 389 (409) |
| arav_kyc_1 | 0.473 | +31.8% | 0.273 | +26.9% | 0.596 | -0.7% | 0% | 465 (352) |
| arav_renewal_0 | 0.434 | +7.1% | 0.264 | +0.1% | 0.586 | +7.0% | 37% | 455 (408) |
| kest_cancel_2 | 0.373 | +10.7% | 0.249 | +2.7% | 0.534 | +7.0% | 46% | 407 (418) |
| kest_kyc_1 | 0.369 | +3.9% | 0.223 | +3.9% | 0.593 | -0.7% | 0% | 398 (370) |
| kest_renewal_0 | 0.431 | +7.3% | 0.264 | -0.1% | 0.577 | +6.0% | 31% | 437 (403) |
| nort_cancel_2 | 0.340 | +0.3% | 0.246 | +0.9% | 0.497 | -0.3% | 0% | 370 (368) |
| nort_kyc_1 | 0.429 | +20.6% | 0.252 | +17.2% | 0.593 | -0.5% | 0% | 425 (318) |
| nort_renewal_0 | 0.436 | +7.7% | 0.265 | +0.3% | 0.585 | +6.8% | 37% | 449 (419) |
| tide_cancel_2 | 0.367 | +6.8% | 0.246 | +0.8% | 0.530 | +5.7% | 41% | 397 (401) |
| tide_kyc_1 | 0.469 | +31.5% | 0.271 | +26.0% | 0.595 | -0.6% | 0% | 412 (376) |
| tide_renewal_0 | 0.434 | +7.3% | 0.265 | +0.2% | 0.581 | +6.5% | 34% | 421 (425) |
| ALL | 0.410 | +11.8% | 0.255 | +6.1% | 0.567 | +3.8% | 21% | 5025 (4667) |

## Changes applied by the controller

45 applied — neutral: 21, beneficial: 23, harmful: 1

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
- tide_cancel_2 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.077 didΔ=+0.000 → **beneficial**
- kest_cancel_2 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.076 didΔ=+0.000 → **beneficial**
- nort_kyc_1 v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.061 → **beneficial**
- arav_cancel_2 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.025 didΔ=+0.000 → **beneficial**
- kest_kyc_1 v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.045 → **beneficial**
- tide_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.429 → **beneficial**
- nort_renewal_0 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.058 didΔ=+0.000 → **beneficial**
- arav_renewal_0 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.057 didΔ=+0.000 → **beneficial**
- kest_renewal_0 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- arav_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.512 → **beneficial**
- tide_renewal_0 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.058 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v5 (controller_auto) dims=['voice'] engageΔ=+0.017 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v6 (controller_auto) dims=['voice'] engageΔ=+0.016 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v7 (controller_auto) dims=['voice'] engageΔ=+0.016 didΔ=+0.000 → **beneficial**
- nort_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.461 → **beneficial**
- nort_renewal_0 v5 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- kest_renewal_0 v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.059 didΔ=+0.000 → **beneficial**
- nort_renewal_0 v6 (controller_approved) dims=['voice'] engageΔ=-0.001 didΔ=+0.000 → **neutral**
- kest_cancel_2 v5 (controller_auto) dims=['welcome_message'] engageΔ=+0.006 didΔ=+0.000 → **neutral**
- kest_cancel_2 v6 (controller_auto) dims=['welcome_message'] engageΔ=+0.006 didΔ=+0.000 → **neutral**
- kest_cancel_2 v7 (controller_auto) dims=['welcome_message'] engageΔ=+0.003 didΔ=+0.000 → **neutral**
- arav_cancel_2 v8 (controller_auto) dims=['welcome_message'] engageΔ=-0.006 didΔ=+0.000 → **neutral**
- tide_cancel_2 v5 (controller_auto) dims=['welcome_message'] engageΔ=-0.006 didΔ=+0.000 → **neutral**
- arav_cancel_2 v9 (controller_auto) dims=['welcome_message'] engageΔ=-0.002 didΔ=+0.000 → **neutral**
- tide_cancel_2 v6 (controller_auto) dims=['welcome_message'] engageΔ=-0.002 didΔ=+0.000 → **neutral**
- kest_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.403 → **beneficial**
- tide_renewal_0 v5 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- kest_renewal_0 v5 (controller_approved) dims=['cohorts', 'voice'] engageΔ=+0.022 didΔ=+0.000 → **beneficial**
- tide_renewal_0 v6 (controller_approved) dims=['welcome_message'] engageΔ=-0.018 didΔ=+0.000 → **harmful**

## Governance

```
{
  "approval_requests": 33,
  "decisions": {
    "approved": 27,
    "rejected": 4,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 4
  },
  "applied_via_approval": 27,
  "auto_applied": 18,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nort_renewal_0": 2,
    "arav_renewal_0": 1,
    "arav_cancel_2": 2,
    "tide_renewal_0": 2,
    "tide_cancel_2": 2,
    "nort_kyc_1": 2,
    "arav_kyc_1": 1,
    "tide_kyc_1": 2,
    "kest_renewal_0": 1,
    "kest_kyc_1": 2,
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
    "3": 0.752,
    "4": 0.752
  },
  "arav_renewal_0:welcome_message=W3": {
    "3": 0.753,
    "4": 0.75
  },
  "tide_renewal_0:welcome_message=W3": {
    "3": 0.749,
    "4": 0.453
  },
  "kest_renewal_0:welcome_message=W3": {
    "4": 0.747
  }
}
```

Credits used: 0 · validation runs: 0 · LLM fix calls: 0