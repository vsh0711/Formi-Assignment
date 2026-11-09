# Grade report — public_01_dev

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.354 | +3.8% | 0.245 | +0.4% | 0.504 | +2.5% | 18% | 61 (57) |
| nw_kyc | 0.393 | +7.1% | 0.259 | +7.1% | 0.599 | +0.3% | 0% | 29 (21) |
| nw_renewal | 0.445 | +6.8% | 0.267 | +0.9% | 0.568 | +4.9% | 22% | 44 (54) |
| ALL | 0.393 | +5.6% | 0.255 | +1.8% | 0.546 | +3.1% | 15% | 134 (132) |

## Changes applied by the controller

14 applied — neutral: 7, beneficial: 7

- nw_renewal v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.008 → **neutral**
- ks_cancel v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- nw_renewal v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- ks_cancel v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- nw_kyc v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.036 → **beneficial**
- ks_cancel v4 (controller_auto) dims=['welcome_message'] engageΔ=+0.020 didΔ=+0.000 → **beneficial**
- ks_cancel v5 (controller_auto) dims=['welcome_message'] engageΔ=+0.005 didΔ=+0.000 → **neutral**
- ks_cancel v6 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v7 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- nw_renewal v5 (controller_approved) dims=['cohorts', 'welcome_message', 'voice'] engageΔ=+0.040 didΔ=+0.000 → **beneficial**
- ks_cancel v8 (controller_auto) dims=['welcome_message', 'voice'] engageΔ=+0.014 didΔ=+0.000 → **beneficial**
- ks_cancel v9 (controller_auto) dims=['welcome_message', 'voice'] engageΔ=+0.013 didΔ=+0.000 → **beneficial**
- ks_cancel v10 (controller_auto) dims=['welcome_message', 'voice'] engageΔ=+0.013 didΔ=+0.000 → **beneficial**

## Governance

```
{
  "approval_requests": 5,
  "decisions": {
    "approved": 4,
    "rejected": 1,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 1
  },
  "applied_via_approval": 4,
  "auto_applied": 10,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_renewal": 1,
    "nw_kyc": 1,
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
    "3": 0.255,
    "4": 0.258,
    "5": 0.14,
    "6": 0.0,
    "7": 0.0
  }
}
```

Credits used: 0 · validation runs: 0 · LLM fix calls: 0