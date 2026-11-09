# Grade report — stress_b

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.350 | +2.7% | 0.244 | +0.9% | 0.500 | +1.0% | -1% | 58 (64) |
| nw_kyc | 0.367 | -0.2% | 0.249 | +2.5% | 0.576 | -3.0% | 0% | 31 (27) |
| nw_renewal | 0.501 | +21.9% | 0.274 | +4.2% | 0.615 | +14.3% | 23% | 52 (51) |
| ALL | 0.404 | +9.2% | 0.255 | +2.4% | 0.557 | +5.3% | 18% | 141 (142) |

## Changes applied by the controller

18 applied — neutral: 11, beneficial: 6, harmful: 1

- nw_renewal v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.016 → **neutral**
- ks_cancel v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- nw_renewal v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.092 didΔ=+0.000 → **beneficial**
- ks_cancel v3 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=-0.016 didΔ=+0.000 → **harmful**
- nw_renewal v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.003 → **neutral**
- nw_kyc v2 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.046 → **beneficial**
- nw_renewal v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- nw_renewal v6 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.009 → **neutral**
- ks_cancel v4 (controller_auto) dims=['voice'] engageΔ=+0.035 didΔ=+0.000 → **beneficial**
- nw_renewal v7 (controller_approved) dims=['welcome_message'] engageΔ=+0.047 didΔ=+0.000 → **beneficial**
- ks_cancel v5 (controller_auto) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_kyc v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.015 → **neutral**
- nw_renewal v8 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.123 didΔ=+0.000 → **beneficial**
- ks_cancel v6 (controller_auto) dims=['welcome_message', 'voice'] engageΔ=-0.007 didΔ=+0.000 → **neutral**
- ks_cancel v7 (controller_auto) dims=['welcome_message', 'voice'] engageΔ=-0.007 didΔ=+0.000 → **neutral**
- ks_cancel v8 (controller_auto) dims=['welcome_message', 'voice'] engageΔ=-0.004 didΔ=+0.000 → **neutral**
- nw_kyc v4 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.222 → **beneficial**
- nw_renewal v9 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**

## Governance

```
{
  "approval_requests": 9,
  "decisions": {
    "rejected": 2,
    "approved": 7,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 2
  },
  "applied_via_approval": 7,
  "auto_applied": 11,
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