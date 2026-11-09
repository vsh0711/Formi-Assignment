# Grade report — public_03_load

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| arav_cancel_2 | 0.372 | +10.4% | 0.248 | +1.8% | 0.533 | +7.4% | 44% | 414 (409) |
| arav_kyc_1 | 0.425 | +18.5% | 0.250 | +16.3% | 0.593 | -1.2% | 0% | 396 (352) |
| arav_renewal_0 | 0.439 | +8.2% | 0.264 | +0.1% | 0.589 | +7.5% | 39% | 415 (408) |
| kest_cancel_2 | 0.367 | +9.1% | 0.246 | +1.4% | 0.532 | +6.6% | 42% | 383 (418) |
| kest_kyc_1 | 0.395 | +11.0% | 0.233 | +8.9% | 0.600 | +0.4% | 0% | 395 (370) |
| kest_renewal_0 | 0.436 | +8.6% | 0.264 | -0.2% | 0.586 | +7.6% | 37% | 453 (403) |
| nort_cancel_2 | 0.343 | +1.0% | 0.248 | +1.6% | 0.496 | -0.4% | 0% | 393 (368) |
| nort_kyc_1 | 0.400 | +12.5% | 0.238 | +10.5% | 0.594 | -0.2% | 0% | 411 (318) |
| nort_renewal_0 | 0.441 | +8.7% | 0.265 | +0.3% | 0.593 | +8.3% | 44% | 451 (419) |
| tide_cancel_2 | 0.372 | +8.3% | 0.246 | +0.7% | 0.536 | +7.0% | 49% | 400 (401) |
| tide_kyc_1 | 0.428 | +20.2% | 0.251 | +17.1% | 0.593 | -0.8% | 0% | 437 (376) |
| tide_renewal_0 | 0.436 | +7.7% | 0.263 | -0.5% | 0.589 | +7.9% | 39% | 441 (425) |
| ALL | 0.404 | +10.3% | 0.251 | +4.4% | 0.570 | +4.4% | 24% | 4989 (4667) |

## Changes applied by the controller

50 applied — neutral: 25, beneficial: 25

- nort_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.009 → **neutral**
- nort_cancel_2 v2 (controller_auto) dims=['caller_id', 'schedule'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- kest_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.009 → **neutral**
- kest_cancel_2 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- arav_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.009 → **neutral**
- arav_cancel_2 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- tide_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.009 → **neutral**
- tide_cancel_2 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- tide_cancel_2 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.004 didΔ=+0.000 → **neutral**
- nort_renewal_0 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.061 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.004 didΔ=+0.000 → **neutral**
- kest_cancel_2 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.004 didΔ=+0.000 → **neutral**
- tide_kyc_1 v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.052 → **beneficial**
- kest_renewal_0 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.061 didΔ=+0.000 → **beneficial**
- tide_renewal_0 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.060 didΔ=+0.000 → **beneficial**
- arav_kyc_1 v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.055 → **beneficial**
- tide_cancel_2 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.063 didΔ=+0.000 → **beneficial**
- arav_renewal_0 v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.061 didΔ=+0.000 → **beneficial**
- kest_cancel_2 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.046 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.037 didΔ=+0.000 → **beneficial**
- nort_renewal_0 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.054 didΔ=+0.000 → **beneficial**
- nort_kyc_1 v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.061 → **beneficial**
- kest_kyc_1 v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.045 → **beneficial**
- arav_renewal_0 v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.014 didΔ=+0.000 → **beneficial**
- tide_cancel_2 v5 (controller_approved) dims=['voice'] engageΔ=+0.025 didΔ=+0.000 → **beneficial**
- kest_cancel_2 v5 (controller_approved) dims=['voice'] engageΔ=+0.042 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v5 (controller_approved) dims=['voice'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- tide_renewal_0 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.056 didΔ=+0.000 → **beneficial**
- kest_renewal_0 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.057 didΔ=+0.000 → **beneficial**
- arav_renewal_0 v5 (controller_approved) dims=['welcome_message'] engageΔ=+0.041 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v6 (controller_auto) dims=['schedule'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- arav_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.410 → **beneficial**
- tide_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.410 → **beneficial**
- arav_renewal_0 v6 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nort_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.042 → **beneficial**
- arav_kyc_1 v4 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- tide_cancel_2 v6 (controller_auto) dims=['welcome_message'] engageΔ=+0.006 didΔ=+0.000 → **neutral**
- tide_cancel_2 v7 (controller_auto) dims=['welcome_message'] engageΔ=+0.003 didΔ=+0.000 → **neutral**
- nort_kyc_1 v4 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.354 → **beneficial**
- kest_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.415 → **beneficial**
- kest_kyc_1 v4 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- kest_renewal_0 v5 (controller_approved) dims=['voice'] engageΔ=-0.002 didΔ=+0.000 → **neutral**
- arav_cancel_2 v7 (controller_auto) dims=['welcome_message'] engageΔ=+0.006 didΔ=+0.000 → **neutral**
- arav_cancel_2 v8 (controller_auto) dims=['welcome_message'] engageΔ=+0.003 didΔ=+0.000 → **neutral**
- nort_kyc_1 v5 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.000 → **neutral**
- kest_cancel_2 v6 (controller_auto) dims=['welcome_message'] engageΔ=-0.006 didΔ=+0.000 → **neutral**
- kest_cancel_2 v7 (controller_auto) dims=['welcome_message'] engageΔ=-0.006 didΔ=+0.000 → **neutral**
- kest_cancel_2 v8 (controller_auto) dims=['welcome_message'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- tide_renewal_0 v5 (controller_approved) dims=['cohorts', 'voice'] engageΔ=-0.002 didΔ=+0.000 → **neutral**
- arav_renewal_0 v7 (controller_approved) dims=['cohorts', 'voice'] engageΔ=+0.024 didΔ=+0.000 → **beneficial**

## Governance

```
{
  "approval_requests": 37,
  "decisions": {
    "approved": 34,
    "rejected": 3,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 3
  },
  "applied_via_approval": 34,
  "auto_applied": 16,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nort_renewal_0": 2,
    "arav_renewal_0": 2,
    "arav_cancel_2": 2,
    "tide_renewal_0": 1,
    "tide_cancel_2": 2,
    "nort_kyc_1": 2,
    "arav_kyc_1": 2,
    "tide_kyc_1": 2,
    "kest_renewal_0": 2,
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
    "3": 0.801,
    "4": 0.802
  },
  "kest_renewal_0:welcome_message=W3": {
    "3": 0.799,
    "4": 0.801
  },
  "arav_renewal_0:welcome_message=W3": {
    "3": 0.802,
    "4": 0.799
  },
  "tide_renewal_0:welcome_message=W3": {
    "3": 0.796,
    "4": 0.8
  }
}
```

Credits used: 0 · validation runs: 0 · LLM fix calls: 0