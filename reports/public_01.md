# Grade report — public_01_dev

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.359 | +5.1% | 0.250 | +2.1% | 0.505 | +2.7% | 5% | 64 (57) |
| nw_kyc | 0.464 | +26.6% | 0.304 | +25.8% | 0.592 | -0.8% | 0% | 23 (21) |
| nw_renewal | 0.432 | +3.8% | 0.266 | +0.7% | 0.556 | +2.6% | 7% | 47 (54) |
| ALL | 0.406 | +9.2% | 0.266 | +6.0% | 0.542 | +2.4% | 4% | 134 (132) |

## Changes applied by the controller

20 applied — neutral: 12, beneficial: 7, harmful: 1

- nw_renewal v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.008 → **neutral**
- ks_cancel v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.009 → **neutral**
- nw_renewal v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- ks_cancel v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- nw_kyc v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.201 → **beneficial**
- ks_cancel v4 (controller_auto) dims=['welcome_message'] engageΔ=+0.020 didΔ=+0.000 → **beneficial**
- ks_cancel v5 (controller_auto) dims=['welcome_message'] engageΔ=+0.005 didΔ=+0.000 → **neutral**
- ks_cancel v6 (controller_auto) dims=['welcome_message'] engageΔ=-0.006 didΔ=+0.000 → **neutral**
- nw_kyc v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.185 → **beneficial**
- ks_cancel v7 (controller_auto) dims=['welcome_message'] engageΔ=-0.002 didΔ=+0.000 → **neutral**
- ks_cancel v8 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.020 didΔ=+0.000 → **beneficial**
- nw_renewal v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.026 → **beneficial**
- nw_renewal v6 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v7 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.018 didΔ=+0.000 → **harmful**
- ks_cancel v9 (controller_auto) dims=['voice'] engageΔ=-0.009 didΔ=+0.000 → **neutral**
- nw_renewal v8 (controller_approved) dims=['voice'] engageΔ=-0.000 didΔ=+0.000 → **neutral**
- ks_cancel v10 (controller_auto) dims=['voice'] engageΔ=-0.006 didΔ=+0.000 → **neutral**
- nw_renewal v9 (controller_approved) dims=['welcome_message'] engageΔ=+0.055 didΔ=+0.000 → **beneficial**
- nw_renewal v10 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.014 → **neutral**

## Governance

```
{
  "approval_requests": 11,
  "decisions": {
    "approved": 10,
    "rejected": 1,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 1
  },
  "applied_via_approval": 9,
  "auto_applied": 11,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_renewal": 2,
    "nw_kyc": 2,
    "ks_cancel": 1
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
  "nw_renewal:welcome_message=W3": {
    "3": 0.404,
    "4": 0.488,
    "5": 0.708,
    "6": 0.753,
    "7": 0.079
  }
}
```

Credits used: 0 · validation runs: 0 · LLM fix calls: 0