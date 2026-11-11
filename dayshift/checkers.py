"""Governance for the governed mode: commitment checks and handoff receipts.

Two mechanisms, both deterministic:

1. **Commitment check** — before an external commitment lands (a quoted
   discount, an invoice total, a delivery promise, a refund grant, a
   published claim), it is validated against the company fact store.
   A violating commitment is corrected to the nearest legal value and
   the correction is counted. The checker can only validate against
   facts and the item's *recorded* fields: if a fact about the world
   (say, an order's age) was never captured and an agent acted on a
   default, the checker sees the same default — that class escapes by
   construction, and the audit reports it separately as residual.

2. **Handoff receipts** — on a governed handoff the receiver lists the
   fields the next stage requires; a field dropped in transit is
   restored from the sender's retained copy and the recovery counted.
   A field that was never captured cannot be restored by any receipt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .company import Facts


@dataclass
class GateLog:
    """Counts of what the gate caught, by commitment class."""

    corrected: dict[str, int] = field(default_factory=dict)
    recoveries: int = 0

    def correct(self, kind: str) -> None:
        self.corrected[kind] = self.corrected.get(kind, 0) + 1

    @property
    def total_corrected(self) -> int:
        return sum(self.corrected.values())


def check_discount(facts: Facts, discount_pct: float, gate: GateLog) -> float:
    if discount_pct > facts.max_discount_pct:
        gate.correct("discount")
        return facts.max_discount_pct
    return discount_pct


def check_promise(facts: Facts, product: str, promised_days: int, gate: GateLog) -> int:
    floor = facts.sla_days[product]
    if promised_days < floor:
        gate.correct("promise")
        return floor
    return promised_days


def check_claim(facts: Facts, claim: str, gate: GateLog) -> str:
    if claim not in facts.approved_claims:
        gate.correct("claim")
        return facts.approved_claims[0]
    return claim


def check_refund(facts: Facts, order_age_days: int, granted: bool, gate: GateLog) -> bool:
    if granted and order_age_days > facts.refund_window_days:
        gate.correct("refund")
        return False
    return granted


def check_invoice(facts: Facts, product: str, qty: int,
                  discount_pct: float, total: float, gate: GateLog) -> float:
    expected = facts.expected_invoice(product, qty, discount_pct)
    if abs(total - expected) > 0.005:
        gate.correct("invoice")
        return expected
    return total


def apply_receipt(item_fields: dict, sender_copy: dict,
                  required: tuple[str, ...], gate: GateLog) -> None:
    """Restore in-transit field losses from the sender's retained copy.

    Mutates item_fields. Only fields the sender actually held can come
    back; a never-captured field is absent from both copies.
    """
    for name in required:
        if name not in item_fields and name in sender_copy:
            item_fields[name] = sender_copy[name]
            gate.recoveries += 1
