# Grade report — stress_a

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.308 | -5.1% | 0.231 | -5.5% | 0.468 | +1.3% | 6% | 42 (42) |
| nw_kyc | 0.355 | +66.0% | 0.228 | +53.9% | 0.603 | +0.7% | 0% | 21 (15) |
| nw_renewal | 0.432 | +41.1% | 0.266 | +41.8% | 0.544 | -4.0% | -196% | 86 (128) |
| ALL | 0.359 | +21.8% | 0.242 | +17.6% | 0.521 | +1.5% | -10% | 149 (185) |

## Changes applied by the controller

23 applied — neutral: 13, harmful: 2, beneficial: 8

- nw_renewal v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.016 → **neutral**
- nw_renewal v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.033 didΔ=+0.000 → **harmful**
- ks_cancel v2 (controller_approved) dims=['welcome_message', 'voice', 'caller_id'] engageΔ=+0.055 didΔ=+0.007 → **beneficial**
- nw_kyc v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.048 → **beneficial**
- nw_renewal v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.512 → **beneficial**
- ks_cancel v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.009 → **neutral**
- nw_renewal v6 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.011 → **neutral**
- ks_cancel v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v7 (controller_approved) dims=['prompt_version'] engageΔ=-0.047 didΔ=+0.000 → **harmful**
- nw_renewal v8 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.012 → **neutral**
- nw_renewal v9 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.012 → **neutral**
- nw_kyc v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+1.632 → **beneficial**
- ks_cancel v5 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.015 → **neutral**
- nw_renewal v10 (controller_approved) dims=['welcome_message'] engageΔ=+0.039 didΔ=+0.000 → **beneficial**
- nw_renewal v11 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- nw_renewal v12 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.011 → **neutral**
- nw_renewal v13 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.011 → **neutral**
- nw_kyc v4 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.000 → **neutral**
- nw_renewal v14 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- ks_cancel v7 (controller_approved) dims=['welcome_message', 'voice', 'caller_id'] engageΔ=+0.087 didΔ=+0.021 → **beneficial**
- nw_renewal v15 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.005 didΔ=+0.000 → **neutral**
- ks_cancel v8 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.032 → **beneficial**
- ks_cancel v9 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.156 → **beneficial**

## Governance

```
{
  "approval_requests": 16,
  "decisions": {
    "approved": 14,
    "rejected": 2,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 2
  },
  "applied_via_approval": 14,
  "auto_applied": 9,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_renewal": 2,
    "nw_kyc": 1,
    "ks_cancel": 2
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
      "1": 0.349,
      "2": 0.034,
      "3": 0.031,
      "4": 0.03,
      "5": 0.032,
      "6": 0.025,
      "7": 0.027,
      "8": 0.031
    }
  },
  {
    "type": "supervisor_edit",
    "workflow": "nw_renewal",
    "at": "D2 09:30",
    "mttr_minutes": 1755,
    "fixed_by": "controller_approved"
  },
  {
    "type": "did_flagged",
    "workflow": "nw_kyc",
    "at": "D3 11:00",
    "flagged_did_share_by_day": {
      "3": 0.905,
      "4": 0.911,
      "5": 0.608,
      "6": 0.324,
      "7": 0.029,
      "8": 0.035
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
    "1": 0.263,
    "2": 0.247,
    "3": 0.254,
    "4": 0.252,
    "5": 0.249,
    "6": 0.061,
    "7": 0.0,
    "8": 0.0
  }
}
```

Credits used: 20 · validation runs: 2 · LLM fix calls: 0