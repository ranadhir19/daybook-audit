# dayshift — measured results

Company: Fernbrook Supply Co. (fictional sample company)  
Days simulated per mode: 20 (base seed 20261110; identical generated work and per-item error draws in both modes)

| Metric | Naive fleet | Governed fleet |
|---|---|---|
| Work items | 1080 | 1080 |
| Completed | 912 | 1041 |
| Incomplete (failed visibly) | 126 | 39 |
| Orphaned (vanished silently) | 42 | 0 |
| Commitments attempted | 1661 | 1794 |
| **Violations that reached a customer** | **289** | **22** |
| Escape rate per 100 commitments | 17.4 | 1.23 |
| Residual escapes (never-captured field) | 20 | 22 |
| Violations corrected at the gate | 0 (no gate) | 265 |
| Required-field survival at handoffs | 91.62% | 97.54% |
| Receipt recoveries | 0 | 139 |
| Handoffs | 1523 | 1482 |
| Misroute detours | 79 | 0 |
| Conductor interventions | 0 | 39 |

Escaped violations by class (naive → governed):

- claim: 30 → 0
- discount: 84 → 0
- invoice: 82 → 20
- promise: 81 → 0
- refund: 12 → 2

Gate corrections by class (governed): claim 29, discount 87, invoice 31, promise 108, refund 10

Reading: governance removes the checkable escapes. What remains in the
governed column is the residual class — commitments built on a field
that was never captured at intake, validated against the same default
the agent used. No fact check catches those; only better intake does.
