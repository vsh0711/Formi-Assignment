# Grade report — public_01_dev

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.355 | +4.1% | 0.247 | +0.8% | 0.503 | +2.3% | 6% | 65 (57) |
| nw_kyc | 0.399 | +8.9% | 0.267 | +10.5% | 0.589 | -1.3% | 0% | 23 (21) |
| nw_renewal | 0.430 | +3.4% | 0.266 | +0.8% | 0.553 | +2.1% | 10% | 52 (54) |
| ALL | 0.390 | +4.8% | 0.257 | +2.6% | 0.538 | +1.7% | 6% | 140 (132) |

## Changes applied by the controller

18 applied — neutral: 12, beneficial: 5, harmful: 1

- nw_renewal v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.008 → **neutral**
- ks_cancel v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- nw_renewal v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- ks_cancel v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- nw_kyc v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.036 → **beneficial**
- ks_cancel v4 (controller_auto) dims=['welcome_message'] engageΔ=+0.020 didΔ=+0.000 → **beneficial**
- ks_cancel v5 (controller_auto) dims=['welcome_message'] engageΔ=+0.005 didΔ=+0.000 → **neutral**
- nw_renewal v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.009 → **neutral**
- nw_renewal v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.002 → **neutral**
- nw_renewal v6 (controller_approved) dims=['welcome_message'] engageΔ=-0.030 didΔ=+0.000 → **harmful**
- nw_renewal v7 (controller_approved) dims=['voice'] engageΔ=-0.001 didΔ=+0.000 → **neutral**
- nw_kyc v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.019 → **neutral**
- ks_cancel v6 (controller_auto) dims=['welcome_message', 'voice'] engageΔ=-0.008 didΔ=+0.000 → **neutral**
- ks_cancel v7 (controller_auto) dims=['welcome_message', 'voice'] engageΔ=-0.008 didΔ=+0.000 → **neutral**
- ks_cancel v8 (controller_auto) dims=['welcome_message', 'voice'] engageΔ=-0.005 didΔ=+0.000 → **neutral**
- nw_kyc v4 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.225 → **beneficial**
- nw_renewal v8 (controller_approved) dims=['welcome_message'] engageΔ=+0.036 didΔ=+0.000 → **beneficial**
- ks_cancel v9 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.003 → **neutral**

## Governance

```
{
  "approval_requests": 8,
  "decisions": {
    "approved": 8,
    "expired": 0
  },
  "rejection_reasons": {},
  "applied_via_approval": 8,
  "auto_applied": 10,
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
    "3": 0.241,
    "4": 0.241,
    "5": 0.442,
    "6": 0.499,
    "7": 0.053
  }
}
```

Credits used: 0 · validation runs: 0 · LLM fix calls: 0