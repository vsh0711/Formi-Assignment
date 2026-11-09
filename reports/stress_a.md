# Grade report — stress_a

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.341 | +5.0% | 0.250 | +2.6% | 0.473 | +2.5% | 6% | 41 (42) |
| nw_kyc | 0.390 | +82.3% | 0.257 | +73.2% | 0.583 | -2.6% | 0% | 21 (15) |
| nw_renewal | 0.401 | +30.9% | 0.253 | +35.1% | 0.539 | -4.9% | -180% | 72 (128) |
| ALL | 0.371 | +25.8% | 0.252 | +22.6% | 0.518 | +0.7% | -8% | 134 (185) |

## Changes applied by the controller

19 applied — neutral: 7, beneficial: 10, harmful: 2

- nw_renewal v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.016 → **neutral**
- ks_cancel v2 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.055 didΔ=+0.000 → **beneficial**
- nw_renewal v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.033 didΔ=+0.000 → **harmful**
- nw_kyc v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.048 → **beneficial**
- ks_cancel v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.007 → **neutral**
- nw_renewal v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.492 → **beneficial**
- nw_renewal v6 (controller_approved) dims=['prompt_version'] engageΔ=-0.047 didΔ=+0.000 → **harmful**
- nw_renewal v7 (controller_approved) dims=['welcome_message'] engageΔ=+0.039 didΔ=+0.000 → **beneficial**
- nw_kyc v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+1.842 → **beneficial**
- ks_cancel v4 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v8 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.021 → **beneficial**
- nw_renewal v9 (controller_approved) dims=['welcome_message'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v6 (controller_approved) dims=['cohorts', 'welcome_message', 'voice'] engageΔ=+0.073 didΔ=+0.000 → **beneficial**
- nw_renewal v10 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.024 → **beneficial**
- nw_renewal v11 (controller_approved) dims=['voice'] engageΔ=-0.005 didΔ=+0.000 → **neutral**
- nw_renewal v12 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.030 → **beneficial**
- ks_cancel v7 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.003 → **neutral**
- nw_renewal v13 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.025 → **beneficial**
- nw_renewal v14 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.010 → **neutral**

## Governance

```
{
  "approval_requests": 12,
  "decisions": {
    "approved": 12,
    "expired": 0
  },
  "rejection_reasons": {},
  "applied_via_approval": 12,
  "auto_applied": 7,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_renewal": 2,
    "nw_kyc": 1,
    "ks_cancel": 1
  }
}
```

## Incidents

```
[
  {
    "type": "did_flagged",
    "workflow": "nw_renewal",
    "at": "D1 14:00",
    "flagged_did_share_by_day": {
      "1": 0.346,
      "2": 0.028,
      "3": 0.03,
      "4": 0.028,
      "5": 0.026,
      "6": 0.028,
      "7": 0.028,
      "8": 0.028
    }
  },
  {
    "type": "supervisor_edit",
    "workflow": "nw_renewal",
    "at": "D2 09:30",
    "mttr_minutes": 1485,
    "fixed_by": "controller_approved"
  },
  {
    "type": "did_flagged",
    "workflow": "nw_kyc",
    "at": "D3 11:00",
    "flagged_did_share_by_day": {
      "3": 0.913,
      "4": 0.597,
      "5": 0.332,
      "6": 0.032,
      "7": 0.029,
      "8": 0.03
    }
  },
  {
    "type": "supervisor_edit",
    "workflow": "ks_cancel",
    "at": "D4 16:00"
  }
]
```

## Decaying variants — share of in-population calls still on the variant, by day after onset

```
{
  "ks_cancel:welcome_message=W3": {
    "1": 0.253,
    "2": 0.243,
    "3": 0.252,
    "4": 0.246,
    "5": 0.087,
    "6": 0.0,
    "7": 0.0,
    "8": 0.0
  }
}
```

Credits used: 20 · validation runs: 2 · LLM fix calls: 0