# Grade report — stress_a

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.319 | -1.6% | 0.237 | -2.9% | 0.471 | +1.9% | 4% | 42 (42) |
| nw_kyc | 0.355 | +66.2% | 0.228 | +54.3% | 0.602 | +0.5% | 0% | 29 (15) |
| nw_renewal | 0.437 | +42.6% | 0.268 | +42.9% | 0.545 | -3.9% | -173% | 91 (128) |
| ALL | 0.366 | +24.1% | 0.246 | +19.4% | 0.522 | +1.6% | -10% | 162 (185) |

## Changes applied by the controller

23 applied — neutral: 12, harmful: 3, beneficial: 8

- nw_renewal v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.016 → **neutral**
- nw_renewal v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.033 didΔ=+0.000 → **harmful**
- ks_cancel v2 (controller_approved) dims=['welcome_message', 'voice', 'caller_id'] engageΔ=+0.055 didΔ=+0.007 → **beneficial**
- nw_kyc v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.048 → **beneficial**
- nw_renewal v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.512 → **beneficial**
- ks_cancel v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.009 → **neutral**
- nw_renewal v6 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.011 → **neutral**
- nw_renewal v7 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.011 → **neutral**
- ks_cancel v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v8 (controller_approved) dims=['welcome_message'] engageΔ=+0.038 didΔ=+0.000 → **beneficial**
- nw_renewal v9 (controller_approved) dims=['prompt_version'] engageΔ=-0.047 didΔ=+0.000 → **harmful**
- nw_kyc v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+1.632 → **beneficial**
- nw_renewal v10 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.009 → **neutral**
- ks_cancel v5 (controller_approved) dims=['welcome_message', 'caller_id'] engageΔ=+0.053 didΔ=+0.015 → **beneficial**
- nw_renewal v11 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.011 → **neutral**
- nw_renewal v12 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.016 → **neutral**
- nw_renewal v13 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v14 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.011 → **neutral**
- ks_cancel v7 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.028 → **beneficial**
- ks_cancel v8 (controller_approved) dims=['voice', 'caller_id'] engageΔ=-0.016 didΔ=+0.024 → **harmful**
- nw_renewal v15 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.005 didΔ=+0.000 → **neutral**
- ks_cancel v9 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.022 → **beneficial**
- ks_cancel v10 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.017 → **neutral**

## Governance

```
{
  "approval_requests": 17,
  "decisions": {
    "approved": 15,
    "rejected": 2,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 2
  },
  "applied_via_approval": 15,
  "auto_applied": 8,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_renewal": 3,
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
      "1": 0.349,
      "2": 0.034,
      "3": 0.032,
      "4": 0.026,
      "5": 0.037,
      "6": 0.029,
      "7": 0.033,
      "8": 0.034
    }
  },
  {
    "type": "supervisor_edit",
    "workflow": "nw_renewal",
    "at": "D2 09:30",
    "mttr_minutes": 2925,
    "fixed_by": "controller_approved"
  },
  {
    "type": "did_flagged",
    "workflow": "nw_kyc",
    "at": "D3 11:00",
    "flagged_did_share_by_day": {
      "3": 0.905,
      "4": 0.918,
      "5": 0.619,
      "6": 0.337,
      "7": 0.03,
      "8": 0.036
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
    "3": 0.255,
    "4": 0.062,
    "5": 0.0,
    "6": 0.0,
    "7": 0.0,
    "8": 0.0
  }
}
```

Credits used: 20 · validation runs: 2 · LLM fix calls: 0