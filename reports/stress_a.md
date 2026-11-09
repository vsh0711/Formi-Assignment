# Grade report — stress_a

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.330 | +1.8% | 0.245 | +0.6% | 0.470 | +1.8% | 8% | 51 (42) |
| nw_kyc | 0.448 | +109.5% | 0.288 | +94.6% | 0.592 | -1.1% | 0% | 29 (15) |
| nw_renewal | 0.452 | +47.4% | 0.276 | +47.2% | 0.550 | -2.9% | -184% | 77 (128) |
| ALL | 0.396 | +34.2% | 0.264 | +28.3% | 0.525 | +2.1% | -7% | 157 (185) |

## Changes applied by the controller

17 applied — neutral: 6, beneficial: 9, harmful: 2

- nw_renewal v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.017 → **neutral**
- nw_kyc v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.149 → **beneficial**
- ks_cancel v2 (controller_approved) dims=['welcome_message', 'voice', 'caller_id'] engageΔ=+0.055 didΔ=+0.007 → **beneficial**
- nw_renewal v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.033 didΔ=+0.000 → **harmful**
- nw_renewal v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.574 → **beneficial**
- nw_kyc v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.148 → **beneficial**
- ks_cancel v3 (controller_approved) dims=['welcome_message'] engageΔ=-0.005 didΔ=+0.000 → **neutral**
- nw_renewal v6 (controller_approved) dims=['prompt_version'] engageΔ=-0.047 didΔ=+0.000 → **harmful**
- ks_cancel v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.111 didΔ=+0.000 → **beneficial**
- nw_renewal v7 (controller_approved) dims=['welcome_message'] engageΔ=+0.039 didΔ=+0.000 → **beneficial**
- ks_cancel v5 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v7 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v8 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.005 didΔ=+0.000 → **neutral**
- ks_cancel v8 (controller_approved) dims=['cohorts', 'voice'] engageΔ=+0.013 didΔ=+0.000 → **beneficial**
- nw_renewal v9 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_renewal v10 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.022 → **beneficial**
- ks_cancel v9 (controller_approved) dims=['voice'] engageΔ=+0.014 didΔ=+0.000 → **beneficial**

## Governance

```
{
  "approval_requests": 16,
  "decisions": {
    "approved": 14,
    "rejected": 1,
    "expired": 1
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 1
  },
  "applied_via_approval": 14,
  "auto_applied": 3,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_renewal": 1,
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
      "1": 0.343,
      "2": 0.027,
      "3": 0.031,
      "4": 0.03,
      "5": 0.036,
      "6": 0.033,
      "7": 0.036,
      "8": 0.031
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
      "3": 0.378,
      "4": 0.204,
      "5": 0.038,
      "6": 0.026,
      "7": 0.032,
      "8": 0.028
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
    "1": 0.247,
    "2": 0.448,
    "3": 0.159,
    "4": 0.0,
    "5": 0.0,
    "6": 0.0,
    "7": 0.0,
    "8": 0.0
  }
}
```

Credits used: 20 · validation runs: 2 · LLM fix calls: 0