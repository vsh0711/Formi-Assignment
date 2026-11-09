# Grade report — stress_b

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.351 | +2.9% | 0.244 | +0.9% | 0.501 | +1.3% | -1% | 61 (64) |
| nw_kyc | 0.397 | +7.8% | 0.256 | +5.1% | 0.603 | +1.5% | 0% | 26 (27) |
| nw_renewal | 0.491 | +19.5% | 0.271 | +3.0% | 0.611 | +13.7% | 24% | 49 (51) |
| ALL | 0.407 | +10.1% | 0.255 | +2.4% | 0.561 | +6.1% | 19% | 136 (142) |

## Changes applied by the controller

15 applied — neutral: 9, beneficial: 5, harmful: 1

- nw_renewal v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.016 → **neutral**
- ks_cancel v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- nw_renewal v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.092 didΔ=+0.000 → **beneficial**
- ks_cancel v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.016 didΔ=+0.000 → **harmful**
- nw_renewal v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.003 → **neutral**
- nw_kyc v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.046 → **beneficial**
- nw_renewal v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- nw_renewal v6 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.009 → **neutral**
- ks_cancel v4 (controller_auto) dims=['voice'] engageΔ=+0.035 didΔ=+0.000 → **beneficial**
- nw_renewal v7 (controller_approved) dims=['welcome_message'] engageΔ=+0.093 didΔ=+0.000 → **beneficial**
- ks_cancel v5 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v6 (controller_auto) dims=['welcome_message', 'voice'] engageΔ=-0.007 didΔ=+0.000 → **neutral**
- ks_cancel v7 (controller_auto) dims=['welcome_message', 'voice'] engageΔ=-0.007 didΔ=+0.000 → **neutral**
- ks_cancel v8 (controller_auto) dims=['welcome_message', 'voice'] engageΔ=-0.004 didΔ=+0.000 → **neutral**
- nw_renewal v8 (controller_approved) dims=['voice'] engageΔ=+0.126 didΔ=+0.000 → **beneficial**

## Governance

```
{
  "approval_requests": 7,
  "decisions": {
    "rejected": 2,
    "approved": 5,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 2
  },
  "applied_via_approval": 5,
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
{}
```

Credits used: 0 · validation runs: 0 · LLM fix calls: 0