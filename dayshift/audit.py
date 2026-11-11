"""The audit: what the operation actually did, per mode.

Aggregates DayResults into the numbers the tool exists to produce:

- **escaped violations** — commitments that reached a customer while
  contradicting the company's own facts (or the item's true fields),
  per 100 commitments attempted, split into *checkable* escapes and
  *residual* escapes (built on a never-captured field, so no fact
  check could have caught them);
- **handoff fidelity** — required fields present after transit, and
  after receipts where receipts exist;
- **floor losses** — items orphaned (vanished) vs incomplete (failed
  visibly) vs completed;
- **conductor load** — interventions the governed mode surfaced.
  The naive mode reports zero by construction: nothing surfaces,
  which is the finding, not a virtue.
"""

from __future__ import annotations

from .engine import DayResult


def audit(results: list[DayResult]) -> dict:
    items = [it for r in results for it in r.items]
    counters = results[0].counters.__class__()
    gate_corrected: dict[str, int] = {}
    recoveries = 0
    for r in results:
        c = r.counters
        counters.handoffs += c.handoffs
        counters.detours += c.detours
        counters.interventions += c.interventions
        counters.fields_required += c.fields_required
        counters.fields_present_transit += c.fields_present_transit
        counters.fields_present_final += c.fields_present_final
        recoveries += r.gate.recoveries
        for kind, n in r.gate.corrected.items():
            gate_corrected[kind] = gate_corrected.get(kind, 0) + n

    commitments = [cm for it in items for cm in it.commitments]
    escaped = [cm for cm in commitments if cm.violating]
    by_class: dict[str, int] = {}
    residual_by_class: dict[str, int] = {}
    for cm in escaped:
        by_class[cm.kind] = by_class.get(cm.kind, 0) + 1
        if cm.residual:
            residual_by_class[cm.kind] = residual_by_class.get(cm.kind, 0) + 1

    n = len(items)
    status = {s: sum(1 for it in items if it.status == s)
              for s in ("completed", "incomplete", "orphaned")}
    req = counters.fields_required or 1
    return {
        "mode": results[0].mode,
        "days": len(results),
        "items": n,
        "status": status,
        "completion_rate": round(status["completed"] / n, 4) if n else 0.0,
        "orphan_rate": round(status["orphaned"] / n, 4) if n else 0.0,
        "commitments_attempted": len(commitments),
        "violations_escaped": len(escaped),
        "escape_rate_per_100": round(100 * len(escaped) / len(commitments), 2)
        if commitments else 0.0,
        "violations_by_class": by_class,
        "residual_violations": sum(residual_by_class.values()),
        "residual_by_class": residual_by_class,
        "gate_corrected": gate_corrected,
        "gate_corrected_total": sum(gate_corrected.values()),
        "handoffs": counters.handoffs,
        "detours": counters.detours,
        "conductor_interventions": counters.interventions,
        "fields_required": counters.fields_required,
        "field_survival_transit": round(counters.fields_present_transit / req, 4),
        "field_survival_final": round(counters.fields_present_final / req, 4),
        "receipt_recoveries": recoveries,
    }


def compare(naive: dict, governed: dict) -> dict:
    """Side-by-side deltas for the headline metrics."""
    def delta(key):
        return round(governed[key] - naive[key], 4)
    return {
        "escape_rate_per_100": {
            "naive": naive["escape_rate_per_100"],
            "governed": governed["escape_rate_per_100"],
            "delta": delta("escape_rate_per_100"),
        },
        "orphan_rate": {
            "naive": naive["orphan_rate"],
            "governed": governed["orphan_rate"],
            "delta": delta("orphan_rate"),
        },
        "completion_rate": {
            "naive": naive["completion_rate"],
            "governed": governed["completion_rate"],
            "delta": delta("completion_rate"),
        },
        "field_survival_final": {
            "naive": naive["field_survival_final"],
            "governed": governed["field_survival_final"],
            "delta": delta("field_survival_final"),
        },
    }
